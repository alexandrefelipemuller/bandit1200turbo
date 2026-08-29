#include "globals.h"
#include "secondaryTables.h"
#include "corrections.h"

static inline byte applyMotoVectorFuel2Trim(byte baseVE2)
{
#if MOTO_PROFILE_ENABLE_VECTOR_FUEL2_TRIM
  // Keep persistent state local and tiny (2x int16) for transient vector math.
  static int16_t lastTps = -1;
  static int16_t lastMap = -1;

  const int16_t tpsNow = currentStatus.TPS; // 0.5% units
  const int16_t mapNow = currentStatus.MAP; // kPa

  // Overlay is designed for Alpha-N main with MAP trim table.
  if(configPage2.fuelAlgorithm != LOAD_SOURCE_TPS)
  {
    lastTps = tpsNow;
    lastMap = mapNow;
    return baseVE2;
  }

  // Avoid cold-start / very low rpm transients.
  if(currentStatus.RPM < MOTO_PROFILE_VECTOR_FUEL2_RPM_MIN)
  {
    lastTps = tpsNow;
    lastMap = mapNow;
    return baseVE2;
  }

  if(lastTps < 0 || lastMap < 0)
  {
    lastTps = tpsNow;
    lastMap = mapNow;
    return baseVE2;
  }

  int16_t tpsRise = tpsNow - lastTps;
  int16_t mapRise = mapNow - lastMap;

  lastTps = tpsNow;
  lastMap = mapNow;

  if(tpsRise < 0) { tpsRise = 0; }
  if(mapRise < 0) { mapRise = 0; }

  if( (tpsNow < MOTO_PROFILE_VECTOR_FUEL2_TPS_MIN) || (mapNow < MOTO_PROFILE_VECTOR_FUEL2_MAP_MIN) )
  {
    return baseVE2;
  }

  if( (tpsRise < MOTO_PROFILE_VECTOR_FUEL2_TPS_RISE_MIN) && (mapRise < MOTO_PROFILE_VECTOR_FUEL2_MAP_RISE_MIN) )
  {
    return baseVE2;
  }

  uint16_t score = ((uint16_t)tpsRise * MOTO_PROFILE_VECTOR_FUEL2_TPS_WEIGHT) +
                   ((uint16_t)mapRise * MOTO_PROFILE_VECTOR_FUEL2_MAP_WEIGHT);

  uint16_t addPct = MOTO_PROFILE_VECTOR_FUEL2_BASE_ADD + (score >> MOTO_PROFILE_VECTOR_FUEL2_SCORE_SHIFT);
  if(addPct > MOTO_PROFILE_VECTOR_FUEL2_MAX_ADD) { addPct = MOTO_PROFILE_VECTOR_FUEL2_MAX_ADD; }

  currentStatus.fuel2VectorAdd = (byte)addPct;
  currentStatus.fuel2VectorActive = 1U;
  uint16_t adjustedVE2 = (uint16_t)baseVE2 + addPct;
  if(adjustedVE2 > UINT8_MAX) { adjustedVE2 = UINT8_MAX; }
  return (byte)adjustedVE2;
#else
  return baseVE2;
#endif
}

void calculateSecondaryFuel(void)
{
  // Fuel 2 is always active in this build as a fixed MAP-based trim table.
  BIT_SET(currentStatus.status3, BIT_STATUS3_FUEL2_ACTIVE);
  const byte baseVE2 = getVE2();
  currentStatus.ve2Base = baseVE2;
  currentStatus.fuel2VectorAdd = 0U;
  currentStatus.fuel2VectorEffective = 0U;
  currentStatus.fuel2VectorActive = 0U;
  currentStatus.VE2 = applyMotoVectorFuel2Trim(baseVE2);
  currentStatus.fuel2VectorEffective = (currentStatus.VE2 >= baseVE2) ? (byte)(currentStatus.VE2 - baseVE2) : 0U;
  uint16_t combinedVE = ((uint16_t)currentStatus.VE1 * (uint16_t)currentStatus.VE2) / 100;
  if(combinedVE <= UINT8_MAX) { currentStatus.VE = combinedVE; }
  else { currentStatus.VE = UINT8_MAX; }
}


void calculateSecondarySpark(void)
{
  constexpr int16_t SPARK_FINAL_MIN = -40;
  constexpr int16_t SPARK_FINAL_MAX = 70;

  BIT_CLEAR(currentStatus.status5, BIT_STATUS5_SPARK2_ACTIVE); //Clear the bit indicating that the 2nd spark table is in use. 
  if(configPage10.spark2Mode == SPARK2_MODE_MULTIPLY)
  {
    BIT_SET(currentStatus.status5, BIT_STATUS5_SPARK2_ACTIVE);
    currentStatus.advance2 = getAdvance2();
    if(currentStatus.advance2 < 50) { currentStatus.advance2 = 50; }
    else if(currentStatus.advance2 > 127) { currentStatus.advance2 = 127; }
    int16_t combinedAdvance = ((int16_t)currentStatus.advance1 * (int16_t)currentStatus.advance2) / 100;
    if(combinedAdvance < SPARK_FINAL_MIN) { combinedAdvance = SPARK_FINAL_MIN; }
    else if(combinedAdvance > SPARK_FINAL_MAX) { combinedAdvance = SPARK_FINAL_MAX; }
    currentStatus.advance = (int8_t)combinedAdvance;
  }
  else if(configPage10.spark2Mode == SPARK2_MODE_ADD)
  {
    BIT_SET(currentStatus.status5, BIT_STATUS5_SPARK2_ACTIVE);
    currentStatus.advance2 = getAdvance2();
    if(currentStatus.advance2 < -20) { currentStatus.advance2 = -20; }
    else if(currentStatus.advance2 > 30) { currentStatus.advance2 = 30; }
    int16_t combinedAdvance = (int16_t)currentStatus.advance1 + (int16_t)currentStatus.advance2;
    if(combinedAdvance < SPARK_FINAL_MIN) { combinedAdvance = SPARK_FINAL_MIN; }
    else if(combinedAdvance > SPARK_FINAL_MAX) { combinedAdvance = SPARK_FINAL_MAX; }
    currentStatus.advance = (int8_t)combinedAdvance;
  }

}

/**
 * @brief Looks up and returns the VE value from the secondary fuel table
 * 
 * This performs largely the same operations as getVE() however the lookup is of the secondary fuel table and uses the secondary load source
 * @return byte 
 */
byte getVE2(void)
{
  byte tempVE = 100;
  currentStatus.fuelLoad2 = currentStatus.MAP;
  tempVE = get3DTableValue(&fuelTable2, currentStatus.fuelLoad2, currentStatus.RPM); //Perform lookup into fuel map for RPM vs MAP value

  return tempVE;
}

/**
 * @brief Performs a lookup of the second ignition advance table. The values used to look this up will be RPM and whatever load source the user has configured
 * 
 * @return Signed table value in degrees.
 */
int8_t getAdvance2(void)
{
  int16_t tempAdvance = 0;
  currentStatus.ignLoad2 = currentStatus.TPS * 2;
  const int16_t tableValue = get3DTableValue(&ignitionTable2, currentStatus.ignLoad2, currentStatus.RPM);
  // One raw table serves both modes: 100% and 0 deg use the same raw neutral value.
  const int16_t tableOffset = (configPage10.spark2Mode == SPARK2_MODE_ADD) ? 140 : OFFSET_IGNITION;
  tempAdvance = tableValue - tableOffset;

  return (int8_t)tempAdvance;
}
