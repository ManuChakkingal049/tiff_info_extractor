import streamlit as st
import pandas as pd
import rasterio
from rasterio.plot import show
from rasterio.warp import transform_bounds
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from io import BytesIO
import requests

st.set_page_config(page_title="GeoTIFF Coordinate Extractor", layout="wide")
st.title("🗺️ GeoTIFF Coordinate Extractor with OpenStreetMap")

st.markdown("""
Upload a **GeoTIFF** (e.g., satellite or climate data),  
see its **bounds in real coordinates**, input latitude/longitude,  
and extract the pixel value directly.  
""")

# -------------------------------------------------------------------
# Load example TIFF (cached)
# -------------------------------------------------------------------
@st.cache_data
def load_example_tiff():
    url = "https://github.com/mapbox/rasterio/raw/main/tests/data/RGB.byte.tif"
    response = requests.get(url)
    return response.content

# -------------------------------------------------------------------
# File upload or example
# -------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 Upload a GeoTIFF file", type=["tif", "tiff"])
if uploaded_file:
    tiff_data = uploaded_file.read()
    filename = uploaded_file.name
else:
    st.info("Using sample wildfire image (`wildfires.tiff` example).")
    tiff_data = load_example_tiff()
    filename = "wildfires.tiff"

# -------------------------------------------------------------------
# Read TIFF once and store metadata
# -------------------------------------------------------------------
with rasterio.MemoryFile(tiff_data) as memfile:
    with memfile.open() as src:
        band = src.read(1)
        bounds = src.bounds
        crs = src.crs
        transform = src.transform

# Convert bounds to EPSG:4326 for readable lat/lon
try:
    bounds_latlon = transform_bounds(crs, "EPSG:4326", *bounds)
except Exception:
    bounds_latlon = None

st.subheader("📐 GeoTIFF Information")
col1, col2 = st.columns(2)
with col1:
    st.write(f"**File:** {filename}")
    st.write(f"**CRS:** {crs}")
    st.write(f"**Width × Height:** {band.shape[1]} × {band.shape[0]}")
with col2:
    if bounds_latlon:
        st.write("**Coordinate Bounds (EPSG:4326)**")
        st.write(f"Left (min lon): {bounds_latlon[0]:.4f}")
        st.write(f"Bottom (min lat): {bounds_latlon[1]:.4f}")
        st.write(f"Right (max lon): {bounds_latlon[2]:.4f}")
        st.write(f"Top (max lat): {bounds_latlon[3]:.4f}")
    else:
        st.warning("Could not transform bounds to EPSG:4326")

# -------------------------------------------------------------------
# Preview TIFF Image
# -------------------------------------------------------------------
st.subheader("🖼️ GeoTIFF Preview")
fig, ax = plt.subplots(figsize=(6, 6))
show(band, transform=transform, ax=ax)
ax.set_title(filename)
st.pyplot(fig)

# -------------------------------------------------------------------
# Coordinate input section
# -------------------------------------------------------------------
st.subheader("📍 Coordinate Input")
st.markdown("Enter **latitude and longitude** to extract the pixel value:")

with st.form("coord_form"):
    lat = st.number_input("Latitude", format="%.6f")
    lon = st.number_input("Longitude", format="%.6f")
    extract_btn = st.form_submit_button("Extract Value")

if extract_btn:
    with rasterio.MemoryFile(tiff_data) as memfile:
        with memfile.open() as src:
            transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
            try:
                x, y = transformer.transform(lon, lat)
                row, col = src.index(x, y)
                value = src.read(1)[row, col]
                st.success(f"✅ Pixel value at ({lat:.6f}, {lon:.6f}) = **{value}**")
            except Exception as e:
                st.error(f"Could not extract value: {e}")
                value = None

    # ----------------------------------------------------------------
    # Show map only after extraction
    # ----------------------------------------------------------------
    if value is not None:
        st.subheader("🌍 Map View (OpenStreetMap)")
        fmap = folium.Map(location=[lat, lon], zoom_start=10, tiles="OpenStreetMap")
        folium.Marker(
            [lat, lon],
            popup=f"Lat: {lat}, Lon: {lon}<br>Value: {value}",
            tooltip="Clicked Point",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(fmap)
        st_folium(fmap, width=900, height=500)
