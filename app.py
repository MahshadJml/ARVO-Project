import streamlit as st
import folium
from streamlit_folium import st_folium
import osmnx as ox
import networkx as nx

# --- تنظیمات ظاهری صفحه ---
st.set_page_config(layout="wide", page_title="ARVO SDSS - Location Allocation")

st.title("ARVO: Spatial Decision-Support System (SDSS)")
st.markdown("### Dynamic Supply Chain Localization & Capacity Aggregation")

# --- پنل کناری (Sidebar) ---
with st.sidebar:
    st.header("Allocation Parameters")
    st.write("Set the required volume for the green mega-project in Oulu region.")
    
    # فیلد دریافت تقاضا
    demand = st.number_input("EPC DEMAND (UNITS/YR)", value=12000, step=1000, min_value=1000)
    
    # دکمه اجرای موتور تخصیص
    run_btn = st.button("RUN ALLOCATION ENGINE", type="primary")
    
    st.markdown("---")
    st.markdown("**Model Info:**")
    st.caption("This tool uses real road-network routing (OSMnx) and NetworkX optimization to allocate regional SMEs dynamically.")

# --- بارگذاری شبکه جاده‌ای اولو بر اساس شعاع نقطه‌ای (بسیار سریع و بهینه) ---
@st.cache_resource
def load_road_network():
    # مختصات مرکز اولو با شعاع ۱۵ کیلومتر (برای جلوگیری از سنگین شدن و گیر کردن)
    center_coords = (65.0121, 25.4651)
    G = ox.graph_from_point(center_coords, dist=15000, network_type='drive')
    return G

with st.spinner("Loading Oulu road network graph... Please wait."):
    G = load_road_network()

# --- دیتای فرضی شرکت‌های منطقه (SMEs) ---
smes = [
    {"name": "Oulu Fab Oy", "coords": (65.0121, 25.4651), "tier": 1, "capacity": 5000},
    {"name": "Pohjoinen Steel", "coords": (65.0500, 25.4000), "tier": 2, "capacity": 2500},
    {"name": "Kempele Industrial", "coords": (64.9120, 25.5030), "tier": 2, "capacity": 4000},
    {"name": "Haukipudas Assembly", "coords": (65.1760, 25.3520), "tier": 3, "capacity": 6000},
    {"name": "Oulunsalo Tech", "coords": (64.9350, 25.4050), "tier": 1, "capacity": 3500},
    {"name": "Rusko Machine Works", "coords": (65.0510, 25.4950), "tier": 2, "capacity": 2800}
]

# موقعیت پیش‌فرض مگاپروژه (تقاضا)
mega_project_coords = (65.0210, 25.4750)

# --- تقسیم صفحه به دو بخش (نقشه و داشبورد) ---
col1, col2 = st.columns([3, 1])

with col1:
    # ساخت نقشه پایه
    m = folium.Map(location=mega_project_coords, zoom_start=11, tiles='OpenStreetMap')
    
    # اضافه کردن نشانگر مگاپروژه (قرمز)
    folium.Marker(
        mega_project_coords, 
        popup="<b>Mega-Project Site (Demand)</b>", 
        icon=folium.Icon(color='red', icon='industry', prefix='fa')
    ).add_to(m)

    allocated_smes = []
    total_capacity = 0
    max_dist = 0

    # اگر کاربر دکمه اجرا را زد، محاسبات شبکه جاده‌ای انجام شود
    if run_btn:
        demand_node = ox.distance.nearest_nodes(G, X=mega_project_coords[1], Y=mega_project_coords[0])
        
        processed_smes = []
        for sme in smes:
            sme_node = ox.distance.nearest_nodes(G, X=sme["coords"][1], Y=sme["coords"][0])
            # محاسبه مسافت واقعی روی جاده بر حسب کیلومتر
            road_dist = nx.shortest_path_length(G, sme_node, demand_node, weight='length') / 1000.0
            processed_smes.append({**sme, 'road_dist': road_dist, 'node': sme_node})
        
        # مرتب‌سازی بر اساس کوتاه‌ترین مسافت جاده‌ای (الگوریتم حریصانه)
        processed_smes.sort(key=lambda x: x['road_dist'])

        for sme in processed_smes:
            if total_capacity < demand:
                allocated_smes.append(sme)
                total_capacity += sme['capacity']
                if sme['road_dist'] > max_dist:
                    max_dist = sme['road_dist']
                
                # استخراج و رسم مسیر واقعی روی جاده‌های نقشه
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

    # رندر کردن نقشه درون استریم‌لیت
    st_folium(m, width=900, height=650)

with col2:
    st.markdown("### Dashboard Metrics")
    
    contracted_count = len(allocated_smes) if run_btn else 0
    display_cap = total_capacity if run_btn else 0
    display_dist = f"{max_dist:.1f}" if run_btn else "0.0"

    # باکس‌های آماری مشابه پنل درخواستی شما
    st.metric(label="SMES CONTRACTED", value=contracted_count)
    st.metric(label="TOTAL ALLOCATED CAPACITY", value=f"{display_cap:,}")
    st.metric(label="MAX TRANSPORT DISTANCE (KM)", value=display_dist)
    
    if not run_btn:
        st.info("Click **'RUN ALLOCATION ENGINE'** to calculate optimal routes via real road networks.")
    else:
        st.success("Optimization completed successfully!")
