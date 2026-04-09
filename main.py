import pandas as pd
import streamlit as st

from app.data_loader import (
    fetch_data,
    fetch_drivers,
    fetch_laps,
    fetch_pit_stop,
    fetch_race_control,
    fetch_sessions,
    fetch_stints,
)
from app.data_processor import (
    aggregate_mean_sectors,
    best_lap_per_driver,
    build_driver_color_map,
    join_laps_with_stints,
    process_lap_data,
    process_pit_stops,
    process_race_control,
    process_stints,
    session_key_for_types,
)
from app.visualizer import (
    plot_lap_times,
    plot_pit_stop,
    plot_quali_vs_race_pace,
    plot_sector_comparison,
    plot_tire_degradation,
    plot_tire_strategy,
)

st.set_page_config(page_title="Samarjit's OpenF1 Strategy Dashboard", layout="wide")

st.title("🏎️ Samarjit's OpenF1 Strategy Dashboard")
st.markdown("_Powered by OpenF1.org • Built by Samarjit Kabadi_")

col1, col2 = st.columns(2)

with col1:
    # Step 1: Select Year and Country dynamically
    available_years = [2023, 2024, 2025]
    selected_year = st.selectbox("Select Year", available_years, index=len(available_years) - 1)

    # Fetch all meetings for selected year
    all_meetings = fetch_data("meetings", {"year": selected_year})

    if all_meetings.empty:
        st.error("No meetings found for this year.")
        st.stop()

    available_countries = sorted(all_meetings["country_name"].dropna().unique())
    selected_country = st.selectbox("Select Country", available_countries)

    # Filter meetings for selected year and country
    filtered_meetings = all_meetings[all_meetings["country_name"] == selected_country].copy()
    filtered_meetings["label"] = filtered_meetings["meeting_name"] + " - " + filtered_meetings["location"]
    filtered_meetings = filtered_meetings.sort_values(by="meeting_key", ascending=False)

with col2:
    selected_meeting = st.selectbox("Select Grand Prix", filtered_meetings["label"], disabled=True)
    selected_meeting_key = filtered_meetings.loc[
        filtered_meetings["label"] == selected_meeting, "meeting_key"
    ].values[0]
    sessions = fetch_sessions(selected_meeting_key)
    selected_session = st.selectbox("Select Session", sessions["label"])
    selected_session_type = sessions.loc[sessions["label"] == selected_session, "session_type"].iloc[0]
    selected_session_key = sessions.loc[sessions["label"] == selected_session, "session_key"].values[0]

st.markdown(f"### 🏁 Session Overview: `{selected_session}`")
with st.expander("📋 Session Details", expanded=False):
    st.write(f"**Meeting Key:** {selected_meeting_key}")
    st.write(f"**Session Key:** {selected_session_key}")

# Fetch and preprocess driver info
driver_df = fetch_drivers(selected_session_key)
driver_df["driver_number"] = driver_df["driver_number"].astype(str)
driver_color_map = build_driver_color_map(driver_df)
driver_info = driver_df[["driver_number", "name_acronym"]]

processed_df = pd.DataFrame()

# Lap Times
with st.expander(f"📈 Lap Time Chart for {selected_session_type} at {selected_country} {selected_year}",
                 expanded=True):
    lap_df = fetch_laps(selected_session_key)
    processed_df = process_lap_data(lap_df)

    # Merge name_acronym into the lap data
    processed_df["driver_number"] = processed_df["driver_number"].astype(str)
    processed_df = processed_df.merge(driver_info, on="driver_number", how="left")

    if processed_df.empty:
        st.warning("No lap time data found.")
    else:
        fig = plot_lap_times(processed_df, driver_color_map)
        st.plotly_chart(fig, use_container_width=True)

        fastest = best_lap_per_driver(processed_df)
        if not fastest.empty and "name_acronym" in fastest.columns:
            show = fastest[["name_acronym", "lap_number", "lap_duration"]].copy()
            show = show.sort_values("lap_duration")
            show["Time (MM:SS.mmm)"] = show["lap_duration"].map(
                lambda s: f"{int(s // 60):02}:{s % 60:06.3f}"
            )
            show = show.drop(columns=["lap_duration"]).rename(columns={
                "name_acronym": "Driver",
                "lap_number": "Lap",
            })
            st.caption("Fastest clean lap per driver (excludes pit-out laps)")
            st.dataframe(show, use_container_width=True, hide_index=True)

# Tire Strategy
with st.expander(f"🛞 Tire strategy for {selected_session_type} at {selected_country} {selected_year}", expanded=True):
    stints = fetch_stints(selected_session_key)
    stints_df = process_stints(stints)
    stints_df["driver_number"] = stints_df["driver_number"].astype(str)
    stints_df = stints_df.merge(driver_info, on="driver_number", how="left")

    if stints_df.empty:
        st.warning("No tire strategy data found.")
    else:
        fig = plot_tire_strategy(stints_df, driver_color_map)
        st.plotly_chart(fig, use_container_width=True)

# Pit Stops
with st.expander(f"⏱  Pit stop durations for {selected_session_type} at {selected_country} {selected_year}",
                 expanded=True):
    pit_stop = fetch_pit_stop(selected_session_key)
    pit_stop_df = process_pit_stops(pit_stop)
    pit_stop_df["driver_number"] = pit_stop_df["driver_number"].astype(str)
    pit_stop_df = pit_stop_df.merge(driver_info, on="driver_number", how="left")

    if pit_stop_df.empty:
        st.warning("No pit stop data found.")
    else:
        fig = plot_pit_stop(pit_stop_df, driver_color_map)
        st.plotly_chart(fig, use_container_width=True)

# --- Extensions (README): degradation, quali vs race, events, sectors ---

with st.expander(
    f"📉 Tire degradation (within stint) — {selected_country} {selected_year}",
    expanded=False,
):
    st.caption(
        "Lap time vs lap index inside each stint. Rising times often reflect tire wear "
        "(fuel load and traffic also matter in a race)."
    )
    lap_raw = fetch_laps(selected_session_key)
    st_raw = fetch_stints(selected_session_key)
    lap_p = process_lap_data(lap_raw)
    st_p = process_stints(st_raw)
    joined = join_laps_with_stints(lap_p, st_p)
    if joined.empty:
        st.warning("Need lap and stint data for degradation view.")
    else:
        joined["driver_number"] = joined["driver_number"].astype(str)
        joined = joined.merge(driver_info, on="driver_number", how="left")
        fig = plot_tire_degradation(joined, driver_color_map)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough stint-linked laps to plot degradation.")

with st.expander(
    f"⚖️ Qualifying vs race pace (best lap) — {selected_country} {selected_year}",
    expanded=False,
):
    st.caption(
        "Compares each driver's best clean lap in qualifying against their best clean lap "
        "in the race (or Sprint vs Sprint Qualifying on sprint weekends)."
    )
    quali_key = session_key_for_types(sessions, ["Qualifying", "Sprint Qualifying"])
    race_key = session_key_for_types(sessions, ["Race", "Sprint"])
    if not quali_key or not race_key or quali_key == race_key:
        st.info("Need distinct qualifying and race sessions for this meeting.")
    else:
        q_laps = process_lap_data(fetch_laps(quali_key))
        r_laps = process_lap_data(fetch_laps(race_key))
        qb = best_lap_per_driver(q_laps)
        rb = best_lap_per_driver(r_laps)
        if qb.empty or rb.empty:
            st.warning("Missing lap timing for quali or race session.")
        else:
            qb = qb[["driver_number", "lap_duration"]].rename(columns={"lap_duration": "best_quali"})
            rb = rb[["driver_number", "lap_duration"]].rename(columns={"lap_duration": "best_race"})
            qb["driver_number"] = qb["driver_number"].astype(str)
            rb["driver_number"] = rb["driver_number"].astype(str)
            pace = qb.merge(rb, on="driver_number", how="inner")
            pace = pace.merge(driver_info, on="driver_number", how="left")
            pace = pace.dropna(subset=["name_acronym"])
            fig = plot_quali_vs_race_pace(pace, driver_color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

with st.expander(
    f"🚩 Race control & flags — {selected_session_type} at {selected_country} {selected_year}",
    expanded=False,
):
    rc = fetch_race_control(selected_session_key)
    rc = process_race_control(rc)
    if rc.empty:
        st.info("No race control messages for this session.")
    else:
        show_cols = [c for c in ["date", "category", "message", "flag", "lap_number", "driver_number"] if c in rc.columns]
        st.dataframe(rc[show_cols], use_container_width=True, hide_index=True)

with st.expander(
    f"📐 Sector time analytics — {selected_session_type} at {selected_country} {selected_year}",
    expanded=False,
):
    st.caption(
        "Mean sector times (S1–S3) per driver across clean laps. "
        "From OpenF1 `/laps`: `duration_sector_1` … `duration_sector_3`."
    )
    lap_raw = fetch_laps(selected_session_key)
    lap_p = process_lap_data(lap_raw)
    lap_p["driver_number"] = lap_p["driver_number"].astype(str)
    sec = aggregate_mean_sectors(lap_p)
    if sec.empty:
        st.info("Sector durations not available for this session (common during some races).")
    else:
        sec = sec.merge(driver_info, on="driver_number", how="left")
        sec = sec.dropna(subset=["name_acronym"])
        fig = plot_sector_comparison(sec, driver_color_map)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

if processed_df.empty:
    st.info("Lap data is not available for this session.")
