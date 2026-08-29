#ifndef THERMAL_IDLE_ASSIST_H
#define THERMAL_IDLE_ASSIST_H

#include <stdint.h>

void thermalIdleAssistUpdate(void);
void thermalIdleAssistApplyTarget(void);
bool thermalIdleAssistApplyFuel(uint16_t pwLimit);
uint16_t thermalIdleAssistAdjustInjectionAngle(uint16_t baseAngle);

uint8_t thermalIdleAssistGetState(void);
uint8_t thermalIdleAssistGetWeight(void);
int8_t thermalIdleAssistGetFuelTrim(void);
int8_t thermalIdleAssistGetAngleOffset(void);

#endif
