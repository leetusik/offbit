from datetime import datetime

from app.utils import handle_candle as hc

# def get_condition(
#     strategy_name: str, execution_time: datetime, holding_position: bool
# ) -> str:
#     if strategy_name == "rsi_cut_5%":
#         if holding_position:
#             return condition -> "sell or hold"
#         else:
#             return condition -> "buy or stay"
