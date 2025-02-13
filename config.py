from dotenv import load_dotenv
import os

load_dotenv()
config = {
    'telegram_token': os.getenv('TELEGRAM_TOKEN', ''),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'min_profit_percent': float(os.getenv('MIN_PROFIT_PERCENT', 0.5)),
    'min_liquidity': float(os.getenv('MIN_LIQUIDITY', 5000))
}
