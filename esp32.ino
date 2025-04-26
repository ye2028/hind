#include <WiFi.h>
#include <HTTPClient.h>
#include <Keypad.h>
#include <WebServer.h>

const char *ssid = "pi";
const char *password = "pi12345678900";
const char *flask_host = "http://192.168.8.220:5000";
const char *start_scan_endpoint = "/simulate_motion";
const char *confirm_endpoint = "/confirm_delivery";

const int pirPin = 19;
const int relayPin = 18;
WebServer server(80);

// Keypad configuration
const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
    {'1', '2', '3', 'A'},
    {'4', '5', '6', 'B'},
    {'7', '8', '9', 'C'},
    {'*', '0', '#', 'D'}};
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {26, 25, 33, 32};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

bool motionSent = false;
unsigned long lastMotionTime = 0;
const unsigned long motionCooldown = 10000; // 10 seconds cooldown

void setup()
{
    Serial.begin(115200);
    pinMode(pirPin, INPUT);
    pinMode(relayPin, OUTPUT);
    digitalWrite(relayPin, HIGH); // الريلاي الخاص بقفل الباب سيكون مطفئ مبدئيا

    IPAddress local_IP(192, 168, 8, 111);
    IPAddress gateway(192, 168, 8, 1);
    IPAddress subnet(255, 255, 255, 0);

    WiFi.config(local_IP, gateway, subnet);
    WiFi.begin(ssid, password);

    Serial.print("-- Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\n--- Connected to WiFi");
    Serial.print("--- ESP32 IP address: ");
    Serial.println(WiFi.localIP());

    server.on("/open_box", HTTP_POST, []()
              {
        Serial.println("-- تم استلام طلب من فلاسك بفتح الصندوق");
        digitalWrite(relayPin, LOW);
        delay(2000);  // تفعيل الريلاي لمدة ثانيتين ثم يطفئ
        digitalWrite(relayPin, HIGH);
        server.send(200, "text/plain", "-- فتح الصندوق بنجاح"); });

    server.begin();
    Serial.println("--- Web server started on port 80");
}

void loop()
{
    server.handleClient(); // يجب استدعاؤه دائمًا

    // Detect motion with cooldown
    if (digitalRead(pirPin) == HIGH && !motionSent && millis() - lastMotionTime > motionCooldown)
    {
        Serial.println("-- Motion detected, sending to Flask...");
        sendScanSignal();
        motionSent = true;
        lastMotionTime = millis();
    }

    // Reset motionSent when motion ends
    if (digitalRead(pirPin) == LOW)
    {
        motionSent = false;
    }

    // Handle keypad input
    char key = keypad.getKey();
    if (key)
    {
        Serial.print("-- Key pressed: ");
        Serial.println(key);

        // Send each key press to Flask immediately
        sendKeyPressToFlask(key);
    }
}

void sendScanSignal()
{
    if (WiFi.status() == WL_CONNECTED)
    {
        HTTPClient http;
        String url = String(flask_host) + String(start_scan_endpoint);
        http.begin(url);
        http.addHeader("Content-Type", "application/json");

        int httpResponseCode = http.POST("{\"motion\": true}");

        if (httpResponseCode > 0)
        {
            Serial.print("-- Scan Response code: ");
            Serial.println(httpResponseCode);
        }
        else
        {
            Serial.print("- Error sending scan: ");
            Serial.println(httpResponseCode);
        }
        http.end();
    }
    else
    {
        Serial.println("- WiFi disconnected");
    }
}

void sendDeliveryCode(String code)
{
    if (WiFi.status() == WL_CONNECTED)
    {
        HTTPClient http;
        String url = String(flask_host) + String(confirm_endpoint);
        http.begin(url);
        http.addHeader("Content-Type", "application/json");

        String payload = "{\"code\":\"" + code + "\"}";

        int httpResponseCode = http.POST(payload);

        if (httpResponseCode > 0)
        {
            Serial.print("-- Confirm Response code: ");
            Serial.println(httpResponseCode);
        }
        else
        {
            Serial.print("- Error sending code: ");
            Serial.println(httpResponseCode);
        }
        http.end();
    }
    else
    {
        Serial.println("- WiFi disconnected");
    }
}

// Function to send individual key press to the Flask server
void sendKeyPressToFlask(char key)
{
    if (WiFi.status() == WL_CONNECTED)
    {
        HTTPClient http;
        String url = String(flask_host) + "/keypad_input"; // Assuming Flask route is /keypad_input
        http.begin(url);
        http.addHeader("Content-Type", "application/json");

        String payload = "{\"key\":\"" + String(key) + "\"}";

        int httpResponseCode = http.POST(payload);

        if (httpResponseCode > 0)
        {
            Serial.print("-- Key press sent to Flask: ");
            Serial.println(key);
        }
        else
        {
            Serial.print("- Error sending key press: ");
            Serial.println(httpResponseCode);
        }
        http.end();
    }
    else
    {
        Serial.println("- WiFi disconnected");
    }
}
