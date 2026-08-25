#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <SPI.h>
#include <BH1750.h>
#include <MAX30100_PulseOximeter.h>
#include <Adafruit_BMP085.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <MFRC522.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_HOST = "YOUR_RASPBERRY_PI_IP";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "caregrid";
const char* MQTT_PASSWORD = "YOUR_MQTT_PASSWORD";

const char* DEVICE_ID = "hospital_ward_01";
const char* NODE_TYPE = "smart_hospital_ward";
const char* TELEMETRY_TOPIC = "caregrid/hospital/ward/ward-01/telemetry";
const char* STATUS_TOPIC = "caregrid/hospital/ward/ward-01/status";
const char* RFID_TOPIC = "caregrid/hospital/ward/ward-01/rfid";
const char* PANIC_TOPIC = "caregrid/hospital/ward/ward-01/panic";

constexpr uint8_t PIN_MQ = 1;
constexpr uint8_t PIN_VIBRATION = 6;
constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;
constexpr uint8_t PIN_TRIG = 10;
constexpr uint8_t PIN_ECHO = 11;
constexpr uint8_t PIN_PMS_RX = 12;
constexpr uint8_t PIN_PMS_TX = 13;
constexpr uint8_t PIN_RFID_SCK = 14;
constexpr uint8_t PIN_RFID_MOSI = 15;
constexpr uint8_t PIN_RFID_MISO = 16;
constexpr uint8_t PIN_RFID_CS = 17;
constexpr uint8_t PIN_RFID_RST = 18;
constexpr uint8_t PIN_PANIC = 21;

constexpr uint8_t OLED_ADDRESS = 0x3C;
constexpr int SCREEN_WIDTH = 128;
constexpr int SCREEN_HEIGHT = 64;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
BH1750 lightMeter;
PulseOximeter pox;
Adafruit_BMP085 bmp;
MFRC522 rfid(PIN_RFID_CS, PIN_RFID_RST);
HardwareSerial pmsSerial(1);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

bool bh1750OK=false, max30100OK=false, bmp180OK=false, oledOK=false;
bool pms5003OK=false, ultrasonicOK=false, rc522OK=false;
bool vibrationActive=false, panicActive=false, vitalsValid=false;
float lux=0, heartRate=0, spo2=0, temperatureC=0, pressureHpa=0;
uint16_t pm1=0, pm25=0, pm10=0, mqRaw=0;
float mqGPIOVoltage=0, mqSensorVoltage=0, mqBaseline=0;
bool mqBaselineReady=false, mqAnomaly=false;
float filteredDistanceCM=-1, binFillPercent=0;
float BIN_EMPTY_DISTANCE_CM=45.0, BIN_FULL_DISTANCE_CM=5.0;
String lastRFID="NONE";

uint8_t pmsFrame[32];
uint8_t pmsIndex=0;
unsigned long lastPMSFrame=0, lastVibrationPulse=0, lastPanicChange=0;
unsigned long lastEnvironmentRead=0, lastVitalsRead=0, lastUltrasonicRead=0;
unsigned long lastOLEDUpdate=0, lastMQTTPublish=0, lastWiFiAttempt=0, lastMQTTAttempt=0;
unsigned long startupTime=0;
int lastPanicRaw=HIGH, stablePanicRaw=HIGH;

constexpr unsigned long VIBRATION_HOLD_MS=800;
constexpr unsigned long PANIC_DEBOUNCE_MS=50;
constexpr unsigned long MQTT_INTERVAL=5000;

void processPMS5003() {
  while (pmsSerial.available()) {
    uint8_t v=pmsSerial.read();
    if (pmsIndex==0 && v!=0x42) continue;
    if (pmsIndex==1 && v!=0x4D) { pmsIndex=0; continue; }
    pmsFrame[pmsIndex++]=v;
    if (pmsIndex==32) {
      uint16_t sum=0; for(int i=0;i<30;i++) sum+=pmsFrame[i];
      uint16_t expected=((uint16_t)pmsFrame[30]<<8)|pmsFrame[31];
      if(sum==expected) {
        pm1=((uint16_t)pmsFrame[10]<<8)|pmsFrame[11];
        pm25=((uint16_t)pmsFrame[12]<<8)|pmsFrame[13];
        pm10=((uint16_t)pmsFrame[14]<<8)|pmsFrame[15];
        pms5003OK=true; lastPMSFrame=millis();
      }
      pmsIndex=0;
    }
  }
  if(millis()-lastPMSFrame>10000) pms5003OK=false;
}

void updateEnvironment() {
  if(bh1750OK) { float x=lightMeter.readLightLevel(); if(x>=0) lux=x; }
  if(bmp180OK) {
    float t=bmp.readTemperature(); int32_t p=bmp.readPressure();
    if(t>-40 && t<85 && p>30000 && p<120000) { temperatureC=t; pressureHpa=p/100.0f; }
  }
}

void updateVitals() {
  if(!max30100OK) { vitalsValid=false; return; }
  float hr=pox.getHeartRate(), s=pox.getSpO2();
  vitalsValid=(hr>=40 && hr<=200 && s>=80 && s<=100);
  if(vitalsValid) { heartRate=hr; spo2=s; }
}

float readDistance() {
  digitalWrite(PIN_TRIG,LOW); delayMicroseconds(3);
  digitalWrite(PIN_TRIG,HIGH); delayMicroseconds(10); digitalWrite(PIN_TRIG,LOW);
  unsigned long d=pulseIn(PIN_ECHO,HIGH,25000);
  if(!d) return -1;
  float cm=d*0.0343f/2.0f;
  return (cm>=2 && cm<=400)?cm:-1;
}

void updateUltrasonic() {
  float x=readDistance();
  if(x<0) { ultrasonicOK=false; return; }
  ultrasonicOK=true;
  filteredDistanceCM=(filteredDistanceCM<0)?x:(0.75f*filteredDistanceCM+0.25f*x);
  float span=BIN_EMPTY_DISTANCE_CM-BIN_FULL_DISTANCE_CM;
  if(span>0) binFillPercent=constrain((BIN_EMPTY_DISTANCE_CM-filteredDistanceCM)/span*100.0f,0.0f,100.0f);
}

void updateMQ() {
  mqRaw=analogRead(PIN_MQ);
  mqGPIOVoltage=analogReadMilliVolts(PIN_MQ)/1000.0f;
  mqSensorVoltage=mqGPIOVoltage*1.5f;
  if(!mqBaselineReady && millis()-startupTime>15000) { mqBaseline=mqRaw; mqBaselineReady=true; }
  if(mqBaselineReady) {
    mqAnomaly=fabs((float)mqRaw-mqBaseline)>300.0f;
    if(!mqAnomaly) mqBaseline=0.995f*mqBaseline+0.005f*mqRaw;
  }
}

void updateVibration() {
  if(digitalRead(PIN_VIBRATION)==HIGH) { vibrationActive=true; lastVibrationPulse=millis(); }
  if(vibrationActive && millis()-lastVibrationPulse>VIBRATION_HOLD_MS) vibrationActive=false;
}

void updatePanic() {
  int raw=digitalRead(PIN_PANIC);
  if(raw!=lastPanicRaw) { lastPanicRaw=raw; lastPanicChange=millis(); }
  if(millis()-lastPanicChange<PANIC_DEBOUNCE_MS || raw==stablePanicRaw) return;
  stablePanicRaw=raw;
  bool next=(stablePanicRaw==LOW);
  if(next==panicActive) return;
  panicActive=next;
  Serial.println(panicActive?"[PANIC] EMERGENCY":"[PANIC] NORMAL");
  if(mqtt.connected()) mqtt.publish(PANIC_TOPIC, panicActive?"EMERGENCY":"NORMAL", true);
}

String readUID() {
  String uid="";
  for(byte i=0;i<rfid.uid.size;i++) {
    if(rfid.uid.uidByte[i]<0x10) uid+="0";
    uid+=String(rfid.uid.uidByte[i],HEX);
    if(i<rfid.uid.size-1) uid+=":";
  }
  uid.toUpperCase(); return uid;
}

void checkRFID() {
  if(!rc522OK || !rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  lastRFID=readUID();
  Serial.printf("[RFID] %s\n",lastRFID.c_str());
  if(mqtt.connected()) mqtt.publish(RFID_TOPIC,lastRFID.c_str(),false);
  rfid.PICC_HaltA(); rfid.PCD_StopCrypto1();
}

void updateOLED() {
  if(!oledOK) return;
  display.clearDisplay(); display.setTextColor(SSD1306_WHITE); display.setCursor(0,0);
  if(panicActive) {
    display.setTextSize(2); display.println("EMERGENCY"); display.println(); display.println("PANIC!"); display.display(); return;
  }
  display.setTextSize(1);
  display.println("CAREGRID HOSPITAL"); display.println("---------------------");
  display.print("HR:"); if(vitalsValid) display.print(heartRate,0); else display.print("--");
  display.print(" SpO2:"); if(vitalsValid) display.print(spo2,0); else display.print("--"); display.println();
  display.print("Temp:"); display.print(temperatureC,1); display.print("C Lux:"); display.println(lux,0);
  display.print("PM2.5:"); if(pms5003OK) display.print(pm25); else display.print("--");
  display.print(" Bin:"); if(ultrasonicOK) { display.print(binFillPercent,0); display.println("%"); } else display.println("--");
  display.print("Bed: "); display.println(vibrationActive?"VIBRATION":"STABLE");
  display.print("RFID: "); display.println(lastRFID=="NONE"?"NONE":lastRFID.substring(0,11));
  display.display();
}

void maintainWiFi() {
  if(WiFi.status()==WL_CONNECTED || millis()-lastWiFiAttempt<10000) return;
  lastWiFiAttempt=millis(); WiFi.disconnect(); WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
}

bool connectMQTT() {
  if(WiFi.status()!=WL_CONNECTED) return false;
  char id[80]; snprintf(id,sizeof(id),"caregrid-%s-%04X",DEVICE_ID,(uint16_t)(ESP.getEfuseMac()&0xFFFF));
  bool ok=mqtt.connect(id,MQTT_USER,MQTT_PASSWORD,STATUS_TOPIC,1,true,"offline");
  if(ok) mqtt.publish(STATUS_TOPIC,"online",true);
  return ok;
}

void maintainMQTT() {
  if(mqtt.connected() || WiFi.status()!=WL_CONNECTED || millis()-lastMQTTAttempt<5000) return;
  lastMQTTAttempt=millis(); connectMQTT();
}

void publishTelemetry() {
  if(!mqtt.connected()) return;
  JsonDocument doc;
  doc["device_id"]=DEVICE_ID; doc["node_type"]=NODE_TYPE;
  JsonObject d=doc["data"].to<JsonObject>(); d["uptime_ms"]=millis();
  JsonObject v=d["vitals"].to<JsonObject>(); v["valid"]=vitalsValid; if(vitalsValid){v["heart_rate"]=heartRate; v["spo2"]=spo2;} else {v["heart_rate"]=nullptr; v["spo2"]=nullptr;}
  JsonObject e=d["environment"].to<JsonObject>(); if(bh1750OK)e["lux"]=lux;else e["lux"]=nullptr; if(bmp180OK){e["temperature_c"]=temperatureC;e["pressure_hpa"]=pressureHpa;}else{e["temperature_c"]=nullptr;e["pressure_hpa"]=nullptr;} if(pms5003OK){e["pm1"]=pm1;e["pm25"]=pm25;e["pm10"]=pm10;}else{e["pm1"]=nullptr;e["pm25"]=nullptr;e["pm10"]=nullptr;}
  JsonObject b=d["bin"].to<JsonObject>(); b["valid"]=ultrasonicOK; if(ultrasonicOK){b["distance_cm"]=filteredDistanceCM;b["fill_percent"]=binFillPercent;}else{b["distance_cm"]=nullptr;b["fill_percent"]=nullptr;} b["full"]=ultrasonicOK && binFillPercent>=85;
  JsonObject bed=d["bed"].to<JsonObject>(); bed["vibration"]=vibrationActive; bed["status"]=vibrationActive?"vibration":"stable";
  JsonObject em=d["emergency"].to<JsonObject>(); em["panic"]=panicActive; em["status"]=panicActive?"PANIC":"NORMAL";
  JsonObject air=d["air"].to<JsonObject>(); air["adc"]=mqRaw; air["gpio_voltage"]=mqGPIOVoltage; air["sensor_voltage"]=mqSensorVoltage; air["baseline_ready"]=mqBaselineReady; air["anomaly"]=mqAnomaly;
  JsonObject rf=d["rfid"].to<JsonObject>(); rf["last_uid"]=lastRFID;
  JsonObject h=d["health"].to<JsonObject>(); h["wifi"]=WiFi.status()==WL_CONNECTED; h["wifi_rssi"]=WiFi.status()==WL_CONNECTED?WiFi.RSSI():0; h["mqtt"]=mqtt.connected(); h["bh1750"]=bh1750OK; h["max30100"]=max30100OK; h["bmp180"]=bmp180OK; h["oled"]=oledOK; h["pms5003"]=pms5003OK; h["ultrasonic"]=ultrasonicOK; h["rc522"]=rc522OK; h["mq"]=true; h["vibration"]=true; h["panic_button"]=true;
  char payload[2048]; size_t n=serializeJson(doc,payload,sizeof(payload));
  mqtt.publish(TELEMETRY_TOPIC,reinterpret_cast<const uint8_t*>(payload),(unsigned int)n,false);
  serializeJsonPretty(doc,Serial); Serial.println();
}

void initializeSensors() {
  Wire.begin(PIN_SDA,PIN_SCL); Wire.setClock(100000);
  bh1750OK=lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  max30100OK=pox.begin(); if(max30100OK) pox.setIRLedCurrent(MAX30100_LED_CURR_27_1MA);
  bmp180OK=bmp.begin();
  oledOK=display.begin(SSD1306_SWITCHCAPVCC,OLED_ADDRESS);
  pmsSerial.begin(9600,SERIAL_8N1,PIN_PMS_RX,PIN_PMS_TX);
  pinMode(PIN_TRIG,OUTPUT); pinMode(PIN_ECHO,INPUT); digitalWrite(PIN_TRIG,LOW);
  pinMode(PIN_VIBRATION,INPUT); pinMode(PIN_PANIC,INPUT_PULLUP);
  lastPanicRaw=stablePanicRaw=digitalRead(PIN_PANIC); panicActive=(stablePanicRaw==LOW);
  analogReadResolution(12); analogSetPinAttenuation(PIN_MQ,ADC_11db);
  SPI.begin(PIN_RFID_SCK,PIN_RFID_MISO,PIN_RFID_MOSI,PIN_RFID_CS); rfid.PCD_Init(); delay(50);
  byte version=rfid.PCD_ReadRegister(MFRC522::VersionReg); rc522OK=(version!=0x00 && version!=0xFF);
}

void setup() {
  Serial.begin(115200); delay(1000); startupTime=millis();
  initializeSensors();
  mqtt.setServer(MQTT_HOST,MQTT_PORT); mqtt.setBufferSize(3072); mqtt.setKeepAlive(30);
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
}

void loop() {
  if(max30100OK) pox.update();
  processPMS5003(); updateVibration(); updatePanic(); checkRFID(); maintainWiFi(); maintainMQTT(); if(mqtt.connected()) mqtt.loop();
  unsigned long now=millis();
  if(now-lastEnvironmentRead>=1000) { lastEnvironmentRead=now; updateEnvironment(); updateMQ(); }
  if(now-lastVitalsRead>=1000) { lastVitalsRead=now; updateVitals(); }
  if(now-lastUltrasonicRead>=1500) { lastUltrasonicRead=now; updateUltrasonic(); }
  if(now-lastOLEDUpdate>=1000) { lastOLEDUpdate=now; updateOLED(); }
  if(now-lastMQTTPublish>=MQTT_INTERVAL) { lastMQTTPublish=now; publishTelemetry(); }
}
