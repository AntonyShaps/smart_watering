from influxdb_client import InfluxDBClient
import pandas as pd
from datetime import datetime, timezone, timedelta

# --- InfluxDB Config ---
token = "pBYVJ_atQUi-7eHpxFJXNJWOsP9NDwBdRCk8vyLVXykHvRi0qskGSl4AIo985J01BUub5U2ODewGDml0ha3W9A=="
url = "https://influxdb-ds24m010-mds2spz1-nigv2.apps.okd.cs.technikum-wien.at/"
org = "org0"
bucket = "db0"
csv_path = "influx_data_last_3_days.csv"

# --- Connect & Ping ---
client = InfluxDBClient(url=url, token=token, org=org)
if client.ping():
    print("Connected to InfluxDB")
else:
    print("Failed to connect")
    exit()

# --- Query for the latest _time value ---
latest_time_query = f'''
from(bucket: "{bucket}")
  |> range(start: -30d)
  |> sort(columns: ["_time"], desc: true)
  |> limit(n:1)
'''

try:
    tables = client.query_api().query(latest_time_query)

    # Extract latest _time
    latest_time = None
    for table in tables:
        for record in table.records:
            latest_time = record.get_time()
    
    if latest_time:
        print(f"Latest data timestamp in DB: {latest_time.isoformat()}")

        now = datetime.now(timezone.utc)
        age = now - latest_time

        if age > timedelta(days=2):
            print("Data is older than 2 days. Fetching newest data ..")

            # --- Query full data from last 3 days ---
            data_query = f'''
            from(bucket: "{bucket}")
              |> range(start: -1d)
            '''

            data_tables = client.query_api().query(data_query)
            records = []
            for table in data_tables:
                for row in table.records:
                    records.append(row.values)

            # Convert to DataFrame and save to CSV
            df = pd.DataFrame(records)
            df.to_csv(csv_path, index=False)
            print(f" Data newly written to: {csv_path}")
        else:
            print(" Data is recent. No need to update CSV.")
    else:
        print(" No data found in the bucket.")

except Exception as e:
    print(f" Error during query: {e}")