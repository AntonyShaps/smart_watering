import requests
import random
import time
from datetime import datetime

url = "http://localhost:8000/ingest"

def generate_fake_sensor_data():
    return {
        "sensor_id": "sensor_01",
        "timestamp": datetime.now().isoformat(),
        "humidity": round(random.uniform(30.0, 70.0), 1),
        "co2": random.randint(400, 800),
        "soil_moisture": random.randint(300, 800),
        "temperature": round(random.uniform(18.0, 30.0), 1),
        "pressure": round(random.uniform(990.0, 1030.0), 2)
    }

while True:
    data = generate_fake_sensor_data()

    try:
        response = requests.post(url, json=data)
        print(f"Sent: {data} | Status: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"❌ Failed to connect. Data: {data}")

    time.sleep(1)  # simulate every second (change to 60 for every minute)
