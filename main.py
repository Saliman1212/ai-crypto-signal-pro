import os
from typing import Optional
import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="AI Crypto Signal Pro", version="1.0.0")
origins = [os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=False,
    allow_methods=["GET"], allow_headers=["*"]
)

BINANCE = "https://api.binance.com"
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
INTERVALS = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

async def get_klines(symbol: str, interval: str, limit: int = 250):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BINANCE}/api/v3/klines",
                             params={"symbol": symbol.upper(), "interval": interval, "limit": limit})
        r.raise_for_status()
        raw = r.json()
    cols = ["open_time","open","high","low","close","volume","close_time",
            "quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df

def enrich(df):
    d = df.copy()
    close = d.close
    d["ema20"] = close.ewm(span=20, adjust=False).mean()
    d["ema50"] = close.ewm(span=50, adjust=False).mean()
    d["ema200"] = close.ewm(span=200, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = (100 - (100 / (1 + rs))).fillna(50)
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    d["macd"] = fast - slow
    d["macd_signal"] = d.macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d.macd - d.macd_signal
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    d["bb_upper"] = mid + 2 * std
    d["bb_lower"] = mid - 2 * std
    prev = d.close.shift(1)
    tr = pd.concat([(d.high-d.low), (d.high-prev).abs(), (d.low-prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.rolling(14).mean()
    d["vol_avg"] = d.volume.rolling(20).mean()
    return d

def build_signal(d, symbol, timeframe, balance, risk_pct):
    x = d.iloc[-1]
    price = float(x.close)
    score = 0
    reasons = []
    if x.close > x.ema20 > x.ema50:
        score += 2; reasons.append("Price is above EMA20 and EMA50 (short-term bullish structure).")
    elif x.close < x.ema20 < x.ema50:
        score -= 2; reasons.append("Price is below EMA20 and EMA50 (short-term bearish structure).")
    else:
        reasons.append("Price/EMA20/EMA50 structure is mixed.")
    if x.close > x.ema200:
        score += 1; reasons.append("Price is above EMA200.")
    else:
        score -= 1; reasons.append("Price is below EMA200.")
    if x.macd > x.macd_signal:
        score += 1; reasons.append("MACD is above its signal line.")
    else:
        score -= 1; reasons.append("MACD is below its signal line.")
    if 50 <= x.rsi <= 68:
        score += 1; reasons.append("RSI shows positive momentum without being deeply overbought.")
    elif x.rsi < 35:
        score += 1; reasons.append("RSI is oversold; a reversal is possible but needs confirmation.")
    elif x.rsi > 72:
        score -= 1; reasons.append("RSI is elevated; chasing a long entry carries risk.")
    else:
        reasons.append("RSI momentum is neutral or weak.")
    vol_ratio = float(x.volume / x.vol_avg) if pd.notna(x.vol_avg) and x.vol_avg else 1.0
    if vol_ratio >= 1.25:
        score += 1 if x.close >= d.close.iloc[-2] else -1
        reasons.append(f"Volume is elevated at {vol_ratio:.2f}x its 20-candle average.")
    else:
        reasons.append(f"Volume is below the confirmation threshold ({vol_ratio:.2f}x average).")

    # Use recent completed candles for local levels; exclude current candle.
    recent = d.iloc[-21:-1]
    support = float(recent.low.min())
    resistance = float(recent.high.max())
    atr = float(x.atr) if pd.notna(x.atr) and x.atr > 0 else price * 0.01

    if score >= 3:
        action = "BUY"
        entry_low, entry_high = price - atr*0.20, price + atr*0.10
        stop = min(price - atr*1.5, support - atr*0.15)
        risk_per_unit = max(price-stop, atr*0.5)
        tp1, tp2 = price + risk_per_unit*1.5, price + risk_per_unit*2.5
    elif score <= -3:
        action = "SELL"
        entry_low, entry_high = price - atr*0.10, price + atr*0.20
        stop = max(price + atr*1.5, resistance + atr*0.15)
        risk_per_unit = max(stop-price, atr*0.5)
        tp1, tp2 = price - risk_per_unit*1.5, price - risk_per_unit*2.5
    else:
        action = "HOLD"
        entry_low = entry_high = stop = tp1 = tp2 = None
        risk_per_unit = None

    confidence = int(min(92, 50 + abs(score)*8 + (5 if vol_ratio >= 1.25 else 0)))
    risk_cash = max(0, float(balance) * max(0, float(risk_pct))/100)
    size = (risk_cash / risk_per_unit) if risk_per_unit and risk_per_unit > 0 else 0
    return {
        "symbol": symbol, "timeframe": timeframe, "action": action,
        "confidence": confidence, "score": score, "price": price,
        "entry_low": entry_low, "entry_high": entry_high, "stop_loss": stop,
        "take_profit_1": tp1, "take_profit_2": tp2,
        "support": support, "resistance": resistance, "rsi": float(x.rsi),
        "macd": float(x.macd), "macd_signal": float(x.macd_signal),
        "ema20": float(x.ema20), "ema50": float(x.ema50), "ema200": float(x.ema200),
        "volume_ratio": vol_ratio, "atr": atr, "risk_amount": risk_cash,
        "position_size_base": size, "reasons": reasons,
        "disclaimer": "Rule-based technical setup, not a prediction or guaranteed trade. Confirm before entering."
    }

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI Crypto Signal Pro"}

@app.get("/api/universe")
async def universe():
    return {"symbols": UNIVERSE, "timeframes": list(INTERVALS.keys())}

@app.get("/api/market")
async def market(symbol: str = "BTCUSDT", timeframe: str = "1h"):
    symbol = symbol.upper()
    if timeframe not in INTERVALS:
        raise HTTPException(400, "Unsupported timeframe")
    try:
        df = await get_klines(symbol, timeframe, 120)
        return {"symbol": symbol, "timeframe": timeframe,
                "candles": [{"time": int(row.open_time.timestamp()), "open": row.open,
                             "high": row.high, "low": row.low, "close": row.close,
                             "volume": row.volume} for row in df.tail(100).itertuples()]}
    except Exception as e:
        raise HTTPException(502, f"Market data unavailable: {str(e)}")

@app.get("/api/scan")
async def scan(symbol: str = "BTCUSDT", timeframe: str = "1h",
               balance: float = Query(1000, ge=0),
               risk_pct: float = Query(1, ge=0, le=5)):
    symbol = symbol.upper()
    if timeframe not in INTERVALS:
        raise HTTPException(400, "Unsupported timeframe")
    try:
        df = enrich(await get_klines(symbol, timeframe, 250)).dropna()
        if len(df) < 30:
            raise ValueError("Not enough candle history to calculate indicators")
        result = build_signal(df, symbol, timeframe, balance, risk_pct)
        key = os.getenv("OPENAI_API_KEY")
        if key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key)
                prompt = ("Explain this technical signal in plain language. Do not change the action, "
                          "levels, confidence or invent data. Mention uncertainty and invalidation. "
                          f"Signal JSON: {result}")
                response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=220
                )
                result["ai_explanation"] = response.choices[0].message.content
            except Exception:
                result["ai_explanation"] = "AI explanation unavailable; see the indicator reasons."
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Exchange returned an error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(502, f"Could not generate signal: {str(e)}")
