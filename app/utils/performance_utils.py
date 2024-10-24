from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import sqlalchemy as sa

from app import db
from app.models import Coin, Strategy
from app.utils.trading_conditions import get_condition, resample_df


def calculate_strategy_performance(
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
            strategy.make_historical_data()

    df = strategy.coins[0].get_historical_data()
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

        day_ago_benchmark = df["benchmark_returns"].iloc[-2]

        month_ago_benchmark = df["benchmark_returns"].iloc[-31]

        year_ago_benchmark = df["benchmark_returns"].iloc[-366]

        last_day_benchmark = df["benchmark_returns"].iloc[-1]

        benchmark_return_day = (
            last_day_benchmark - day_ago_benchmark
        ) / day_ago_benchmark
        benchmark_return_month = (
            last_day_benchmark - month_ago_benchmark
        ) / month_ago_benchmark
        benchmark_return_year = (
            last_day_benchmark - year_ago_benchmark
        ) / year_ago_benchmark
        return (
            round(float(total_return_day), 2),
            round(float(total_return_month), 2),
            round(float(total_return_year), 2),
        )


def calculate_coin_performance(
    coin: Coin,
    execution_time: datetime = datetime(1970, 1, 1, 0, 0),
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
    # # Filter the data to only include rows within the specified time period
    # end_time = pd.Timestamp.now(tz="UTC").to_pydatetime().replace(tzinfo=None)
    # start_time = end_time - time_period
    # filtered_df = df[df["time_utc"] >= start_time]
    df = resample_df(df=df, execution_time=execution_time)
    # Calculate the benchmark cumulative returns (buy and hold strategy)
    df["coin_returns"] = (1 + df["open"].pct_change()).cumprod()

    day_ago_coin = df["coin_returns"].iloc[-2]

    month_ago_coin = df["coin_returns"].iloc[-31]

    year_ago_coin = df["coin_returns"].iloc[-366]

    last_day_coin = df["coin_returns"].iloc[-1]

    coin_return_day = (last_day_coin - day_ago_coin) / day_ago_coin
    coin_return_month = (last_day_coin - month_ago_coin) / month_ago_coin
    coin_return_year = (last_day_coin - year_ago_coin) / year_ago_coin
    return (
        round(float(coin_return_day), 2),
        round(float(coin_return_month), 2),
        round(float(coin_return_year), 2),
    )


def get_backtest(
    strategy: Strategy,
    selected_coin=str,
    execution_time: datetime = datetime(1970, 1, 1, 0, 0),
) -> float:
    coin = db.session.scalar(sa.select(Coin).where(Coin.name == selected_coin))
    df = coin.get_historical_data()
    # Filter the data to only include rows within the specified time period
    # end_time = pd.Timestamp.now(tz="UTC").to_pydatetime().replace(tzinfo=None)
    # start_time = end_time - time_period
    # filtered_df = df[df["time_utc"] >= start_time]
    df = resample_df(df=df, execution_time=execution_time)
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

    return win_rate


def get_gain_loss_ratio(df):
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
    win_rate = get_win_rate(df)

    # get gain loss ratio
    gain_loss_ratio = get_gain_loss_ratio(df)

    if type(gain_loss_ratio) != str:
        gain_loss_ratio = round(gain_loss_ratio, 2)

    # holding percent
    holding_time_ratio = get_holding_time_ratio(df)

    return {
        "total_return": tr,
        "cagr": cagr,
        "mdd": mdd,
        "win_rate": win_rate,
        "gain_loss_ratio": gain_loss_ratio,
        "holding_time_ratio": holding_time_ratio,
        "investing_period": days,
    }
