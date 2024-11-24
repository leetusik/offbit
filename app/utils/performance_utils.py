from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import sqlalchemy as sa

from app import db
from app.models import Coin, Strategy
from app.utils.handle_candle import resample_df


def calculate_strategy_performance(
    strategy: Strategy,
    time_period: timedelta,
    execution_time: datetime = datetime(1970, 1, 1, datetime.now(timezone.utc).hour, 0),
) -> float:

    while True:
        # Assuming formatted_now is a datetime object without seconds (formatted_now = datetime.now().replace(second=0, microsecond=0))
        formatted_now = datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        )  # Convert formatted_now to naive if it has timezone info
        formatted_now_naive = formatted_now.replace(tzinfo=None)

        short_historical_data = strategy.coins[0].get_short_historical_data()
        # Get the last row of the DataFrame
        last_row = short_historical_data.iloc[-1]

        # Convert the 'time_utc' column value from the last row to a datetime object
        last_time_utc = pd.to_datetime(last_row["time_utc"])

        if last_time_utc == formatted_now_naive:
            print("pass!")
            break
        else:
            print("no pass!")
            strategy.coins[0].make_historical_data()

    df = min(strategy.coins, key=lambda x: x.id).get_historical_data()
    # Filter the data to only include rows within the specified time period
    end_time = pd.Timestamp.now(tz="UTC").to_pydatetime().replace(tzinfo=None)
    start_time = end_time - time_period
    filtered_df = df[df["time_utc"] >= start_time]
    df = resample_df(df=filtered_df, execution_time=execution_time)

    if strategy.name == "Relative_Strength_Index":
        # 2
        # Calculate the price change
        df["price_change"] = df["close"].diff()

        # Calculate the gains and losses
        df["gain"] = np.where(df["price_change"] > 0, df["price_change"], 0)
        df["loss"] = np.where(df["price_change"] < 0, -df["price_change"], 0)

        # Calculate the average gain and average loss
        window_length = strategy.base_param1
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

        # Variable to track the current position status
        current_position = 0

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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Moving_Average_Crossover":
        # 1, 20
        short_ma = strategy.base_param1
        long_ma = strategy.base_param2
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

        # Variable to track the current position status
        current_position = 0

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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Trading_Range_Breakout":
        # 10
        lookback_period = strategy.base_param1

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

        # Variable to track the current position status
        current_position = 0

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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Moving_Average_Convergence_Divergence":
        # 1, 15
        fast_period = strategy.base_param1
        slow_period = strategy.base_param2

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

        # Variable to track the current position status
        current_position = 0

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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Rate_of_Change":
        # 20
        momentum_period = strategy.base_param1
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

        # Variable to track the current position status
        current_position = 0

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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "On_Balance_Volume":
        # 15, 30
        short_ma = strategy.base_param1
        long_ma = strategy.base_param2
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

        # Variable to track the current position status
        current_position = 0

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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    day_ago_balance = df["cumulative_returns2"].iloc[-2]

    month_ago_balance = df["cumulative_returns2"].iloc[-31]

    year_ago_balance = df["cumulative_returns2"].iloc[-366]

    last_day_balance = df["cumulative_returns2"].iloc[-1]

    total_return_day = (last_day_balance - day_ago_balance) / day_ago_balance
    total_return_month = (last_day_balance - month_ago_balance) / month_ago_balance
    total_return_year = (last_day_balance - year_ago_balance) / year_ago_balance

    return (
        round(float(total_return_day * 100), 2),
        round(float(total_return_month * 100), 2),
        round(float(total_return_year * 100), 2),
    )


def calculate_coin_performance(
    coin: Coin,
    execution_time: datetime = datetime(1970, 1, 1, datetime.now(timezone.utc).hour, 0),
) -> float:

    while True:
        # Assuming formatted_now is a datetime object without seconds (formatted_now = datetime.now().replace(second=0, microsecond=0))
        formatted_now = datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        )  # Convert formatted_now to naive if it has timezone info
        formatted_now_naive = formatted_now.replace(tzinfo=None)

        short_historical_data = coin.get_short_historical_data()
        # Get the last row of the DataFrame
        last_row = short_historical_data.iloc[-1]

        # Convert the 'time_utc' column value from the last row to a datetime object
        last_time_utc = pd.to_datetime(last_row["time_utc"])

        if last_time_utc == formatted_now_naive:
            print("pass!")
            break
        else:
            print("no pass!")
            coin.make_historical_data()

    df = coin.get_historical_data()
    df = resample_df(df=df, execution_time=execution_time)
    # Calculate the benchmark cumulative returns (buy and hold strategy)
    df["coin_returns"] = (1 + df["close"].pct_change()).cumprod()

    day_ago_coin = df["coin_returns"].iloc[-2]

    month_ago_coin = df["coin_returns"].iloc[-31]

    year_ago_coin = df["coin_returns"].iloc[-366]

    last_day_coin = df["coin_returns"].iloc[-1]

    coin_return_day = (last_day_coin - day_ago_coin) / day_ago_coin
    coin_return_month = (last_day_coin - month_ago_coin) / month_ago_coin
    coin_return_year = (last_day_coin - year_ago_coin) / year_ago_coin
    return (
        round(float(coin_return_day * 100), 2),
        round(float(coin_return_month * 100), 2),
        round(float(coin_return_year * 100), 2),
    )


def get_backtest(
    strategy: Strategy,
    selected_coin: str,
    param1: int,
    param2: int | None,
    stop_loss: int | None,
    execution_time: datetime = datetime(1970, 1, 1, 0, 0),
) -> float:
    coin = db.session.scalar(sa.select(Coin).where(Coin.name == selected_coin))
    df = coin.get_historical_data()
    df = resample_df(df=df, execution_time=execution_time)
    if stop_loss:
        stop_loss_pct = stop_loss / 100
    if strategy.name == "Relative_Strength_Index":
        window_length = param1
        # Calculate the price change
        df["price_change"] = df["close"].diff()

        # Calculate the gains and losses
        df["gain"] = np.where(df["price_change"] > 0, df["price_change"], 0)
        df["loss"] = np.where(df["price_change"] < 0, -df["price_change"], 0)

        # Calculate the average gain and average loss
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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Moving_Average_Crossover":
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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Trading_Range_Breakout":
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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Moving_Average_Convergence_Divergence":
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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "Rate_of_Change":
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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    if strategy.name == "On_Balance_Volume":
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

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"] * df["close"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        # Adjust for trading fees (buy with 0.2% fee, sell with 0.2% fee)
        df["buy_price"] = df["close"].shift(1) * np.where(
            df["signal"].shift(1) == 1, 1.002, 1
        )
        df["sell_price"] = df["close"] * np.where(df["signal"] == -1, 0.998, 1)

        # Calculate strategy returns with fees
        df["strategy_returns2"] = np.where(
            df["position"] == 1, df["sell_price"] / df["buy_price"] - 1, 0
        )

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

    return df


def get_rounded(number):
    return round(number * 100, 2)


def get_total_return(inital_value, final_value):
    number = (final_value - inital_value) / inital_value
    return float(number)


def get_cagr(total_return, days):
    years = days / 365
    cagr = (1 + total_return) ** (1 / years) - 1
    return float(cagr)


def get_mdd(df):
    values = list(df["cumulative_returns2"])

    peak = values[0]
    max_drawdown = 0

    # Check if peak is NaN
    temp = 1
    while np.isnan(peak):
        peak = values[temp]
        temp += 1

    for value in values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def get_win_rate(df):
    # Check if the 'position' column exists
    if "position" not in df.columns:
        return None, None, None

    # Initialize variables to track buy and win times
    buy_time = 0
    win_time = 0
    holding_period = False  # Track whether we're in a holding period
    start_returns = 0  # To store the returns at the start of the buy signal

    for index, row in df.iterrows():
        if row["signal"] == 1 and not holding_period:
            # Start of a new buy period
            holding_period = True
            buy_time += 1
            start_returns = row["cumulative_returns2"]

        elif row["position"] == 0 and holding_period:
            # End of a buy period (sell signal)
            holding_period = False
            # Calculate total returns during this holding period
            end_returns = row["cumulative_returns2"]
            if end_returns > start_returns:
                win_time += 1  # Count as a winning trade if returns increased

    # Calculate win rate
    if buy_time > 0:
        win_rate = win_time / buy_time
    else:
        win_rate = 0

    return win_rate, buy_time, win_time


def get_gain_loss_ratio(df):
    # Check if the 'position' column exists
    if "position" not in df.columns:
        return None
    holding_period = False  # Track whether we're in a holding period
    start_returns = 0  # To store the returns at the start of the buy signal
    win_list = []
    loss_list = []

    for index, row in df.iterrows():
        if row["signal"] == 1 and not holding_period:
            # Start of a new buy period
            holding_period = True
            start_returns = row["cumulative_returns2"]

        elif row["position"] == 0 and holding_period:
            # End of a buy period (sell signal)
            holding_period = False
            # Calculate total returns during this holding period
            end_returns = row["cumulative_returns2"]
            if end_returns > start_returns:
                gain = (end_returns - start_returns) / start_returns
                win_list.append(gain)
            elif end_returns < start_returns:
                gain = (end_returns - start_returns) / start_returns
                loss_list.append(gain)

    if len(win_list) != 0:
        win_avg = sum(win_list) / len(win_list)
    else:
        win_avg = 0

    if len(loss_list) != 0:
        loss_avg = sum(loss_list) / len(loss_list)
    else:
        loss_avg = 0

    if win_avg != 0 and loss_avg != 0:
        gain_loss_ratio = win_avg / abs(loss_avg)
    else:
        gain_loss_ratio = "not enough data"
    return gain_loss_ratio


def get_holding_time_ratio(df):
    # Check if the 'position' column exists
    if "position" not in df.columns:
        return None
    # Step 1: Filter rows where there is no NaN in any column except 'highest_price' and 'exit_price'
    df_no_na_except_cols = df.dropna(
        subset=[col for col in df.columns if col not in ["highest_price", "exit_price"]]
    )

    # Step 2: Calculate the total period from the first non-NaN row in this filtered dataframe
    total_period_except_cols = len(df_no_na_except_cols)

    # Step 3: Calculate the position time (when position is non-zero) in this filtered dataframe
    position_time_except_cols = len(
        df_no_na_except_cols[df_no_na_except_cols["position"] != 0]
    )

    # Calculate the ratio of position time to total period
    if total_period_except_cols > 0:
        position_time_ratio_except_cols = (
            position_time_except_cols / total_period_except_cols
        )
    else:
        position_time_ratio_except_cols = 0

    return position_time_ratio_except_cols


def get_sharpe_ratio(df, risk_free_rate=0.03):
    # Calculate daily returns
    daily_returns = df["cumulative_returns2"].pct_change()

    # Calculate excess returns (over risk-free rate)
    excess_returns = daily_returns - (
        risk_free_rate / 365
    )  # Convert annual risk-free rate to daily

    # Calculate annualized Sharpe ratio using 365 days for crypto
    if daily_returns.std() != 0:
        sharpe_ratio = np.sqrt(365) * (excess_returns.mean() / daily_returns.std())
    else:
        sharpe_ratio = 0

    return float(sharpe_ratio)


def get_performance(df):
    # get total return
    initial_value = df["cumulative_returns2"].iloc[1]
    final_value = df["cumulative_returns2"].iloc[-1]

    tr = get_total_return(
        inital_value=initial_value,
        final_value=final_value,
    )

    df_no_na_except_cols = df.dropna(
        subset=[col for col in df.columns if col not in ["highest_price", "exit_price"]]
    )

    # Step 2: Calculate the total period from the first non-NaN row in this filtered dataframe
    days = len(df_no_na_except_cols)
    cagr = get_cagr(
        total_return=tr,
        days=days,
    )
    # print(len(df), first_signal_day, days)

    # get mdd
    mdd = get_mdd(df)

    # get win rate
    win_rate, buy_time, win_time = get_win_rate(df)

    # get gain loss ratio
    gain_loss_ratio = get_gain_loss_ratio(df)

    if type(gain_loss_ratio) != str and gain_loss_ratio != None:
        gain_loss_ratio = round(gain_loss_ratio, 2)

    # holding percent
    holding_time_ratio = get_holding_time_ratio(df)

    # get sharpe ratio
    sharpe_ratio = get_sharpe_ratio(df)
    return {
        "total_return": tr,
        "cagr": cagr,
        "mdd": mdd,
        "win_rate": win_rate,
        "buy_time": buy_time,
        "win_time": win_time,
        "gain_loss_ratio": gain_loss_ratio,
        "holding_time_ratio": holding_time_ratio,
        "investing_period": days,
        "sharpe_ratio": sharpe_ratio,
    }
