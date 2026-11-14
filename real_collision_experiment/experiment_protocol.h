#ifndef __EXPERIMENT_PROTOCOL_H__
#define __EXPERIMENT_PROTOCOL_H__

#include <stdbool.h>
#include <stdint.h>

#define EXP_PROTOCOL_MAGIC_0               0x53U
#define EXP_PROTOCOL_MAGIC_1               0x50U
#define EXP_PROTOCOL_VERSION               2U

#define EXP_FRAME_TYPE_CONFIG              1U
#define EXP_FRAME_TYPE_START               2U

#define EXP_CONFIG_FRAME_SIZE              34U
#define EXP_START_FRAME_SIZE               18U
#define EXP_DATA_PAYLOAD_SIZE              20U

#define EXP_PHY_PROFILE_MIN_ID             1U
#define EXP_PHY_PROFILE_MAX_ID             9U
#define EXP_TRAFFIC_PROFILE_MIN_ID         1U
#define EXP_TRAFFIC_PROFILE_MAX_ID         3U

typedef struct ExperimentConfig_s
{
    uint8_t flags;
    uint32_t runId;
    uint16_t activeMask;
    uint8_t numActiveNodes;
    uint8_t phyProfileId;
    uint8_t trafficProfileId;
    int8_t txPowerDbm;
    uint32_t durationMs;
    uint32_t warmupMs;
    uint32_t globalSeed;
    uint32_t payloadSeed;
    uint16_t frameCrc;
} ExperimentConfig_t;

uint16_t ExperimentCrc16( const uint8_t *data, uint16_t size );
bool ExperimentDecodeConfig( const uint8_t *frame, uint16_t size,
                             ExperimentConfig_t *config );
bool ExperimentDecodeStart( const uint8_t *frame, uint16_t size,
                            uint32_t expectedRunId, uint16_t expectedConfigCrc,
                            uint32_t *startDelayMs );
void ExperimentBuildPayload( uint8_t payload[EXP_DATA_PAYLOAD_SIZE],
                             const ExperimentConfig_t *config,
                             uint8_t nodeId, uint32_t sequence );
bool ExperimentGetPhyProfile( uint8_t phyProfileId, uint8_t *bandwidthIndex,
                              uint8_t *spreadingFactor );
uint32_t ExperimentTrafficDutyMilli( uint8_t trafficProfileId );
uint32_t ExperimentPrngNext( uint32_t *state );
uint32_t ExperimentExponentialGapMs( uint32_t meanGapMs, uint32_t *prngState );

#endif
