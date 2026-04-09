from typing import Optional

import pandas as pd


def process_lap_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and prepare lap data for visualization.

    - Filters out laps without duration.
    - Sorts by driver number and lap number.

    Args:
        df (pd.DataFrame): Raw lap data from API.

    Returns:
        pd.DataFrame: Cleaned and sorted lap data.
    """
    if df.empty:
        return df

    df = df[df['lap_duration'].notna()]  # Drop laps missing duration info (i.e. retirements or red flags)
    df = df.sort_values(['driver_number', 'lap_number'])  # Sort for logical order in lap-time visualization
    return df


def process_stints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare stint data for the tire strategy chart.

    - Sorts by driver and stint number.
    - Fills missing compound values with "Unknown".
    - Adds a lap_count column.

    Args:
        df (pd.DataFrame): Raw stint data.

    Returns:
        pd.DataFrame: Cleaned stint data with compound info and lap counts.
    """
    if df.empty:
        return df

    df = df.sort_values(by=["driver_number", "stint_number"])  # Sort by driver and stint sequence
    df["compound"] = df["compound"].fillna("Unknown")  # Replace missing compound with placeholder
    df["lap_count"] = df["lap_end"] - df["lap_start"] + 1  # Compute total laps in each stint
    return df


def process_pit_stops(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare pit stop data for charting.

    - Filters out entries without a recorded duration.
    - Sorts by driver and lap number.

    Args:
        df (pd.DataFrame): Raw pit stop data.

    Returns:
        pd.DataFrame: Cleaned and sorted pit stop data.
    """
    if df.empty:
        return df

    df = df[df["pit_duration"].notna()]  # Only keep pit stops with a recorded duration
    df = df.sort_values(by=["driver_number", "lap_number"])  # Organize by race sequence
    return df


def build_driver_color_map(driver_df: pd.DataFrame) -> dict:
    """
    Build a dictionary that maps driver acronyms to their team color.

    Args:
        driver_df (pd.DataFrame): DataFrame with driver and team information.

    Returns:
        dict: Dictionary mapping name_acronym to team_colour.
    """
    if driver_df.empty:
        return {}

    # Format team colors to always start with '#' for valid CSS color input
    driver_df["team_colour"] = driver_df["team_colour"].apply(
        lambda x: f"#{x}" if not str(x).startswith("#") else x
    )
    # Plotly prefers string keys; ensure driver_number is string
    driver_df["driver_number"] = driver_df["driver_number"].astype(str)

    # Build the mapping from acronym to team color
    color_map = {
        str(row["name_acronym"]): row["team_colour"]
        for _, row in driver_df.iterrows()
        if pd.notna(row["team_colour"])
    }

    return color_map


def join_laps_with_stints(laps_df: pd.DataFrame, stints_df: pd.DataFrame) -> pd.DataFrame:
    """Attach compound and lap-within-stint index to each lap row."""
    if laps_df.empty or stints_df.empty:
        return pd.DataFrame()

    laps = laps_df.copy()
    stints = stints_df.copy()
    laps["driver_number"] = laps["driver_number"].astype(str)
    stints["driver_number"] = stints["driver_number"].astype(str)

    rows = []
    for _, lap in laps.iterrows():
        dn = lap["driver_number"]
        ln = lap["lap_number"]
        mask = (
            (stints["driver_number"] == dn)
            & (stints["lap_start"] <= ln)
            & (stints["lap_end"] >= ln)
        )
        hit = stints[mask]
        if hit.empty:
            rows.append({**lap.to_dict(), "compound": None, "stint_number": None, "lap_in_stint": None})
        else:
            s = hit.iloc[0]
            lap_in = int(ln - s["lap_start"] + 1)
            rows.append({
                **lap.to_dict(),
                "compound": s.get("compound"),
                "stint_number": s.get("stint_number"),
                "lap_in_stint": lap_in,
            })
    return pd.DataFrame(rows)


def best_lap_per_driver(lap_df: pd.DataFrame) -> pd.DataFrame:
    if lap_df.empty:
        return lap_df
    df = lap_df[lap_df["lap_duration"].notna()].copy()
    if "is_pit_out_lap" in df.columns:
        df = df[~df["is_pit_out_lap"].fillna(False).astype(bool)]
    if df.empty:
        return df
    idx = df.groupby("driver_number")["lap_duration"].idxmin()
    return df.loc[idx].drop_duplicates(subset=["driver_number"])


def aggregate_mean_sectors(lap_df: pd.DataFrame) -> pd.DataFrame:
    """Mean sector times per driver (clean laps only)."""
    if lap_df.empty:
        return lap_df
    sec_cols = ["duration_sector_1", "duration_sector_2", "duration_sector_3"]
    if not all(c in lap_df.columns for c in sec_cols):
        return pd.DataFrame()
    df = lap_df.copy()
    if "is_pit_out_lap" in df.columns:
        df = df[~df["is_pit_out_lap"].fillna(False).astype(bool)]
    df = df.dropna(subset=sec_cols + ["lap_duration"], how="any")
    if df.empty:
        return df
    agg = df.groupby("driver_number", as_index=False)[sec_cols].mean()
    agg["driver_number"] = agg["driver_number"].astype(str)
    return agg


def process_race_control(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "date" in out.columns:
        out = out.sort_values("date")
    return out


def session_key_for_types(sessions_df: pd.DataFrame, session_types: list) -> Optional[int]:
    for st in session_types:
        hit = sessions_df[sessions_df["session_type"] == st]
        if not hit.empty:
            return int(hit.iloc[0]["session_key"])
    return None
