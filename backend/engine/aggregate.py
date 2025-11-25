import pandas as pd


def _supports_new_schema(df: pd.DataFrame) -> bool:
    return {"MonthIndex", "CalendarYear", "MonthInYear"}.issubset(df.columns)


def aggregate_period(df: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """Aggregate monthly simulator output to M/Q/Y frequencies with ordering metadata."""
    if df.empty:
        return df

    freq = (freq or "M").upper()
    df = df.copy()

    if _supports_new_schema(df):
        df = df.sort_values(["Scenario", "MonthIndex"])
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

    # Fallback for legacy simulator output
    df = df.sort_values(["Scenario", "MonthIndex"])
    if freq == "Q":
        if "Label_Q" not in df.columns:
            raise KeyError("Quarterly aggregation requires 'Label_Q' column.")
        df["PeriodValue"] = df["MonthIndex"] // 3
        grouped = df.groupby(["Scenario", "PeriodValue"], as_index=False).last()
        grouped["Period"] = grouped["Label_Q"]
        return grouped
    if freq == "Y":
        if "Label_Y" not in df.columns:
            raise KeyError("Yearly aggregation requires 'Label_Y' column.")
        df["PeriodValue"] = df["YearIndex"]
        grouped = df.groupby(["Scenario", "PeriodValue"], as_index=False).last()
        grouped["Period"] = grouped["Label_Y"]
        return grouped
    if "Label_M" not in df.columns:
        raise KeyError("Monthly aggregation requires 'Label_M' column.")
    df["PeriodValue"] = df["MonthIndex"]
    df["Period"] = df["Label_M"]
    return df
