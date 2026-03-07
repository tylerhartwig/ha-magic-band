# Disney MagicBand+ & Popcorn Bucket for Home Assistant

Control your Disney MagicBand+ and Popcorn Buckets directly from Home Assistant! This integration allows you to:
- **Connected Mode**: Control individual buckets via BLE with full RGB and brightness support.
- **Broadcaster Mode**: Trigger "Glow with the Show" effects on all devices in the room simultaneously.
- **Presence Detection**: See which buckets are nearby in real-time.

## Prerequisites
- **Bluetooth Hardware**: A built-in Bluetooth adapter or an **ESPHome Bluetooth Proxy** is required.
- **HACS**: Installed in your Home Assistant.

## Installation
1. Add this URL to your **HACS Custom Repositories**.
2. Search for "Disney MagicBand+" and click **Download**.
3. Restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for "Disney MagicBand+".

## Virtual Testing
If you don't have a physical bucket yet, run the simulator in this repo:
```bash
pip install bless
python3 custom_components/ha_magic_band/simulators/magic_bucket_sim.py
```
