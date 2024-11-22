from datetime import datetime

import numpy as np
import pandas as pd

# from app.models import UserStrategy
from app.utils.handle_candle import resample_df


def get_condition(
    # user_strategy: UserStrategy,
    strategy_name: str,
    execution_time: datetime,
    holding_position: bool,
    param1: int,
    param2: int | None,
    stop_loss: int | None,
    short_historical_data: pd.DataFrame,
) -> str:
    df = resample_df(df=short_historical_data, execution_time=execution_time)
    if stop_loss:
        stop_loss_pct = stop_loss / 100

    if strategy_name == "Relative_Strength_Index":
        # 2
        window_length = param1
        # Calculate the price change
        df["price_change"] = df["close"].diff()

        # Calculate gains and losses
        df["gain"] = np.where(df["price_change"] > 0, df["price_change"], 0)
        df["loss"] = np.where(df["price_change"] < 0, -df["price_change"], 0)

        # Calculate average gain and average loss over a 14-period window
        df["avg_gain"] = df["gain"].rolling(window=window_length).mean()
        df["avg_loss"] = df["loss"].rolling(window=window_length).mean()

        # Calculate RS and RSI
        df["rs"] = df["avg_gain"] / df["avg_loss"]
        df["rsi"] = 100 - (100 / (1 + df["rs"]))

        # Set default signal to 0, no position
        df["signal"] = 0
        df.loc[(df["rsi"] >= 30) & (df["rsi"].shift(1).fillna(0) < 30), "signal"] = (
            1  # Buy signal
        )
        df.loc[(df["rsi"] <= 70) & (df["rsi"].shift(1).fillna(0) > 70), "signal"] = (
            -1
        )  # Sell signal

        # Initialize the position column with default value 0
        df["position"] = 0
        df["highest_price"] = np.nan

        # Variable to track the current position status
        current_position = 0

        if stop_loss:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "close"], df.loc[i, "close"]
                    )
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue

                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue
                    current_position = 1
                elif (
                    df.loc[i, "signal"] == -1 and current_position == 1
                ):  # Exit position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue

                elif (
                    current_position == 1
                ):  # Check current_position instead of df position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue

                if (
                    current_position == 0
                    and df.loc[i, "rsi"] > 30
                    and df.loc[i - 1, "rsi"] <= 30
                ):
                    df.loc[i, "signal"] = 1
                df.loc[i, "position"] = current_position
        else:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    current_position = 1
                elif df.loc[i, "signal"] == -1:  # Exit position
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue
                df.loc[i, "position"] = current_position

    if strategy_name == "Moving_Average_Crossover":
        # 1, 20
        short_ma = param1
        long_ma = param2
        df[f"ma_{short_ma}"] = df["close"].rolling(window=short_ma).mean()
        df[f"ma_{long_ma}"] = df["close"].rolling(window=long_ma).mean()

        # Initialize the signal column with default value 0
        df["signal"] = 0

        # Generate buy signal: 1 when ma5 crosses above ma20
        df.loc[
            (df[f"ma_{short_ma}"] > df[f"ma_{long_ma}"])
            & (df[f"ma_{short_ma}"].shift(1) <= df[f"ma_{long_ma}"].shift(1)),
            "signal",
        ] = 1

        # Generate sell signal: -1 when ma_5 crosses below ma_20
        df.loc[
            (df[f"ma_{short_ma}"] < df[f"ma_{long_ma}"])
            & (df[f"ma_{short_ma}"].shift(1) >= df[f"ma_{long_ma}"].shift(1)),
            "signal",
        ] = -1

        # Initialize the position column with default value 0
        df["position"] = 0
        df["highest_price"] = np.nan

        # Variable to track the current position status
        current_position = 0

        if stop_loss:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "close"], df.loc[i, "close"]
                    )
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue
                    current_position = 1
                elif (
                    df.loc[i, "signal"] == -1 and current_position == 1
                ):  # Exit position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue

                elif (
                    current_position == 1
                ):  # Check current_position instead of df position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue

                if (
                    current_position == 0
                    and df.loc[i, f"ma_{short_ma}"] > df.loc[i, f"ma_{long_ma}"]
                ):
                    df.loc[i, "signal"] = 1
                df.loc[i, "position"] = current_position
        else:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    current_position = 1
                elif df.loc[i, "signal"] == -1:  # Exit position
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue
                df.loc[i, "position"] = current_position

    if strategy_name == "Trading_Range_Breakout":
        lookback_period = param1

        df[f"high_{lookback_period}"] = df["high"].rolling(window=lookback_period).max()
        df[f"low_{lookback_period}"] = df["low"].rolling(window=lookback_period).min()

        # Initialize the signal column with default value 0
        df["signal"] = 0

        # Generate buy signal: 1 when price breaks above the high
        df.loc[df["close"] > df[f"high_{lookback_period}"].shift(1), "signal"] = 1

        # Generate sell signal: -1 when price breaks below the low
        df.loc[df["close"] < df[f"low_{lookback_period}"].shift(1), "signal"] = -1

        # Initialize the position column with default value 0
        df["position"] = 0
        df["highest_price"] = np.nan
        # Variable to track the current position status
        current_position = 0

        if stop_loss:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "close"], df.loc[i, "close"]
                    )
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    elif df.loc[i, "signal"] == 1:
                        df.loc[i, "signal"] = 0

                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue
                    current_position = 1
                elif (
                    df.loc[i, "signal"] == -1 and current_position == 1
                ):  # Exit position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue

                elif (
                    current_position == 1
                ):  # Check current_position instead of df position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "signal"] = 0
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue

                if (
                    current_position == 0
                    and df.loc[i, "close"] > df.loc[i, f"high_{lookback_period}"]
                ):
                    df.loc[i, "signal"] = 1
                df.loc[i, "position"] = current_position
        else:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    elif df.loc[i, "signal"] == 1:
                        df.loc[i, "signal"] = 0
                    current_position = 1
                elif df.loc[i, "signal"] == -1:  # Exit position
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue
                elif current_position == 1:
                    df.loc[i, "signal"] = 0
                df.loc[i, "position"] = current_position

    if strategy_name == "Moving_Average_Convergence_Divergence":
        fast_period = param1
        slow_period = param2

        # Calculate MACD components
        df["ema_fast"] = df["close"].ewm(span=fast_period, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow_period, adjust=False).mean()
        df["macd"] = df["ema_fast"] - df["ema_slow"]
        # df["signal_line"] = df["macd"].ewm(span=signal_period, adjust=False).mean()

        # Initialize the signal column with default value 0
        df["signal"] = 0

        # Generate buy signal: 1 when MACD crosses above zero
        df.loc[(df["macd"] > 0) & (df["macd"].shift(1) <= 0), "signal"] = 1

        # Generate sell signal: -1 when MACD crosses below zero
        df.loc[(df["macd"] < 0) & (df["macd"].shift(1) >= 0), "signal"] = -1

        # Initialize the position column with default value 0
        df["position"] = 0
        df["highest_price"] = np.nan
        # Variable to track the current position status
        current_position = 0

        if stop_loss:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "close"], df.loc[i, "close"]
                    )
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue

                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue
                    current_position = 1
                elif (
                    df.loc[i, "signal"] == -1 and current_position == 1
                ):  # Exit position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue

                elif (
                    current_position == 1
                ):  # Check current_position instead of df position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue

                if current_position == 0 and df.loc[i, "macd"] > 0:
                    df.loc[i, "signal"] = 1
                df.loc[i, "position"] = current_position
        else:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    current_position = 1
                elif df.loc[i, "signal"] == -1:  # Exit position
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue
                df.loc[i, "position"] = current_position

    if strategy_name == "Rate_of_Change":
        momentum_period = param1

        df["momentum"] = df["close"].pct_change(periods=momentum_period)

        # Initialize the signal column with default value 0
        df["signal"] = 0

        # Generate buy signal: 1 when momentum crosses above zero
        df.loc[
            (df["momentum"] > 0) & (df["momentum"].shift(1).fillna(0) <= 0), "signal"
        ] = 1

        # Generate sell signal: -1 when momentum crosses below zero
        df.loc[
            (df["momentum"] < 0) & (df["momentum"].shift(1).fillna(0) >= 0), "signal"
        ] = -1

        # Initialize the position column with default value 0
        df["position"] = 0
        df["highest_price"] = np.nan
        # Variable to track the current position status
        current_position = 0

        if stop_loss:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "close"], df.loc[i, "close"]
                    )
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue

                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue
                    current_position = 1
                elif (
                    df.loc[i, "signal"] == -1 and current_position == 1
                ):  # Exit position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue

                elif (
                    current_position == 1
                ):  # Check current_position instead of df position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue

                if current_position == 0 and df.loc[i, "momentum"] > 0:
                    df.loc[i, "signal"] = 1
                df.loc[i, "position"] = current_position
        else:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    current_position = 1
                elif df.loc[i, "signal"] == -1:  # Exit position
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue
                df.loc[i, "position"] = current_position

    if strategy_name == "On_Balance_Volume":
        short_ma = param1
        long_ma = param2
        df["short_volume_ma"] = df["volume_krw"].rolling(short_ma).mean()
        df["long_volume_ma"] = df["volume_krw"].rolling(long_ma).mean()

        # Initialize the signal column with default value 0
        df["signal"] = 0

        # Generate buy signal: 1 when MACD crosses above zero
        df.loc[
            (df["short_volume_ma"] > df["long_volume_ma"])
            & (
                df["short_volume_ma"].shift(1).fillna(0)
                <= df["long_volume_ma"].shift(1).fillna(0)
            ),
            "signal",
        ] = 1

        # Generate sell signal: -1 when MACD crosses below zero
        df.loc[
            (df["short_volume_ma"] < df["long_volume_ma"])
            & (
                df["short_volume_ma"].shift(1).fillna(0)
                >= df["long_volume_ma"].shift(1).fillna(0)
            ),
            "signal",
        ] = -1

        # Initialize the position column with default value 0
        df["position"] = 0
        df["highest_price"] = np.nan
        # Variable to track the current position status
        current_position = 0

        if stop_loss:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "close"], df.loc[i, "close"]
                    )
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue

                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue
                    current_position = 1
                elif (
                    df.loc[i, "signal"] == -1 and current_position == 1
                ):  # Exit position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue

                elif (
                    current_position == 1
                ):  # Check current_position instead of df position
                    df.loc[i, "highest_price"] = max(
                        df.loc[i - 1, "highest_price"], df.loc[i, "close"]
                    )
                    if df.loc[i, "close"] <= df.loc[i, "highest_price"] * (
                        1 - stop_loss_pct
                    ):
                        df.loc[i, "position"] = 1
                        df.loc[i, "signal"] = -1
                        current_position = 0
                        continue

                if (
                    current_position == 0
                    and df.loc[i, "short_volume_ma"] > df.loc[i, "long_volume_ma"]
                ):
                    df.loc[i, "signal"] = 1
                df.loc[i, "position"] = current_position
        else:
            # Iterate over the rows and set the position
            for i in range(1, len(df)):
                if df.loc[i - 1, "signal"] == 1:  # Enter long position
                    if df.loc[i, "signal"] == -1:
                        df.loc[i, "position"] = 1
                        current_position = 0
                        continue
                    current_position = 1
                elif df.loc[i, "signal"] == -1:  # Exit position
                    df.loc[i, "position"] = current_position
                    current_position = 0
                    continue
                df.loc[i, "position"] = current_position

    # wait for the buying chance
    if not holding_position:
        # buy 0, 1 or 1, 0
        if (df.iloc[-2]["position"] == 1 and df.iloc[-2]["signal"] != -1) or (
            df.iloc[-2]["signal"]
        ) == 1:
            return "buy"
        else:
            return "stay"
    # wait for the selling chance
    else:
        # sell 0, 0 or -1, 1
        if (df.iloc[-2]["signal"] == 0 and df.iloc[-2]["position"] == 0) or df.iloc[-2][
            "signal"
        ] == -1:
            return "sell"
        else:
            return "hold"
