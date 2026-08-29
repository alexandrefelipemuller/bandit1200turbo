#include "thermal_idle_assist.h"

#include <stddef.h>
#include "globals.h"
#include "maths.h"
#include "speeduino.h"

namespace {

constexpr uint8_t CONFIG_VERSION = 29U;
constexpr uint8_t FLAG_ENABLE = 0x01U;
constexpr uint8_t FLAG_FUEL = 0x02U;
constexpr uint8_t FLAG_ANGLE = 0x04U;
constexpr uint8_t FLAG_LAMBDA = 0x08U;
constexpr uint8_t FLAG_PS10 = 0x10U;

enum AssistState : uint8_t {
  ASSIST_OFF = 0U,
  ASSIST_CRANK_CAPTURE = 1U,
  ASSIST_HOLD = 2U,
  ASSIST_DECAY = 3U,
  ASSIST_SENSOR_VETO = 4U,
};

struct Runtime {
  uint8_t state;
  uint8_t weight;
  uint8_t elapsedTicks;
  uint8_t stableTicks;
  int16_t startCLT;
  int16_t startIAT;
  int8_t lambdaTrim;
  int8_t fuelTrim;
  int8_t angleOffset;
  bool sawCrank;
  bool hotProfile;
  bool ps10Valid;
  bool lambdaValid;
};

Runtime runtime = {};

static_assert(sizeof(config6) == 128U, "config6 layout changed");
static_assert(offsetof(config6, iacOLStepVal) == 74U, "thermal assist config offset changed");
static_assert(offsetof(config6, iacOLPWMVal) == 84U, "thermal assist config offset changed");
static_assert(offsetof(config6, iacCrankSteps) == 104U, "thermal assist config offset changed");

inline uint8_t flags(void) { return configPage6.iacOLStepVal[0]; }
inline bool enabled(uint8_t flag) { return (flags() & flag) != 0U; }
inline bool configValid(void) { return configPage6.iacCrankBins[0] == CONFIG_VERSION && enabled(FLAG_ENABLE); }
inline uint8_t abs8(int16_t value) { return (uint8_t)((value < 0) ? -value : value); }
inline uint16_t abs16(int16_t value) { return (uint16_t)((value < 0) ? -value : value); }

inline int8_t clampSigned(int16_t value, uint8_t limit)
{
  if (value > limit) { return (int8_t)limit; }
  if (value < -(int16_t)limit) { return -(int8_t)limit; }
  return (int8_t)value;
}

inline bool engineAllowsAssist(void)
{
  return currentStatus.hasSync &&
         BIT_CHECK(currentStatus.engine, BIT_ENGINE_RUN) &&
         !BIT_CHECK(currentStatus.engine, BIT_ENGINE_CRANK) &&
         !BIT_CHECK(currentStatus.status1, BIT_STATUS1_DFCO) &&
         !BIT_CHECK(currentStatus.engine, BIT_ENGINE_ACC) &&
         !BIT_CHECK(currentStatus.engine, BIT_ENGINE_DCC);
}

inline uint16_t targetRPM(void) { return (uint16_t)configPage6.iacOLStepVal[1] * 10U; }

bool inIdleWindow(void)
{
  const uint16_t target = targetRPM();
  const uint16_t band = (uint16_t)configPage6.iacOLStepVal[3] * 10U;
  const uint16_t upperRPM = target + band;
  const uint8_t tpsMax = configPage6.iacOLStepVal[2];
  const uint16_t map = (uint16_t)currentStatus.MAP;

  return currentStatus.hasSync && BIT_CHECK(currentStatus.engine, BIT_ENGINE_RUN) &&
         !BIT_CHECK(currentStatus.engine, BIT_ENGINE_CRANK) && target >= 600U &&
         currentStatus.RPM >= 400U && currentStatus.RPM <= upperRPM &&
         currentStatus.TPS <= tpsMax &&
         map >= configPage6.iacOLStepVal[4] && map <= configPage6.iacOLStepVal[5];
}

bool ps10Plausible(void)
{
  if (!enabled(FLAG_PS10)) { return true; }
  if (configPage10.fuelPressureEnable == 0U) { return false; }

  const uint8_t expected = configPage6.iacOLPWMVal[5];
  const uint8_t hysteresis = configPage6.iacOLPWMVal[6];
  return abs8((int16_t)currentStatus.fuelPressure - expected) <= hysteresis;
}

uint8_t lambdaX100(void)
{
  if (configPage2.stoich == 0U) { return 0U; }
  const uint16_t lambda = ((uint16_t)currentStatus.O2 * 100U) / configPage2.stoich;
  return (lambda > 255U) ? 255U : (uint8_t)lambda;
}

void updateLambdaTrim(void)
{
  runtime.lambdaValid = false;
  if (!enabled(FLAG_LAMBDA) || configPage6.egoType != 2U || !runtime.ps10Valid ||
      runtime.elapsedTicks < (uint8_t)(configPage6.iacCrankDuty[0] * 10U)) { return; }

  const uint8_t lambda = lambdaX100();
  if (lambda < configPage6.iacCrankDuty[2] || lambda > configPage6.iacCrankDuty[3]) { return; }

  runtime.lambdaValid = true;
  const uint8_t target = configPage6.iacOLPWMVal[3];
  const uint8_t hysteresis = configPage6.iacOLPWMVal[4];
  const uint8_t step = (configPage6.iacCrankDuty[1] == 0U) ? 1U : configPage6.iacCrankDuty[1];
  const uint8_t limit = configPage6.iacOLPWMVal[2];

  if (lambda > (uint16_t)target + hysteresis)
  {
    runtime.lambdaTrim = clampSigned((int16_t)runtime.lambdaTrim + step, limit);
  }
  else if ((uint16_t)lambda + hysteresis < target)
  {
    runtime.lambdaTrim = clampSigned((int16_t)runtime.lambdaTrim - step, limit);
  }
}

void calculateOutputs(void)
{
  const int8_t baseFuel = runtime.hotProfile ? (int8_t)configPage6.iacOLPWMVal[1] : (int8_t)configPage6.iacOLPWMVal[0];
  const int8_t baseAngle = runtime.hotProfile ? (int8_t)configPage6.iacOLPWMVal[8] : (int8_t)configPage6.iacOLPWMVal[7];
  const uint8_t fuelLimit = configPage6.iacOLPWMVal[2];
  const uint8_t angleLimit = configPage6.iacOLPWMVal[9];

  const int16_t weightedFuel = ((int16_t)baseFuel + runtime.lambdaTrim) * runtime.weight / 100;
  runtime.fuelTrim = enabled(FLAG_FUEL) ? clampSigned(weightedFuel, fuelLimit) : 0;
  runtime.angleOffset = enabled(FLAG_ANGLE) ? clampSigned((int16_t)baseAngle * runtime.weight / 100, angleLimit) : 0;
}

uint16_t applyTrim(uint16_t pw, uint16_t pwLimit)
{
  if (pw == 0U || pw <= inj_opentime_uS || runtime.fuelTrim == 0) { return pw; }
  const uint16_t effectivePW = pw - inj_opentime_uS;
  const uint8_t multiplier = (uint8_t)(200 + runtime.fuelTrim);
  uint32_t corrected = (uint32_t)inj_opentime_uS + halfPercentage(multiplier, effectivePW);
  if (corrected > pwLimit) { corrected = pwLimit; }
  return (uint16_t)corrected;
}

void resetRuntime(void)
{
  runtime.state = ASSIST_OFF;
  runtime.weight = 0U;
  runtime.elapsedTicks = 0U;
  runtime.stableTicks = 0U;
  runtime.lambdaTrim = 0;
  runtime.fuelTrim = 0;
  runtime.angleOffset = 0;
  runtime.sawCrank = false;
  runtime.ps10Valid = false;
  runtime.lambdaValid = false;
}

} // namespace

void thermalIdleAssistUpdate(void)
{
  if (!configValid()) { resetRuntime(); return; }

  if (BIT_CHECK(currentStatus.engine, BIT_ENGINE_CRANK))
  {
    runtime.sawCrank = true;
    runtime.state = ASSIST_CRANK_CAPTURE;
    runtime.startCLT = currentStatus.coolant;
    runtime.startIAT = currentStatus.IAT;
    runtime.elapsedTicks = 0U;
    runtime.weight = 0U;
    runtime.lambdaTrim = 0;
    calculateOutputs();
    return;
  }

  if (!BIT_CHECK(currentStatus.engine, BIT_ENGINE_RUN)) { resetRuntime(); return; }

  if (runtime.sawCrank && runtime.weight == 0U)
  {
    const int16_t coldCLT = (int16_t)configPage6.iacCrankSteps[0] - CALIBRATION_TEMPERATURE_OFFSET;
    const int16_t coldIAT = (int16_t)configPage6.iacCrankSteps[1] - CALIBRATION_TEMPERATURE_OFFSET;
    runtime.hotProfile = runtime.startCLT > coldCLT || runtime.startIAT > coldIAT;
    runtime.weight = 100U;
    runtime.state = ASSIST_HOLD;
  }

  if (!runtime.sawCrank || runtime.weight == 0U) { calculateOutputs(); return; }
  if (runtime.elapsedTicks < 255U) { runtime.elapsedTicks++; }

  const uint8_t confirmTicks = configPage6.iacCrankSteps[3];
  if (runtime.elapsedTicks <= confirmTicks &&
      runtime.startIAT - currentStatus.IAT >= configPage6.iacCrankSteps[2])
  {
    runtime.hotProfile = true;
  }

  runtime.ps10Valid = ps10Plausible();
  if (!inIdleWindow())
  {
    resetRuntime();
    return;
  }

  // Ignition idle control reads this target even though no physical IAC exists.
  currentStatus.CLIdleTarget = configPage6.iacOLStepVal[1];

  // AE/DFCO/DCC keep their authority. The event is paused, not cancelled.
  if (!engineAllowsAssist()) { calculateOutputs(); return; }

  if (!runtime.ps10Valid)
  {
    runtime.state = ASSIST_SENSOR_VETO;
    runtime.lambdaTrim = 0;
  }
  else
  {
    updateLambdaTrim();
  }

  const uint8_t holdTicks = configPage6.iacOLStepVal[7];
  const uint8_t maxTicks = (uint8_t)(configPage6.iacOLStepVal[8] * 10U);
  const uint16_t rpmError = (currentStatus.RPM > targetRPM()) ? currentStatus.RPM - targetRPM() : targetRPM() - currentStatus.RPM;
  const bool stable = rpmError <= (uint16_t)configPage6.iacOLStepVal[3] * 10U &&
                      abs16(currentStatus.mapDOT) <= 5U && abs16(currentStatus.rpmDOT / 10) <= 20U;
  runtime.stableTicks = stable ? (uint8_t)(runtime.stableTicks < 255U ? runtime.stableTicks + 1U : 255U) : 0U;

  if (runtime.elapsedTicks >= maxTicks || (runtime.elapsedTicks >= holdTicks && runtime.stableTicks >= configPage6.iacOLStepVal[6]))
  {
    runtime.state = ASSIST_DECAY;
    const uint8_t step = (configPage6.iacOLStepVal[9] == 0U) ? 1U : configPage6.iacOLStepVal[9];
    runtime.weight = (runtime.weight > step) ? runtime.weight - step : 0U;
    if (runtime.weight == 0U) { runtime.sawCrank = false; }
  }
  calculateOutputs();
}

void thermalIdleAssistApplyTarget(void)
{
  if (configValid() && runtime.sawCrank && runtime.weight > 0U && inIdleWindow())
  {
    currentStatus.CLIdleTarget = configPage6.iacOLStepVal[1];
  }
}

bool thermalIdleAssistApplyFuel(uint16_t pwLimit)
{
  if (!configValid() || runtime.weight == 0U || runtime.fuelTrim == 0 || !inIdleWindow() || !engineAllowsAssist()) { return false; }
  currentStatus.PW1 = applyTrim(currentStatus.PW1, pwLimit);
  currentStatus.PW2 = applyTrim(currentStatus.PW2, pwLimit);
  currentStatus.PW3 = applyTrim(currentStatus.PW3, pwLimit);
  currentStatus.PW4 = applyTrim(currentStatus.PW4, pwLimit);
  return true;
}

uint16_t thermalIdleAssistAdjustInjectionAngle(uint16_t baseAngle)
{
  if (!configValid() || runtime.weight == 0U || runtime.angleOffset == 0 || !inIdleWindow() || !engineAllowsAssist()) { return baseAngle; }
  int16_t adjusted = (int16_t)baseAngle + runtime.angleOffset;
  if (adjusted < 0) { adjusted += CRANK_ANGLE_MAX_INJ; }
  if (adjusted > CRANK_ANGLE_MAX_INJ) { adjusted -= CRANK_ANGLE_MAX_INJ; }
  return (uint16_t)adjusted;
}

uint8_t thermalIdleAssistGetState(void) { return runtime.state; }
uint8_t thermalIdleAssistGetWeight(void) { return runtime.weight; }
int8_t thermalIdleAssistGetFuelTrim(void) { return runtime.fuelTrim; }
int8_t thermalIdleAssistGetAngleOffset(void) { return runtime.angleOffset; }
