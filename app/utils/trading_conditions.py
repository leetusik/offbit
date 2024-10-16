from datetime import datetime

import numpy as np
import pandas as pd

from app.utils import handle_candle as hc


def get_condition(
    strategy_name: str,
    execution_time: datetime,
    holding_position: bool,
    short_historical_data: pd.DataFrame,
) -> str:
    df = resample_df(df=short_historical_data, execution_time=execution_time)
    if strategy_name == "rsi_cut_5%":
        df["price_change"] = df["open"].diff()
        # Calculate the gains and losses
        df["gain"] = np.where(df["price_change"] > 0, df["price_change"], 0)
        df["loss"] = np.where(df["price_change"] < 0, -df["price_change"], 0)
        # Calculate the average gain and average loss
        window_length = 14
        df["avg_gain"] = df["gain"].rolling(window=window_length).mean()
        df["avg_loss"] = df["loss"].rolling(window=window_length).mean()

        # Calculate the RS (Relative Strength) and RSI
        df["rs"] = df["avg_gain"] / df["avg_loss"]
        df["rsi"] = 100 - (100 / (1 + df["rs"]))

        if not holding_position:
            if df.iloc[-1]["rsi"] >= 30 and df.iloc[-2]["rsi"] < 30:
                return "buy"
            else:
                return "stay"
        else:
            if df.iloc[-1]["rsi"] <= 70 and df.iloc[-2]["rsi"] > 70:
                return "sell"
            else:
                return "hold"


def resample_df(df, execution_time):
    df.set_index("time_utc", inplace=True)

    # Assuming execution_time is a datetime object, with specific hour and minute (e.g., 13:12)
    daily_df = (
        df.resample(
            "24h",
            offset=pd.Timedelta(
                hours=execution_time.hour, minutes=execution_time.minute
            ),
            origin="epoch",
        )
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume_krw": "sum",
                "volume_market": "sum",
            }
        )
        .reset_index()
    )

    return daily_df
