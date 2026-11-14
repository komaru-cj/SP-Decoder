"""Shared defaults for the real LoRa receiver experiments."""

DEFAULT_CENTER_FREQ_HZ = 487_700_000.0
DEFAULT_SAMPLE_RATE_HZ = 1_000_000.0
DEFAULT_USRP_RX_BW_HZ = 250_000.0
DEFAULT_RX_GAIN_DB = 30.0
DEFAULT_CAPTURE_SECONDS = 2.0

LORA_SF = 10
LORA_BW_HZ = 125_000.0
LORA_PREAMBLE_SYMBOLS = 8
LORA_CODING_RATE = "4/5"
LORA_CRC = "on"
LORA_HEADER_MODE = "implicit fixed length"
LORA_PAYLOAD_BYTES = 32
LORA_PAYLOAD_SYMBOLS = 38
LORA_PAYLOAD_START_SYMBOLS = 12.25
LORA_TX_INTERVAL_S = 1.0
LORA_TX_POWER_DBM = 20.0
LORA_SYNC_WORD = 0x12

DEFAULT_CONFIG_NOTE = (
    "Experiment profile matched to the current transmitter: 487.7 MHz, LoRa "
    "SF10, BW125k, CR4/5, preamble 8, implicit fixed-length header, PHY CRC on, "
    "fixed 32-byte random payload, 1 s interval, TX power 20 dBm. The receiver "
    "decodes 38 LoRa payload symbol windows starting after preamble+4.25 symbols."
)
