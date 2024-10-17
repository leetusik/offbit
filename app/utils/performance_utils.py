from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.models import Strategy
from app.utils.trading_conditions import get_condition, resample_df


def calculate_performance(
    strategy: Strategy,
    time_period: timedelta,
    execution_time: datetime = datetime(1970, 1, 1, 0, 0),
) -> float:

    while True:
        # Assuming formatted_now is a datetime object without seconds (formatted_now = datetime.now().replace(second=0, microsecond=0))
        formatted_now = datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        )  # Convert formatted_now to naive if it has timezone info
        formatted_now_naive = formatted_now.replace(tzinfo=None)

        short_historical_data = strategy.get_short_historical_data()
        # Get the last row of the DataFrame
        last_row = short_historical_data.iloc[-1]

        # Convert the 'time_utc' column value from the last row to a datetime object
        last_time_utc = pd.to_datetime(last_row["time_utc"])

        if last_time_utc == formatted_now_naive:
            print("pass!")
            break
        else:
            print("no pass!")
            strategy.make_historical_data()

    df = strategy.get_historical_data()
    # Filter the data to only include rows within the specified time period
    end_time = pd.Timestamp.now(tz="UTC").to_pydatetime().replace(tzinfo=None)
    start_time = end_time - time_period
    filtered_df = df[df["time_utc"] >= start_time]
    df = resample_df(df=filtered_df, execution_time=execution_time)
    if strategy.name == "rsi_cut_5%":
        # Calculate the price change
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
        holding_position = False

        for i in range(1, len(df)):
            if df["signal"].iloc[i] == 1 and not holding_position:
                # Enter position
                df.loc[i, "position"] = 1
                df.loc[i, "highest_price"] = df.loc[i, "open"]
                holding_position = True
            elif holding_position:
                # Calculate percentage change since entry
                # df['highest_price'].iloc[i] = max(df['highest_price'].iloc[i-1], df['open'].iloc[i])
                df.loc[i, "highest_price"] = max(
                    df.loc[i - 1, "highest_price"], df.loc[i - 1, "open"]
                )
                highest_price = df["highest_price"].iloc[i]
                current_price = df["open"].iloc[i]
                percent_change = (current_price - highest_price) / highest_price * 100

                if df["signal"].iloc[i] == -1:  # Sell signal condition
                    # print(f"cond1 on{i}")
                    df.loc[i, "position"] = 0
                    df.loc[i, "exit_price"] = current_price
                    holding_position = False
                elif percent_change <= -5:  # Stop loss condition
                    # print(f"cond2 on{i}")
                    df.loc[i, "position"] = 0
                    df.loc[i, "exit_price"] = current_price
                    holding_position = False
                else:
                    # Continue holding the position if no sell conditions are met
                    df.loc[i, "position"] = df.loc[i - 1, "position"]

            else:
                # No signal and no position
                # df['position'].iloc[i] = df['position'].iloc[i-1]
                df.loc[i, "position"] = df.loc[i - 1, "position"]

        # Calculate the strategy returns (only when in a long position)
        df["strategy_returns"] = df["position"].shift(1) * df["open"].pct_change()
        df["strategy_returns2"] = df["strategy_returns"]

        for i in range(1, len(df)):
            buy_price = df.loc[i - 1, "open"]
            buy_price_copy = buy_price
            sell_price = df.loc[i, "open"]
            sell_price_copy = sell_price
            if df.loc[i - 1, "position"] == 1 and df.loc[i - 1, "signal"] == 1:
                # df.loc[i, 'strategy_returns2'] = (df.loc[i,'position'])/(df.loc[i-1, 'position'] * 1.002) -1
                buy_price = df.loc[i - 1, "open"] * 1.002
            if df.loc[i, "position"] == 0 and df.loc[i - 1, "position"] != 0:
                # df.loc[i, 'strategy_returns2'] = (df.loc[i,'position'] * 0.998)/(df.loc[i-1, 'position']) -1
                sell_price = df.loc[i, "open"] * 0.998

            if buy_price == buy_price_copy and sell_price == sell_price_copy:
                continue

            df.loc[i, "strategy_returns2"] = sell_price / buy_price - 1

        # Calculate the cumulative returns
        df["cumulative_returns"] = (1 + df["strategy_returns"]).cumprod()
        df["cumulative_returns2"] = (1 + df["strategy_returns2"]).cumprod()

        # Calculate the benchmark cumulative returns (buy and hold strategy)
        df["benchmark_returns"] = (1 + df["open"].pct_change()).cumprod()

        day_ago_balance = df["cumulative_returns2"].iloc[-2]

        month_ago_balance = df["cumulative_returns2"].iloc[-31]

        year_ago_balance = df["cumulative_returns2"].iloc[-366]

        last_day_balance = df["cumulative_returns2"].iloc[-1]

        total_return_day = (last_day_balance - day_ago_balance) / day_ago_balance
        total_return_month = (last_day_balance - month_ago_balance) / month_ago_balance
        total_return_year = (last_day_balance - year_ago_balance) / year_ago_balance

        return (
            round(float(total_return_day), 2),
            round(float(total_return_month), 2),
            round(float(total_return_year), 2),
        )
