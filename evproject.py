import streamlit as st
import requests
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium

# API Keys
GEOAPIFY_API_KEY = 'f8a8860dba5647da9d7c7b45ad31e74c'
OPENCHARGEMAP_API_KEY = 'cd238a0a-8788-420d-9897-dd88e064119b'

OSRM_BASE_URL = 'http://router.project-osrm.org/route/v1/driving/'

# Initialize session state
if 'route_data' not in st.session_state:
    st.session_state.route_data = None
if 'charging_stops' not in st.session_state:
    st.session_state.charging_stops = []
if 'origin' not in st.session_state:
    st.session_state.origin = None
if 'destination' not in st.session_state:
    st.session_state.destination = None

def get_coordinates_geoapify(location_name):
    url = f"https://api.geoapify.com/v1/geocode/search?text={location_name}&apiKey={GEOAPIFY_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        st.error("Failed to fetch coordinates.")
        return None
    data = response.json()
    if data['features']:
        feature = data['features'][0]
        return {'lat': feature['properties']['lat'], 'lon': feature['properties']['lon']}
    return None

def get_directions_osrm(origin, destination):
    origin_coords = f"{origin['lon']},{origin['lat']}"
    destination_coords = f"{destination['lon']},{destination['lat']}"
    url = f"{OSRM_BASE_URL}{origin_coords};{destination_coords}?overview=full&geometries=geojson"
    response = requests.get(url)
    if response.status_code != 200:
        st.error("Failed to fetch route.")
        return None
    return response.json()

def get_charging_stations(lat, lon, max_results=5):
    url = f"https://api.openchargemap.io/v3/poi/?output=json&latitude={lat}&longitude={lon}&maxresults={max_results}&key={OPENCHARGEMAP_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        st.error("Failed to fetch charging stations.")
        return []
    return response.json()

def create_route_map(origin, destination, route_coordinates, charging_stops):
    route_map = folium.Map(location=[origin['lat'], origin['lon']], zoom_start=8)

    # Add route line
    route_line = [(coord[1], coord[0]) for coord in route_coordinates]
    folium.PolyLine(route_line, color='blue', weight=5, opacity=0.8).add_to(route_map)

    # Add markers for start, destination, and charging stations
    folium.Marker([origin['lat'], origin['lon']], popup="Start", icon=folium.Icon(color="green")).add_to(route_map)
    folium.Marker([destination['lat'], destination['lon']], popup="Destination", icon=folium.Icon(color="red")).add_to(route_map)

    for stop in charging_stops:
        station_coords = [stop['AddressInfo']['Latitude'], stop['AddressInfo']['Longitude']]
        folium.Marker(station_coords, popup=f"Charging Station: {stop['AddressInfo']['Title']}",
                      icon=folium.Icon(color="blue")).add_to(route_map)

    return route_map

# Main logic
st.title("EV Route Planner with Charging Stops")

# Input fields
origin_input = st.text_input("Enter Origin", value=st.session_state.origin or "")
destination_input = st.text_input("Enter Destination", value=st.session_state.destination or "")

# User-adjustable parameters
max_range_km = st.slider("Max Range (km)", min_value=50, max_value=500, value=200, step=10)
buffer_km = st.slider("Buffer Distance (km)", min_value=0, max_value=50, value=10, step=1)

# Route planning button
if st.button("Plan Route"):
    origin = get_coordinates_geoapify(origin_input)
    destination = get_coordinates_geoapify(destination_input)

    if origin and destination:
        st.session_state.origin = origin
        st.session_state.destination = destination

        route = get_directions_osrm(origin, destination)
        if route:
            coordinates = route['routes'][0]['geometry']['coordinates']
            st.session_state.route_data = coordinates

            # Find charging stops along the route
            charging_stops = []
            total_distance = 0
            current_battery_range = max_range_km

            for i in range(len(coordinates) - 1):
                coord1 = (coordinates[i][1], coordinates[i][0])
                coord2 = (coordinates[i + 1][1], coordinates[i + 1][0])
                segment_distance = geodesic(coord1, coord2).kilometers
                total_distance += segment_distance

                if segment_distance + buffer_km > current_battery_range:
                    stations = get_charging_stations(coord1[0], coord1[1])
                    if stations:
                        charging_stops.append(stations[0])
                        current_battery_range = max_range_km  # Reset battery after charging

                current_battery_range -= segment_distance

            st.session_state.charging_stops = charging_stops

# Display route and charging stops
if st.session_state.route_data and st.session_state.origin and st.session_state.destination:
    with st.sidebar:
        st.write("Charging Stations Along the Route:")
        for stop in st.session_state.charging_stops:
            st.write(f"**{stop['AddressInfo']['Title']}**")
            st.write(f"Location: {stop['AddressInfo']['Latitude']}, {stop['AddressInfo']['Longitude']}")
            st.write("---")

    route_map = create_route_map(
        st.session_state.origin, 
        st.session_state.destination, 
        st.session_state.route_data, 
        st.session_state.charging_stops
    )
    st_folium(route_map, width=700, height=500)
