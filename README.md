# Solana Alert Bot v2.1 (DexScreener → Telegram)
Uses DexScreener's documented endpoints:
- GET /token-profiles/latest/v1 → latest token profiles (filter to chainId=solana)
- GET /token-pairs/v1/{chainId}/{tokenAddress} → pools/pairs of a token

Steps:
1) Replace main.py in your repo with this version (or upload this whole package).
2) Deploy new revision in Cloud Run (env vars unchanged).
3) 404 polling errors should be gone.
