import streamlit as st
import pandas as pd
import rasterio
from rasterio.plot import show
from rasterio.warp import transform_bounds
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import requests

# -------------------------------------------------------------------
# Streamlit setup
# -------------------------------------------------------------------
st.set_page_config(page_title="GeoTIFF Multi-Coordinate Extractor", layout="wide")
st.title("🗺️ GeoTIFF Multi-Coordinate Extractor (CRS-Aware + Max Value)")

st.markdown("""
Upload a **GeoTIFF** or use the example.  
Enter **latitude & longitude (EPSG:4326)** — single, multiple, or CSV — and the app will:  
✅ Convert coordinates to the raster’s CRS  
✅ Extract pixel values  
✅ Display results and an OpenStreetMap preview  
✅ Identify and display the coordinate with **maximum raster value**
""")

# -------------------------------------------------------------------
# Cached example TIFF
# -------------------------------------------------------------------
@st.cache_data
def load_example_tiff():
    url = "https://github.com/mapbox/rasterio/raw/main/tests/data/RGB.byte.tif"
    response = requests.get(url)
    return response.content

# -------------------------------------------------------------------
# Upload or use sample
# -------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 Upload GeoTIFF", type=["tif", "tiff"])
if uploaded_file:
    tiff_bytes = uploaded_file.read()
    filename = uploaded_file.name
else:
    st.info("Using example GeoTIFF (`wildfires.tiff`).")
    tiff_bytes = load_example_tiff()
    filename = "wildfires.tiff"

# -------------------------------------------------------------------
# Read raster metadata
# -------------------------------------------------------------------
with rasterio.MemoryFile(tiff_bytes) as memfile:
    with memfile.open() as src:
        band = src.read(1)
        crs = src.crs
        bounds = src.bounds
        transform = src.transform
        height, width = band.shape

# Convert bounds to EPSG:4326
try:
    bounds4326 = transform_bounds(crs, "EPSG:4326", *bounds)
except Exception:
    bounds4326 = None

# -------------------------------------------------------------------
# Display raster metadata
# -------------------------------------------------------------------
st.subheader("📘 Raster Information")
col1, col2 = st.columns(2)
with col1:
    st.write(f"**File:** {filename}")
    st.write(f"**CRS:** {crs}")
    st.write(f"**Dimensions:** {width} × {height}")
with col2:
    if bounds4326:
        st.write("**Bounds (EPSG:4326)**")
        st.write(f"Min Lon: {bounds4326[0]:.4f}")
        st.write(f"Min Lat: {bounds4326[1]:.4f}")
        st.write(f"Max Lon: {bounds4326[2]:.4f}")
        st.write(f"Max Lat: {bounds4326[3]:.4f}")
    else:
        st.warning("⚠️ Could not convert bounds to EPSG:4326")

# -------------------------------------------------------------------
# Show raster image
# -------------------------------------------------------------------
st.subheader("🖼️ Raster Preview")
fig, ax = plt.subplots(figsize=(6, 6))
show(band, transform=transform, ax=ax)
ax.set_title(filename)
st.pyplot(fig)

# -------------------------------------------------------------------
# Coordinate input form
# -------------------------------------------------------------------
st.subheader("📍 Coordinate Input Options")

input_mode = st.radio(
    "Choose input mode:",
    ["Single coordinate", "Multiple coordinates", "Upload CSV (lat, lon)"],
    horizontal=True
)

coords = []

if input_mode == "Single coordinate":
    with st.form("single_coord"):
        lat = st.number_input("Latitude", format="%.6f")
        lon = st.number_input("Longitude", format="%.6f")
        submitted = st.form_submit_button("Extract Value")
        if submitted:
            coords = [(lat, lon)]

elif input_mode == "Multiple coordinates":
    with st.form("multi_coord"):
        text_input = st.text_area(
            "Enter coordinates (lat,lon) one per line:",
            placeholder="Example:\n24.4675,54.3667\n25.1234,55.9876"
        )
        submitted = st.form_submit_button("Extract Values")
        if submitted and text_input.strip():
            try:
                coords = [
                    tuple(map(float, line.split(",")))
                    for line in text_input.strip().splitlines()
                    if "," in line
                ]
            except Exception:
                st.error("⚠️ Invalid coordinate format. Use 'lat,lon' per line.")

else:  # CSV upload
    uploaded_csv = st.file_uploader("Upload CSV file with 'lat' and 'lon' columns", type=["csv"])
    if uploaded_csv:
        df_csv = pd.read_csv(uploaded_csv)
        if "lat" in df_csv.columns and "lon" in df_csv.columns:
            st.write(f"✅ Loaded {len(df_csv)} coordinates from CSV.")
            if st.button("Extract Values from CSV"):
                coords = list(zip(df_csv["lat"], df_csv["lon"]))
        else:
            st.error("CSV must contain columns named 'lat' and 'lon'.")

# -------------------------------------------------------------------
# Process coordinates and find max value
# -------------------------------------------------------------------
if coords:
    results = []
    with rasterio.MemoryFile(tiff_bytes) as memfile:
        with memfile.open() as src:
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            for lat, lon in coords:
                try:
                    x, y = transformer.transform(lon, lat)
                    row, col = src.index(x, y)
                    val = src.read(1)[row, col]
                    results.append({
                        "latitude (EPSG:4326)": lat,
                        "longitude (EPSG:4326)": lon,
                        "value": val
                    })
                except Exception:
                    results.append({
                        "latitude (EPSG:4326)": lat,
                        "longitude (EPSG:4326)": lon,
                        "value": None
                    })

    df_result = pd.DataFrame(results)

    # Find max value and its coordinate
    if df_result["value"].notna().any():
        max_row = df_result.loc[df_result["value"].idxmax()]
        st.subheader("🌟 Maximum Value Found")
        st.write(f"**Max Value:** {max_row['value']}")
        st.write(f"**Coordinate (EPSG:4326):** ({max_row['latitude (EPSG:4326)']:.6f}, {max_row['longitude (EPSG:4326)']:.6f})")
    else:
        max_row = None
        st.warning("No valid raster values extracted.")

    # Display results in table
    st.subheader("📊 Extracted Results")
    st.dataframe(df_result)

    csv_bytes = df_result.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Results as CSV",
        data=csv_bytes,
        file_name="tiff_extracted_values.csv",
        mime="text/csv"
    )

    # -------------------------------------------------------------------
    # Map visualization
    # -------------------------------------------------------------------
    st.subheader("🗺️ Locations on OpenStreetMap")
    if not df_result.empty:
        center_lat = df_result["latitude (EPSG:4326)"].mean()
        center_lon = df_result["longitude (EPSG:4326)"].mean()
        fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles="OpenStreetMap")

        for _, row in df_result.iterrows():
            popup = f"Lat: {row['latitude (EPSG:4326)']}, Lon: {row['longitude (EPSG:4326)']}<br>Value: {row['value']}"
            folium.Marker(
                [row["latitude (EPSG:4326)"], row["longitude (EPSG:4326)"]],
                popup=popup,
                tooltip="Pixel value",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(fmap)

        # Highlight max-value point
        if max_row is not None:
            folium.Marker(
                [max_row["latitude (EPSG:4326)"], max_row["longitude (EPSG:4326)"]],
                popup=f"🌟 Max Value: {max_row['value']}",
                tooltip="Max Value",
                icon=folium.Icon(color="green", icon="star")
            ).add_to(fmap)

        st_folium(fmap, width=900, height=550)
