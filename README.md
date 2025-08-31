# Solana Alert Bot (DexScreener → Telegram) — v2

Filters supported:
- Solana only (via endpoint)
- All DEXes (via endpoint)
- **Profile required** (heuristic: DexScreener `info` present)
- **Minimum 24h Volume**
- **Maximum Pair Age (minutes)**
- **Maximum Market Cap (uses `marketCap` or `fdv`)**

## Env Vars (copy/paste example below)
- `TELEGRAM_BOT_TOKEN` (required)
- `TELEGRAM_CHAT_ID` (required)
- `MIN_LIQUIDITY` (default `0`)
- `MIN_VOLUME24H` (default `10000`)
- `MAX_AGE_MINUTES` (default `60`)
- `MAX_MARKET_CAP` (default `1000000`)
- `PROFILE_REQUIRED` (default `true`)
- `CHECK_INTERVAL_SECONDS` (default `30`)

