#pragma once

#include <Arduino.h>

enum CylinderBalanceRegion : uint8_t {
  CYL_BALANCE_REGION_NONE = 0U,
  CYL_BALANCE_REGION_IDLE = 1U,
  CYL_BALANCE_REGION_LIGHT = 2U,
  CYL_BALANCE_REGION_HIGH = 3U,
};

void cylinderBalanceUpdate(void);
bool cylinderBalanceApply(uint16_t pwLimit);
void cylinderBalanceSetInjectionAngles(uint16_t c1, uint16_t c2, uint16_t c4, uint16_t c3);

int8_t cylinderBalanceGetTrim(uint8_t channel);
uint16_t cylinderBalanceGetEffectiveBasePW(void);
uint16_t cylinderBalanceGetInjectionAngle(uint8_t channel);
uint16_t cylinderBalanceGetEndAngle(void);
uint8_t cylinderBalanceGetState(void);
uint8_t cylinderBalanceGetWeight(void);
