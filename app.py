import streamlit as st
import folium
from streamlit_folium import st_folium
import osmnx as ox
import networkx as nx

# --- تنظیمات ظاهری صفحه ---
st.set_page_config(layout="wide", page_title="ARVO SDSS - Location Allocation")

st.title("ARVO: Spatial Decision-Support System (SDSS)")
st.markdown("### Dynamic Supply Chain Localization & Capacity Aggregation")

# --- مدیریت حافظه موقت (Session State) ---
if 'ran_allocation' not in st.session_state:
    st.session_state.ran_allocation = False
    st.session_state.allocated_smes = []
    st.session_state.total_capacity = 0
    st.session_state.max_dist = 0

# --- پنل کناری (Sidebar) ---
with st.sidebar:
    st.header("Allocation Parameters")
    st.write("Set the required volume for the green mega-project in Oulu region.")
    
    demand = st.number_input("EPC DEMAND (UNITS/YR)", value=25000, step=5000, min_value=1000)
    
    run_btn = st.button("RUN ALLOCATION ENGINE", type="primary")
    
    st.markdown("---")
    st.markdown("**Model Info:**")
    st.caption("This tool uses real road-network routing (OSMnx) and NetworkX optimization to allocate regional SMEs dynamically.")

# --- بارگذاری شبکه جاده‌ای اولو (به صورت شعاعی برای سرعت بالا) ---
@st.cache_resource
def load_road_network():
    center_coords = (65.0121, 25.4651)
    G = ox.graph_from_point(center_coords, dist=18000, network_type='drive')
    return G

with st.spinner("Loading Oulu road network graph... Please wait."):
    G = load_road_network()

# --- دیتای غنی‌شده و متراکم شرکت‌های منطقه اولو (SMEs) ---
smes = [
    {"name": "Oulu Fab Oy", "coords": (65.0121, 25.4651), "tier": 3, "capacity": 5000},
    {"name": "Pohjoinen Steel", "coords": (65.0500, 25.4000), "tier": 2, "capacity": 2500},
    {"name": "Kempele Industrial", "coords": (64.9120, 25.5030), "tier": 2, "capacity": 4000},
    {"name": "Haukipudas Assembly", "coords": (65.1760, 25.3520), "tier": 3, "capacity": 6000},
    {"name": "Oulunsalo Tech", "coords": (64.9350, 25.4050), "tier": 1, "capacity": 3500},
    {"name": "Rusko Machine Works", "coords": (65.0510, 25.4950), "tier": 2, "capacity": 2800},
    # شرکت‌های جدید اضافه شده در اطراف اولو:
    {"name": "Linnanmaa Tech Hub", "coords": (65.0550, 25.4680), "tier": 1, "capacity": 4200},
    {"name": "Toppila Industrial", "coords": (65.0350, 25.4350), "tier": 2, "capacity": 3100},
    {"name": "Kaakkuri Components", "coords": (64.9750, 25.5100), "tier": 1, "capacity": 4500},
    {"name": "Oulu Port Logistics", "coords": (65.0250, 25.4150), "tier": 1, "capacity": 6000},
    {"name": "Pateniemi Steel Works", "coords": (65.0800, 25.4100), "tier": 3, "capacity": 2500},
    {"name": "Herukka Fabrication", "coords": (65.0950, 25.3900), "tier": 2, "capacity": 3300},
    {"name": "Maikkula Engineering", "coords": (64.9900, 25.5400), "tier": 1, "capacity": 3800},
    {"name": "Oritkari Cargo Services", "coords": (64.9850, 25.4400), "tier": 2, "capacity": 4100},
    {"name": "Intiö Precision Parts", "coords": (65.0200, 25.4850), "tier": 3, "capacity": 2900},
    {"name": "Kiiminki Mechanical", "coords": (65.1300, 25.7200), "tier": 2, "capacity": 3800}
]

mega_project_coords = (65.0210, 25.4750)

# اگر کاربر دکمه را زد
if run_btn:
    st.session_state.ran_allocation = True
    demand_node = ox.distance.nearest_nodes(G, X=mega_project_coords[1], Y=mega_project_coords[0])
    
    processed_smes = []
    for sme in smes:
        # --- فیلتر کردن شرکت‌های سطح 3 (موانع ساختاریافته / قرمز) ---
        if sme['tier'] == 3:
            continue  # این شرکت‌ها کلاً از دایره انتخاب EPC خارج می‌شوند
            
        sme_node = ox.distance.nearest_nodes(G, X=sme["coords"][1], Y=sme["coords"][0])
        road_dist = nx.shortest_path_length(G, sme_node, demand_node, weight='length') / 1000.0
        processed_smes.append({**sme, 'road_dist': road_dist, 'node': sme_node})
    
    processed_smes.sort(key=lambda x: x['road_dist'])

    total_cap = 0
    max_d = 0
    alloc_smes = []
    
    for sme in processed_smes:
        if total_cap < demand:
            alloc_smes.append(sme)
            total_cap += sme['capacity']
            if sme['road_dist'] > max_d:
                max_d = sme['road_dist']
                
    st.session_state.allocated_smes = alloc_smes
    st.session_state.total_capacity = total_cap
    st.session_state.max_dist = max_d

# --- تقسیم صفحه به دو بخش (نقشه و داشبورد) ---
col1, col2 = st.columns([3, 1])

with col1:
    m = folium.Map(location=mega_project_coords, zoom_start=11, tiles='OpenStreetMap')
    
    # نشانگر مگاپروژه
    folium.Marker(
        mega_project_coords, 
        popup="<b>Mega-Project Site (Demand)</b>", 
        icon=folium.Icon(color='red', icon='industry', prefix='fa')
    ).add_to(m)

    # رسم مسیرهای جاده‌ای شرکت‌های انتخاب‌شده
    if st.session_state.ran_allocation:
        demand_node = ox.distance.nearest_nodes(G, X=mega_project_coords[1], Y=mega_project_coords[0])
        for sme in st.session_state.allocated_smes:
            route = nx.shortest_path(G, sme['node'], demand_node, weight='length')
            route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in route]
            folium.PolyLine(route_coords, color="blue", weight=4, opacity=0.7).add_to(m)

    # نمایش پین تمام شرکت‌ها روی نقشه بر اساس Tier
    tier_colors = {1: 'green', 2: 'orange', 3: 'red'}
    for sme in smes:
        color = tier_colors.get(sme['tier'], 'blue')
        folium.CircleMarker(
            location=sme["coords"],
            radius=8,
            popup=f"<b>{sme['name']}</b><br>Tier: {sme['tier']}<br>Capacity: {sme['capacity']}",
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9
        ).add_to(m)

    st_folium(m, width=900, height=650)

with col2:
    st.markdown("### Metrics")
    
    contracted_count = len(st.session_state.allocated_smes) if st.session_state.ran_allocation else 0
    display_cap = st.session_state.total_capacity if st.session_state.ran_allocation else 0
    display_dist = f"{st.session_state.max_dist:.1f}" if st.session_state.ran_allocation else "0.0"

    st.metric(label="SMES CONTRACTED", value=contracted_count)
    st.metric(label="TOTAL ALLOCATED CAPACITY", value=f"{display_cap:,}")
    st.metric(label="MAX TRANSPORT DISTANCE (KM)", value=display_dist)
    
    if not st.session_state.ran_allocation:
        st.info("Click **'RUN ALLOCATION ENGINE'** to calculate optimal routes via real road networks.")
    else:
        st.success("Optimization completed successfully!")
