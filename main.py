import os
import time
import sqlite3
import requests
import threading
from datetime import datetime, timezone
from flask import Flask

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", 0))
MIN_VOLUME24H = float(os.getenv("MIN_VOLUME24H", 10000))
MAX_AGE_MINUTES = int(os.getenv("MAX_AGE_MINUTES", 60))
MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", 1_000_000))
PROFILE_REQUIRED = os.getenv("PROFILE_REQUIRED", "true").lower() in ("1","true","yes","y")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 10))

DB_PATH = os.getenv("DB_PATH", "alerts.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS alerts (address TEXT PRIMARY KEY)")
conn.commit()

# Documented endpoints
TOKEN_PROFILES_LATEST = "https://api.dexscreener.com/token-profiles/latest/v1"
TOKEN_POOLS = "https://api.dexscreener.com/token-pairs/v1/{chainId}/{tokenAddress}"

def send_telegram_message(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram config missing")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def extract_market_cap(pair: dict) -> float:
    mc = pair.get("marketCap")
    if mc is None:
        mc = pair.get("fdv")
    try:
        return float(mc or 0)
    except Exception:
        return 0.0

def has_profile(info: dict) -> bool:
    if not info:
        return False
    keys = ("imageUrl", "websites", "socials")
    return any(k in info and info.get(k) for k in keys)

def fetch_latest_spl_token_addresses():
    try:
        r = requests.get(TOKEN_PROFILES_LATEST, timeout=15)
        r.raise_for_status()
        data = r.json() or []
        addrs = [d.get("tokenAddress") for d in data if d.get("chainId") == "solana"]
        seen = set()
        out = []
        for a in addrs:
            if a and a not in seen:
                seen.add(a)
                out.append(a)
        return out[:100]
    except Exception as e:
        print("profiles fetch error:", e)
        return []

def fetch_pools_for_token(addr: str):
    try:
        url = TOKEN_POOLS.format(chainId="solana", tokenAddress=addr)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        print("pools fetch error:", e)
        return []

def check_new_tokens():
    addrs = fetch_latest_spl_token_addresses()
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    for token_addr in addrs:
        pools = fetch_pools_for_token(token_addr)
        for pair in pools:
            if pair.get("chainId") != "solana":
                continue
            pair_address = pair.get("pairAddress")
            if not pair_address:
                continue

            info = pair.get("info") or {}
            if PROFILE_REQUIRED and not has_profile(info):
                continue

            base_token = pair.get("baseToken", {}).get("symbol", "?")
            quote_token = pair.get("quoteToken", {}).get("symbol", "?")
            created_at = pair.get("pairCreatedAt") or 0
            liq_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)
            vol24_usd = float(pair.get("volume", {}).get("h24", 0) or 0)
            market_cap = extract_market_cap(pair)

            age_minutes = (now_ms - created_at) / 60000 if created_at else 999999

            if (liq_usd >= MIN_LIQUIDITY and
                vol24_usd >= MIN_VOLUME24H and
                age_minutes <= MAX_AGE_MINUTES and
                market_cap <= MAX_MARKET_CAP):

                cursor.execute("SELECT 1 FROM alerts WHERE address=?", (pair_address,))
                if cursor.fetchone():
                    continue
                cursor.execute("INSERT OR IGNORE INTO alerts (address) VALUES (?)", (pair_address,))
                conn.commit()

                link = f"https://dexscreener.com/solana/{pair_address}"
                msg = (
                    "🚀 <b>New Solana Token Match</b>\n\n"
                    f"Pair: <b>{base_token}/{quote_token}</b>\n"
                    f"Liquidity: ${liq_usd:,.0f}\n"
                    f"24h Volume: ${vol24_usd:,.0f}\n"
                    f"Market Cap: ${market_cap:,.0f}\n"
                    f"Age: {age_minutes:.1f} min\n\n"
                    f"<a href='{link}'>Open in DexScreener</a>"
                )
                send_telegram_message(msg)

def poll_loop():
    while True:
        try:
            check_new_tokens()
        except Exception as e:
            print("Polling loop error:", e)
        time.sleep(CHECK_INTERVAL_SECONDS)

app = Flask(__name__)

@app.route("/")
def root():
    return "Solana alert bot v2.1 running", 200

if __name__ == "__main__":
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
