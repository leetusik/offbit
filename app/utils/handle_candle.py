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
    start="2024-01-01 00:00:00",
    interval2="1",
):
    times = get_time_intervals(
        initial_time_str=start,
        interval=interval,
        interval2=interval2,
    )
    if len(times) == 2:
        # Get the current time
        current_time = times[1]
        start_time = times[0]
        current_time = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
        start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        time_difference = current_time - start_time
        # when interval minutes 1
        if time_difference < timedelta(hours=4):
            total_minutes = time_difference.total_seconds() // 60 + 1
        # when interval minutes 60
        else:
            total_minutes = time_difference.total_seconds() // 3600 + 1
        count = int(total_minutes)

    times = times[1:]

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
        "candle_date_time_utc",
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
            "candle_date_time_utc": "time_utc",
            "opening_price": "open",
            "high_price": "high",
            "low_price": "low",
            "trade_price": "close",
            "candle_acc_trade_price": "volume_krw",
            "candle_acc_trade_volume": "volume_market",
        },
        inplace=True,
    )
    df_selected["time_utc"] = pd.to_datetime(df_selected["time_utc"])
    return df_selected


def get_time_intervals(initial_time_str, interval, interval2):
    # Convert the initial time string to a datetime object
    initial_time = datetime.strptime(initial_time_str, "%Y-%m-%d %H:%M:%S")
    # initial_time = initial_time - timedelta(hours=9)

    # Get the current time
    current_time = str(datetime.now(timezone.utc))
    current_time = current_time.split(".")[0]
    current_time = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")

    # Initialize an empty list to store the times
    time_intervals = []
    time_intervals.append(initial_time.strftime("%Y-%m-%d %H:%M:%S"))

    if interval == "minutes":
        # Generate times in 3-hour intervals until the current time
        if interval2 == "1":
            while initial_time <= current_time:
                if current_time - initial_time < timedelta(hours=3, minutes=20):
                    break
                initial_time += timedelta(hours=3, minutes=20)
                time_intervals.append(initial_time.strftime("%Y-%m-%d %H:%M:%S"))
        elif interval2 == "60":
            while initial_time <= current_time:
                if current_time - initial_time < timedelta(hours=200):
                    break
                initial_time += timedelta(hours=200)
                time_intervals.append(initial_time.strftime("%Y-%m-%d %H:%M:%S"))
    elif interval == "hours":
        # add later
        return

    time_intervals.append(current_time.strftime("%Y-%m-%d %H:%M:%S"))
    return time_intervals


def concat_candles(long_df, short_df):
    concatenated_df = pd.concat([long_df, short_df])

    # Drop duplicates based on 'day_starting_at_4am', keeping the last occurrence (from df2)
    final_df = concatenated_df.drop_duplicates(subset="time_utc", keep="last")

    # Sort the DataFrame by 'day_starting_at_4am' to maintain chronological order
    final_df = final_df.sort_values(by="time_utc").copy()

    # Reset the index if needed
    final_df.reset_index(drop=True, inplace=True)

    return final_df


# df = get_candles(start="2024-10-10 00:00:00")
# print(df)
# print(df.dtypes)

# # Get the last row of the DataFrame
# last_row = df.iloc[-1]

# # Convert the 'time_utc' column value from the last row to a datetime object
# last_time_utc = pd.to_datetime(last_row["time_utc"])

# # Assuming formatted_now is a datetime object without seconds (formatted_now = datetime.now().replace(second=0, microsecond=0))
# formatted_now = datetime.now(timezone.utc).replace(
#     second=0, microsecond=0
# )  # Convert formatted_now to naive if it has timezone info
# formatted_now_naive = formatted_now.replace(tzinfo=None)

# # Compare the two naive datetime objects
# if last_time_utc == formatted_now_naive:
#     print("The times match!")
# else:
#     print(
#         f"The times do not match. Last time_utc: {last_time_utc}, formatted_now: {formatted_now_naive}"
#     )


# # """Sets the execution time based on a provided time string in hh:mm:ss format."""
# # # Parse the string and store it as a timezone-aware datetime in UTC
# time_format = "%H:%M:%S"
# # time_obj = datetime.strptime("04:12:00", time_format).time()
# # now_time = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).time()
# time_obj = (
#     datetime.strptime("04:12:00", time_format)
#     .replace(microsecond=0, tzinfo=None)
#     .time()
# )

# # # Combine current date with the provided time and store it as a UTC-aware datetime
# # execution_datetime = datetime.combine(now.date(), time_obj).astimezone(timezone.utc)
# # execution_datetime = execution_datetime.replace(tzinfo=None)
# print(time_obj.minute)
