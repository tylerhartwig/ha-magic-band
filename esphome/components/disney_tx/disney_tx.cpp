#include "disney_tx.h"
#include "esphome/core/log.h"

#ifdef USE_ESP32

namespace esphome::disney_tx {

ESPHOME_LOG_TAG(TAG, "disney_tx");

static bool parse_hex_bytes(const std::string &hex, std::vector<uint8_t> &out) {
  out.clear();
  int hi = -1;
  for (char c : hex) {
    int v;
    if (c >= '0' && c <= '9') {
      v = c - '0';
    } else if (c >= 'a' && c <= 'f') {
      v = c - 'a' + 10;
    } else if (c >= 'A' && c <= 'F') {
      v = c - 'A' + 10;
    } else if (c == ' ' || c == ':') {
      continue;
    } else {
      return false;
    }
    if (hi < 0) {
      hi = v;
    } else {
      out.push_back(static_cast<uint8_t>(hi << 4 | v));
      hi = -1;
    }
  }
  return hi < 0;
}

void DisneyTx::setup() {
  this->params_ = {
      .adv_int_min = 0x30,  // 30 ms
      .adv_int_max = 0x30,
      .adv_type = ADV_TYPE_NONCONN_IND,
      .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
      .peer_addr = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
      .peer_addr_type = BLE_ADDR_TYPE_PUBLIC,
      .channel_map = ADV_CHNL_ALL,
      .adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
  };
}

void DisneyTx::dump_config() { ESP_LOGCONFIG(TAG, "Disney TX (raw non-connectable advertiser)"); }

bool DisneyTx::advertise(const std::string &mfr_hex, int32_t duration_ms, int32_t interval_ms) {
  std::vector<uint8_t> mfr;
  if (!parse_hex_bytes(mfr_hex, mfr) || mfr.size() < 2) {
    ESP_LOGW(TAG, "Bad manufacturer data hex: %s", mfr_hex.c_str());
    return false;
  }
  std::vector<uint8_t> payload = {0x02, 0x01, 0x06, static_cast<uint8_t>(mfr.size() + 1), 0xFF};
  payload.insert(payload.end(), mfr.begin(), mfr.end());
  return this->start_(std::move(payload), duration_ms, interval_ms);
}

bool DisneyTx::advertise_raw(const std::string &adv_hex, int32_t duration_ms, int32_t interval_ms) {
  std::vector<uint8_t> payload;
  if (!parse_hex_bytes(adv_hex, payload) || payload.empty()) {
    ESP_LOGW(TAG, "Bad advertising hex: %s", adv_hex.c_str());
    return false;
  }
  return this->start_(std::move(payload), duration_ms, interval_ms);
}

bool DisneyTx::start_(std::vector<uint8_t> &&payload, int32_t duration_ms, int32_t interval_ms) {
  if (payload.size() > 31) {
    ESP_LOGW(TAG, "Advertisement is %u bytes (max 31)", (unsigned) payload.size());
    return false;
  }
  if (!esp32_ble::global_ble->is_active()) {
    ESP_LOGW(TAG, "BLE not active yet");
    return false;
  }
  if (interval_ms < 20)
    interval_ms = 20;
  uint16_t units = static_cast<uint16_t>(interval_ms / 0.625f);
  this->params_.adv_int_min = units;
  this->params_.adv_int_max = units;

  this->cancel_timeout("stop");
  if (this->on_air_)
    esp_ble_gap_stop_advertising();
  this->payload_ = std::move(payload);
  this->want_start_ = true;
  esp_err_t err = esp_ble_gap_config_adv_data_raw(this->payload_.data(), this->payload_.size());
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "esp_ble_gap_config_adv_data_raw failed: %s", esp_err_to_name(err));
    this->want_start_ = false;
    return false;
  }
  if (duration_ms > 0)
    this->set_timeout("stop", duration_ms, [this]() { this->stop(); });
  char hex[2 * 31 + 1];
  ESP_LOGD(TAG, "Advertising %s for %d ms @ %d ms", format_hex_to(hex, this->payload_.data(), this->payload_.size()),
           (int) duration_ms, (int) interval_ms);
  return true;
}

void DisneyTx::stop() {
  this->cancel_timeout("stop");
  this->want_start_ = false;
  if (this->on_air_) {
    esp_ble_gap_stop_advertising();
    this->on_air_ = false;
  }
}

void DisneyTx::gap_event_handler(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param) {
  switch (event) {
    case ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT:
      if (!this->want_start_)
        return;
      this->want_start_ = false;
      if (esp_ble_gap_start_advertising(&this->params_) == ESP_OK)
        this->on_air_ = true;
      break;
    case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
      if (param->adv_start_cmpl.status != ESP_BT_STATUS_SUCCESS) {
        ESP_LOGE(TAG, "Advertising start failed: %d", param->adv_start_cmpl.status);
        this->on_air_ = false;
      }
      break;
    default:
      break;
  }
}

}  // namespace esphome::disney_tx

#endif
