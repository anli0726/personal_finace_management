import pandas as pd

REQUIRED_COLUMNS = {"Scenario", "MonthIndex", "CalendarYear", "MonthInYear"}


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {', '.join(sorted(missing))}")
    return df.sort_values(["Scenario", "MonthIndex"]).copy()


def aggregate_period(df: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """Aggregate monthly simulator output to monthly/quarterly/yearly snapshots."""
    if df.empty:
        return df

    freq = (freq or "M").upper()
    df = _prepare(df)

    if freq == "Q":
        df["PeriodValue"] = df["MonthIndex"] // 3
        quarter = ((df["MonthInYear"] - 1) // 3 + 1).astype(int)
        df["Period"] = df["CalendarYear"].astype(str) + " Q" + quarter.astype(str)
        return df.groupby(["Scenario", "PeriodValue"], as_index=False).last()

    if freq == "Y":
        df["PeriodValue"] = df["MonthIndex"] // 12
        df["Period"] = df["CalendarYear"].astype(str)
        return df.groupby(["Scenario", "PeriodValue"], as_index=False).last()

    df["PeriodValue"] = df["MonthIndex"]
    df["Period"] = df.get("Month", df["MonthIndex"].astype(str))
    return df
