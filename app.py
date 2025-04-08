import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import datetime
import matplotlib.pyplot as plt
import plotly.graph_objects as go

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

@st.cache_data(ttl=400)
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
    st.markdown("This section for live plant monitoring tools")

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

    if "plant_list" not in st.session_state:
        st.session_state.plant_list = []

    # Show most recent values
    latest = df.sort_index(ascending=False).iloc[0]
    st.markdown(f"**Last Reading — {latest.name}**")
    st.markdown(f"Temperature: {latest['temperature']} °C")
    st.markdown(f"Moisture: {latest['soil_moisture']} %")
    st.markdown(f"Humidity: {latest['humidity']} %")
    st.markdown(f"CO₂: {latest['co2']} ppm")

    with st.sidebar.expander("Live Sensor Gauges", expanded=True):
        if not df.empty:
            latest = df.sort_index(ascending=False).iloc[0]
            for label, value, unit, range_vals, steps, color in [
                ("Humidity (%)", latest["humidity"], "%", [0, 100], [
                    {"range": [0, 30], "color": "lightcoral"},
                    {"range": [30, 60], "color": "lightgreen"},
                    {"range": [60, 100], "color": "khaki"}], "dodgerblue"),
                ("Temperature (°C)", latest["temperature"], "°C", [-5, 40], [
                    {"range": [-5, 5], "color": "#b0e0e6"},
                    {"range": [5, 25], "color": "#90ee90"},
                    {"range": [25, 40], "color": "#ffcccb"}], "orangered"),
                ("CO₂ (ppm)", latest["co2"], "ppm", [0, 5000], [
                    {"range": [0, 800], "color": "lightgreen"},
                    {"range": [800, 1200], "color": "gold"},
                    {"range": [1200, 5000], "color": "lightcoral"}], "darkred"),
                ("Soil Moisture (%)", latest["soil_moisture"], "%", [0, 100], [
                    {"range": [0, 20], "color": "lightcoral"},
                    {"range": [20, 60], "color": "lightgreen"},
                    {"range": [60, 100], "color": "khaki"}], "seagreen")
            ]:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=value,
                    title={"text": label},
                    gauge={
                        "axis": {"range": range_vals},
                        "bar": {"color": color},
                        "steps": steps
                    }
                ))
                st.plotly_chart(fig, use_container_width=True)
    
    with st.sidebar.expander("My Plants", expanded=False):
        if st.session_state.plant_list:
            for i, plant in enumerate(st.session_state.plant_list):
                st.markdown(f"**{plant['name']}**")
                st.markdown(f"- Type: {plant['plant_type']} ({plant['pot_size']})")
                st.markdown(f"- Facing: {plant['orientation']}")
                st.markdown(f"- Last Watered: {plant['last_watered']}")
                st.markdown(f"- Days Since Watered: {plant['days_since_watered']} days")
                st.markdown(f"- Soil Moisture: {plant['current_moisture']}%")
                st.markdown(f"- Prognosed Moisture: {plant['prognosed_moisture']}%")
                #st.markdown(f"- Predicted Next Watering: {plant['predicted_next_watering']}")
                st.markdown(f"- Watering Plan: {plant.get('watering_plan', 'Plan will update shortly based on forecast and sensor data.')}")
                #st.markdown(f"- Advice: {plant['water_advice']}")
                st.markdown("---")
        else:
            st.info("No plants added yet.")

    # Predictive Watering Plan Generator
    forecast = get_hourly_weather()
    if forecast and "time" in forecast:
        future_df = pd.DataFrame(forecast)
        future_df["time"] = pd.to_datetime(future_df["time"])
        forecast_3d = future_df.head(72)  # 3 days hourly = 72 rows

        avg_temp_3d = forecast_3d["temperature_2m"].mean()
        avg_humidity_3d = df["humidity"].mean() if "humidity" in df.columns else 50
        avg_soil_moisture = df["soil_moisture"].mean() if "soil_moisture" in df.columns else 30
        rain_total = forecast_3d["rain"].sum() if "rain" in forecast_3d.columns else 0
        forecast_days = 3

        # Define dynamic moisture targets based on plant types
        type_targets = {
            "Indoor": 55,
            "Outdoor": 60,
            "Desert": 35,
            "Tropical": 70
        }

        orientation_modifier = {
            "North": 0.9,
            "East": 1.0,
            "West": 1.1,
            "South": 1.2
        }

        for plant in st.session_state.plant_list:
            target = type_targets.get(plant["plant_type"], 60)
            current = plant.get("current_moisture", avg_soil_moisture)
            robustness = plant.get("robustness", 5)
            buffer = (10 - robustness) * 0.5

            # Estimate moisture growth from forecasted rain and future soil moisture
            future_soil_avg = forecast_3d[[
                "soil_moisture_0_to_1cm",
                "soil_moisture_1_to_3cm",
                "soil_moisture_3_to_9cm"]].mean(axis=1).mean()

            gain_per_day = (future_soil_avg * 100 - current) / forecast_days
            gain_per_day *= orientation_modifier.get(plant["orientation"], 1.0)
            rain_gain = rain_total * 0.5  # heuristically 0.5% per mm rain
            #projected_moisture = max(0, min(100, current + gain_per_day * 5 + (rain_gain if rain_total > 0 else 0)))
            projected_moisture = current + gain_per_day * 5 + (rain_gain if rain_total > 0 else 0)

           # if current < target - (15 + buffer):
              #  freq = "2x over the next 5 days"
             #   reason = "significantly below optimal moisture"
           # elif current < target - (5 + buffer):
            #    freq = "1x in the next 4 days"
            #    reason = "slightly below optimal moisture"
           # elif current > target + (5 - buffer):
           #     freq = "no watering needed — moisture is above ideal"
           #     reason = "moisture exceeds tolerance"
           # else:
            #    freq = "1x next week"
            #    reason = "within acceptable range"

            if projected_moisture >= target - buffer:
                freq = "no watering needed"
                reason = "forecasted rain and soil moisture will meet plant needs"
            elif current < target - (15 + buffer):
                freq = "2x over the next 5 days"
                reason = "significantly below optimal moisture"
            elif current < target - (5 + buffer):
                freq = "1x in the next 4 days"
                reason = "slightly below optimal moisture"
            else:
                freq = "1x next week"
                reason = "within acceptable range"

            plan = f"Next 3-day avg temp: {avg_temp_3d:.1f}°C, humidity: {avg_humidity_3d:.1f}%. " \
                   f"Current soil moisture for {plant['name']} is {current:.1f}%. " \
                   f"Target for {plant['plant_type']} plants is ~{target}%. " \
                   f"Projected in 5 days: {projected_moisture:.1f}%. " \
                   f"Suggest watering {freq} ({reason})."

            #plan = f"Next 3-day avg temp: {avg_temp_3d:.1f}°C, humidity: {avg_humidity_3d:.1f}%. " \
             #      f"Current soil moisture for {plant['name']} is {current:.1f}%. " \
              #     f"Target for {plant['plant_type']} plants is ~{target}%. " \
               #    f"Suggest watering {freq} ({reason})."

            plant["watering_plan"] = plan

        st.markdown("### Predictive Watering Forecast")
        st.info("Personalized watering plans updated for each plant based on latest sensor data and forecast.")
     
  # Add Plant Button
    with st.expander("Add a Plant", expanded=False):
        plant_name = st.text_input("Plant Name")
        pot_size = st.selectbox("Pot Size", ["Small (500ml)", "Medium (1L)", "Large (2L)"])
        orientation = st.selectbox("Facing Direction", ["North", "East", "South", "West"])
        plant_type = st.selectbox("Plant Environment", ["Indoor", "Outdoor", "Desert", "Tropical"])
        default_robustness = {"Indoor": 5, "Outdoor": 6, "Desert": 9, "Tropical": 3}
        robustness = st.slider("Plant Robustness (1-10)", 1, 10, value=default_robustness[plant_type])
        time_of_day = st.selectbox("Time of Day", ["Morning", "Afternoon", "Evening", "Night"])
        last_watered = st.date_input("Last Watered", datetime.date.today())
        days_since_watered = (datetime.date.today() - last_watered).days

        # Suggest species examples
        suggestions = {
            "Indoor": ["Peace Lily", "Spider Plant", "ZZ Plant"],
            "Outdoor": ["Lavender", "Basil", "Geranium"],
            "Desert": ["Aloe Vera", "Cactus", "Echeveria"],
            "Tropical": ["Bird of Paradise", "Calathea", "Philodendron"]
        }
        st.markdown(f"**Suggested Species:** {', '.join(suggestions[plant_type])}")

        # Determine light exposure based on orientation
        sun_exposure = {
            "North": "Low light",
            "East": "Morning light",
            "South": "Full sun",
            "West": "Afternoon sun"
        }[orientation]

        # Get current sensor moisture reading
        if not df.empty and "soil_moisture" in df.columns:
            current_moisture = df.sort_index(ascending=False)["soil_moisture"].iloc[0]
        else:
            current_moisture = st.slider("Current Soil Moisture (%)", 0, 100)

         # Determine watering volume by pot size
        volume_ml = {
                "Small (500ml)": 100,
                "Medium (1L)": 200,
                "Large (2L)": 400
        }[pot_size]
        prognosed_moisture = min(current_moisture + volume_ml * 0.05, 100)

        if st.button("Submit Plant"):
            st.success(f"{plant_name} added successfully!")
            
            plant_entry = {
                "name": plant_name,
                "pot_size": pot_size,
                "orientation": orientation,
                "plant_type": plant_type,
                "robustness": robustness,
                "time_of_day": time_of_day,
                "last_watered": str(last_watered),
                "species_suggestion": suggestions[plant_type],
                "sun_exposure": sun_exposure,
                "current_moisture": current_moisture,
                "added_at": datetime.datetime.now().isoformat(),
                "days_since_watered": days_since_watered,
                "prognosed_moisture": round(prognosed_moisture, 1),
                #"water_advice": water_advice

            }
            st.session_state.plant_list.append(plant_entry)

            # Forecast
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

            # Predictive watering logic
            # Estimate decay rate based on temp & humidity
            decay_factor = (avg_forecast_temp / 30) * (1 - latest["humidity"] / 100)
            daily_loss = decay_factor * 5  # moisture % lost per day
            days_until_dry = max(0, (current_moisture - 30) / daily_loss) if daily_loss > 0 else 0

            # Round up prediction
            predicted_next_watering = datetime.date.today() + datetime.timedelta(days=int(days_until_dry))

            plant_entry["predicted_next_watering"] = str(predicted_next_watering)
            plant_entry["watering_plan"] = "Plan will update shortly based on forecast and sensor data."

            if not any(p["name"] == plant_name and p["last_watered"] == str(last_watered) for p in st.session_state.plant_list):
                st.session_state.plant_list.append(plant_entry)

            # Determine watering volume by pot size
            # volume_ml = {
            #    "Small (500ml)": 100,
             #   "Medium (1L)": 200,
            #    "Large (2L)": 400
            #}[pot_size]

            # Smart logic
            if current_moisture < 30:
                if days_since_watered < 1:
                    water_advice = "Soil appears dry but was just watered. Monitor before watering again."
                if avg_forecast_temp < 5:
                    water_advice = f"Soil is very dry and cold. Water lightly (~{int(volume_ml/2)}ml) and bring indoors."
                elif avg_forecast_temp < 10:
                    water_advice = f"Soil is dry and chilly. Light watering (~{int(volume_ml/2)}ml) advised."
                elif avg_forecast_moisture < 0.25 and avg_forecast_temp > 22:
                    water_advice = f"Very dry weather coming. Water fully (~{volume_ml}ml)."
                else:
                    water_advice = f"Soil is dry – consider watering (~{int(volume_ml*0.75)}ml)."
            elif current_moisture > 70:
                water_advice = "Soil is saturated. Do not water."
            elif avg_forecast_moisture < 0.2 and avg_forecast_temp > 25:
                water_advice = "Forecast is hot and dry. Watch closely, light watering may help."
            elif 30 <= current_moisture <= 40:
                water_advice = f"Slightly dry – optional light watering (~{int(volume_ml/3)}ml)."
            else:
                water_advice = "Moisture levels are fine. No watering needed."

            if avg_forecast_temp < 5:
                location_advice = "It's very cold. Consider keeping the plant inside."
            else:
                location_advice = f"{sun_exposure} conditions expected. Monitor based on plant type."

            # Display recommendation
            st.markdown("### Smart Recommendation")
            st.markdown(f"**Soil Moisture Now:** {current_moisture:.1f}%")
            st.markdown(f"**Avg Forecast Temp (12h):** {avg_forecast_temp:.1f}°C")
            st.markdown(f"**Forecast Soil Moisture:** {avg_forecast_moisture:.2f} m³/m³")
            st.markdown(f"**Watering Advice:** {water_advice}")
            st.markdown(f"**Location Advice:** {location_advice}")
            # Show watering plan under the Smart Recommendation
            st.markdown("### Watering Plan")
            st.markdown(plant_entry["watering_plan"])

