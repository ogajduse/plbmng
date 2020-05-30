import folium
import sys
import os


def main():
    """
    Creates a map with location of a node.

    :return: map_one.html file
    """
    latitude = float(sys.argv[1])
    longitude = float(sys.argv[2])
    name = sys.argv[3]

    map_1 = folium.Map(location=[latitude, longitude],
                       zoom_start=2)
    folium.Marker([latitude, longitude], popup=name).add_to(map_1)

    map_1.save('map_1.html')

    sys.stdout = os.devnull
    sys.stderr = os.devnull


if __name__ == "__main__":
    main()
