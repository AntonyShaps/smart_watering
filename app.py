import streamlit as st
import requests
import pandas as pd
import plotly.express as px

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

    data = get_hourly_weather()

    if data and "time" in data:
        df = pd.DataFrame(data)
        df["time"] = pd.to_datetime(df["time"])

        # Compute average top-layer soil moisture
        df["avg_soil_moisture"] = df[[
            "soil_moisture_0_to_1cm",
            "soil_moisture_1_to_3cm",
            "soil_moisture_3_to_9cm"
        ]].mean(axis=1)

        # Define watering condition: dry soil + hot weather
        dry_threshold = 0.25  # m³/m³
        hot_threshold = 25  # °C
        df["needs_watering"] = (df["avg_soil_moisture"] < dry_threshold) & (df["temperature_2m"] > hot_threshold)

        # ------------------------------
        #  Temperature & Moisture Line Chart
        # ------------------------------
        st.subheader(" Temperature & Moisture Trends")
        st.line_chart(df.set_index("time")[["temperature_2m", "avg_soil_moisture"]])
        st.markdown("temperature 2m = lowest temperature of air at 2m above the surface of land")

        # ------------------------------
        # Interactive Soil Moisture Heatmap
        # ------------------------------
        st.subheader(" Interactive Soil Moisture Heatmap")

        melt_df = df[["time", "soil_moisture_0_to_1cm", "soil_moisture_1_to_3cm", 
                    "soil_moisture_3_to_9cm", "soil_moisture_9_to_27cm"]].melt(
            id_vars="time", var_name="Depth", value_name="Moisture"
        )

        pivot_df = melt_df.pivot(index="Depth", columns="time", values="Moisture")

        fig = px.imshow(
            pivot_df,
            labels=dict(color="Moisture (m³/m³)"),
            color_continuous_scale="YlGnBu",
            aspect="auto"
        )
        fig.update_layout(
            title="Soil Moisture by Depth & Time",
            xaxis_title="Time",
            yaxis_title="Soil Depth",
            xaxis_tickangle=45,
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

        # ------------------------------
        # 🚨 Watering Alerts
        # ------------------------------
        st.subheader(" Watering Recommendations")

        alerts = df[df["needs_watering"]][["time", "temperature_2m", "avg_soil_moisture"]]

        if not alerts.empty:
            st.warning(f"⚠️ {len(alerts)} hours predicted where watering is needed!")
            st.dataframe(alerts.rename(columns={
                "time": "Time",
                "temperature_2m": "Temperature (°C)",
                "avg_soil_moisture": "Avg Soil Moisture (m³/m³)"
            }))
        else:
            st.success(" Soil moisture is sufficient. No watering needed based on forecast.")

    else:
        st.error("Failed to retrieve weather data. Please try again later.")

    # Define grid of lat/lon points (around Vienna)
    def generate_grid(center_lat, center_lon, spacing_km=5, size=5):
        offset = 0.045  # ~5km in degrees
        half = size // 2
        grid = []
        for i in range(-half, half+1):
            for j in range(-half, half+1):
                lat = center_lat + i * offset
                lon = center_lon + j * offset
                grid.append((lat, lon))
        return grid

    # Fetch soil moisture for a single lat/lon
    def fetch_soil_moisture(lat, lon):
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "soil_moisture_0_to_1cm",
            "timezone": "Europe/Vienna"
        }
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            moisture = data["hourly"]["soil_moisture_0_to_1cm"][0]
            return moisture
        except:
            return None

    # ------------------------------
    # 🌍 Soil Moisture Map with Alert Threshold
    # ------------------------------
    st.title("Soil Moisture Map")

    st.markdown("Shows top-layer soil moisture (0–1 cm) across a regional grid with watering alerts.")

    # Moisture threshold slider
    map_threshold = st.slider("Trigger watering if moisture is below (m³/m³)", 0.05, 0.35, 0.15, 0.01)

    # Grid controls
    grid_size = st.slider("Grid Size (NxN)", min_value=3, max_value=21, value=11, step=2)
    grid_spacing = st.slider("Point Spacing (km)", min_value=1.0, max_value=10.0, value=2.5)

    grid = generate_grid(48.2085, 16.3721, spacing_km=grid_spacing, size=grid_size)

    # Fetch data
    results = []
    with st.spinner("Fetching soil moisture data for grid..."):
        for lat, lon in grid:
            moisture = fetch_soil_moisture(lat, lon)
            if moisture is not None:
                results.append({
                    "lat": lat,
                    "lon": lon,
                    "moisture": moisture
                })

    df = pd.DataFrame(results)

    if not df.empty:
        # Flag dry zones
        df["needs_watering"] = df["moisture"] < map_threshold
        dry_points = df[df["needs_watering"]]

        # Main density heatmap
        fig = px.density_mapbox(
            df,
            lat="lat",
            lon="lon",
            z="moisture",
            radius=30,
            center={"lat": 48.2085, "lon": 16.3721},
            zoom=9,
            mapbox_style="carto-positron",
            color_continuous_scale="YlGnBu",
            title="Soil Moisture Heatmap (0–1 cm)"
        )

        # Red dot overlay for dry zones
        if not dry_points.empty:
            fig.add_scattermapbox(
                lat=dry_points["lat"],
                lon=dry_points["lon"],
                mode="markers",
                marker=dict(size=10, color="red", symbol="circle"),
                name="Needs Watering",
                hoverinfo="text",
                hovertext=[f"Moisture: {m:.3f}" for m in dry_points["moisture"]]
            )

        st.plotly_chart(fig, use_container_width=True)

        # Show table of dry zones
        st.subheader("📍 Areas Needing Water")
        if not dry_points.empty:
            st.dataframe(
                dry_points[["lat", "lon", "moisture"]].sort_values(by="moisture").reset_index(drop=True),
                use_container_width=True
            )
        else:
            st.success("All zones are above the moisture threshold. No watering needed.")

    else:
        st.error(" Failed to fetch any soil moisture data.")


# ------------------------------
# TAB 2: MY PLANTS (Empty)
# ------------------------------
with tab2:
    st.title("🌿 My Plants")
    st.markdown("This section is currently empty. Add your plant monitoring tools here later.")
