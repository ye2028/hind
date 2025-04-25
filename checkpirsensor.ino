const int pirPin = 19;

void setup()
{
    pinMode(pirPin, INPUT);
    Serial.begin(115200);
}

void loop()
{
    int motion = digitalRead(pirPin);
    if (motion == HIGH)
    {
        Serial.println("Motion detected");
    }
    else
    {
        Serial.println("No motion");
    }
    delay(1000);
}
