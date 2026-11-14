#include "experiment_protocol.h"

typedef struct ExperimentPhyProfile_s
{
    uint8_t bandwidthIndex;
    uint8_t spreadingFactor;
} ExperimentPhyProfile_t;

static uint16_t ReadU16Le( const uint8_t *data )
{
    return ( uint16_t )data[0] | ( ( uint16_t )data[1] << 8 );
}

static uint32_t ReadU32Le( const uint8_t *data )
{
    return ( uint32_t )data[0] |
           ( ( uint32_t )data[1] << 8 ) |
           ( ( uint32_t )data[2] << 16 ) |
           ( ( uint32_t )data[3] << 24 );
}

static void WriteU16Le( uint8_t *data, uint16_t value )
{
    data[0] = ( uint8_t )value;
    data[1] = ( uint8_t )( value >> 8 );
}

static void WriteU32Le( uint8_t *data, uint32_t value )
{
    data[0] = ( uint8_t )value;
    data[1] = ( uint8_t )( value >> 8 );
    data[2] = ( uint8_t )( value >> 16 );
    data[3] = ( uint8_t )( value >> 24 );
}

bool ExperimentGetPhyProfile( uint8_t phyProfileId, uint8_t *bandwidthIndex,
                              uint8_t *spreadingFactor )
{
    static const ExperimentPhyProfile_t profiles[EXP_PHY_PROFILE_MAX_ID + 1U] =
    {
        { 0U, 0U },
        { 0U, 8U },   /* 1: SF8 / BW125 */
        { 0U, 10U },  /* 2: SF10 / BW125 */
        { 0U, 12U },  /* 3: SF12 / BW125 */
        { 1U, 8U },   /* 4: SF8 / BW250 */
        { 1U, 10U },  /* 5: SF10 / BW250 */
        { 1U, 12U },  /* 6: SF12 / BW250 */
        { 2U, 8U },   /* 7: SF8 / BW500 */
        { 2U, 10U },  /* 8: SF10 / BW500 */
        { 2U, 12U },  /* 9: SF12 / BW500 */
    };

    if( ( bandwidthIndex == 0 ) || ( spreadingFactor == 0 ) ||
        ( phyProfileId < EXP_PHY_PROFILE_MIN_ID ) ||
        ( phyProfileId > EXP_PHY_PROFILE_MAX_ID ) )
    {
        return false;
    }

    *bandwidthIndex = profiles[phyProfileId].bandwidthIndex;
    *spreadingFactor = profiles[phyProfileId].spreadingFactor;
    return true;
}

uint16_t ExperimentCrc16( const uint8_t *data, uint16_t size )
{
    uint16_t crc = 0xFFFFU;
    uint16_t i;
    uint8_t bit;

    for( i = 0; i < size; i++ )
    {
        crc ^= ( uint16_t )data[i] << 8;
        for( bit = 0; bit < 8U; bit++ )
        {
            crc = ( crc & 0x8000U ) ? ( uint16_t )( ( crc << 1 ) ^ 0x1021U )
                                    : ( uint16_t )( crc << 1 );
        }
    }
    return crc;
}

bool ExperimentDecodeConfig( const uint8_t *frame, uint16_t size,
                             ExperimentConfig_t *config )
{
    uint16_t receivedCrc;
    uint16_t mask;
    uint8_t activeCount = 0U;
    uint8_t bandwidthIndex;
    uint8_t spreadingFactor;

    if( ( frame == 0 ) || ( config == 0 ) || ( size != EXP_CONFIG_FRAME_SIZE ) )
    {
        return false;
    }
    if( ( frame[0] != EXP_PROTOCOL_MAGIC_0 ) ||
        ( frame[1] != EXP_PROTOCOL_MAGIC_1 ) ||
        ( frame[2] != EXP_PROTOCOL_VERSION ) ||
        ( frame[3] != EXP_FRAME_TYPE_CONFIG ) ||
        ( frame[4] != EXP_CONFIG_FRAME_SIZE ) )
    {
        return false;
    }

    receivedCrc = ReadU16Le( &frame[32] );
    if( ExperimentCrc16( frame, 32U ) != receivedCrc )
    {
        return false;
    }

    config->flags = frame[5];
    config->runId = ReadU32Le( &frame[6] );
    config->activeMask = ReadU16Le( &frame[10] );
    config->numActiveNodes = frame[12];
    config->phyProfileId = frame[13];
    config->trafficProfileId = frame[14];
    config->txPowerDbm = ( int8_t )frame[15];
    config->durationMs = ReadU32Le( &frame[16] );
    config->warmupMs = ReadU32Le( &frame[20] );
    config->globalSeed = ReadU32Le( &frame[24] );
    config->payloadSeed = ReadU32Le( &frame[28] );
    config->frameCrc = receivedCrc;

    mask = config->activeMask;
    while( mask != 0U )
    {
        activeCount += ( uint8_t )( mask & 1U );
        mask >>= 1;
    }

    if( ( config->numActiveNodes == 0U ) || ( config->numActiveNodes > 15U ) ||
        ( activeCount != config->numActiveNodes ) ||
        ( ( config->activeMask & 0x8000U ) != 0U ) ||
        ( ExperimentGetPhyProfile( config->phyProfileId, &bandwidthIndex,
                                   &spreadingFactor ) == false ) ||
        ( ExperimentTrafficDutyMilli( config->trafficProfileId ) == 0U ) ||
        ( config->txPowerDbm < -4 ) || ( config->txPowerDbm > 20 ) ||
        ( config->durationMs < 1000U ) || ( config->durationMs > 3600000UL ) ||
        ( config->warmupMs > 60000UL ) )
    {
        return false;
    }
    return true;
}

bool ExperimentDecodeStart( const uint8_t *frame, uint16_t size,
                            uint32_t expectedRunId, uint16_t expectedConfigCrc,
                            uint32_t *startDelayMs )
{
    uint16_t frameCrc;
    uint32_t delayMs;

    if( ( frame == 0 ) || ( startDelayMs == 0 ) ||
        ( size != EXP_START_FRAME_SIZE ) )
    {
        return false;
    }
    if( ( frame[0] != EXP_PROTOCOL_MAGIC_0 ) ||
        ( frame[1] != EXP_PROTOCOL_MAGIC_1 ) ||
        ( frame[2] != EXP_PROTOCOL_VERSION ) ||
        ( frame[3] != EXP_FRAME_TYPE_START ) ||
        ( frame[4] != EXP_START_FRAME_SIZE ) ||
        ( ReadU32Le( &frame[6] ) != expectedRunId ) ||
        ( ReadU16Le( &frame[10] ) != expectedConfigCrc ) )
    {
        return false;
    }

    delayMs = ReadU32Le( &frame[12] );
    if( ( delayMs == 0U ) || ( delayMs > 60000UL ) )
    {
        return false;
    }

    frameCrc = ReadU16Le( &frame[16] );
    if( ExperimentCrc16( frame, 16U ) != frameCrc )
    {
        return false;
    }

    *startDelayMs = delayMs;
    return true;
}

uint32_t ExperimentPrngNext( uint32_t *state )
{
    uint32_t value = *state;

    if( value == 0U )
    {
        value = 0x6D2B79F5UL;
    }
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    *state = value;
    return value;
}

void ExperimentBuildPayload( uint8_t payload[EXP_DATA_PAYLOAD_SIZE],
                             const ExperimentConfig_t *config,
                             uint8_t nodeId, uint32_t sequence )
{
    uint32_t prbsState;
    uint32_t prbsWord;
    uint16_t crc;

    payload[0] = EXP_PROTOCOL_MAGIC_0;
    payload[1] = EXP_PROTOCOL_MAGIC_1;
    payload[2] = EXP_PROTOCOL_VERSION;
    payload[3] = nodeId;
    WriteU32Le( &payload[4], config->runId );
    WriteU32Le( &payload[8], sequence );
    payload[12] = config->phyProfileId;
    payload[13] = config->trafficProfileId;

    prbsState = config->payloadSeed ^ config->runId ^
                ( ( uint32_t )nodeId * 0x9E3779B9UL ) ^ sequence;
    prbsWord = ExperimentPrngNext( &prbsState );
    WriteU32Le( &payload[14], prbsWord );

    crc = ExperimentCrc16( payload, 18U );
    WriteU16Le( &payload[18], crc );
}

uint32_t ExperimentTrafficDutyMilli( uint8_t trafficProfileId )
{
    static const uint16_t dutyMilli[EXP_TRAFFIC_PROFILE_MAX_ID + 1U] =
    {
        0U, 250U, 500U, 750U
    };

    if( ( trafficProfileId < EXP_TRAFFIC_PROFILE_MIN_ID ) ||
        ( trafficProfileId > EXP_TRAFFIC_PROFILE_MAX_ID ) )
    {
        return 0U;
    }
    return dutyMilli[trafficProfileId];
}

static uint32_t NegativeLogQ16( uint32_t uniformValue )
{
    uint32_t normalized;
    uint32_t yQ16;
    uint32_t termQ16;
    uint32_t sumQ16;
    uint8_t exponent = 0U;
    uint8_t n;

    if( uniformValue == 0U )
    {
        uniformValue = 1U;
    }
    normalized = uniformValue;
    while( ( normalized & 0x80000000UL ) == 0U )
    {
        normalized <<= 1;
        exponent++;
    }

    yQ16 = 65536UL - ( normalized >> 16 );
    termQ16 = yQ16;
    sumQ16 = termQ16;
    for( n = 2U; n <= 8U; n++ )
    {
        termQ16 = ( uint32_t )( ( ( uint64_t )termQ16 * yQ16 ) >> 16 );
        sumQ16 += termQ16 / n;
    }

    return sumQ16 + ( ( uint32_t )exponent * 45426UL );
}

uint32_t ExperimentExponentialGapMs( uint32_t meanGapMs, uint32_t *prngState )
{
    uint32_t expQ16;
    uint32_t gapMs;
    uint32_t maximumGapMs;

    if( meanGapMs == 0U )
    {
        return 1U;
    }
    expQ16 = NegativeLogQ16( ExperimentPrngNext( prngState ) );
    gapMs = ( uint32_t )( ( ( uint64_t )meanGapMs * expQ16 ) >> 16 );
    maximumGapMs = ( meanGapMs <= ( 0xFFFFFFFFUL / 8U ) ) ?
                   ( meanGapMs * 8U ) : 0xFFFFFFFFUL;

    if( gapMs > maximumGapMs )
    {
        gapMs = maximumGapMs;
    }
    return ( gapMs == 0U ) ? 1U : gapMs;
}
