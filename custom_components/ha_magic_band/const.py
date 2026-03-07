"""Constants for the Disney MagicBand+ & Bucket integration."""

DOMAIN = "ha_magic_band"

# BLE Service and Characteristic UUIDs (Amazon Gadgets Protocol)
MAGICBAND_SERVICE_UUID = "0000fee8-0000-1000-8000-00805f9b34fb"
MAGICBAND_CHAR_WRITE_UUID = "f04eb177-3005-43a7-ac61-a390ddf83076"
MAGICBAND_CHAR_NOTIFY_UUID = "2beea05b-1879-4bb4-8a2f-72641f82420b"

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
