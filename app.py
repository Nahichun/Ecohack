import streamlit as st
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

st.set_page_config(page_title="Карта скоплений пластика", layout="wide")

st.title("🛰 Карта скоплений пластика")
st.caption("Анализ данных Sentinel-2 с использованием индекса FDI")

if "fdi" not in st.session_state:
    st.session_state.fdi = None

if "area" not in st.session_state:
    st.session_state.area = None

if "status" not in st.session_state:
    st.session_state.status = "Готов к запуску"

st.sidebar.header("Параметры")

mode = st.sidebar.selectbox(
    "Источник данных",
    ["Демо-режим", "Sentinel Hub"]
)

lat = st.sidebar.number_input("Широта", value=43.0)
lon = st.sidebar.number_input("Долгота", value=39.0)
radius = st.sidebar.slider("Радиус (км)", 5, 50, 20)

st.sidebar.markdown("---")
st.sidebar.info(f"Статус: {st.session_state.status}")


def demo_field(size=512):
    x = np.linspace(-3, 3, size)
    y = np.linspace(-3, 3, size)
    X, Y = np.meshgrid(x, y)

    z1 = np.exp(-((X - 1.2) ** 2 + (Y + 0.8) ** 2))
    z2 = np.exp(-((X + 1.5) ** 2 + (Y - 0.4) ** 2))
    z3 = np.exp(-((X - 0.6) ** 2 + (Y - 1.3) ** 2))

    noise = np.random.normal(0, 0.05, (size, size))
    field = z1 + z2 + z3 + noise
    field = (field - field.min()) / (field.max() - field.min())

    return field


if st.sidebar.button("Запустить анализ"):

    st.session_state.status = "Выполняется анализ..."
    delta = radius / 111

    with st.spinner("Получение данных..."):

        try:
            if mode == "Sentinel Hub":

                from sentinelhub import (
                    SHConfig, DataCollection,
                    SentinelHubRequest, MimeType,
                    CRS, BBox
                )

                config = SHConfig()
                config.sh_client_id = "YOUR_CLIENT_ID"
                config.sh_client_secret = "YOUR_CLIENT_SECRET"

                bbox = BBox(
                    [lon - delta, lat - delta, lon + delta, lat + delta],
                    crs=CRS.WGS84
                )

                time_range = (
                    (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
                    datetime.now().strftime("%Y-%m-%d")
                )

                script = """
                //VERSION=3
                function setup() {
                  return {
                    input: ["B04","B06","B08","SCL"],
                    output: { bands: 1 }
                  };
                }

                function evaluatePixel(s) {
                  if ([3,8,9,10,11].includes(s.SCL)) return [0];
                  let fdi = s.B08 - (s.B04 + (s.B06 - s.B04) * 0.5);
                  return [fdi];
                }
                """

                req = SentinelHubRequest(
                    evalscript=script,
                    input_data=[
                        SentinelHubRequest.input_data(
                            data_collection=DataCollection.SENTINEL2_L2A,
                            time_interval=time_range
                        )
                    ],
                    responses=[
                        SentinelHubRequest.output_response("default", MimeType.TIFF)
                    ],
                    bbox=bbox,
                    size=(512, 512),
                    config=config
                )

                data = req.get_data()[0][:, :, 0]
                data[data == 0] = np.nan

            else:
                raise RuntimeError

        except Exception:
            st.warning("API недоступен. Используется демонстрационный режим.")
            data = demo_field()

        norm = (data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data))
        area = np.sum(norm > 0.7) / norm.size * 100

        st.session_state.fdi = norm
        st.session_state.area = area
        st.session_state.status = "Анализ завершён"


if st.session_state.fdi is not None:

    delta = radius / 111

    m = folium.Map(
        location=[lat, lon],
        zoom_start=8,
        tiles="CartoDB positron"
    )

    folium.raster_layers.ImageOverlay(
        image=st.session_state.fdi,
        bounds=[[lat - delta, lon - delta],
                [lat + delta, lon + delta]],
        opacity=0.75,
        colormap=lambda x: (1, 0, 0, x)
    ).add_to(m)

    st_folium(
        m,
        width=1100,
        height=650,
        key="plastic_map",
        returned_objects=[]
    )

    st.metric(
        "Доля зоны повышенной концентрации",
        f"{st.session_state.area:.2f} %"
    )