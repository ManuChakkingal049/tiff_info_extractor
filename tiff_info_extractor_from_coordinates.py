import streamlit as st
import pandas as pd
import rasterio
from rasterio.plot import show
from rasterio.io import MemoryFile
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import requests
from io import BytesIO
from pyproj import Transformer

st.set_page_config(page_title="GeoTIFF Value Extractor", layout="wide")
st.title("🔥 GeoTIFF Value Extractor (with CRS Handling & OpenStreetMap)")

st.write("""
Upload a GeoTIFF file or use the built-in wildfire example.  
Extract pixel values by latitude and longitude — even if your TIFF uses a projected CRS (like UTM).  
""")

# Download example GeoTIFF (rasterio sample)
@st.cache_data
def load_example_tiff():
    url = "https://github.com/mapbox/rasterio/raw/main/tests/data/RGB.byte.tif"
    response = requests.get(url)
    return response.content

uploaded_file = st.file_uploader("📂 Upload a GeoTIFF file", type=["tif", "tiff"])
if uploaded_file:
    src_file = uploaded_file.read()
    filename = uploaded_file.name
else:
    st.info("No file uploaded. Using sample wildfire raster (for demo).")
    src_file = load_example_tiff()
    filename = "wildfires.tiff"

# Read TIFF
with MemoryFile(src_file) as memfile:
    with memfile.open() as src:
        arr = src.read(1)
        bounds = src.bounds
        transform = src.transform
        crs = src.crs

st.subheader("🧭 Coordinate Bounds")
st.write(f"**CRS:** {crs}")
st.write(f"**Left (min X):** {bounds.left}")
st.write(f"**Bottom (min Y):** {bounds.bottom}")
st.write(f"**Right (max X):** {bounds.right}")
st.write(f"**Top (max Y):** {bounds.top}")

# Create transformer (for lat/lon → raster CRS)
transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

st.subheader("🖼️ GeoTIFF Preview")
fig, ax = plt.subplots(figsize=(6, 6))
show(arr, transform=transform, ax=ax)
ax.set_title(filename)
st.pyplot(fig)

st.subheader("📍 Input Coordinates")
coord_mode = st.radio("Select input type:", ["Single coordinate", "Multiple coordinates"])

coords = []
if coord_mode == "Single coordinate":
    lat = st.number_input("Latitude", format="%.6f")
    lon = st.number_input("Longitude", format="%.6f")
    if lat or lon:
        coords = [(lat, lon)]
else:
    coord_text = st.text_area("Enter coordinates (one 'lat, lon' per line):")
    if coord_text.strip():
        try:
            for line in coord_text.strip().split("\n"):
                lat, lon = map(float, line.split(","))
                coords.append((lat, lon))
        except Exception:
            st.error("⚠️ Please enter valid coordinates (format: lat, lon per line).")

if st.button("🔍 Extract Values"):
    if not coords:
        st.warning("Please enter at least one coordinate.")
    else:
        results = []
        with MemoryFile(src_file) as memfile:
            with memfile.open() as src:
                for lat, lon in coords:
                    try:
                        # Convert from lat/lon (EPSG:4326) to raster CRS
                        x, y = transformer.transform(lon, lat)
                        row, col = src.index(x, y)
                        value = src.read(1)[row, col]
                        results.append({
                            "latitude": lat,
                            "longitude": lon,
                            "value": float(value)
                        })
                    except Exception:
                        results.append({
                            "latitude": lat,
                            "longitude": lon,
                            "value": None
                        })

        df = pd.DataFrame(results)
        st.success("✅ Extraction complete!")
        st.dataframe(df)

        # Map visualization
        st.subheader("🗺️ Map View (OpenStreetMap)")
        center_lat = df["latitude"].mean()
        center_lon = df["longitude"].mean()
        fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles="OpenStreetMap")

        for _, row in df.iterrows():
            popup_text = f"Lat: {row['latitude']}, Lon: {row['longitude']}<br>Value: {row['value']}"
            folium.Marker(
                [row["latitude"], row["longitude"]],
                popup=popup_text,
                icon=folium.Icon(color="red", icon="fire")
            ).add_to(fmap)

        st_folium(fmap, width=800, height=500)

        # CSV download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download results as CSV",
            data=csv,
            file_name="tiff_extracted_values.csv",
            mime="text/csv"
        )
