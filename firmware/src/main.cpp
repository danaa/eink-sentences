#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <SPI.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// If your panel rev shows garbled output with GxEPD2_750_T7, swap the
// include + class to GxEPD2_750_GDEY075T7 (newer SSD168x controllers).
#include <GxEPD2_BW.h>
#include <epd/GxEPD2_750_T7.h>

#include <PNGdec.h>
#include "secrets.h"

// Pinout — Seeed XIAO ePaper Driver Board (default).
#define EPD_CS   3   // D1
#define EPD_DC   5   // D3
#define EPD_RST  2   // D0
#define EPD_BUSY 4   // D2

GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(
    GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

static const uint64_t SLEEP_US        = 5ULL * 60ULL * 1000000ULL; // 5 min
static const uint32_t WIFI_TIMEOUT_MS = 15000;
static const size_t   PNG_BUF_SIZE    = 64 * 1024;

static uint8_t pngBuffer[PNG_BUF_SIZE];
static size_t  pngBufferLen = 0;
static PNG     png;

int pngDraw(PNGDRAW *pDraw) {
  const uint8_t *row = pDraw->pPixels;
  for (int x = 0; x < pDraw->iWidth && x < 800; x++) {
    uint8_t byte = row[x >> 3];
    uint8_t bit  = (byte >> (7 - (x & 7))) & 1;
    uint16_t color = bit ? GxEPD_WHITE : GxEPD_BLACK;
    display.drawPixel(x, pDraw->y, color);
  }
  return 1;
}

void deepSleep() {
  // Diagnostic window: stay alive for 10s so we can capture serial output
  // before USB-CDC dies in deep sleep.
  Serial.println("STAYING ALIVE 10s FOR DIAGNOSTICS");
  Serial.flush();
  for (int i = 10; i > 0; i--) {
    Serial.printf("alive %ds\n", i);
    delay(1000);
  }
  Serial.println("Sleeping 5 min");
  Serial.flush();
  esp_sleep_enable_timer_wakeup(SLEEP_US);
  esp_deep_sleep_start();
}

bool connectWiFi() {
  Serial.printf("Connecting to %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);  // reduce current draw during connect
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi timeout");
    return false;
  }
  Serial.printf("IP: %s, RSSI: %d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  return true;
}

bool fetchPng() {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  if (!http.begin(client, SERVER_URL)) {
    Serial.println("http.begin failed");
    return false;
  }
  int code = http.GET();
  if (code != 200) {
    Serial.printf("HTTP %d\n", code);
    http.end();
    return false;
  }
  WiFiClient *stream = http.getStreamPtr();
  pngBufferLen = 0;
  uint32_t start = millis();
  while (http.connected() && (millis() - start) < 30000) {
    size_t avail = stream->available();
    if (avail > 0) {
      size_t space = PNG_BUF_SIZE - pngBufferLen;
      if (space == 0) {
        Serial.println("PNG larger than buffer");
        http.end();
        return false;
      }
      size_t toRead = avail < space ? avail : space;
      int got = stream->readBytes(pngBuffer + pngBufferLen, toRead);
      pngBufferLen += got;
    } else if (!stream->connected() || http.getSize() == (int)pngBufferLen) {
      break;
    } else {
      delay(5);
    }
  }
  http.end();
  Serial.printf("Fetched %u bytes\n", (unsigned)pngBufferLen);
  return pngBufferLen > 0;
}

bool decodeAndDraw() {
  Serial.println("Init display");
  display.init(115200, true, 2, false);

  int rc = png.openRAM(pngBuffer, pngBufferLen, pngDraw);
  if (rc != PNG_SUCCESS) {
    Serial.printf("PNG open failed: %d\n", rc);
    return false;
  }
  Serial.printf("PNG %dx%d, %dbpp\n", png.getWidth(), png.getHeight(), png.getBpp());
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    rc = png.decode(NULL, 0);
  } while (display.nextPage());
  png.close();
  display.hibernate();
  return rc == PNG_SUCCESS;
}

void setup() {
  // Disable brownout detector — prevents reset loops on partial battery
  // when Wi-Fi + display init spike the current draw.
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  // Give USB-CDC time to enumerate before any heavy work.
  delay(2000);
  Serial.println("\n=== eink-sentences wake ===");

  if (!connectWiFi()) {
    deepSleep();
  }
  if (!fetchPng()) {
    deepSleep();
  }
  if (!decodeAndDraw()) {
    Serial.println("Decode/draw failed");
    deepSleep();
  }

  Serial.println("Display refreshed");
  deepSleep();
}

void loop() {
  // never reached
}
