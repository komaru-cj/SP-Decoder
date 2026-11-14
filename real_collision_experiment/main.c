#include <stdio.h>
#include <string.h>

#include "board.h"
#include "delay.h"
#include "experiment_protocol.h"
#include "gpio.h"
#include "radio.h"
#include "sx1276Regs-LoRa.h"
#include "timer.h"

/* Build one image per board by setting EXPERIMENT_NODE_ID to 1..15. */
#ifndef EXPERIMENT_NODE_ID
#define EXPERIMENT_NODE_ID                         1U
#endif

#if ( EXPERIMENT_NODE_ID < 1 ) || ( EXPERIMENT_NODE_ID > 15 )
#error "EXPERIMENT_NODE_ID must be in the range 1..15"
#endif

#define EXPERIMENT_FREQUENCY_HZ                    487700000UL
#define CONTROL_BANDWIDTH_INDEX                    0U
#define CONTROL_SPREADING_FACTOR                   10U
#define EXPERIMENT_CODING_RATE                     1U
#define EXPERIMENT_PREAMBLE_LENGTH                 8U
#define EXPERIMENT_FIXED_LENGTH                    false
#define EXPERIMENT_PHY_CRC                         true
#define EXPERIMENT_FREQ_HOP                        false
#define EXPERIMENT_HOP_PERIOD                      0U
#define EXPERIMENT_IQ_INVERTED                     false
#define EXPERIMENT_SYNC_WORD                       0x34U
#define EXPERIMENT_TX_TIMEOUT_MS                   5000U
#define CONTROL_RX_SYMBOL_TIMEOUT                  10U
#define RX_FRAME_BUFFER_SIZE                       64U

typedef enum ExperimentNodeState_e
{
    NODE_WAIT_CONFIG = 0,
    NODE_WAIT_START,
    NODE_ARMED,
    NODE_WARMUP,
    NODE_WAIT_GAP,
    NODE_TX_RUNNING,
    NODE_INACTIVE,
    NODE_RUN_COMPLETE
} ExperimentNodeState_t;

static RadioEvents_t RadioEvents;
static TimerEvent_t StateTimer;
static ExperimentConfig_t RunConfig;
static ExperimentNodeState_t NodeState = NODE_WAIT_CONFIG;

static volatile bool RxFrameReady = false;
static volatile bool TxDoneReady = false;
static volatile bool TxTimeoutReady = false;
static volatile bool StateTimerReady = false;
static volatile uint16_t RxFrameSize = 0U;
static volatile int16_t RxFrameRssi = 0;
static volatile int8_t RxFrameSnr = 0;
static volatile TimerTime_t TxDoneIrqTime = 0U;

static uint8_t RxFrameBuffer[RX_FRAME_BUFFER_SIZE];
static uint8_t TxPayload[EXP_DATA_PAYLOAD_SIZE];
static uint32_t PrngState = 1U;
static uint32_t PacketSequence = 0U;
static uint32_t PacketTimeOnAirMs = 0U;
static uint32_t MeanGapMs = 0U;
static uint32_t MeanPeriodMs = 0U;
static uint32_t ScheduledGapMs = 0U;
static uint32_t DataBandwidthHz = 125000UL;
static TimerTime_t TrafficEpochMs = 0U;
static TimerTime_t TxStartMs = 0U;
static uint8_t DataBandwidthIndex = CONTROL_BANDWIDTH_INDEX;
static uint8_t DataSpreadingFactor = CONTROL_SPREADING_FACTOR;

extern Gpio_t Led2;
extern Gpio_t Led3;

static void RunBootLedSelfTest( void )
{
    uint8_t pulse;

    /* PC13 is active-low: three pulses prove the LED path before radio RX. */
    for( pulse = 0U; pulse < 3U; pulse++ )
    {
        GpioWrite( &Led3, 0 );
        DelayMs( 200U );
        GpioWrite( &Led3, 1 );
        DelayMs( 200U );
    }
}

static void IndicateInvalidControlFrame( void )
{
    uint8_t pulse;

    /* Two quick pulses mean LoRa PHY reception succeeded but protocol validation failed. */
    for( pulse = 0U; pulse < 2U; pulse++ )
    {
        GpioWrite( &Led3, 0 );
        DelayMs( 80U );
        GpioWrite( &Led3, 1 );
        DelayMs( 80U );
    }
}

static void ConfigureRadioTx( int8_t txPowerDbm )
{
    Radio.SetChannel( EXPERIMENT_FREQUENCY_HZ );
    Radio.SetTxConfig( MODEM_LORA, txPowerDbm, 0U,
                       DataBandwidthIndex, DataSpreadingFactor,
                       EXPERIMENT_CODING_RATE, EXPERIMENT_PREAMBLE_LENGTH,
                       EXPERIMENT_FIXED_LENGTH, EXPERIMENT_PHY_CRC,
                       EXPERIMENT_FREQ_HOP, EXPERIMENT_HOP_PERIOD,
                       EXPERIMENT_IQ_INVERTED, EXPERIMENT_TX_TIMEOUT_MS );
}

static void StartControlRx( void )
{
    Radio.SetChannel( EXPERIMENT_FREQUENCY_HZ );
    Radio.SetRxConfig( MODEM_LORA, CONTROL_BANDWIDTH_INDEX,
                       CONTROL_SPREADING_FACTOR, EXPERIMENT_CODING_RATE,
                       0U, EXPERIMENT_PREAMBLE_LENGTH,
                       CONTROL_RX_SYMBOL_TIMEOUT, EXPERIMENT_FIXED_LENGTH,
                       0U, EXPERIMENT_PHY_CRC, EXPERIMENT_FREQ_HOP,
                       EXPERIMENT_HOP_PERIOD, EXPERIMENT_IQ_INVERTED, true );
    Radio.Rx( 0U );
}

static void ScheduleStateTimer( uint32_t delayMs )
{
    StateTimerReady = false;
    TimerSetValue( &StateTimer, ( delayMs == 0U ) ? 1U : delayMs );
    TimerStart( &StateTimer );
}

static uint32_t BandwidthIndexToHz( uint8_t bandwidthIndex )
{
    if( bandwidthIndex == 1U )
    {
        return 250000UL;
    }
    if( bandwidthIndex == 2U )
    {
        return 500000UL;
    }
    return 125000UL;
}

static uint32_t RemainingRunTimeMs( void )
{
    uint32_t elapsed = TimerGetElapsedTime( TrafficEpochMs );

    return ( elapsed < RunConfig.durationMs ) ?
           ( RunConfig.durationMs - elapsed ) : 0U;
}

static void FinishRun( void )
{
    TimerStop( &StateTimer );
    Radio.Sleep( );
    NodeState = NODE_RUN_COMPLETE;
    GpioWrite( &Led2, 1 );
    GpioWrite( &Led3, 1 );
    printf( "RUN_COMPLETE,run=%lu,node=%u,packets=%lu,elapsed_ms=%lu\r\n",
            ( unsigned long )RunConfig.runId, ( unsigned int )EXPERIMENT_NODE_ID,
            ( unsigned long )PacketSequence,
            ( unsigned long )TimerGetElapsedTime( TrafficEpochMs ) );
    NodeState = NODE_WAIT_CONFIG;
    printf( "WAIT_CONFIG,node=%u\r\n", ( unsigned int )EXPERIMENT_NODE_ID );
    StartControlRx( );
}

static void ScheduleNextTransmission( bool initialDelay )
{
    uint32_t delayMs;
    uint32_t remainingMs = RemainingRunTimeMs( );

    if( remainingMs == 0U )
    {
        FinishRun( );
        return;
    }

    if( initialDelay == true )
    {
        delayMs = ExperimentPrngNext( &PrngState ) % ( MeanPeriodMs + 1U );
    }
    else
    {
        delayMs = ExperimentExponentialGapMs( MeanGapMs, &PrngState );
    }
    if( delayMs > remainingMs )
    {
        delayMs = remainingMs;
    }

    ScheduledGapMs = delayMs;
    NodeState = NODE_WAIT_GAP;
    ScheduleStateTimer( delayMs );
}

static bool ConfigureAcceptedRun( const ExperimentConfig_t *config )
{
    uint32_t dutyMilli = ExperimentTrafficDutyMilli( config->trafficProfileId );
    uint32_t aggregateLoadMilli;
    uint32_t numerator;
    uint8_t bandwidthIndex;
    uint8_t spreadingFactor;

    if( ( ExperimentGetPhyProfile( config->phyProfileId, &bandwidthIndex,
                                   &spreadingFactor ) == false ) ||
        ( dutyMilli == 0U ) || ( dutyMilli >= 1000UL ) )
    {
        printf( "CONFIG_REJECT,reason=invalid_phy_or_duty,phy=%u,traffic=%u,duty_milli=%lu,N=%u\r\n",
                ( unsigned int )config->phyProfileId,
                ( unsigned int )config->trafficProfileId,
                ( unsigned long )dutyMilli,
                ( unsigned int )config->numActiveNodes );
        return false;
    }

    RunConfig = *config;
    DataBandwidthIndex = bandwidthIndex;
    DataSpreadingFactor = spreadingFactor;
    DataBandwidthHz = BandwidthIndexToHz( bandwidthIndex );
    ConfigureRadioTx( RunConfig.txPowerDbm );
    PacketTimeOnAirMs = Radio.TimeOnAir( MODEM_LORA, EXP_DATA_PAYLOAD_SIZE );

    numerator = 1000UL - dutyMilli;
    MeanGapMs = ( uint32_t )( ( ( uint64_t )PacketTimeOnAirMs * numerator ) /
                              dutyMilli );
    if( MeanGapMs == 0U )
    {
        MeanGapMs = 1U;
    }
    MeanPeriodMs = PacketTimeOnAirMs + MeanGapMs;
    aggregateLoadMilli = ( uint32_t )RunConfig.numActiveNodes * dutyMilli;

    printf( "CONFIG_OK,run=%lu,node=%u,active=%u,mask=0x%04X,N=%u,phy=%u,SF=%u,BW_hz=%lu,traffic=%u,duty_milli=%lu,G_milli=%lu,power_dbm=%d,duration_ms=%lu,warmup_ms=%lu,toa_ms=%lu,mean_gap_ms=%lu,crc=0x%04X\r\n",
            ( unsigned long )RunConfig.runId, ( unsigned int )EXPERIMENT_NODE_ID,
            ( unsigned int )( ( RunConfig.activeMask >> ( EXPERIMENT_NODE_ID - 1U ) ) & 1U ),
            ( unsigned int )RunConfig.activeMask,
            ( unsigned int )RunConfig.numActiveNodes,
            ( unsigned int )RunConfig.phyProfileId,
            ( unsigned int )DataSpreadingFactor,
            ( unsigned long )DataBandwidthHz,
            ( unsigned int )RunConfig.trafficProfileId,
            ( unsigned long )dutyMilli,
            ( unsigned long )aggregateLoadMilli, ( int )RunConfig.txPowerDbm,
            ( unsigned long )RunConfig.durationMs,
            ( unsigned long )RunConfig.warmupMs,
            ( unsigned long )PacketTimeOnAirMs,
            ( unsigned long )MeanGapMs,
            ( unsigned int )RunConfig.frameCrc );
    return true;
}

static void HandleControlFrame( void )
{
    ExperimentConfig_t config;
    uint32_t startDelayMs = 0U;
    uint16_t size = RxFrameSize;
    int16_t rssi = RxFrameRssi;
    int8_t snr = RxFrameSnr;

    RxFrameReady = false;

    if( ( NodeState == NODE_WAIT_CONFIG ) || ( NodeState == NODE_WAIT_START ) )
    {
        if( ExperimentDecodeConfig( RxFrameBuffer, size, &config ) == true )
        {
            if( ConfigureAcceptedRun( &config ) == true )
            {
                NodeState = NODE_WAIT_START;
                /* PC13 stays on while an accepted CONFIG is waiting for START. */
                GpioWrite( &Led3, 0 );
            }
            StartControlRx( );
            return;
        }
    }

    if( ( NodeState == NODE_WAIT_START ) || ( NodeState == NODE_ARMED ) )
    {
        if( ExperimentDecodeStart( RxFrameBuffer, size, RunConfig.runId,
                                   RunConfig.frameCrc, &startDelayMs ) == true )
        {
            bool active = ( ( RunConfig.activeMask >>
                              ( EXPERIMENT_NODE_ID - 1U ) ) & 1U ) != 0U;

            GpioWrite( &Led3, 1 );
            PacketSequence = 0U;
            PrngState = RunConfig.globalSeed ^ RunConfig.payloadSeed ^
                        RunConfig.runId ^
                        ( ( uint32_t )EXPERIMENT_NODE_ID * 0x9E3779B9UL );
            if( PrngState == 0U )
            {
                PrngState = 1U;
            }

            printf( "START_OK,run=%lu,node=%u,active=%u,rssi=%d,snr=%d,start_delay_ms=%lu,warmup_ms=%lu\r\n",
                    ( unsigned long )RunConfig.runId,
                    ( unsigned int )EXPERIMENT_NODE_ID,
                    ( unsigned int )active, ( int )rssi, ( int )snr,
                    ( unsigned long )startDelayMs,
                    ( unsigned long )RunConfig.warmupMs );

            if( active == false )
            {
                Radio.Sleep( );
                NodeState = NODE_INACTIVE;
                ScheduleStateTimer( startDelayMs + RunConfig.warmupMs +
                                    RunConfig.durationMs );
                return;
            }

            NodeState = NODE_ARMED;
            ScheduleStateTimer( startDelayMs );
            StartControlRx( );
            return;
        }
    }

    IndicateInvalidControlFrame( );
    printf( "CONTROL_DROP,node=%u,size=%u,rssi=%d,snr=%d,state=%u\r\n",
            ( unsigned int )EXPERIMENT_NODE_ID, ( unsigned int )size,
            ( int )rssi, ( int )snr, ( unsigned int )NodeState );
    StartControlRx( );
}

static void SendExperimentPacket( void )
{
    uint16_t appCrc;

    ExperimentBuildPayload( TxPayload, &RunConfig,
                            ( uint8_t )EXPERIMENT_NODE_ID, PacketSequence );
    appCrc = ( uint16_t )TxPayload[18] | ( ( uint16_t )TxPayload[19] << 8 );

    ConfigureRadioTx( RunConfig.txPowerDbm );
    TxStartMs = TimerGetCurrentTime( );
    NodeState = NODE_TX_RUNNING;
    GpioWrite( &Led3, 0 );

    printf( "TX_START,run=%lu,node=%u,seq=%lu,t_ms=%lu,gap_ms=%lu,app_crc=0x%04X,prbs=%02X%02X%02X%02X\r\n",
            ( unsigned long )RunConfig.runId,
            ( unsigned int )EXPERIMENT_NODE_ID,
            ( unsigned long )PacketSequence,
            ( unsigned long )TimerGetElapsedTime( TrafficEpochMs ),
            ( unsigned long )ScheduledGapMs, ( unsigned int )appCrc,
            TxPayload[17], TxPayload[16], TxPayload[15], TxPayload[14] );
    Radio.Send( TxPayload, EXP_DATA_PAYLOAD_SIZE );
}

static void HandleStateTimer( void )
{
    StateTimerReady = false;

    if( NodeState == NODE_ARMED )
    {
        Radio.Sleep( );
        NodeState = NODE_WARMUP;
        ScheduleStateTimer( RunConfig.warmupMs );
    }
    else if( NodeState == NODE_WARMUP )
    {
        TrafficEpochMs = TimerGetCurrentTime( );
        printf( "TRAFFIC_BEGIN,run=%lu,node=%u,t_ms=0\r\n",
                ( unsigned long )RunConfig.runId,
                ( unsigned int )EXPERIMENT_NODE_ID );
        ScheduleNextTransmission( true );
    }
    else if( NodeState == NODE_WAIT_GAP )
    {
        if( RemainingRunTimeMs( ) == 0U )
        {
            FinishRun( );
        }
        else
        {
            SendExperimentPacket( );
        }
    }
    else if( NodeState == NODE_INACTIVE )
    {
        printf( "RUN_COMPLETE,run=%lu,node=%u,active=0,packets=0\r\n",
                ( unsigned long )RunConfig.runId,
                ( unsigned int )EXPERIMENT_NODE_ID );
        NodeState = NODE_WAIT_CONFIG;
        printf( "WAIT_CONFIG,node=%u\r\n", ( unsigned int )EXPERIMENT_NODE_ID );
        StartControlRx( );
    }
}

static void HandleTxDone( void )
{
    uint32_t sequence = PacketSequence;
    uint32_t txDurationMs = TimerGetElapsedTime( TxStartMs );

    TxDoneReady = false;
    Radio.Sleep( );
    GpioWrite( &Led3, 1 );
    PacketSequence++;

    printf( "TX_DONE,run=%lu,node=%u,seq=%lu,t_ms=%lu,tx_ms=%lu,irq_ms=%lu\r\n",
            ( unsigned long )RunConfig.runId,
            ( unsigned int )EXPERIMENT_NODE_ID,
            ( unsigned long )sequence,
            ( unsigned long )TimerGetElapsedTime( TrafficEpochMs ),
            ( unsigned long )txDurationMs,
            ( unsigned long )TxDoneIrqTime );
    ScheduleNextTransmission( false );
}

static void HandleTxTimeout( void )
{
    uint32_t sequence = PacketSequence;

    TxTimeoutReady = false;
    Radio.Sleep( );
    GpioWrite( &Led3, 1 );
    PacketSequence++;
    printf( "TX_TIMEOUT,run=%lu,node=%u,seq=%lu,t_ms=%lu\r\n",
            ( unsigned long )RunConfig.runId,
            ( unsigned int )EXPERIMENT_NODE_ID,
            ( unsigned long )sequence,
            ( unsigned long )TimerGetElapsedTime( TrafficEpochMs ) );
    ScheduleNextTransmission( false );
}

static void OnTxDone( void )
{
    TxDoneIrqTime = TimerGetCurrentTime( );
    TxDoneReady = true;
}

static void OnTxTimeout( void )
{
    TxTimeoutReady = true;
}

static void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr )
{
    Radio.Sleep( );
    if( size <= RX_FRAME_BUFFER_SIZE )
    {
        memcpy( RxFrameBuffer, payload, size );
        RxFrameSize = size;
    }
    else
    {
        RxFrameSize = 0U;
    }
    RxFrameRssi = rssi;
    RxFrameSnr = snr;
    RxFrameReady = true;
}

static void OnRxTimeout( void )
{
    Radio.Sleep( );
    StartControlRx( );
}

static void OnRxError( void )
{
    Radio.Sleep( );
    StartControlRx( );
}

static void OnStateTimer( void *context )
{
    ( void )context;
    StateTimerReady = true;
}

int main( void )
{
    BoardInitMcu( );
    BoardInitPeriph( );
    RunBootLedSelfTest( );

    TimerInit( &StateTimer, OnStateTimer );

    RadioEvents.TxDone = OnTxDone;
    RadioEvents.RxDone = OnRxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    RadioEvents.RxTimeout = OnRxTimeout;
    RadioEvents.RxError = OnRxError;
    RadioEvents.FhssChangeChannel = 0;
    RadioEvents.CadDone = 0;
    Radio.Init( &RadioEvents );
    Radio.SetPublicNetwork( true );
    Radio.Write( REG_LR_SYNCWORD, EXPERIMENT_SYNC_WORD );

    GpioWrite( &Led2, 1 );
    GpioWrite( &Led3, 1 );

    printf( "BOOT,board=STM32F103C8T6,radio=SX1276,node=%u,protocol=2,freq_hz=%lu,control_SF=10,control_BW_hz=125000,CR=4/5,preamble=8,header=explicit,phy_crc=on,sync=0x34,payload_bytes=20\r\n",
            ( unsigned int )EXPERIMENT_NODE_ID,
            ( unsigned long )EXPERIMENT_FREQUENCY_HZ );
    printf( "WAIT_CONFIG,node=%u\r\n", ( unsigned int )EXPERIMENT_NODE_ID );
    StartControlRx( );

    while( 1 )
    {
        if( RxFrameReady == true )
        {
            HandleControlFrame( );
        }
        if( StateTimerReady == true )
        {
            HandleStateTimer( );
        }
        if( TxDoneReady == true )
        {
            HandleTxDone( );
        }
        if( TxTimeoutReady == true )
        {
            HandleTxTimeout( );
        }

        BoardLowPowerHandler( );
    }
}
