from io import BytesIO

import pandas as pd


def save_dataframe_as_pickle(df: pd.DataFrame) -> bytes:
    """
    Convert a Pandas DataFrame to pickle format and return the binary data.

    Args:
        df (pd.DataFrame): The DataFrame to be saved.

    Returns:
        bytes: The binary pickle data.
    """
    pickle_buffer = BytesIO()
    df.to_pickle(pickle_buffer)
    return pickle_buffer.getvalue()


def get_dataframe_from_pickle(binary_data: bytes) -> pd.DataFrame:
    """
    Convert binary pickle data back to a Pandas DataFrame.

    Args:
        binary_data (bytes): The binary pickle data.

    Returns:
        pd.DataFrame: The restored DataFrame.
    """
    pickle_buffer = BytesIO(binary_data)
    return pd.read_pickle(pickle_buffer)
