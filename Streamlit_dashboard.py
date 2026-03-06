import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from pathlib import Path


# Page Configuration
st.set_page_config(
    page_title="Indoor Air Quality",
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

BASE_DIR = Path(__file__).resolve().parent
PREDICTION_FILE = BASE_DIR / "predictions_log.csv"
ACTUAL_PM_FILE = BASE_DIR / "kaiterra_data.csv"
REFRESH_SECONDS = 60
DEFAULT_PAST_HOURS = 1
DEFAULT_FUTURE_HOURS = 1

POLLUTANTS = ["Bacteria", "Fungi", "Pollen", "PM2.5", "PM10"]
IAQ_LABELS = {1: "Light Green", 2: "Green", 3: "Yellow", 4: "Red"}
IAQ_COLORS = {1: "#B8E986", 2: "#7ED321", 3: "#F8E71C", 4: "#D0021B"}
IAQ_THRESHOLDS = {
    "Bacteria": [108925, 217850, 435700],
    "PM2.5": [7, 14, 70],
    "PM10": [10, 20, 100]
}


@st.cache_data(ttl=10)
def load_prediction_data():
    if not PREDICTION_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(PREDICTION_FILE)
        if "Timestamp" in df.columns:
            df["Datetime"] = pd.to_datetime(df["Timestamp"], utc=True).dt.tz_convert(None)
        elif {"Date", "Time"}.issubset(df.columns):
            df["Datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], utc=True).dt.tz_convert(None)
        else:
            return pd.DataFrame()
        cols = ["Datetime"] + [c for c in POLLUTANTS if c in df.columns]
        for col in ["PM2.5_actual", "PM10_actual"]:
            if col in df.columns:
                cols.append(col)
        return df[cols].dropna(subset=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
    except Exception as e:
        st.error(f"Error reading predictions: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=10)
def load_actual_pm_data(full_df):
    actual_cols = ["Datetime", "PM2.5_actual", "PM10_actual"]
    if not full_df.empty and all(c in full_df.columns for c in actual_cols):
        actual_df = full_df[actual_cols].rename(columns={
            "PM2.5_actual": "PM2.5",
            "PM10_actual": "PM10"
        })
        return actual_df.dropna(subset=["Datetime"]).dropna(subset=["PM2.5", "PM10"], how="all").sort_values("Datetime").reset_index(drop=True)
    if not ACTUAL_PM_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(ACTUAL_PM_FILE)
        if "timestamp" in df.columns:
            df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(None)
        elif {"Date", "Time"}.issubset(df.columns):
            df["Datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], utc=True).dt.tz_convert(None)
        else:
            return pd.DataFrame()
        if "rpm25c" in df.columns:
            df["PM2.5"] = df["rpm25c"]
        if "rpm10c" in df.columns:
            df["PM10"] = df["rpm10c"]
        cols = ["Datetime"] + [c for c in ["PM2.5", "PM10"] if c in df.columns]
        return df[cols].dropna(subset=["Datetime"]).dropna(subset=["PM2.5", "PM10"], how="all").sort_values("Datetime").reset_index(drop=True)
    except Exception as e:
        st.error(f"Error reading actual PM data: {e}")
        return pd.DataFrame()


def pick_value_at_time(df, time_col, value_col, target_time):
    if df.empty or value_col not in df.columns:
        return None
    df_sorted = df.sort_values(time_col)
    past = df_sorted[df_sorted[time_col] <= target_time]
    if not past.empty:
        return past.iloc[-1][value_col]
    return df_sorted.iloc[0][value_col]


def classify_series(series, thresholds):
    return pd.Series(
        pd.cut(
            series,
            bins=[-float("inf"), thresholds[0], thresholds[1], thresholds[2], float("inf")],
            labels=[1, 2, 3, 4]
        )
    ).astype("float")


def align_levels_to_times(times, level_series):
    if level_series is None or len(times) == 0:
        return pd.Series([None] * len(times))
    levels_df = pd.DataFrame({"Datetime": level_series.index, "Level": level_series.values}).dropna()
    times_df = pd.DataFrame({"Datetime": pd.to_datetime(times)})
    if levels_df.empty:
        return pd.Series([None] * len(times_df))
    levels_df = levels_df.sort_values("Datetime")
    times_df = times_df.sort_values("Datetime")
    aligned = pd.merge_asof(times_df, levels_df, on="Datetime", direction="backward")
    return aligned["Level"].reset_index(drop=True)


def add_level_line_traces(fig, times, values, levels, dash, showlegend=True, legendgroup="IAQ"):
    if len(times) == 0:
        return
    x_vals = pd.Series(pd.to_datetime(times)).reset_index(drop=True)
    y_vals = pd.Series(values).reset_index(drop=True)
    level_vals = pd.Series(levels).reset_index(drop=True)
    if len(x_vals) != len(y_vals) or len(x_vals) != len(level_vals):
        min_len = min(len(x_vals), len(y_vals), len(level_vals))
        x_vals = x_vals.iloc[:min_len]
        y_vals = y_vals.iloc[:min_len]
        level_vals = level_vals.iloc[:min_len]
    for level, label in IAQ_LABELS.items():
        mask = level_vals == level
        if mask.any():
            series = y_vals.where(mask)
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=series,
                mode="lines",
                name=label,
                legendgroup=legendgroup,
                showlegend=showlegend,
                line=dict(color=IAQ_COLORS[level], dash=dash),
                connectgaps=False,
                hovertemplate="%{x|%Y-%m-%d %H:%M:%S}<br>%{y:.2f}<extra></extra>"
            ))


def add_history_forecast_legend(fig, label):
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="lines",
        name="History",
        line=dict(color="#555555", dash="solid")
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="lines",
        name="Forecast",
        line=dict(color="#555555", dash="dash")
    ))


def apply_time_window(fig, focus_time):
    if focus_time is None:
        return
    start = focus_time - pd.Timedelta(hours=DEFAULT_PAST_HOURS)
    end = focus_time + pd.Timedelta(hours=DEFAULT_FUTURE_HOURS)
    fig.update_layout(
        xaxis=dict(range=[start, end]),
        dragmode="pan"
    )


def get_latest_prediction_start(pred_df):
    if pred_df.empty:
        return None
    pred_sorted = pred_df.sort_values("Datetime")
    if len(pred_sorted) >= 60:
        window = pred_sorted.iloc[-60:]
        return window["Datetime"].min()
    return pred_sorted["Datetime"].min()


st.sidebar.title("Control Panel")

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

st.sidebar.info(f"System updates automatically every {REFRESH_SECONDS} seconds.")


st.title("Indoor Air Quality")

full_df = load_prediction_data()
pred_df = full_df[full_df["Bacteria"].notna()] if not full_df.empty and "Bacteria" in full_df.columns else full_df
actual_pm_df = load_actual_pm_data(full_df)

if not pred_df.empty:
    current_time = None
    if not actual_pm_df.empty:
        current_time = actual_pm_df["Datetime"].max()
    else:
        current_time = pred_df["Datetime"].max()
    prediction_start_time = get_latest_prediction_start(pred_df)
    
    pred_roll = pred_df.set_index("Datetime").rolling("10min", min_periods=1).mean()
    bacteria_idx = classify_series(pred_roll["Bacteria"], IAQ_THRESHOLDS["Bacteria"])
    pred_pm25_idx = classify_series(pred_roll["PM2.5"], IAQ_THRESHOLDS["PM2.5"])
    pred_pm10_idx = classify_series(pred_roll["PM10"], IAQ_THRESHOLDS["PM10"])

    actual_pm25_idx = None
    actual_pm10_idx = None
    if not actual_pm_df.empty:
        actual_roll = actual_pm_df.set_index("Datetime").rolling("10min", min_periods=1).mean()
        actual_pm25_idx = classify_series(actual_roll["PM2.5"], IAQ_THRESHOLDS["PM2.5"])
        actual_pm10_idx = classify_series(actual_roll["PM10"], IAQ_THRESHOLDS["PM10"])

    st.markdown(f"**Last Updated:** {current_time}")
    st.divider()

    tab1, tab2, tab3 = st.tabs(["Current Readings", "Component Trends", "IAQ Index"])

    
    with tab1:
        st.subheader("Current Readings")
        col1, col2, col3, col4, col5 = st.columns(5)

        def render_metric(col, label, value, unit="", help_text=None, index_label=None, index_color=None):
            with col:
                help_html = f'<span title="{help_text}" style="cursor:help; font-size:1em">ⓘ</span>' if help_text else ""
                st.markdown(f"<div style='color: #666; font-size: 16px;'>{label} {help_html}</div>", unsafe_allow_html=True)
                if value is None or pd.isna(value):
                    display_value = "—"
                else:
                    display_value = f"{value:.0f}"
                badge = ""
                if index_label and index_color:
                    badge = f"<span style='background:{index_color}; color:#000; padding:2px 6px; border-radius:6px; font-size:12px; margin-left:6px;'>IAQ {index_label}</span>"
                st.markdown(f"<div style='font-size: 36px; margin-top: -5px;'>{display_value} <span style='font-size: 16px; color: #999; font-weight: normal;'>{unit}</span>{badge}</div>", unsafe_allow_html=True)

        bacteria_now = pick_value_at_time(pred_df, "Datetime", "Bacteria", current_time)
        fungi_now = pick_value_at_time(pred_df, "Datetime", "Fungi", current_time)
        pollen_now = pick_value_at_time(pred_df, "Datetime", "Pollen", current_time)
        pm25_now = None
        pm10_now = None
        if not actual_pm_df.empty:
            pm25_now = pick_value_at_time(actual_pm_df, "Datetime", "PM2.5", current_time)
            pm10_now = pick_value_at_time(actual_pm_df, "Datetime", "PM10", current_time)
        else:
            pm25_now = pick_value_at_time(pred_df, "Datetime", "PM2.5", current_time)
            pm10_now = pick_value_at_time(pred_df, "Datetime", "PM10", current_time)

        pm25_idx = actual_pm25_idx if actual_pm25_idx is not None else pred_pm25_idx
        pm10_idx = actual_pm10_idx if actual_pm10_idx is not None else pred_pm10_idx

        bacteria_level = bacteria_idx.iloc[-1] if not bacteria_idx.empty else None
        pm25_level = pm25_idx.iloc[-1] if not pm25_idx.empty else None
        pm10_level = pm10_idx.iloc[-1] if not pm10_idx.empty else None

        bacteria_label = IAQ_LABELS.get(int(bacteria_level)) if bacteria_level and not pd.isna(bacteria_level) else None
        pm25_label = IAQ_LABELS.get(int(pm25_level)) if pm25_level and not pd.isna(pm25_level) else None
        pm10_label = IAQ_LABELS.get(int(pm10_level)) if pm10_level and not pd.isna(pm10_level) else None

        bacteria_color = IAQ_COLORS.get(int(bacteria_level)) if bacteria_level and not pd.isna(bacteria_level) else None
        pm25_color = IAQ_COLORS.get(int(pm25_level)) if pm25_level and not pd.isna(pm25_level) else None
        pm10_color = IAQ_COLORS.get(int(pm10_level)) if pm10_level and not pd.isna(pm10_level) else None

        with col1:
            render_metric(col1, "Bacteria", bacteria_now, " #/L", index_label=bacteria_label, index_color=bacteria_color)
        with col2:
            render_metric(col2, "Fungi", fungi_now, " #/L")
        with col3:
            render_metric(col3, "Pollen", pollen_now, " #/L")
        with col4:
            render_metric(col4, "PM2.5", pm25_now, " µg/m³", index_label=pm25_label, index_color=pm25_color)
        with col5:
            render_metric(col5, "PM10", pm10_now, " µg/m³", index_label=pm10_label, index_color=pm10_color)

    with tab2:
        st.subheader("Component Concentration Over Time")
        st.caption("Colored based on IAQ index")

        past = pred_df[pred_df["Datetime"] < prediction_start_time]
        future = pred_df[pred_df["Datetime"] >= prediction_start_time]

        bacteria_levels = align_levels_to_times(pred_df["Datetime"], bacteria_idx)
        st.subheader("Bacteria Trend")
        fig_bacteria = go.Figure()
        add_level_line_traces(
            fig_bacteria,
            past["Datetime"],
            past["Bacteria"],
            align_levels_to_times(past["Datetime"], bacteria_idx),
            "solid",
            showlegend=False
        )
        add_level_line_traces(
            fig_bacteria,
            future["Datetime"],
            future["Bacteria"],
            align_levels_to_times(future["Datetime"], bacteria_idx),
            "dash",
            showlegend=False
        )
        add_history_forecast_legend(fig_bacteria, "Bacteria")
        fig_bacteria.update_layout(
            hovermode="x unified",
            height=420,
            yaxis_title="Concentration (#/L)",
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        apply_time_window(fig_bacteria, prediction_start_time)
        st.plotly_chart(fig_bacteria, use_container_width=True)

        st.subheader("Fungi Trend")
        fig_fungi = go.Figure()
        fig_fungi.add_trace(go.Scatter(
            x=past["Datetime"], y=past["Fungi"], mode="lines",
            name="Fungi History", showlegend=False, line=dict(color="#7f7f7f", dash="solid"),
            hovertemplate="%{x|%Y-%m-%d %H:%M:%S}<br>%{y:.2f}<extra></extra>"
        ))
        fig_fungi.add_trace(go.Scatter(
            x=future["Datetime"], y=future["Fungi"], mode="lines",
            name="Fungi Forecast", showlegend=False, line=dict(color="#7f7f7f", dash="dash"),
            hovertemplate="%{x|%Y-%m-%d %H:%M:%S}<br>%{y:.2f}<extra></extra>"
        ))
        add_history_forecast_legend(fig_fungi, "Fungi")
        fig_fungi.update_layout(
            hovermode="x unified",
            height=380,
            yaxis_title="Concentration (#/L)",
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        apply_time_window(fig_fungi, prediction_start_time)
        st.plotly_chart(fig_fungi, use_container_width=True)

        st.subheader("Pollen Trend")
        fig_pollen = go.Figure()
        fig_pollen.add_trace(go.Scatter(
            x=past["Datetime"], y=past["Pollen"], mode="lines",
            name="Pollen History", showlegend=False, line=dict(color="#9a9a9a", dash="solid"),
            hovertemplate="%{x|%Y-%m-%d %H:%M:%S}<br>%{y:.2f}<extra></extra>"
        ))
        fig_pollen.add_trace(go.Scatter(
            x=future["Datetime"], y=future["Pollen"], mode="lines",
            name="Pollen Forecast", showlegend=False, line=dict(color="#9a9a9a", dash="dash"),
            hovertemplate="%{x|%Y-%m-%d %H:%M:%S}<br>%{y:.2f}<extra></extra>"
        ))
        add_history_forecast_legend(fig_pollen, "Pollen")
        fig_pollen.update_layout(
            hovermode="x unified",
            height=380,
            yaxis_title="Concentration (#/L)",
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        apply_time_window(fig_pollen, prediction_start_time)
        st.plotly_chart(fig_pollen, use_container_width=True)

        st.subheader("PM2.5 Trend")
        # st.caption("PM2.5: actual measurements for history, model predictions for future.")
        future_pred = pred_df[pred_df["Datetime"] >= prediction_start_time]
        fig_pm25 = go.Figure()
        if not actual_pm_df.empty:
            pm25_levels_past = align_levels_to_times(actual_pm_df["Datetime"], actual_pm25_idx)
            add_level_line_traces(fig_pm25, actual_pm_df["Datetime"], actual_pm_df["PM2.5"], pm25_levels_past, "solid", showlegend=False)
        if not future_pred.empty:
            pm25_levels_future = align_levels_to_times(future_pred["Datetime"], pred_pm25_idx)
            add_level_line_traces(fig_pm25, future_pred["Datetime"], future_pred["PM2.5"], pm25_levels_future, "dash", showlegend=False)
        add_history_forecast_legend(fig_pm25, "PM2.5")
        fig_pm25.update_layout(
            hovermode="x unified",
            height=420,
            yaxis_title="Concentration (µg/m³)",
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        apply_time_window(fig_pm25, prediction_start_time)
        st.plotly_chart(fig_pm25, use_container_width=True)

        st.subheader("PM10 Trend")
        # st.caption("PM10: actual measurements for history, model predictions for future.")
        fig_pm10 = go.Figure()
        if not actual_pm_df.empty:
            pm10_levels_past = align_levels_to_times(actual_pm_df["Datetime"], actual_pm10_idx)
            add_level_line_traces(fig_pm10, actual_pm_df["Datetime"], actual_pm_df["PM10"], pm10_levels_past, "solid", showlegend=False)
        if not future_pred.empty:
            pm10_levels_future = align_levels_to_times(future_pred["Datetime"], pred_pm10_idx)
            add_level_line_traces(fig_pm10, future_pred["Datetime"], future_pred["PM10"], pm10_levels_future, "dash", showlegend=False)
        add_history_forecast_legend(fig_pm10, "PM10")
        fig_pm10.update_layout(
            hovermode="x unified",
            height=420,
            yaxis_title="Concentration (µg/m³)",
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        apply_time_window(fig_pm10, prediction_start_time)
        st.plotly_chart(fig_pm10, use_container_width=True)

    with tab3:
        st.subheader("Air Quality Summary")
        summary_times = pd.concat([pred_df["Datetime"], actual_pm_df["Datetime"]], ignore_index=True).sort_values().dropna().unique()
        bacteria_levels_summary = align_levels_to_times(summary_times, bacteria_idx)
        if actual_pm_df.empty:
            pm25_series = pred_pm25_idx
            pm10_series = pred_pm10_idx
        else:
            pm25_series = pd.concat([actual_pm25_idx, pred_pm25_idx[pred_pm25_idx.index > current_time]]).sort_index()
            pm10_series = pd.concat([actual_pm10_idx, pred_pm10_idx[pred_pm10_idx.index > current_time]]).sort_index()
        pm25_levels_summary = align_levels_to_times(summary_times, pm25_series)
        pm10_levels_summary = align_levels_to_times(summary_times, pm10_series)
        overall_levels = pd.concat([
            pd.Series(bacteria_levels_summary),
            pd.Series(pm25_levels_summary),
            pd.Series(pm10_levels_summary)
        ], axis=1).max(axis=1)
        fig_summary = go.Figure()
        add_level_line_traces(fig_summary, summary_times, overall_levels, overall_levels, "solid", showlegend=True)
        fig_summary.update_layout(
            hovermode="x unified",
            height=420,
            yaxis_title="IAQ Level (1-4)",
            template="plotly_white",
            showlegend=False,
            yaxis=dict(range=[0.5, 4.5], tickmode="array", tickvals=[1, 2, 3, 4], ticktext=list(IAQ_LABELS.values()))
        )
        apply_time_window(fig_summary, prediction_start_time)
        st.plotly_chart(fig_summary, use_container_width=True)

        window_start = prediction_start_time - pd.Timedelta(hours=DEFAULT_PAST_HOURS)
        window_end = prediction_start_time + pd.Timedelta(hours=DEFAULT_FUTURE_HOURS)
        window_mask = (pd.Series(summary_times) >= window_start) & (pd.Series(summary_times) <= window_end)
        window_levels = pd.Series(overall_levels)[window_mask]
        level_counts = window_levels.value_counts().reindex([1, 2, 3, 4]).fillna(0)
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Bar(
            x=[IAQ_LABELS[i] for i in [1, 2, 3, 4]],
            y=level_counts.values,
            marker_color=[IAQ_COLORS[i] for i in [1, 2, 3, 4]],
            name="Time Share"
        ))
        fig_dist.update_layout(
            height=300,
            template="plotly_white",
            yaxis_title="Count",
            showlegend=False
        )
        st.plotly_chart(fig_dist, use_container_width=True)

else:
    st.warning("No data available yet. Waiting for the automation script to generate results...")
    st.info(f"Please ensure 'automated_prediction.py' is running and writing: {PREDICTION_FILE}")

# Auto refresh
time.sleep(REFRESH_SECONDS)
st.rerun()
