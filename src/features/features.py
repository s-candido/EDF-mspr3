import pandas as pd

def aggregate_hourly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("ND", pd.NA)

    # datetime
    df["datetime"] = pd.to_datetime(
        df["date"].astype(str) + " " + df["heures"].astype(str),
        errors="coerce"
    )

    df["hour_ts"] = df["datetime"].dt.floor("h")

    numeric_cols = df.select_dtypes(include="number").columns
    non_numeric_cols = df.columns.difference(numeric_cols)

    agg_dict = {}

    for col in numeric_cols:
        agg_dict[col] = "mean"

    for col in non_numeric_cols:
        if col not in ["datetime", "hour_ts"]:
            agg_dict[col] = "first"

    hourly_df = (
        df.groupby("hour_ts")
          .agg(agg_dict)
          .reset_index()
          .rename(columns={"hour_ts": "datetime"})
    )

    return hourly_df



def create_features(df: pd.DataFrame) -> pd.DataFrame:
    df = aggregate_hourly(df)

    df["year"] = df["datetime"].dt.year
    df["hour"] = df["datetime"].dt.hour
    df["day"] = df["datetime"].dt.day
    df["month"] = df["datetime"].dt.month
    df["dayofweek"] = df["datetime"].dt.dayofweek
    df["weekend"] = df["dayofweek"].isin([5, 6]).astype(int)

    df.drop(columns=[
        "perimetre",
        "nature",
        "source_file",
        "date",
        "heures",
        "datetime"
    ], errors="ignore", inplace=True)
    
    df = df.fillna(0)

    return df

def aggregate_hourly_region(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    df["datetime"] = pd.to_datetime(
        df["date"].astype(str) + " " + df["heures"].astype(str),
        errors="coerce"
    )

    df["hour_ts"] = df["datetime"].dt.floor("h")

    numeric_cols = df.select_dtypes(include="number").columns

    agg_dict = {col: "mean" for col in numeric_cols}


    hourly_df = (
        df.groupby(["region", "hour_ts"])
          .agg(agg_dict)
          .reset_index()
          .rename(columns={"hour_ts": "datetime"})
    )

    return hourly_df


def create_region_features(df: pd.DataFrame) -> pd.DataFrame:
    df = aggregate_hourly_region(df)

    df["year"] = df["datetime"].dt.year
    df["hour"] = df["datetime"].dt.hour
    df["day"] = df["datetime"].dt.day
    df["month"] = df["datetime"].dt.month
    df["dayofweek"] = df["datetime"].dt.dayofweek
    df["weekend"] = df["dayofweek"].isin([5, 6]).astype(int)

    df.drop(columns=[
        "perimetre",
        "nature",
        "source_file",
        "date",
        "heures",
        "datetime"
    ], errors="ignore", inplace=True)

    df = df.fillna(0)

    return df

