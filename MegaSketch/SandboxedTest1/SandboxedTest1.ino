/* * MFKB SD BRIDGE v1.1 (Isolated Test Version)
 * Handshake enabled for safe writing
 */

#include <SPI.h>
#include <SD.h>

const int chipSelect = 53;

void setup() {
  Serial.begin(115200);
  pinMode(53, OUTPUT);
  if (!SD.begin(chipSelect)) {
    // Initialized
  }
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "SD_LS") {
      listFiles();
    } 
    else if (cmd.startsWith("SD_READ:")) {
      String filename = cmd.substring(8);
      sendFile(filename);
    } 
    else if (cmd.startsWith("SD_WRITE:")) {
      String filename = cmd.substring(9);
      receiveFile(filename);
    }
    else if (cmd.startsWith("SD_DEL:")) {
      String filename = cmd.substring(7);
      if (SD.exists(filename)) {
        SD.remove(filename);
        Serial.println("DEL_OK");
      }
    }
  }
}

void listFiles() {
  File root = SD.open("/");
  while (true) {
    File entry = root.openNextFile();
    if (!entry) break;
    Serial.print("FILE:");
    Serial.print(entry.name());
    Serial.print("|");
    Serial.println(entry.size());
    entry.close();
  }
  Serial.println("SD_END");
  root.close();
}

void sendFile(String filename) {
  if (SD.exists(filename)) {
    File f = SD.open(filename);
    Serial.print("START_FILE:");
    Serial.println(filename);
    while (f.available()) {
      Serial.write(f.read());
    }
    Serial.println("\nEND_FILE");
    f.close();
  } else {
    Serial.println("ERR:NOT_FOUND");
  }
}

void receiveFile(String filename) {
  if (SD.exists(filename)) {
    SD.remove(filename);
  }
  
  File f = SD.open(filename, FILE_WRITE);
  if (!f) {
    Serial.println("ERR:CANT_WRITE");
    return;
  }

  Serial.println("READY_TO_RECEIVE");
  
  while (true) {
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      if (line == "SD_EOF") break;
      
      f.println(line);
      Serial.println("ACK"); // Send acknowledge back to Python
    }
  }
  f.close();
  Serial.println("WRITE_OK");
}