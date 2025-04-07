import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import datetime
import matplotlib.pyplot as plt

# ------------------------------
# Fetch weather data from Open-Meteo
# ------------------------------
def get_hourly_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 48.2085,
        "longitude": 16.3721,
        "hourly": ",".join([
            "temperature_2m",
            "soil_moisture_0_to_1cm",
            "soil_moisture_1_to_3cm",
            "soil_moisture_3_to_9cm",
            "soil_moisture_9_to_27cm",
            "rain",
            "showers",
            "precipitation"
        ]),
        "timezone": "Europe/Vienna"
    }
    response = requests.get(url, params=params)
    return response.json().get("hourly", {})

# ------------------------------
# Streamlit Tabs
# ------------------------------

tab1, tab2 = st.tabs(["📍 Vienna", "🌿 My Plants"])

# ------------------------------
# TAB 1: VIENNA
# ------------------------------
with tab1:
    st.title("🌱 Predictive Watering - Vienna")
    st.markdown("This app visualizes **soil moisture levels** and recommends **when to water** based on temperature + dryness.")

    # Use @st.cache_resource to avoid re-fetching if unchanged
    @st.cache_data(ttl=3600)
    def get_data():
        return get_hourly_weather()

    data = get_data()

    if data and "time" in data:
        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"])

        # Calculate soil moisture only once and drop unused columns early
        moisture_cols = [
            "soil_moisture_0_to_1cm",
            "soil_moisture_1_to_3cm",
            "soil_moisture_3_to_9cm"
        ]
        df["avg_soil_moisture"] = df[moisture_cols].mean(axis=1)
        df["needs_watering"] = (df["avg_soil_moisture"] < 0.25) & (df["temperature_2m"] > 25)

        # Downsample for charts if needed
        if len(df) > 100:
            df_chart = df.iloc[::3]  # Keep every 3rd row
        else:
            df_chart = df

        # Charts
        st.subheader("Temperature & Moisture Trends")
        st.line_chart(df_chart.set_index("time")[["temperature_2m", "avg_soil_moisture"]])

        st.subheader("Interactive Soil Moisture Heatmap")
        melt_df = df[["time"] + moisture_cols + ["soil_moisture_9_to_27cm"]].melt(
            id_vars="time", var_name="Depth", value_name="Moisture"
        )
        pivot_df = melt_df.pivot(index="Depth", columns="time", values="Moisture")

        fig = px.imshow(
            pivot_df,
            labels={"color": "Moisture (m³/m³)"},
            color_continuous_scale="YlGnBu"
        )
        fig.update_layout(
            height=500,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Watering alerts
        st.subheader("Watering Recommendations")
        alerts = df[df["needs_watering"]][["time", "temperature_2m", "avg_soil_moisture"]]
        if not alerts.empty:
            st.warning(f"⚠️ {len(alerts)} hours predicted where watering is needed!")
            st.dataframe(alerts.rename(columns={
                "time": "Time",
                "temperature_2m": "Temperature (°C)",
                "avg_soil_moisture": "Avg Soil Moisture (m³/m³)"
            }), use_container_width=True)
        else:
            st.success("Soil moisture is sufficient. No watering needed based on forecast.")
    else:
        st.error("Failed to retrieve weather data. Please try again later.")

    # Define & cache grid function
    @st.cache_data
    def generate_grid(center_lat, center_lon, spacing_km=5, size=5):
        offset = spacing_km / 111  # degrees/km approximation
        half = size // 2
        return [(center_lat + i * offset, center_lon + j * offset)
                for i in range(-half, half + 1) for j in range(-half, half + 1)]

    @st.cache_data
    def fetch_soil_moisture(lat, lon):
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "soil_moisture_0_to_1cm",
                "timezone": "Europe/Vienna"
            }
            response = requests.get(url, params=params, timeout=3)
            data = response.json()
            return data["hourly"]["soil_moisture_0_to_1cm"][0]
        except:
            return None

    st.title("Soil Moisture Map")
    st.markdown("Shows top-layer soil moisture (0–1 cm) across a regional grid with watering alerts.")

    map_threshold = st.slider("Trigger watering if moisture is below (m³/m³)", 0.05, 0.35, 0.15, 0.01)
    grid_size = st.slider("Grid Size (NxN)", min_value=3, max_value=21, value=11, step=2)
    grid_spacing = st.slider("Point Spacing (km)", 1.0, 10.0, 2.5)

    grid = generate_grid(48.2085, 16.3721, spacing_km=grid_spacing, size=grid_size)

    # Reduce calls to external API by limiting grid size or concurrency
    @st.cache_data(ttl=1800)
    def fetch_all(grid):
        results = []
        for lat, lon in grid:
            moisture = fetch_soil_moisture(lat, lon)
            if moisture is not None:
                results.append({"lat": lat, "lon": lon, "moisture": moisture})
        return results

    with st.spinner("Fetching soil moisture data for grid..."):
        results = fetch_all(grid)

    df = pd.DataFrame(results)
    if not df.empty:
        df["needs_watering"] = df["moisture"] < map_threshold
        dry_points = df[df["needs_watering"]]

        fig = px.density_mapbox(
            df,
            lat="lat", lon="lon", z="moisture",
            radius=30,
            center={"lat": 48.2085, "lon": 16.3721},
            zoom=9,
            mapbox_style="carto-positron",
            color_continuous_scale="YlGnBu"
        )

        if not dry_points.empty:
            fig.add_scattermapbox(
                lat=dry_points["lat"],
                lon=dry_points["lon"],
                mode="markers",
                marker=dict(size=10, color="red", symbol="circle"),
                name="Needs Watering",
                hovertext=[f"Moisture: {m:.3f}" for m in dry_points["moisture"]],
                hoverinfo="text"
            )

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📍 Areas Needing Water")
        if not dry_points.empty:
            st.dataframe(
                dry_points[["lat", "lon", "moisture"]].sort_values("moisture").reset_index(drop=True),
                use_container_width=True
            )
        else:
            st.success("All zones are above the moisture threshold. No watering needed.")
    else:
        st.error("Failed to fetch any soil moisture data.")

# ------------------------------
# TAB 2: MY PLANTS (Empty)
# ------------------------------

SENSOR_ENDPOINTS = {
    "co2": "http://104.248.47.104:8000/co2",
    "humidity": "http://104.248.47.104:8000/humidity",
    "soil_moisture": "http://104.248.47.104:8000/soil_moisture",
    "temperature": "http://104.248.47.104:8000/temperature"
}

@st.cache_data(ttl=200)
def fetch_sensor_df(limit=50):
    dfs = []

    for key, url in SENSOR_ENDPOINTS.items():
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            data = r.json()

            df = pd.DataFrame(data)
            df = df[["timestamp", key]]  # only keep timestamp + this variable
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            dfs.append(df)

        except Exception as e:
            st.warning(f"⚠️ Failed to fetch {key} from {url}: {e}")

    if not dfs:
        return pd.DataFrame()  # nothing fetched

    # ✅ Merge all dataframes on timestamp
    from functools import reduce
    df_final = reduce(lambda left, right: pd.merge(left, right, on="timestamp", how="outer"), dfs)
    #return df_final.sort_values("timestamp")
    return df_final.sort_values("timestamp").tail(300)  # show last 300 readings


with tab2:
    st.title("🌿 My Plants")
    st.markdown("This section is currently empty. Add your plant monitoring tools here later.")

    df = fetch_sensor_df()

    if df.empty:
        st.info("Waiting for sensor data from endpoints...")
    else:
        df = df.set_index("timestamp")
        available_cols = [col for col in ["co2", "humidity", "soil_moisture", "temperature"] if col in df.columns]

        if available_cols:
            # Drop outliers above 5000 ppm
            if "co2" in df.columns:
                df = df[df["co2"] < 5000]
            st.line_chart(df[available_cols])
        else:
            st.warning("No valid sensor readings found.")

    # Show most recent values
    latest = df.sort_index(ascending=False).iloc[0]
    st.markdown(f"**Last Reading — {latest.name}**")
    st.markdown(f"Temperature: {latest['temperature']} °C")
    st.markdown(f"Moisture: {latest['soil_moisture']} %")
    st.markdown(f"Humidity: {latest['humidity']} %")
    st.markdown(f"CO₂: {latest['co2']} ppm")

  # Add Plant Button
    with st.expander("➕ Add a Plant", expanded=False):
        plant_name = st.text_input("Plant Name")
        pot_size = st.selectbox("Pot Size", ["Small", "Medium", "Large"])
        orientation = st.selectbox("Facing Direction", ["North", "East", "South", "West"])
        plant_type = st.selectbox("Plant Environment", ["Indoor", "Outdoor", "Desert", "Tropical"])
        robustness = st.slider("Plant Robustness (1-10)", 1, 10)
        time_of_day = st.selectbox("Time of Day", ["Morning", "Afternoon", "Evening", "Night"])
        last_watered = st.date_input("Last Watered", datetime.date.today())

        # ✅ Get current sensor moisture reading (if available)
        if not df.empty and "soil_moisture" in df.columns:
            current_moisture = df.sort_index(ascending=False)["soil_moisture"].iloc[0]
        else:
            current_moisture = st.slider("Current Soil Moisture (%)", 0, 100)

        if st.button("🌱 Submit Plant"):
            st.success(f"{plant_name} added successfully!")

            # ✅ Fetch Open-Meteo forecast for next 12 hours
            forecast = get_hourly_weather()
            future_df = pd.DataFrame(forecast)
            future_df["time"] = pd.to_datetime(future_df["time"])
            forecast_12h = future_df.head(12)

            avg_forecast_temp = forecast_12h["temperature_2m"].mean()
            avg_forecast_moisture = forecast_12h[[
                "soil_moisture_0_to_1cm",
                "soil_moisture_1_to_3cm",
                "soil_moisture_3_to_9cm"
            ]].mean(axis=1).mean()

            # Smarter logic combining current + forecast
            # Improved watering + plant safety logic
            if current_moisture < 30:
                if avg_forecast_temp < 5:
                    water_advice = "Soil is very dry and it's very cold. Water lightly and move plant indoors if possible."
                elif avg_forecast_temp < 10:
                    water_advice = "Soil is dry, and it's cold. Water lightly and monitor closely."
                elif avg_forecast_moisture < 0.25 and avg_forecast_temp > 22:
                    water_advice = "Definitely water – soil is dry and forecast is hot and dry."
                else:
                    water_advice = "Soil is dry – consider watering soon."

            elif current_moisture > 70:
                water_advice = "Do not water – soil is already saturated."

            elif avg_forecast_moisture < 0.2 and avg_forecast_temp > 25:
                water_advice = "Monitor closely – forecast shows hot and dry conditions."

            elif 30 <= current_moisture <= 40:
                water_advice = "Moisture is slightly low – you may want to water lightly."

            else:
                water_advice = "Moisture levels are fine. No watering needed."

            if avg_forecast_temp < 5:
                location_advice = "It's very cold outside. Move the plant indoors if it's sensitive to frost."
            else:
                location_advice = "Outdoor conditions are acceptable."

            # 🌿 Show Recommendation
            st.markdown("### 🌿 Smart Recommendation")
            st.markdown(f"**Soil Moisture Now:** {current_moisture:.1f}%")
            st.markdown(f"**Avg Forecast Temp (12h):** {avg_forecast_temp:.1f}°C")
            st.markdown(f"**Forecast Soil Moisture:** {avg_forecast_moisture:.2f} m³/m³")
            st.markdown(f"**Watering Advice:** {water_advice}")
            st.markdown(f"**Location Advice:** {location_advice}")