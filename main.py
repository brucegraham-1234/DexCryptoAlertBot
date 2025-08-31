import os
import time
import sqlite3
import requests
import threading
from datetime import datetime, timezone
from flask import Flask

# ======================
# Telegram configuration
# ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ======================
# Filter configuration
# ======================
# Solana only is implicit via API endpoint.
# Adjust via Cloud Run env vars to match your DexScreener filter
MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", 0))              # USD
MIN_VOLUME24H = float(os.getenv("MIN_VOLUME24H", 10000))          # USD (user wants >= 10,000)
MAX_AGE_MINUTES = int(os.getenv("MAX_AGE_MINUTES", 60))           # minutes since pair creation (user wants <= 1 hour)
MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", 1_000_000))    # USD (user wants <= 1,000,000)
PROFILE_REQUIRED = os.getenv("PROFILE_REQUIRED", "true").lower() in ("1","true","yes","y")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 30))  # polling frequency

# DexScreener API endpoint for Solana pairs (all DEXes on Solana)
DEX_API = "https://api.dexscreener.com/latest/dex/pairs/solana"

# ======================
# Duplicate tracking DB
# ======================
DB_PATH = os.getenv("DB_PATH", "alerts.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS alerts (address TEXT PRIMARY KEY)")
conn.commit()

def send_telegram_message(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram config missing: TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def extract_market_cap(token: dict) -> float:
    # DexScreener typically exposes 'marketCap' and/or 'fdv'
    mc = token.get("marketCap")
    if mc is None:
        mc = token.get("fdv")
    try:
        return float(mc or 0)
    except Exception:
        return 0.0

def has_profile(token: dict) -> bool:
    # Heuristic: presence of 'info' object with any metadata
    info = token.get("info") or {}
    # Consider profile present if any of these fields exist
    keys = ("imageUrl", "websites", "twitter", "telegram", "discord", "socials")
    return any(k in info and info.get(k) for k in keys)

def check_new_tokens():
    try:
        r = requests.get(DEX_API, timeout=15)
        r.raise_for_status()
        data = r.json().get("pairs", [])
        now_ms = datetime.now(timezone.utc).timestamp() * 1000

        for token in data:
            pair_address = token.get("pairAddress")
            if not pair_address:
                continue

            base_token = token.get("baseToken", {}).get("symbol", "?")
            quote_token = token.get("quoteToken", {}).get("symbol", "?")
            created_at = token.get("pairCreatedAt", 0) or 0
            liq_usd = float(token.get("liquidity", {}).get("usd", 0) or 0)
            vol24_usd = float(token.get("volume", {}).get("h24", 0) or 0)
            market_cap = extract_market_cap(token)
            profile_ok = has_profile(token)

            # age minutes
            age_minutes = (now_ms - created_at) / 60000 if created_at else 999999

            # "Profile yes" requirement
            if PROFILE_REQUIRED and not profile_ok:
                continue

            # Apply filters
            if (liq_usd >= MIN_LIQUIDITY and
                vol24_usd >= MIN_VOLUME24H and
                age_minutes <= MAX_AGE_MINUTES and
                market_cap <= MAX_MARKET_CAP):

                # De-duplicate
                cursor.execute("SELECT 1 FROM alerts WHERE address=?", (pair_address,))
                if cursor.fetchone():
                    continue  # already alerted

                # Store and alert
                cursor.execute("INSERT OR IGNORE INTO alerts (address) VALUES (?)", (pair_address,))
                conn.commit()

                link = f"https://dexscreener.com/solana/{pair_address}"
                age_str = f"{age_minutes:.1f} min"
                msg = (
                    "🚀 <b>New Solana Token Match</b>\n\n"
                    f"Pair: <b>{base_token}/{quote_token}</b>\n"
                    f"Liquidity: ${liq_usd:,.0f}\n"
                    f"24h Volume: ${vol24_usd:,.0f}\n"
                    f"Market Cap: ${market_cap:,.0f}\n"
                    f"Age: {age_str}\n"
                    f"Profile: {'Yes' if profile_ok else 'No'}\n\n"
                    f"<a href='{link}'>Open in DexScreener</a>"
                )
                send_telegram_message(msg)

    except Exception as e:
        print("Polling error:", e)

def poll_loop():
    while True:
        check_new_tokens()
        time.sleep(CHECK_INTERVAL_SECONDS)

# ======================
# Minimal web server so Cloud Run can keep the container alive
# ======================
from flask import Flask
app = Flask(__name__)

@app.route("/")
def root():
    return "Solana alert bot is running", 200

if __name__ == "__main__":
    # Start polling loop in background thread
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

    # Start HTTP server (Cloud Run expects a web server)
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
