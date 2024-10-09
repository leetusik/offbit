import ast
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests


def remove_duplicates(dict_list):
    seen = set()
    unique_list = []
    for d in dict_list:
        # Create a frozenset from the dictionary items to make it hashable
        # This allows us to use it in a set
        dict_frozen = frozenset(d.items())
        if dict_frozen not in seen:
            seen.add(dict_frozen)
            unique_list.append(d)
    return unique_list


def get_candles(
    interval="minutes",
    market="KRW-BTC",
    count="200",
    start="2024-01-01 01:00:00",
    interval2="1",
):
    times = get_time_intervals(
        initial_time_str=start,
        interval=interval,
        interval2=interval2,
    )
    if len(times) == 1:
        # Get the current time
        current_time = str(datetime.now(timezone.utc))
        current_time = current_time.split(".")[0]
        current_time = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
        start_time = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        start_time = start_time - timedelta(hours=9)
        time_difference = current_time - start_time
        # print(time_difference)

        # Convert the time difference to total minutes
        total_minutes = time_difference.total_seconds() // 3600 + 1
        count = int(total_minutes)
        # print(count)

    lst = []
    rate_limit_interval = 1 / 20  # Time in seconds to wait between requests

    for t in times:
        url = f"https://api.upbit.com/v1/candles/{interval}/{interval2}?market={market}&count={count}&to={t}"

        headers = {"accept": "application/json"}

        response = requests.get(url, headers=headers)
        response = ast.literal_eval(response.text)
        lst += response
        # Wait to respect the rate limit
        time.sleep(rate_limit_interval)
        # print(response, type(response))
        if type(response) == dict:
            print(response)
            return None

    lst = remove_duplicates(lst)
    # Sort the list of dictionaries by 'candle_date_time_utc'
    sorted_list = sorted(lst, key=lambda x: x["candle_date_time_utc"])

    df = pd.DataFrame(sorted_list)
    selected_columns = [
        "market",
        "candle_date_time_kst",
        "opening_price",
        "high_price",
        "low_price",
        "trade_price",
        "candle_acc_trade_price",
        "candle_acc_trade_volume",
    ]
    df_selected = df[selected_columns].copy()

    df_selected.rename(
        columns={
            "candle_date_time_kst": "time_kst",
            "opening_price": "open",
            "high_price": "high",
            "low_price": "low",
            "trade_price": "close",
            "candle_acc_trade_price": "volume_krw",
            "candle_acc_trade_volume": "volume_market",
        },
        inplace=True,
    )
    return df_selected


def get_time_intervals(initial_time_str, interval, interval2):
    # Convert the initial time string to a datetime object
    initial_time = datetime.strptime(initial_time_str, "%Y-%m-%d %H:%M:%S")
    initial_time = initial_time - timedelta(hours=9)

    # Get the current time
    current_time = str(datetime.now(timezone.utc))
    current_time = current_time.split(".")[0]
    current_time = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")

    # Initialize an empty list to store the times
    time_intervals = []

    if interval == "minutes":
        # Generate times in 3-hour intervals until the current time
        if interval2 == "1":
            while initial_time <= current_time:
                time_intervals.append(initial_time.strftime("%Y-%m-%d %H:%M:%S"))
                initial_time += timedelta(hours=3, minutes=20)
        elif interval2 == "60":
            while initial_time <= current_time:
                time_intervals.append(initial_time.strftime("%Y-%m-%d %H:%M:%S"))
                initial_time += timedelta(hours=200)
    elif interval == "hours":
        # Generate times in 200-hour intervals until the current time
        while initial_time <= current_time:
            time_intervals.append(initial_time.strftime("%Y-%m-%d %H:%M:%S"))
            initial_time += timedelta(hours=200)

    time_intervals.append(current_time.strftime("%Y-%m-%d %H:%M:%S"))
    # time_intervals = list(set(time_intervals))
    time_intervals = time_intervals[1:]
    # print(time_intervals)
    return time_intervals


# df = get_candles(start="2024-08-22 04:00:00", interval="minutes", interval2="60")
# print(df)
# df.to_csv("total_2_hours.csv")
