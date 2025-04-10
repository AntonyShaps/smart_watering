from datetime import datetime
import time
import board
import adafruit_ccs811
import requests
import csv
import os
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_bme280 import basic as adafruit_bme280

# API Endpoint Configuration
API_ENDPOINT = "http://104.248.47.104:8000/ingest"

# Local CSV File for Offline Data
CSV_FILE = "offline_data.csv"


# Init I2C Bus
i2c = board.I2C()

# Init Sensors
ccs811 = adafruit_ccs811.CCS811(i2c)
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
ads = ADS.ADS1115(i2c)


# Function to Read Analog Sensor (ADC)
def get_analog_input(channel=0):
    try:
        analog = AnalogIn(ads, getattr(ADS, f"P{channel}"))
        voltage = round(analog.voltage, 3)
        print(voltage)
        # Clamp voltage between 1 and 5 to avoid weird values
        voltage = max(1.0, min(voltage, 4.0))
        
        # Map voltage to moisture percentage: 1V => 100%, 4V => 0%
        moisture_percent = int(round((4.0 - voltage) / 3.0 * 100))
        
        return moisture_percent
    except Exception as e:
        print(f"Error reading ADC: {e}")
        return 0

# Temperature
def get_temp(sensor=bme280):
    try:
        return round(sensor.temperature, 2)
    except Exception as e:
        print(f"Error reading SHT31D: {e}")
        return 0.0

# Humidity
def get_hum(sensor=bme280):
    try:
        return round(sensor.humidity, 2)
    except Exception as e:
        print(f"Error reading SHT31D: {e}")
        return 0.0

# CO2 Level
def get_co2(sensor=ccs811, sensor2=bme280):
    try:
        ccs811.set_environmental_data(int(sensor2.humidity), sensor2.temperature)
        return sensor.eco2
    except Exception as e:
        print(f"Error reading CSS811: {e}")
        return 0


# Generate Sensor Data Message
def generate_sensor_data_msg():
    return {
        "plant_id": "plant_01",
        "timestamp": datetime.now().isoformat(),
        "humidity": float(get_hum()),
        "co2": int(get_co2()),
        "soil_moisture": int(get_analog_input(0)), 
        "temperature": float(get_temp())
    }

# Save data to CSV if API is down
def save_to_csv(data):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()  # Write header if file is new
        writer.writerow(data)
    print(f"Data saved to CSV (offline mode): {data}")

# Send all stored data from CSV to API when connection is back
def send_offline_data():
    if not os.path.isfile(CSV_FILE):
        return  # No offline data

    try:
        with open(CSV_FILE, mode="r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                response = requests.post(API_ENDPOINT, json=row)
                if response.status_code == 200:
                    print(f"Sent offline record to API: {row}")
                else:
                    print(f"Failed to send offline record: {response.status_code}")
                    return

        # Clear the CSV after successful upload
        os.remove(CSV_FILE)
        print("Offline CSV data cleared.")
    except Exception as e:
        print(f"Error sending offline data: {e}")

# Ensure CCS811 Sensor is Ready
while not ccs811.data_ready:
    pass

# Main Loop: Send Data
while True:
    data = generate_sensor_data_msg()
    #print(data)
    
    # Try sending to API
    try:
        response = requests.post(API_ENDPOINT, json=data)
        if response.status_code == 200:
            print(f"Data sent to API: {data}")
            send_offline_data()
        else:
            print(f"API error {response.status_code}, saving locally.")
            save_to_csv(data)
 
    except Exception as e:
        print(f"API error, saving locally: {e}")
        save_to_csv(data)
    
    time.sleep(10)  # Wait before sending next data
    os.system("clear")
