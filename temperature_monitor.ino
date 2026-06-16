// ============================================================
// Temperature Monitor - Arduino UNO
// Reads DHT11 sensor, displays on 16x2 I2C LCD, sends via Serial
// ============================================================

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// ----- DHT11 Configuration -----
#define DHTPIN 2          // DHT11 Signal (S) pin connected to Digital Pin 2
#define DHTTYPE DHT11

// ----- LCD Configuration -----
// IMPORTANT: Change 0x27 to the address you found in the I2C scanner
//            (common values: 0x27 or 0x3F)
#define LCD_ADDRESS 0x27
#define LCD_COLS 16
#define LCD_ROWS 2

// ----- Candidate Name -----
// Change this to your actual name
const char candidateName[] = "Your Full Name Here";

// ----- Object Initialization -----
LiquidCrystal_I2C lcd(LCD_ADDRESS, LCD_COLS, LCD_ROWS);
DHT dht(DHTPIN, DHTTYPE);

// ----- Scrolling Variables -----
int scrollPosition = 0;
unsigned long lastScrollTime = 0;
const unsigned long scrollDelay = 400;  // milliseconds between scroll steps

// ----- Temperature Reading Variables -----
unsigned long lastReadTime = 0;
const unsigned long readInterval = 2000;  // read temperature every 2 seconds
float currentTemp = 0.0;
bool firstReading = true;

void setup() {
  // Initialize Serial Communication (for sending data to PC)
  Serial.begin(9600);
  Serial.println("Temperature Monitor Starting...");

  // Initialize the DHT11 sensor
  dht.begin();

  // Initialize the LCD
  lcd.init();
  lcd.backlight();    // Turn on the backlight
  lcd.clear();

  // Show startup message
  lcd.setCursor(0, 0);
  lcd.print("Starting...");
  lcd.setCursor(0, 1);
  lcd.print("Please wait");
  delay(2000);
  lcd.clear();

  // Display the candidate name initially (first 16 chars)
  displayName();

  // Show placeholder temperature
  lcd.setCursor(0, 1);
  lcd.print("Temp: ---.- C");
}

void loop() {
  unsigned long currentTime = millis();

  // ----- Read Temperature Every 2 Seconds -----
  if (currentTime - lastReadTime >= readInterval || firstReading) {
    lastReadTime = currentTime;
    firstReading = false;

    float t = dht.readTemperature();  // Read temperature in Celsius

    if (!isnan(t)) {
      currentTemp = t;

      // Display temperature on the second row of the LCD
      lcd.setCursor(0, 1);
      lcd.print("Temp: ");
      lcd.print(currentTemp, 1);   // 1 decimal place
      lcd.print((char)223);        // Degree symbol
      lcd.print("C   ");           // Padding to clear old characters

      // Send temperature to PC via Serial
      Serial.print("TEMP:");
      Serial.println(currentTemp, 1);  // e.g., "TEMP:23.5"

    } else {
      // Sensor read failed
      lcd.setCursor(0, 1);
      lcd.print("Sensor Error!   ");
      Serial.println("ERROR:Failed to read DHT11");
    }
  }

  // ----- Scroll the Name if Longer than 16 Characters -----
  int nameLength = strlen(candidateName);

  if (nameLength > LCD_COLS) {
    if (currentTime - lastScrollTime >= scrollDelay) {
      lastScrollTime = currentTime;
      scrollName(nameLength);
    }
  }
}

// ============================================================
// Display the candidate name on the first row
// ============================================================
void displayName() {
  lcd.setCursor(0, 0);
  int nameLength = strlen(candidateName);

  if (nameLength <= LCD_COLS) {
    // Name fits on the screen - just print it
    lcd.print(candidateName);
  } else {
    // Name is too long - show first 16 characters initially
    for (int i = 0; i < LCD_COLS; i++) {
      lcd.print(candidateName[i]);
    }
  }
}

// ============================================================
// Scroll the candidate name horizontally on the first row
// Creates a smooth scrolling effect with wraparound
// ============================================================
void scrollName(int nameLength) {
  // Build the scrolling string with padding for smooth wraparound
  // Format: "name   name" so it loops seamlessly
  String paddedName = String(candidateName) + "   " + String(candidateName);

  lcd.setCursor(0, 0);

  // Display 16 characters starting from the current scroll position
  for (int i = 0; i < LCD_COLS; i++) {
    int charIndex = (scrollPosition + i) % paddedName.length();
    lcd.print(paddedName[charIndex]);
  }

  // Move to the next position
  scrollPosition++;

  // Reset when we've scrolled through the entire name + padding
  if (scrollPosition >= nameLength + 3) {  // 3 = length of the "   " padding
    scrollPosition = 0;
  }
}
