import os
import time
import requests
import threading
from datetime import datetime, timezone
from flask import Flask

# --- Environment variables ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Filter criteria
MIN_VOLUME = 10000        # Minimum 24h volume
MAX_MARKETCAP = 1000000   # Maximum market cap
MAX_PAIR_AGE_HOURS = 1    # Pair must be younger than 1 hour
MIN_LIQUIDITY = 10000     # Liquidity filter
PROFILE_REQUIRED = True   # Profile must exist

# DexScreener API URL for Solana
DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/solana"

# Store seen pairs to avoid duplicates
seen_pairs = set()

# Flask app for Cloud Run
app = Flask(__name__)

@app.route("/")
def healthcheck():
    return "Bot is running!", 200


def send_telegram_message(message: str):
    """Send alert to Telegram chat"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")


def fetch_new_pairs():
    """Fetch new Solana pairs from DexScreener"""
    try:
        response = requests.get(DEX_URL, timeout=15)
        data = response.json()
        return data.get("pairs", [])
    except Exception as e:
        print(f"Error fetching pairs: {e}")
        return []


def passes_filters(pair: dict) -> bool:
    """Apply filters to Dex pair"""
    try:
        volume = float(pair.get("volume", {}).get("h24", 0))
        marketcap = float(pair.get("fdv", 0))
        created_at = int(pair.get("pairCreatedAt", 0)) / 1000
        age_hours = (datetime.now(timezone.utc) - datetime.fromtimestamp(created_at, tz=timezone.utc)).total_seconds() / 3600
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        has_profile = bool(pair.get("info", {}).get("imageUrl"))

        return (
            volume >= MIN_VOLUME and
            marketcap <= MAX_MARKETCAP and
            age_hours <= MAX_PAIR_AGE_HOURS and
            liquidity >= MIN_LIQUIDITY and
            (not PROFILE_REQUIRED or has_profile)
        )
    except Exception:
        return False


def monitor_pairs():
    """Main polling loop"""
    while True:
        pairs = fetch_new_pairs()
        for pair in pairs:
            address = pair.get("pairAddress")
            if not address or address in seen_pairs:
                continue

            if passes_filters(pair):
                seen_pairs.add(address)

                name = pair.get("baseToken", {}).get("name", "Unknown")
                symbol = pair.get("baseToken", {}).get("symbol", "")
                url = f"https://dexscreener.com/solana/{address}"

                message = (
                    f"🚀 <b>New Solana Token Found!</b>\n\n"
                    f"<b>{name} ({symbol})</b>\n"
                    f"Volume 24h: ${pair.get('volume', {}).get('h24', 'N/A')}\n"
                    f"Liquidity: ${pair.get('liquidity', {}).get('usd', 'N/A')}\n"
                    f"Market Cap: ${pair.get('fdv', 'N/A')}\n"
                    f"Pair Age: {round((datetime.now(timezone.utc) - datetime.fromtimestamp(int(pair.get('pairCreatedAt', 0))/1000, tz=timezone.utc)).total_seconds() / 3600, 2)} hours\n"
                    f"\n🔗 <a href='{url}'>View on DexScreener</a>"
                )
                send_telegram_message(message)

        time.sleep(10)  # Polling interval


# Start polling loop in background thread
threading.Thread(target=monitor_pairs, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
