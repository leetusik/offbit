from datetime import datetime

import numpy as np
import pandas as pd

from app.utils import handle_candle as hc


def get_condition(
    strategy_name: str,
    execution_time: datetime,
    holding_position: bool,
    short_historical_data: pd.DataFrame,
    manual_start=False,
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

        if manual_start:
            # Implement RSI strategy for long positions only
            df["signal"] = 0  # Default to no position
            for i in range(1, len(df)):
                # 매수 조건
                if (df.loc[i, "rsi"] >= 30) and (df.loc[i - 1, "rsi"] < 30):
                    df.loc[i, "signal"] = 1
                # 매도 조건
                elif (df.loc[i, "rsi"] <= 70) and (df.loc[i - 1, "rsi"] > 70):
                    df.loc[i, "signal"] = -1
            # Manage positions with stop loss, take profit, and sell signal
            df["position"] = 0
            df["highest_price"] = np.nan
            df["exit_price"] = np.nan
            hp = False

            for i in range(1, len(df)):
                if df["signal"].iloc[i] == 1 and not hp:
                    # Enter position
                    df.loc[i, "position"] = 1
                    df.loc[i, "highest_price"] = df.loc[i, "open"]
                    hp = True
                elif hp:
                    # Calculate percentage change since entry
                    # df['highest_price'].iloc[i] = max(df['highest_price'].iloc[i-1], df['open'].iloc[i])
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i - 1, "open"]
                    )
                    highest_price = df["highest_price"].iloc[i]
                    current_price = df["open"].iloc[i]
                    percent_change = (
                        (current_price - highest_price) / highest_price * 100
                    )

                    if df["signal"].iloc[i] == -1:  # Sell signal condition
                        # print(f"cond1 on{i}")
                        df.loc[i, "position"] = 0
                        df.loc[i, "exit_price"] = current_price
                        hp = False
                    elif percent_change <= -5:  # Stop loss condition
                        # print(f"cond2 on{i}")
                        df.loc[i, "position"] = 0
                        df.loc[i, "exit_price"] = current_price
                        hp = False
                    else:
                        # Continue holding the position if no sell conditions are met
                        df.loc[i, "position"] = df.loc[i - 1, "position"]
            if not holding_position:
                if df.iloc[-1]["position"] == 1:
                    return "buy"
                else:
                    return "stay"
            else:
                if df.iloc[-1]["position"] == 0:
                    return "sell"
                else:
                    return "hold"

        else:
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

    elif strategy_name == "ma_50":
        df["50_ma"] = df["open"].rolling(window=50).mean()
        if manual_start:
            df["signal"] = 0  # Default to no position
            for i in range(50, len(df)):
                # Buy condition
                if (
                    df.loc[i, "open"] >= df.loc[i, "50_ma"]
                    and df.loc[i - 1, "open"] < df.loc[i - 1, "50_ma"]
                ):
                    df.loc[i, "signal"] = 1
                # Sell condition
                elif (
                    df.loc[i, "open"] < df.loc[i, "50_ma"]
                    and df.loc[i - 1, "open"] >= df.loc[i - 1, "50_ma"]
                ):
                    df.loc[i, "signal"] = -1

            # Manage positions
            df["position"] = 0
            hp = False

            for i in range(1, len(df)):
                if df.loc[i, "signal"] == 1 and not hp:
                    df.loc[i, "position"] = 1
                    hp = True
                elif df.loc[i, "signal"] == -1 and hp:
                    df.loc[i, "position"] = 0
                    hp = False
                else:
                    df.loc[i, "position"] = df.loc[i - 1, "position"]

            if not holding_position:
                if df.iloc[-1]["position"] == 1:
                    return "buy"
                else:
                    return "stay"
            else:
                if df.iloc[-1]["position"] == 0:
                    return "sell"
                else:
                    return "hold"
        else:
            if not holding_position:
                if (
                    df.iloc[-1]["open"] >= df.iloc[-1]["50_ma"]
                    and df.iloc[-2]["open"] < df.iloc[-2]["50_ma"]
                ):
                    return "buy"
                else:
                    return "stay"
            else:
                if (
                    df.iloc[-1]["open"] <= df.iloc[-1]["50_ma"]
                    and df.iloc[-2]["open"] > df.iloc[-2]["50_ma"]
                ):
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
