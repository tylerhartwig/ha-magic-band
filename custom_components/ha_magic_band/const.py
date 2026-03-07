"""Constants for the Disney MagicBand+ & Bucket integration."""

DOMAIN = "ha_magic_band"

# BLE Service and Characteristic UUIDs
MAGICBAND_SERVICE_UUID = "0000fee7-0000-1000-8000-00805f9b34fb"
MAGICBAND_CHAR_UUID = "0000fee8-0000-1000-8000-00805f9b34fb"

# Manufacturer ID for Disney (Glow with the Show)
DISNEY_MANUFACTURER_ID = 0x01E5

# Integration Modes
CONF_MODE_CONNECTED = "connected"
CONF_MODE_BROADCASTER = "broadcaster"

# Notification/Update signals
SIGNAL_BUCKET_UPDATE = f"{DOMAIN}_bucket_update"

# Default timeouts
CONNECTION_TIMEOUT = 10.0
ADVERTISEMENT_TIMEOUT = 180.0  # 3 minutes for presence detection
