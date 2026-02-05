import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from pathlib import Path
from Constants import AUTOMATION_FILE, WAIT_TIME


# Page Configuration
st.set_page_config(
    page_title="Bioaerosol Dashboard",
    page_icon="🦠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styles
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stMetric label {
        font-size: 1.2rem !important;
    }
    .stMetric div {
        font-size: 2rem !important;
    }
    /* Hide link anchors next to headers to prevent click redirection */
    [data-testid="stHeaderActionElements"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)


# Data loading function
@st.cache_data(ttl=10) # Cache for 10 seconds to prevent frequent disk reads
def load_data():
    if not AUTOMATION_FILE.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(AUTOMATION_FILE)
        # Merge date and time
        df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
        
        # Handle the composite indicator, temporarily treat as 0
        if 'BioIndex' not in df.columns:
            df['BioIndex'] = 0
            
        return df
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return pd.DataFrame()


# Sidebar
st.sidebar.title("Control Panel")

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

st.sidebar.info("System updates automatically every 60 seconds.")


# Main interface logic
st.title("Bioaerosol Dashboard")

df = load_data()

if not df.empty:
    # Get the latest data record
    latest = df.iloc[-1]
    latest_time = latest['Datetime']
    
    # Top status bar
    st.markdown(f"**Last Updated:** {latest_time}")
    st.divider()

    # Divide into three tabs
    tab1, tab2, tab3 = st.tabs(["Current Readings", "Component Trends", "Index Trend"])

    # Tab 1: Current Readings
    with tab1:
        st.subheader("Current Readings")
        col1, col2, col3, col4 = st.columns(4)
        
        def render_metric(col, label, value, unit="", help_text=None):
            with col:
                help_html = f'<span title="{help_text}" style="cursor:help; font-size:1em">ⓘ</span>' if help_text else ""
                st.markdown(f"<div style='color: #666; font-size: 16px;'>{label} {help_html}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 36px; margin-top: -5px;'>{value:.0f} <span style='font-size: 16px; color: #999; font-weight: normal;'>{unit}</span></div>", unsafe_allow_html=True)

        with col1:
            render_metric(col1, "Bacteria", latest['Bacteria'], " #/L")
        with col2:
            render_metric(col2, "Fungi", latest['Fungi'], " #/L")
        with col3:
            render_metric(col3, "Pollen", latest['Pollen'], " #/L")
        with col4:
            render_metric(
                col4, 
                "Bioaerosol Index", 
                latest['BioIndex'], 
                "", 
                help_text="A composite indicator representing the overall bioaerosol level. "
            )

    # Tab 2: Component Trends
    with tab2:
        st.subheader("Component Concentration Over Time")
        st.caption("Tracking specific components: Bacteria, Fungi, and Pollen levels.")
        
        # Reshape data for Plotly
        melted_df = df.melt(id_vars=['Datetime'], value_vars=['Bacteria', 'Fungi', 'Pollen'], 
                            var_name='Type', value_name='Concentration')
        
        custom_colors = {
            "Bacteria": "#00CC96", 
            "Fungi": "#AB63FA",    
            "Pollen": "#FFA15A"   
        }

        fig_bio = px.line(melted_df, x='Datetime', y='Concentration', color='Type',
                          color_discrete_map=custom_colors,
                          template="plotly_white")
        
        fig_bio.update_traces(mode='lines') 
        
        # Hover display
        fig_bio.update_traces(hovertemplate="%{y:,.0f} #/L") # %{y:,.0f} displays only Y-axis value, with thousands separator, no decimals.
        
        fig_bio.update_layout(
            hovermode="x unified", 
            height=450,
            yaxis_title="Concentration (#/L)"
        )
        
        st.plotly_chart(fig_bio, width='stretch')

    # Tab 3: Index Trend
    with tab3:
        st.subheader("Bioaerosol Index Trend")
        # st.caption("Tracking specific biological components: Bacteria, Fungi, and Pollen levels.")
        
        fig_index = px.line(df, x='Datetime', y='BioIndex',
                            template="plotly_white")
        
        fig_index.update_traces(line_color='#19D3F3', mode='lines')
        
        # Hover display
        fig_index.update_traces(hovertemplate="Index: %{y:.2f}")
        
        fig_index.update_layout(hovermode="x unified", height=450, yaxis_title="Index Value")
        
        st.plotly_chart(fig_index, width='stretch')

else:
    st.warning("No data available yet. Waiting for the automation script to generate results...")
    st.info(f"Please ensure 'Automate.py' is running and processing files in: {AUTOMATION_FILE.parent}")

# Auto refresh
time.sleep(60)
st.rerun()