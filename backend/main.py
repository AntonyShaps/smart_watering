from fastapi import FastAPI, Request
from datetime import datetime
import psycopg2

app = FastAPI()

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname="sensors_data",
    user="root",
    password="root",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# 🔧 Create table if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id SERIAL PRIMARY KEY,
        sensor_id TEXT,
        timestamp TIMESTAMP,
        humidity REAL,
        co2 INTEGER,
        soil_moisture INTEGER,
        temperature REAL,
        pressure REAL
    );
""")
conn.commit()

@app.post("/ingest")
async def ingest_data(request: Request):
    data = await request.json()

    sensor_id = data.get("sensor_id")
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())
    humidity = data.get("humidity")
    co2 = data.get("co2")
    soil_moisture = data.get("soil_moisture")
    temperature = data.get("temperature")
    pressure = data.get("pressure")

    cursor.execute("""
        INSERT INTO sensor_data (
            sensor_id, timestamp, humidity, co2, soil_moisture, temperature, pressure
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        sensor_id, timestamp, humidity, co2, soil_moisture, temperature, pressure
    ))
    conn.commit()

    print(f"[{datetime.utcnow()}] Inserted: {data}")
    return {"status": "ok"}
