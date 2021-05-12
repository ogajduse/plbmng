import folium
import pandas as pd
from vincent import Axis
from vincent import Data
from vincent import DataRef
from vincent import Mark
from vincent import MarkProperties
from vincent import MarkRef
from vincent import PropertySet
from vincent import Scale
from vincent import ValueRef
from vincent import Visualization

from plbmng.utils.config import get_map_path
from plbmng.utils.config import get_plbmng_geolocation_dir
from plbmng.utils.logger import logger


def plot_server_on_map(nodes=None, file_path: str = None) -> None:
    """
    Create a map of every known node and generates chart with information about their's latency.

    :param nodes: list of nodes
    :param file_path: Optional: Path to the file into which the map should be saved.
        If no path is specified, value from plbmng config will be used.
    """
    df = pd.DataFrame({"Data 1": [1, 2, 3, 4, 5, 6, 7, 12], "Data 2": [42, 27, 52, 18, 61, 19, 62, 33]})

    # Top level Visualization
    vis = Visualization(width=500, height=300)
    vis.padding = {"top": 10, "left": 50, "bottom": 50, "right": 100}

    # Data. We're going to key Data 2 on Data 1
    vis.data.append(Data.from_pandas(df, columns=["Data 2"], key_on="Data 1", name="table"))

    # Scales
    vis.scales.append(Scale(name="x", type="ordinal", range="width", domain=DataRef(data="table", field="data.idx")))
    vis.scales.append(Scale(name="y", range="height", nice=True, domain=DataRef(data="table", field="data.val")))

    # Axes
    vis.axes.extend([Axis(type="x", scale="x"), Axis(type="y", scale="y")])

    # Marks
    enter_props = PropertySet(
        x=ValueRef(scale="x", field="data.idx"),
        y=ValueRef(scale="y", field="data.val"),
        width=ValueRef(scale="x", band=True, offset=-1),
        y2=ValueRef(scale="y", value=0),
    )
    update_props = PropertySet(fill=ValueRef(value="steelblue"))
    mark = Mark(
        type="rect", from_=MarkRef(data="table"), properties=MarkProperties(enter=enter_props, update=update_props)
    )

    vis.marks.append(mark)
    vis.axis_titles(x="days", y="latency [ms]")
    vis.to_json(f"{get_plbmng_geolocation_dir()}/vega.json")

    map_full = folium.Map(location=[45.372, -121.6972], zoom_start=2)

    for node in nodes:
        if node["latitude"] == "unknown" or node["longitude"] == "unknown":
            continue
        x = float(node["latitude"])
        y = float(node["longitude"])
        text = """
            NODE: {}, IP: {}
            URL: {}
            FULL NAME: {}
            LATITUDE: {}, LONGITUDE: {}
            """.format(
            node["dns"], node["ip"], node["url"], node["full name"], node["latitude"], node["longitude"]
        )
        popup = folium.Popup(text.strip().replace("\n", "<br>"), max_width=1000)
        folium.Marker([x, y], popup=popup).add_to(map_full)

    save_path = file_path or get_map_path("map_file")
    map_full.save(save_path)
    logger.info(f"Map file was created at {save_path}")


if __name__ == "__main__":
    plot_server_on_map()
