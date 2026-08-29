/** @file
 * Lightweight transient helpers for bike profile.
 */
#ifndef TRANSIENTS_H
#define TRANSIENTS_H

#include <stdint.h>

void transientsDFCOReentryUpdate(bool dfcoActive);
bool transientsDFCOReentryReleaseRequest(void);
uint8_t transientsDFCOReentryFuelMult(void);
uint8_t transientsDFCOReentryFuelAddPct(void);
uint16_t transientsDFCOReentryHoldMs(void);
void transientsDFCOReentryReset(void);
uint16_t transientsSpoolAeOverlay(uint16_t baseAeValue);
bool transientsSpoolAeActive(void);
uint8_t transientsSpoolAeAddPct(void);
uint16_t transientsSpoolAeHoldMs(void);
uint8_t transientsSpoolAeRecoveryActive(void);
void transientsSpoolAeReset(void);

#endif
