import os
import time
import requests
from telegram import Bot

# --- Load environment variables ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

# --- Dex Screener API endpoint ---
API_URL = "https://api.dexscreener.com/latest/dex/tokens/solana"

# --- Filter criteria ---
MIN_VOLUME = 10000
MAX_MARKETCAP = 1000000
MAX_PAIR_AGE_HOURS = 1
MIN_LIQUIDITY = 10000
PROFILE_REQUIRED = True

# --- Track seen pairs ---
seen_pairs = set()

def fetch_pairs():
    """Fetch Solana pairs from Dex Screener API"""
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("pairs", [])
        else:
            print(f"Polling error {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching pairs: {e}")
        return []

def filter_pair(pair):
    """Apply filter criteria"""
    try:
        volume = float(pair.get("volume", {}).get("h24", 0))
        marketcap = float(pair.get("fdv", 0))
        age_hours = float(pair.get("pairCreatedAt", 0)) / 3600000  # ms → hours
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        has_profile = bool(pair.get("info", {}).get("imageUrl"))

        return (
            volume >= MIN_VOLUME and
            marketcap <= MAX_MARKETCAP and
            age_hours <= MAX_PAIR_AGE_HOURS and
            liquidity >= MIN_LIQUIDITY and
            (not PROFILE_REQUIRED or has_profile)
        )
    except Exception as e:
        print(f"Error filtering pair: {e}")
        return False

def format_message(pair):
    """Build Telegram message"""
    name = pair.get("baseToken", {}).get("name", "Unknown")
    symbol = pair.get("baseToken", {}).get("symbol", "")
    url = pair.get("url", "")
    liquidity = pair.get("liquidity", {}).get("usd", 0)

    return (
        f"🚨 New Solana Token Found!\n\n"
        f"Name: {name} ({symbol})\n"
        f"Liquidity: ${liquidity:,.0f}\n"
        f"Link: {url}"
    )

def main():
    while True:
        pairs = fetch_pairs()
        for pair in pairs:
            pair_id = pair.get("pairAddress")
            if not pair_id or pair_id in seen_pairs:
                continue
            if filter_pair(pair):
                message = format_message(pair)
                bot.send_message(chat_id=CHAT_ID, text=message)
                seen_pairs.add(pair_id)

        time.sleep(10)  # poll every 10 seconds

if __name__ == "__main__":
    main()
