from fastapi import FastAPI, Request
from datetime import datetime, timedelta
import psycopg2

app = FastAPI()

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname="sensors_data",
    user="root",
    password="root",
    host="pgdatabase",
    port="5432"
)
cursor = conn.cursor()

# 🔧 Create table if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id SERIAL PRIMARY KEY,
        plant_id TEXT,
        timestamp TIMESTAMP,
        humidity REAL,
        co2 INTEGER,
        soil_moisture INTEGER,
        temperature REAL
    );
""")
conn.commit()

@app.post("/ingest")
async def ingest_data(request: Request):
    data = await request.json()

    plant_id = data.get("plant_id")
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())
    humidity = data.get("humidity")
    co2 = data.get("co2")
    soil_moisture = data.get("soil_moisture")
    temperature = data.get("temperature")

    cursor.execute("""
        INSERT INTO sensor_data (
            plant_id, timestamp, humidity, co2, soil_moisture, temperature
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        plant_id, timestamp, humidity, co2, soil_moisture, temperature
    ))
    conn.commit()

    print(f"[{datetime.utcnow()}] Inserted: {data}")
    return {"status": "ok"}

# 📊 Helper function
def fetch_last_7_days(field: str):
    query = f"""
        SELECT timestamp, {field} FROM sensor_data
        WHERE timestamp >= NOW() - INTERVAL '7 days'
        ORDER BY timestamp ASC;
    """
    cursor.execute(query)
    return [{"timestamp": row[0], field: row[1]} for row in cursor.fetchall()]

# 📈 Endpoints for each variable
@app.get("/humidity")
def get_humidity():
    return fetch_last_7_days("humidity")

@app.get("/co2")
def get_co2():
    return fetch_last_7_days("co2")

@app.get("/soil_moisture")
def get_soil_moisture():
    return fetch_last_7_days("soil_moisture")

@app.get("/temperature")
def get_temperature():
    return fetch_last_7_days("temperature")
