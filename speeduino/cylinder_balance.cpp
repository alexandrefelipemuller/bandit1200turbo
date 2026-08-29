#include "cylinder_balance.h"

#include <stddef.h>
#include "globals.h"
#include "maths.h"
#include "speeduino.h"
#include "user_moto_profile.h"

namespace {

constexpr uint8_t CONFIG_OFFSET = 76U;
constexpr uint8_t CONFIG_VERSION = 28U;
// Idle-only balancing is intentionally limited to a small, measurable correction.
constexpr uint8_t CONFIG_HARD_MAX_HALF_PERCENT = 6U;

enum ConfigOffset : uint8_t {
  CFG_MODE = 0U,
  CFG_VERSION,
  CFG_MAX_TRIM,
  CFG_MATRIX,
  CFG_IDLE_TPS_MAX = 15U,
  CFG_IDLE_RPM_MIN,
  CFG_IDLE_RPM_MAX,
  CFG_IDLE_MAP_MIN,
  CFG_IDLE_MAP_MAX,
  CFG_IDLE_RPMDOT_MAX,
  CFG_IDLE_MAPDOT_MAX,
  CFG_IDLE_TPSDOT_MAX,
  CFG_STABLE_TICKS,
  CFG_LIGHT_TPS_MIN,
  CFG_LIGHT_TPS_MAX,
  CFG_LIGHT_RPM_MIN,
  CFG_LIGHT_RPM_MAX,
  CFG_LIGHT_MAP_MIN,
  CFG_LIGHT_MAP_MAX,
  CFG_HIGH_TPS_MIN,
  CFG_HIGH_RPM_MIN,
  CFG_HIGH_MAP_MIN,
  CFG_ENTRY_STEP,
  CFG_EXIT_STEP,
  CFG_PS10_DELTA_MAX,
  CFG_FLAGS,
};

enum BalanceMode : uint8_t {
  BALANCE_OFF = 0U,
  BALANCE_IDLE = 1U,
};

struct Diagnostics {
  int8_t trimHalfPercent[4];
  uint16_t effectiveBasePW;
  uint16_t startAngle[4];
  uint16_t endAngle;
  uint8_t state;
  uint8_t weight;
};

Diagnostics diagnostics = {};
uint8_t activeRegion = CYL_BALANCE_REGION_NONE;
uint8_t pendingRegion = CYL_BALANCE_REGION_NONE;
uint8_t regionWeight = 0U;
uint8_t stableTicks = 0U;
uint8_t lastFuelPressure = 0U;

static_assert(sizeof(config10) == 192U, "config10 layout changed");
static_assert(offsetof(config10, n2o_minCLT) == CONFIG_OFFSET, "cylinder balance config offset changed");

inline uint8_t *configBytes(void)
{
  return reinterpret_cast<uint8_t *>(&configPage10) + CONFIG_OFFSET;
}

inline uint8_t configValue(ConfigOffset offset)
{
  return configBytes()[offset];
}

inline int8_t matrixValue(uint8_t region, uint8_t channel)
{
  const uint8_t index = (uint8_t)((region - 1U) * 4U + channel);
  return reinterpret_cast<int8_t *>(configBytes() + CFG_MATRIX)[index];
}

inline uint16_t abs16(int16_t value)
{
  return (value < 0) ? (uint16_t)(-value) : (uint16_t)value;
}

inline uint16_t absInt(int value)
{
  return (value < 0) ? (uint16_t)(-value) : (uint16_t)value;
}

inline bool configIsValid(void)
{
  const uint8_t mode = configValue(CFG_MODE);
  return configValue(CFG_VERSION) == CONFIG_VERSION && mode == BALANCE_IDLE;
}

inline bool runtimeAllowsTrim(void)
{
  return configIsValid() &&
         configPage6.fuelTrimEnabled != 0U &&
         configPage2.nCylinders == 4U &&
         configPage2.injLayout == INJ_SEQUENTIAL &&
         currentStatus.hasSync &&
         BIT_CHECK(currentStatus.engine, BIT_ENGINE_RUN) &&
         !BIT_CHECK(currentStatus.engine, BIT_ENGINE_CRANK) &&
         !BIT_CHECK(currentStatus.status1, BIT_STATUS1_DFCO);
}

inline bool pressureIsStable(void)
{
  const bool required = (configValue(CFG_FLAGS) & 0x01U) != 0U;
  if (!required) { return true; }
  if (configPage10.fuelPressureEnable == 0U) { return false; }

  const uint8_t pressure = currentStatus.fuelPressure;
  const uint8_t delta = (pressure > lastFuelPressure) ? pressure - lastFuelPressure : lastFuelPressure - pressure;
  return delta <= configValue(CFG_PS10_DELTA_MAX);
}

uint8_t requestedRegion(void)
{
  const uint16_t rpm = currentStatus.RPM;
  const uint16_t map = currentStatus.MAP;
  const uint8_t tps = currentStatus.TPS;

  const bool idleStable = absInt(currentStatus.rpmDOT) <= (uint16_t)configValue(CFG_IDLE_RPMDOT_MAX) * 10U &&
                          abs16(currentStatus.mapDOT) <= configValue(CFG_IDLE_MAPDOT_MAX) &&
                          abs16(currentStatus.tpsDOT) <= configValue(CFG_IDLE_TPSDOT_MAX) &&
                          !BIT_CHECK(currentStatus.engine, BIT_ENGINE_ACC) &&
                          !BIT_CHECK(currentStatus.engine, BIT_ENGINE_DCC) &&
                          pressureIsStable();
  const bool idle = idleStable &&
                    tps <= configValue(CFG_IDLE_TPS_MAX) &&
                    rpm >= (uint16_t)configValue(CFG_IDLE_RPM_MIN) * 10U &&
                    rpm <= (uint16_t)configValue(CFG_IDLE_RPM_MAX) * 10U &&
                    map >= configValue(CFG_IDLE_MAP_MIN) &&
                    map <= configValue(CFG_IDLE_MAP_MAX);

  if (idle) { return CYL_BALANCE_REGION_IDLE; }
  return CYL_BALANCE_REGION_NONE;
}

inline uint8_t limitedStep(ConfigOffset offset)
{
  const uint8_t step = configValue(offset);
  return (step == 0U) ? 1U : ((step > 100U) ? 100U : step);
}

int8_t calculateTrim(uint8_t channel, bool &limited)
{
  const uint8_t mode = configValue(CFG_MODE);
  int16_t trim = 0;

  if (mode == BALANCE_IDLE && activeRegion == CYL_BALANCE_REGION_IDLE)
  {
    int16_t regional = matrixValue(activeRegion, channel);
    if (regional < -CONFIG_HARD_MAX_HALF_PERCENT) { regional = -CONFIG_HARD_MAX_HALF_PERCENT; limited = true; }
    if (regional > CONFIG_HARD_MAX_HALF_PERCENT) { regional = CONFIG_HARD_MAX_HALF_PERCENT; limited = true; }
    trim += (regional * regionWeight) / 100;
  }

  uint8_t maxTrim = configValue(CFG_MAX_TRIM);
  if (maxTrim == 0U || maxTrim > CONFIG_HARD_MAX_HALF_PERCENT) { maxTrim = CONFIG_HARD_MAX_HALF_PERCENT; }
  if (trim < -(int16_t)maxTrim) { trim = -(int16_t)maxTrim; limited = true; }
  if (trim > (int16_t)maxTrim) { trim = maxTrim; limited = true; }
  return (int8_t)trim;
}

uint16_t applyEffectiveTrim(uint16_t pw, int8_t trimHalfPercent, uint16_t pwLimit)
{
  if (pw == 0U || pw <= inj_opentime_uS || trimHalfPercent == 0) { return pw; }

  const uint16_t effectivePW = pw - inj_opentime_uS;
  const uint8_t multiplier = (uint8_t)(200 + trimHalfPercent);
  uint32_t correctedPW = (uint32_t)inj_opentime_uS + halfPercentage(multiplier, effectivePW);
  if (correctedPW > pwLimit) { correctedPW = pwLimit; diagnostics.state |= 0x04U; }
  return (uint16_t)correctedPW;
}

} // namespace

void cylinderBalanceUpdate(void)
{
  if (!BIT_CHECK(LOOP_TIMER, BIT_TIMER_30HZ)) { return; }

  const uint8_t pressure = currentStatus.fuelPressure;
  if (!runtimeAllowsTrim() || configValue(CFG_MODE) != BALANCE_IDLE)
  {
    activeRegion = CYL_BALANCE_REGION_NONE;
    pendingRegion = CYL_BALANCE_REGION_NONE;
    regionWeight = 0U;
    stableTicks = 0U;
    lastFuelPressure = pressure;
    return;
  }

  const uint8_t desired = requestedRegion();
  const uint8_t requiredTicks = configValue(CFG_STABLE_TICKS);
  if (desired == pendingRegion)
  {
    if (stableTicks < requiredTicks) { stableTicks++; }
  }
  else
  {
    pendingRegion = desired;
    stableTicks = 0U;
  }

  const uint8_t confirmed = (stableTicks >= requiredTicks) ? pendingRegion : (uint8_t)CYL_BALANCE_REGION_NONE;
  if (confirmed != activeRegion)
  {
    const uint8_t step = limitedStep(CFG_EXIT_STEP);
    if (regionWeight > step) { regionWeight -= step; }
    else { regionWeight = 0U; activeRegion = confirmed; }
  }
  else if (activeRegion != CYL_BALANCE_REGION_NONE && regionWeight < 100U)
  {
    const uint8_t step = limitedStep(CFG_ENTRY_STEP);
    regionWeight = ((uint16_t)regionWeight + step > 100U) ? 100U : regionWeight + step;
  }

  lastFuelPressure = pressure;
}

bool cylinderBalanceApply(uint16_t pwLimit)
{
  diagnostics.state = configIsValid() ? 0x08U : 0U;
  diagnostics.weight = regionWeight;
  diagnostics.effectiveBasePW = (currentStatus.PW1 > inj_opentime_uS) ? currentStatus.PW1 - inj_opentime_uS : 0U;
  for (uint8_t channel = 0U; channel < 4U; channel++) { diagnostics.trimHalfPercent[channel] = 0; }

  if (!runtimeAllowsTrim()) { return false; }

  diagnostics.state |= 0x10U | (activeRegion & 0x03U);
  bool limited = false;
  uint16_t *pulseWidths[4] = { &currentStatus.PW1, &currentStatus.PW2, &currentStatus.PW3, &currentStatus.PW4 };

  for (uint8_t channel = 0U; channel < 4U; channel++)
  {
    const int8_t trim = calculateTrim(channel, limited);
    diagnostics.trimHalfPercent[channel] = trim;
    *pulseWidths[channel] = applyEffectiveTrim(*pulseWidths[channel], trim, pwLimit);
    if (*pulseWidths[channel] > pwLimit) { *pulseWidths[channel] = pwLimit; limited = true; }
  }

  if (limited) { diagnostics.state |= 0x04U; }
  return true;
}

void cylinderBalanceSetInjectionAngles(uint16_t c1, uint16_t c2, uint16_t c4, uint16_t c3)
{
  diagnostics.startAngle[0] = c1;
  diagnostics.startAngle[1] = c2;
  diagnostics.startAngle[2] = c4;
  diagnostics.startAngle[3] = c3;
  diagnostics.endAngle = currentStatus.injAngle;
}

int8_t cylinderBalanceGetTrim(uint8_t channel) { return (channel < 4U) ? diagnostics.trimHalfPercent[channel] : 0; }
uint16_t cylinderBalanceGetEffectiveBasePW(void) { return diagnostics.effectiveBasePW; }
uint16_t cylinderBalanceGetInjectionAngle(uint8_t channel) { return (channel < 4U) ? diagnostics.startAngle[channel] : 0U; }
uint16_t cylinderBalanceGetEndAngle(void) { return diagnostics.endAngle; }
uint8_t cylinderBalanceGetState(void) { return diagnostics.state; }
uint8_t cylinderBalanceGetWeight(void) { return diagnostics.weight; }
