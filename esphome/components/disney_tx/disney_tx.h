#pragma once

#include "esphome/components/esp32_ble/ble.h"
#include "esphome/core/component.h"

#ifdef USE_ESP32

#include <esp_gap_ble_api.h>
#include <string>
#include <vector>

namespace esphome::disney_tx {

/// Puts an exact advertising payload on air (non-connectable) for a fixed time.
/// Bypasses ESPHome's own advertising manager, which always adds the name and TX power.
class DisneyTx final : public Component {
 public:
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_BLUETOOTH; }

  /// `mfr_hex` is the manufacturer data including the company ID (e.g. "8301E905000E0EF5B0").
  /// Flags and the AD header are added. duration_ms 0 = until stop().
  bool advertise(const std::string &mfr_hex, int32_t duration_ms, int32_t interval_ms);
  /// `adv_hex` is the complete advertising payload (max 31 bytes).
  bool advertise_raw(const std::string &adv_hex, int32_t duration_ms, int32_t interval_ms);
  void stop();

  void gap_event_handler(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param);

 protected:
  bool start_(std::vector<uint8_t> &&payload, int32_t duration_ms, int32_t interval_ms);

  esp_ble_adv_params_t params_{};
  std::vector<uint8_t> payload_;
  bool want_start_{false};  // set while waiting for our own ADV_DATA_RAW_SET_COMPLETE
  bool on_air_{false};
};

}  // namespace esphome::disney_tx

#endif
