import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import asyncio
from streamlit_folium import st_folium
import folium
from streamlit_drawable_canvas import st_canvas
import geojson
from shapely.geometry import Polygon
import plotly.express as px
import plotly.graph_objects as go
from database import init_database, create_user, sign_in, save_land, get_user_lands, save_recommendation, get_land_recommendations

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

# Enhanced European Data Sources based on EU initiatives
DATA_SOURCES = {
    "agri_prices": "https://agridata.ec.europa.eu/api/v1/prices",
    "fsdn": "https://agriculture.ec.europa.eu/api/fsdn",  # Farm Sustainability Data Network
    "soil_data": "https://esdac.jrc.ec.europa.eu/api/soil",
    "weather": "http://api.openweathermap.org/data/2.5/weather",
    "eurostat": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/",
    "fast_platform": "https://fastplatform.eu/api/v1/"  # FaST Platform API
}

class EuropeanAgriDataService:
    def __init__(self):
        self.cache = {}
        self.cache_duration = timedelta(hours=24)

    def _cache_data(self, key, data):
        self.cache[key] = {
            "timestamp": datetime.now(),
            "data": data
        }

    def _is_cache_valid(self, key):
        return (key in self.cache and 
                datetime.now() - self.cache[key]["timestamp"] < self.cache_duration)

    async def get_fsdn_data(self, region):
        """Get Farm Sustainability Data Network information"""
        if self._is_cache_valid(f"fsdn_{region}"):
            return self.cache[f"fsdn_{region}"]["data"]
        
        try:
            response = requests.get(f"{DATA_SOURCES['fsdn']}/region/{region}")
            data = response.json()
            self._cache_data(f"fsdn_{region}", data)
            return data
        except:
            return {"sustainability_metrics": {
                "soil_health": "medium",
                "water_efficiency": "high",
                "biodiversity": "medium"
            }}

    async def get_fast_platform_data(self, region):
        """Get FaST Platform agricultural data"""
        if self._is_cache_valid(f"fast_{region}"):
            return self.cache[f"fast_{region}"]["data"]
        
        try:
            response = requests.get(
                f"{DATA_SOURCES['fast_platform']}/agricultural-data",
                params={"region": region}
            )
            data = response.json()
            self._cache_data(f"fast_{region}", data)
            return data
        except:
            return {
                "soil_nutrients": "moderate",
                "recommended_practices": ["crop_rotation", "minimum_tillage"]
            }

    async def get_market_prices(self):
        """Get current agricultural market prices"""
        if self._is_cache_valid("prices"):
            return self.cache["prices"]["data"]
        
        try:
            response = requests.get(DATA_SOURCES["agri_prices"])
            data = response.json()
            self._cache_data("prices", data)
            return data
        except:
            return {
                "Wheat": {"price": 250, "unit": "€/tonne"},
                "Barley": {"price": 220, "unit": "€/tonne"}
            }

    async def get_weather_data(self, lat, lon):
        """Get weather data"""
        if self._is_cache_valid(f"weather_{lat}_{lon}"):
            return self.cache[f"weather_{lat}_{lon}"]["data"]

        try:
            response = requests.get(
                f"{DATA_SOURCES['weather']}?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            )
            data = response.json()
            self._cache_data(f"weather_{lat}_{lon}", data)
            return data
        except Exception as e:
            return {"temp": None, "humidity": None, "error": str(e)}

def get_recommendations(region_data, sustainability_data, market_data, weather_data):
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    
    prompt = f"""Based on comprehensive European agricultural data, provide detailed agricultural recommendations:

    Region: {region_data['name']}
    
    Environmental Conditions:
    - Temperature: {weather_data.get('main', {}).get('temp', 'Unknown')}°C
    - Humidity: {weather_data.get('main', {}).get('humidity', 'Unknown')}%
    - Soil Type: {region_data['soil_type']}
    
    Sustainability Metrics:
    - Soil Health: {sustainability_data.get('soil_health', 'Unknown')}
    - Water Efficiency: {sustainability_data.get('water_efficiency', 'Unknown')}
    - Biodiversity: {sustainability_data.get('biodiversity', 'Unknown')}
    
    Market Conditions:
    {json.dumps(market_data, indent=2)}
    
    Please provide a comprehensive analysis including:
    1. Top 3 recommended crops with expected yield projections
    2. Optimal planting and harvesting schedule
    3. Suggested crop rotation plan for the next 3 seasons
    4. Sustainable farming practices specific to the region
    5. Market outlook and price predictions
    6. Risk mitigation strategies
    
    Format the response in clear sections with bullet points where appropriate.
    """
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Failed to get recommendations: {e}")
        return None

def create_map(regions, selected_region=None):
    # Create a map centered on Europe with Mapbox tiles
    m = folium.Map(
        location=[48.8566, 2.3522],
        zoom_start=5,
        tiles=f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
        attr='Mapbox'
    )
    
    for region_key, region_data in regions.items():
        lat, lon = region_data["coordinates"]
        popup_content = f"<b>{region_data['name']}</b><br>Soil Type: {region_data['soil_type']}"
        
        # Highlight selected region
        if selected_region == region_key:
            folium.CircleMarker(
                location=[lat, lon],
                radius=15,
                popup=folium.Popup(popup_content, max_width=300),
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)
        else:
            folium.CircleMarker(
                location=[lat, lon],
                radius=10,
                popup=folium.Popup(popup_content, max_width=300),
                color='blue',
                fill=True,
                fill_color='blue'
            ).add_to(m)
    
    return m

def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Please upload a CSV or Excel file")
            return None
        return df.to_dict(orient='records')
    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

def init_session_state():
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'lands' not in st.session_state:
        st.session_state.lands = []

def login_page():
    st.title("Login to Agricultural Advisor")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            try:
                response = sign_in(email, password)
                if response:
                    st.session_state.user = response
                    st.success("Successfully logged in!")
                    st.rerun()
            except Exception as e:
                st.error(f"Login failed: {str(e)}")
    
    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        role = st.selectbox("Role", ["user", "admin"])
        if st.button("Sign Up"):
            try:
                response = create_user(email, password, role)
                if response:
                    st.success("Account created successfully! Please login.")
            except Exception as e:
                st.error(f"Sign up failed: {str(e)}")

def land_management_page():
    st.title("Land Management")
    create_footer()
    
    # Create a map for land visualization
    m = folium.Map(
        location=[48.8566, 2.3522],
        zoom_start=5,
        tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_TOKEN}",
        attr='Mapbox'
    )
    
    # Add draw control to the map
    draw = folium.plugins.Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'circlemarker': False,
            'marker': False
        }
    )
    m.add_child(draw)
    
    # Display existing lands
    user_lands = get_user_lands(st.session_state.user.id)
    for land in user_lands:
        if land.coordinates:
            folium.GeoJson(
                land.coordinates,
                name=land.name,
                popup=folium.Popup(f"<b>{land.name}</b><br>Soil Type: {land.soil_type}<br>Area: {land.area} sq units")
            ).add_to(m)
    
    # Display the map
    map_data = st_folium(m, width=800, height=400)
    
    # Land details form
    with st.form("land_details"):
        name = st.text_input("Land Name")
        soil_type = st.text_input("Soil Type")
        submit_button = st.form_submit_button("Save Land")
        
        if submit_button and map_data is not None and 'all_drawings' in map_data and len(map_data['all_drawings']) > 0:
            # Get the latest drawn polygon
            polygon = map_data['all_drawings'][-1]
            
            # Create GeoJSON feature
            geojson_data = geojson.Feature(
                geometry=geojson.Polygon(polygon['geometry']['coordinates'])
            )
            
            # Calculate area using shapely
            poly = Polygon(polygon['geometry']['coordinates'][0])
            area = poly.area
            
            # Save land data
            save_land(
                st.session_state.user.id,
                name,
                geojson_data,
                soil_type,
                area
            )
            st.success("Land saved successfully!")
            st.rerun()

    # Display existing lands in a table with recommendations
    if user_lands:
        st.subheader("Your Lands")
        for land in user_lands:
            with st.expander(f"Land: {land.name}"):
                land_data = {
                    "Name": land.name,
                    "Soil Type": land.soil_type,
                    "Area": f"{land.area:.2f} sq units"
                }
                st.write("### Land Details")
                st.write(land_data)
                
                st.write("### Agricultural Recommendations")
                with st.spinner("Analyzing agricultural data..."):
                    agri_service = EuropeanAgriDataService()
                    coords = land.coordinates.get('geometry', {}).get('coordinates', [[[]]])[0][0]
                    
                    st.write("#### Analysis Tools")
                    if st.button("🌱 Sustainability", key=f"sustainability_{land.id}"):
                        sustainability_data = asyncio.run(agri_service.get_fsdn_data(land.name))
                        fast_data = asyncio.run(agri_service.get_fast_platform_data(land.name))
                        
                        st.write("#### Environmental Metrics")
                        metrics = {
                            "Soil Health": sustainability_data.get('soil_health', 'Unknown'),
                            "Water Efficiency": sustainability_data.get('water_efficiency', 'Unknown'),
                            "Biodiversity": sustainability_data.get('biodiversity', 'Unknown'),
                            "Soil Nutrients": fast_data.get('soil_nutrients', 'Unknown')
                        }
                        
                        cols = st.columns(4)
                        for i, (metric, value) in enumerate(metrics.items()):
                            with cols[i]:
                                st.metric(metric, value)
                        
                        st.write("#### Recommended Sustainable Practices")
                        practices = fast_data.get('recommended_practices', [])
                        for practice in practices:
                            st.write(f"- {practice.replace('_', ' ').title()}")
                    
                    if st.button("📈 Market", key=f"market_{land.id}"):
                        market_data = asyncio.run(agri_service.get_market_prices())
                        
                        st.write("#### Market Analysis")
                        market_chart = create_market_trend_chart(market_data)
                        st.plotly_chart(market_chart, use_container_width=True)
                        
                        st.write("#### Current Market Prices")
                        cols = st.columns(len(market_data))
                        for i, (crop, data) in enumerate(market_data.items()):
                            with cols[i]:
                                st.metric(crop, f"€{data['price']}/{data['unit']}")
                    
                    if st.button("🌡️ Climate", key=f"climate_{land.id}"):
                        weather_data = asyncio.run(agri_service.get_weather_data(coords[1], coords[0]))
                        
                        st.write("#### Climate Impact Analysis")
                        if weather_data.get('main'):
                            climate_chart = create_climate_impact_chart(weather_data)
                            st.plotly_chart(climate_chart, use_container_width=True)
                            
                            st.write("#### Current Weather Conditions")
                            cols = st.columns(3)
                            with cols[0]:
                                st.metric("Temperature", f"{weather_data['main'].get('temp', 'Unknown')}°C")
                            with cols[1]:
                                st.metric("Humidity", f"{weather_data['main'].get('humidity', 'Unknown')}%")
                            with cols[2]:
                                st.metric("Pressure", f"{weather_data['main'].get('pressure', 'Unknown')} hPa")
                    
                    if st.button("📊 Analysis", key=f"comprehensive_{land.id}"):
                        sustainability_data = asyncio.run(agri_service.get_fsdn_data(land.name))
                        market_data = asyncio.run(agri_service.get_market_prices())
                        weather_data = asyncio.run(agri_service.get_weather_data(coords[1], coords[0]))
                        
                        recommendations = get_recommendations(
                            {"name": land.name, "soil_type": land.soil_type},
                            sustainability_data,
                            market_data,
                            weather_data
                        )
                        
                        st.write("#### Comprehensive Agricultural Analysis")
                        if recommendations:
                            st.write(recommendations)
                            crop_chart = create_crop_distribution_chart(recommendations)
                            st.plotly_chart(crop_chart, use_container_width=True)

def create_crop_distribution_chart(recommendations_text):
    # Parse the recommendations text to extract crop data
    crops = []
    values = []
    try:
        # Extract crops from the recommendations text
        lines = recommendations_text.split('\n')
        for line in lines:
            if 'yield' in line.lower() and ':' in line:
                crop = line.split(':')[0].strip()
                value = float(line.split(':')[1].split('tons')[0].strip())
                crops.append(crop)
                values.append(value)
    except:
        crops = ['Wheat', 'Barley', 'Corn']
        values = [4.5, 3.2, 2.8]
    
    fig = px.pie(values=values, names=crops, title='Crop Distribution by Yield')
    return fig

def create_market_trend_chart(market_data):
    crops = list(market_data.keys())
    prices = [data['price'] for data in market_data.values()]
    fig = px.bar(x=crops, y=prices, title='Current Market Prices')
    fig.update_layout(yaxis_title='Price (€/tonne)', xaxis_title='Crops')
    return fig

def create_climate_impact_chart(weather_data):
    if not weather_data.get('main'):
        return None
    
    labels = ['Temperature (°C)', 'Humidity (%)', 'Pressure (hPa)']
    values = [
        weather_data['main'].get('temp', 0),
        weather_data['main'].get('humidity', 0),
        weather_data['main'].get('pressure', 0)/10  # Scaled for visualization
    ]
    
    fig = go.Figure(data=[go.Scatterpolar(
        r=values,
        theta=labels,
        fill='toself'
    )])
    fig.update_layout(title='Climate Conditions')
    return fig

def create_footer():
    st.sidebar.markdown(
        """
        <style>
        .sidebar-footer {
            margin-top: 20px;
            padding: 10px;
            text-align: center;
            border-top: 1px solid #ddd;
            background-color: white;
            font-size: 0.8em;
        }
        </style>
        <div class='sidebar-footer'>
            Powered by<br>
            <b>Mapbox</b> • <b>OpenWeather</b> • <b>PostgreSQL</b><br>
            <b>Groq</b> • <b>Deepseek R1</b> • <b>Llama</b>
        </div>
        """,
        unsafe_allow_html=True
    )

def main():
    init_database()
    init_session_state()
    
    if not st.session_state.user:
        login_page()
        return
    
    st.sidebar.text(f"Welcome, {st.session_state.user.email}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()
    
    page = st.sidebar.radio("Navigation", ["Home", "Land Management"])
    
    if page == "Land Management":
        land_management_page()
        return
    
    st.title("Smart Agriculture Advisor - A Proof of Concept in Bidirectional Data Sharing")
    
    # Add file upload and text input section
    st.sidebar.header("User Data Input")
    input_type = st.sidebar.radio("Select Input Type", ["None", "File Upload(CSV/XLS)", "Text Input"])
    
    custom_data = None
    if input_type == "File Upload":
        uploaded_file = st.sidebar.file_uploader("Upload your agricultural data (CSV/Excel)", type=['csv', 'xlsx', 'xls'])
        if uploaded_file:
            custom_data = process_uploaded_file(uploaded_file)
    elif input_type == "Manual Input":
        st.sidebar.subheader("Enter Custom Conditions")
        custom_soil_type = st.sidebar.text_input("Soil Type", "")
        custom_crop_history = st.sidebar.text_area("Previous Crop History", "")
        custom_irrigation = st.sidebar.selectbox("Irrigation System", ["None", "Drip", "Sprinkler", "Flood"])
        
        if custom_soil_type or custom_crop_history or custom_irrigation != "None":
            custom_data = {
                "soil_type": custom_soil_type,
                "crop_history": custom_crop_history,
                "irrigation": custom_irrigation
            }
    
    regions = {
        "Tuscany": {
            "name": "Tuscany, Italy",
            "coordinates": (43.7711, 11.2486),
            "soil_type": "Clay-Limestone"
        },
        "Bavaria": {
            "name": "Bavaria, Germany",
            "coordinates": (48.7904, 11.4979),
            "soil_type": "Loess"
        }
    }
    
    # Create two columns for layout
    col1, col2 = st.columns([2, 1])
    
    with col2:
        region_name = st.selectbox("Select Region", list(regions.keys()))
        region_data = regions[region_name]
    
    with col1:
        # Display the map with the selected region highlighted
        m = create_map(regions, region_name)
        st_folium(m, width=800, height=400)
    
    # Create analysis buttons in vertical layout
    st.subheader("Agricultural Analysis Tools")
    
    if st.button("🌱 Sustainability Analysis"):
        with st.spinner("Analyzing sustainability metrics..."):
            agri_service = EuropeanAgriDataService()
            sustainability_data = asyncio.run(agri_service.get_fsdn_data(region_name))
            fast_data = asyncio.run(agri_service.get_fast_platform_data(region_name))
            
            st.write("### Sustainability Analysis")
            st.write("#### Environmental Metrics")
            metrics = {
                "Soil Health": sustainability_data.get('soil_health', 'Unknown'),
                "Water Efficiency": sustainability_data.get('water_efficiency', 'Unknown'),
                "Biodiversity": sustainability_data.get('biodiversity', 'Unknown'),
                "Soil Nutrients": fast_data.get('soil_nutrients', 'Unknown')
            }
            
            # Create metrics visualization
            cols = st.columns(4)
            for i, (metric, value) in enumerate(metrics.items()):
                with cols[i]:
                    st.metric(metric, value)
            
            st.write("#### Recommended Sustainable Practices")
            practices = fast_data.get('recommended_practices', [])
            for practice in practices:
                st.write(f"- {practice.replace('_', ' ').title()}")
    
    if st.button("📈 Market Analysis"):
        with st.spinner("Analyzing market data..."):
            agri_service = EuropeanAgriDataService()
            market_data = asyncio.run(agri_service.get_market_prices())
            
            st.write("### Market Analysis")
            # Display market trend chart
            market_chart = create_market_trend_chart(market_data)
            st.plotly_chart(market_chart, use_container_width=True)
            
            st.write("#### Current Market Prices")
            cols = st.columns(len(market_data))
            for i, (crop, data) in enumerate(market_data.items()):
                with cols[i]:
                    st.metric(crop, f"€{data['price']}/{data['unit']}")
    
    if st.button("🌡️ Climate Impact Analysis"):
        with st.spinner("Analyzing climate data..."):
            agri_service = EuropeanAgriDataService()
            weather_data = asyncio.run(agri_service.get_weather_data(
                region_data["coordinates"][0], region_data["coordinates"][1]
            ))
            
            st.write("### Climate Impact Analysis")
            if weather_data.get('main'):
                # Display climate impact chart
                climate_chart = create_climate_impact_chart(weather_data)
                st.plotly_chart(climate_chart, use_container_width=True)
                
                st.write("#### Current Weather Conditions")
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Temperature", f"{weather_data['main'].get('temp', 'Unknown')}°C")
                with cols[1]:
                    st.metric("Humidity", f"{weather_data['main'].get('humidity', 'Unknown')}%")
                with cols[2]:
                    st.metric("Pressure", f"{weather_data['main'].get('pressure', 'Unknown')} hPa")
    
    if st.button("📊 Comprehensive Analysis"):
        with st.spinner("Generating comprehensive analysis..."):
            agri_service = EuropeanAgriDataService()
            sustainability_data = asyncio.run(agri_service.get_fsdn_data(region_name))
            market_data = asyncio.run(agri_service.get_market_prices())
            weather_data = asyncio.run(agri_service.get_weather_data(
                region_data["coordinates"][0], region_data["coordinates"][1]
            ))
            
            recommendations = get_recommendations(
                region_data,
                sustainability_data,
                market_data,
                weather_data
            )
            
            st.write("### Comprehensive Agricultural Analysis")
            st.write(recommendations)
            
            # Display crop distribution chart
            if recommendations:
                crop_chart = create_crop_distribution_chart(recommendations)
                st.plotly_chart(crop_chart, use_container_width=True)

if __name__ == "__main__":
    main()