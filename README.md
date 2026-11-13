# AI Crypto Signal Pro

A mobile-friendly crypto market scanner with live Binance spot data, technical indicators,
rule-based BUY / SELL / HOLD signals, risk sizing, and optional OpenAI explanations.

## What it does
- Scans BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK and AVAX (USDT pairs).
- Analyses 15m, 1h and 4h candles.
- Calculates EMA 20/50/200, RSI(14), MACD, Bollinger Bands, ATR, volume ratio,
  recent support/resistance and a simple trend score.
- Produces entry zone, stop loss, take-profit levels, confidence, risk/reward and
  position size based on the account balance and risk percentage you enter.
- Includes an optional OpenAI explanation. The signal itself is computed from
  market data and indicator rules, not invented by the language model.

## Important
This is an analysis and paper-planning tool, not a guarantee of profit or financial advice.
Crypto markets are volatile. Signals can fail, market data can be delayed, and exchange
availability can change. Start with paper trading. This app does not place trades,
connect to private exchange accounts, or withdraw funds.

## Run locally

### Backend
Requires Python 3.10+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Optional: add your OpenAI API key to .env for AI explanations
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal. The frontend expects the API at
`http://localhost:8000`; set `VITE_API_URL` if you host the API elsewhere.

## Deploy
- Deploy `backend/` as a Python web service with start command:
  `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Deploy `frontend/` as a static Vite site with build command `npm run build`
  and output directory `dist`.
- Set `VITE_API_URL` to your deployed backend URL.
- Set `OPENAI_API_KEY` only on the backend if you want AI explanations.
- Configure CORS in `backend/main.py` to your deployed frontend domain before production.

## API
- `GET /api/health`
- `GET /api/scan?symbol=BTCUSDT&timeframe=1h&balance=1000&risk_pct=1`
- `GET /api/market?symbol=BTCUSDT&timeframe=1h`
- `GET /api/universe`

All prices are quoted in USDT. The default universe is configurable in `backend/main.py`.
