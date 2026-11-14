# AI Crypto Signal Pro

A responsive cryptocurrency market scanner that reads **public Binance spot-market candles** and calculates rule-based technical signals. It includes a single-asset analysis view and a market-wide scanner for nine liquid USDT pairs across 15-minute, 1-hour and 4-hour timeframes.

## Features

- Assets: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK and AVAX (USDT pairs).
- Timeframes: 15m, 1h, 4h and 1d for individual asset analysis.
- Closed-candle analysis to avoid basing signals on a still-forming candle.
- Indicators: EMA 20/50/200, RSI(14), MACD, Bollinger Bands, ATR and relative volume.
- Recent support/resistance, entry zone, invalidation stop, two illustrative targets and risk-based position sizing.
- Market-wide scan: 9 assets x 3 timeframes (27 analyses), ranked by indicator agreement.
- Optional OpenAI plain-language explanation. AI does not create or alter the signal.
- No exchange account connection, order placement, leverage or withdrawals.

## Repository layout

This repository is a small single-root project:

- `main.py` — FastAPI backend
- `main.jsx` — React/Vite frontend
- `style.css` — responsive interface
- `index.html` — frontend entry point
- `package.json` — frontend dependencies and scripts
- `requirements.txt` — backend dependencies
- `vite.config.js` — Vite configuration

## Run locally

### Backend (Python 3.11 recommended)

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Optional backend environment variables:

- `OPENAI_API_KEY` — enables optional AI explanations. Keep this secret on the backend only.
- `OPENAI_MODEL` — optional model override; defaults to `gpt-4o-mini`.
- `FRONTEND_ORIGINS` — comma-separated allowed frontend origins. Defaults to `http://localhost:5173`.
- `BINANCE_BASE_URL` — optional Binance API base URL override.

### Frontend

In a second terminal, from the repository root:

```bash
npm install
npm run dev
```

Open the Vite URL shown in the terminal. The frontend defaults to `http://localhost:8000` for the API. Set `VITE_API_URL` to the backend origin when hosted elsewhere.

## Deploy

### Backend on Render

Create a Python web service connected to this repository:

- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Python version: 3.11 (the `.python-version` file pins 3.11.11)
- Add `FRONTEND_ORIGINS` with your deployed frontend origin after the frontend is live.
- Optionally add `OPENAI_API_KEY` and `OPENAI_MODEL`.

### Frontend on Vercel

Import this same repository as a Vite project:

- Framework preset: Vite
- Root directory: `.`
- Build command: `npm run build`
- Output directory: `dist`
- Add `VITE_API_URL` as the public origin of the deployed Render backend (for example, `https://your-service.onrender.com`).

After deployment, check `/api/health` on the backend and run a scan in the frontend. The Render CORS allowlist must include the exact Vercel production domain (and any preview domains you intend to use).

## API

- `GET /api/health`
- `GET /api/universe`
- `GET /api/market?symbol=BTCUSDT&timeframe=1h`
- `GET /api/scan?symbol=BTCUSDT&timeframe=1h&balance=1000&risk_pct=1`
- `GET /api/scan/universe?balance=1000&risk_pct=1`

## Risk and limitations

This is a research and paper-trading aid, **not financial advice** and not a promise of profitable trades. Indicator agreement is a heuristic score, not a calibrated probability of success. Signals can fail, market data can be delayed or unavailable, and slippage, fees, liquidity and exchange minimums are not fully modeled.

Position size is an estimate based on the entered account balance and risk percentage. It does not know your actual wallet balance. A BUY estimate is capped by the entered spot balance; a SELL result represents bearish bias for spot traders and is not an instruction or mechanism to open a short position. Always independently verify a setup and paper trade before risking funds.
