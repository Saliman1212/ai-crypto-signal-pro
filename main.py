import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

APP_VERSION = "1.1.0"
BINANCE = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
INTERVALS = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

app = FastAPI(title="AI Crypto Signal Pro", version=APP_VERSION)
allowed_origins = [
    item.strip() for item in os.getenv(
        "FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    ).split(",") if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def validate_market(symbol: str, timeframe: str) -> tuple[str, str]:
    symbol = symbol.upper().strip()
    if symbol not in UNIVERSE:
        raise HTTPException(400, f"Unsupported symbol. Choose one of: {', '.join(UNIVERSE)}")
    if timeframe not in INTERVALS:
        raise HTTPException(400, f"Unsupported timeframe. Choose one of: {', '.join(INTERVALS)}")
    return symbol, timeframe


async def get_klines(client: httpx.AsyncClient, symbol: str, interval: str, limit: int = 250):
    # Binance's primary hostname can be unreachable or geo-restricted from some
    # cloud regions. Try the public market-data mirror and alternate API hosts.
    configured = BINANCE.rstrip("/")
    hosts = list(dict.fromkeys([
        configured,
        "https://data-api.binance.vision",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api4.binance.com",
    ]))
    columns = ["open_time", "open", "high", "low", "close", "volume", "close_time",
               "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
    failures = []

    for host in hosts:
        try:
            response = await client.get(
                f"{host}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=12.0,
            )
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, list) or not raw:
                raise ValueError("The exchange returned an empty candle response.")

            frame = pd.DataFrame(raw, columns=columns)
            for column in ["open", "high", "low", "close", "volume"]:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
            frame["close_time"] = pd.to_numeric(frame["close_time"], errors="coerce")
            frame = frame.dropna(subset=["open", "high", "low", "close", "volume", "close_time"])

            # Exclude the still-forming candle so signals use closed-candle data only.
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            frame = frame.loc[frame["close_time"] < now_ms].reset_index(drop=True)
            if frame.empty:
                raise ValueError("No completed candles were returned.")
            return frame
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            failures.append(f"{host} ({status or type(exc).__name__})")

    raise ValueError(
        "Binance market data is unreachable from the backend. Tried primary, "
        "data-api mirror and alternate hosts: " + "; ".join(failures)
    )


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    close = data["close"]

    data["ema20"] = close.ewm(span=20, adjust=False).mean()
    data["ema50"] = close.ewm(span=50, adjust=False).mean()
    data["ema200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50)
    data["rsi"] = rsi

    macd_fast = close.ewm(span=12, adjust=False).mean()
    macd_slow = close.ewm(span=26, adjust=False).mean()
    data["macd"] = macd_fast - macd_slow
    data["macd_signal"] = data["macd"].ewm(span=9, adjust=False).mean()
    data["macd_hist"] = data["macd"] - data["macd_signal"]

    middle = close.rolling(20).mean()
    deviation = close.rolling(20).std()
    data["bb_middle"] = middle
    data["bb_upper"] = middle + 2 * deviation
    data["bb_lower"] = middle - 2 * deviation
    data["bb_width_pct"] = ((data["bb_upper"] - data["bb_lower"]) / middle) * 100

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(data["high"] - data["low"]),
         (data["high"] - previous_close).abs(),
         (data["low"] - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    data["atr"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    data["vol_avg"] = data["volume"].rolling(20).mean()
    return data


def build_signal(data: pd.DataFrame, symbol: str, timeframe: str,
                 balance: float, risk_pct: float) -> dict[str, Any]:
    if len(data) < 205:
        raise ValueError("Not enough completed candle history for EMA200. Try again later.")

    latest = data.iloc[-1]
    previous = data.iloc[-2]
    price = float(latest["close"])
    score = 0
    reasons: list[str] = []

    if latest["close"] > latest["ema20"] > latest["ema50"]:
        score += 2
        reasons.append("Price is above EMA20 and EMA50: short-term structure is bullish.")
    elif latest["close"] < latest["ema20"] < latest["ema50"]:
        score -= 2
        reasons.append("Price is below EMA20 and EMA50: short-term structure is bearish.")
    else:
        reasons.append("Price, EMA20 and EMA50 are not aligned.")

    if latest["close"] > latest["ema200"]:
        score += 1
        reasons.append("Price is above EMA200, supporting the broader trend.")
    else:
        score -= 1
        reasons.append("Price is below EMA200, weakening the broader trend.")

    if latest["macd"] > latest["macd_signal"]:
        score += 1
        reasons.append("MACD is above its signal line.")
    else:
        score -= 1
        reasons.append("MACD is below its signal line.")

    rsi = float(latest["rsi"])
    if 50 <= rsi <= 68:
        score += 1
        reasons.append("RSI momentum is positive without being extremely overbought.")
    elif rsi < 30:
        score += 1
        reasons.append("RSI is oversold; a bounce is possible but needs price confirmation.")
    elif rsi > 72:
        score -= 1
        reasons.append("RSI is elevated; chasing a long entry is risky.")
    else:
        reasons.append("RSI is neutral or does not strongly confirm direction.")

    volume_average = float(latest["vol_avg"]) if pd.notna(latest["vol_avg"]) else 0.0
    volume_ratio = float(latest["volume"] / volume_average) if volume_average > 0 else 0.0
    if volume_ratio >= 1.25:
        score += 1 if latest["close"] >= previous["close"] else -1
        reasons.append(f"Volume is elevated at {volume_ratio:.2f}x its 20-candle average.")
    else:
        reasons.append(f"Volume confirmation is limited ({volume_ratio:.2f}x its 20-candle average).")

    recent = data.iloc[-21:-1]
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())
    atr = float(latest["atr"]) if pd.notna(latest["atr"]) and latest["atr"] > 0 else price * 0.01

    if score >= 3:
        action = "BUY"
        entry_low, entry_high = price - atr * 0.20, price + atr * 0.10
        stop = min(price - atr * 1.5, support - atr * 0.15)
        risk_per_unit = max(price - stop, atr * 0.5)
        target1, target2 = price + risk_per_unit * 1.5, price + risk_per_unit * 2.5
    elif score <= -3:
        action = "SELL"
        entry_low, entry_high = price - atr * 0.10, price + atr * 0.20
        stop = max(price + atr * 1.5, resistance + atr * 0.15)
        risk_per_unit = max(stop - price, atr * 0.5)
        target1, target2 = price - risk_per_unit * 1.5, price - risk_per_unit * 2.5
    else:
        action = "HOLD"
        entry_low = entry_high = stop = target1 = target2 = None
        risk_per_unit = None

    confidence = int(min(92, 50 + abs(score) * 8 + (5 if volume_ratio >= 1.25 else 0)))
    risk_cash = float(balance) * float(risk_pct) / 100
    position_size = risk_cash / risk_per_unit if risk_per_unit and risk_per_unit > 0 else 0.0
    # A spot BUY cannot exceed the cash balance supplied by the user.
    if action == "BUY" and price > 0:
        position_size = min(position_size, float(balance) / price)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "confidence": confidence,
        "score": int(score),
        "price": price,
        "entry_low": float(entry_low) if entry_low is not None else None,
        "entry_high": float(entry_high) if entry_high is not None else None,
        "stop_loss": float(stop) if stop is not None else None,
        "take_profit_1": float(target1) if target1 is not None else None,
        "take_profit_2": float(target2) if target2 is not None else None,
        "support": support,
        "resistance": resistance,
        "rsi": rsi,
        "macd": float(latest["macd"]),
        "macd_signal": float(latest["macd_signal"]),
        "macd_hist": float(latest["macd_hist"]),
        "ema20": float(latest["ema20"]),
        "ema50": float(latest["ema50"]),
        "ema200": float(latest["ema200"]),
        "bb_upper": float(latest["bb_upper"]),
        "bb_middle": float(latest["bb_middle"]),
        "bb_lower": float(latest["bb_lower"]),
        "bb_width_pct": float(latest["bb_width_pct"]),
        "volume_ratio": volume_ratio,
        "atr": atr,
        "atr_pct": atr / price * 100 if price else 0,
        "risk_amount": risk_cash,
        "position_size_base": float(position_size),
        "risk_reward_1": 1.5 if action != "HOLD" else None,
        "risk_reward_2": 2.5 if action != "HOLD" else None,
        "reasons": reasons,
        "data_as_of": data.iloc[-1]["open_time"].isoformat(),
        "disclaimer": (
            "Rule-based technical analysis using closed candles, not a prediction or guarantee. "
            "SELL indicates bearish bias for spot traders; this app does not execute or open short positions."
        ),
    }


async def scan_one(client: httpx.AsyncClient, symbol: str, timeframe: str,
                   balance: float, risk_pct: float) -> dict[str, Any]:
    candles = await get_klines(client, symbol, timeframe, 250)
    indicators = enrich(candles).dropna(subset=[
        "ema200", "rsi", "macd", "macd_signal", "atr", "vol_avg",
        "bb_upper", "bb_lower",
    ])
    return build_signal(indicators, symbol, timeframe, balance, risk_pct)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI Crypto Signal Pro", "version": APP_VERSION}


@app.get("/api/universe")
async def universe():
    return {"symbols": UNIVERSE, "timeframes": list(INTERVALS.keys())}


@app.get("/api/market")
async def market(symbol: str = "BTCUSDT", timeframe: str = "1h"):
    symbol, timeframe = validate_market(symbol, timeframe)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            candles = await get_klines(client, symbol, timeframe, 120)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": [
                {
                    "time": int(row.open_time.timestamp()),
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                }
                for row in candles.tail(100).itertuples()
            ],
        }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Binance returned HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, f"Market data unavailable: {exc}") from exc


@app.get("/api/scan")
async def scan(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    balance: float = Query(1000, ge=0),
    risk_pct: float = Query(1, ge=0, le=5),
):
    symbol, timeframe = validate_market(symbol, timeframe)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            result = await scan_one(client, symbol, timeframe, balance, risk_pct)

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import AsyncOpenAI
                ai_client = AsyncOpenAI(api_key=api_key)
                response = await ai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{
                        "role": "user",
                        "content": (
                            "Explain this technical analysis in plain language. Do not change the "
                            "action, levels, confidence or invent data. State uncertainty and what "
                            f"would invalidate the setup. Data: {result}"
                        ),
                    }],
                    temperature=0.2,
                    max_tokens=220,
                )
                result["ai_explanation"] = response.choices[0].message.content
            except Exception:
                result["ai_explanation"] = "AI explanation is temporarily unavailable; use the indicator reasons."
        return result
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Binance returned HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(502, f"Could not generate signal: {exc}") from exc


@app.get("/api/scan/universe")
async def scan_universe(
    balance: float = Query(1000, ge=0),
    risk_pct: float = Query(1, ge=0, le=5),
):
    # Limit concurrency to be polite to the public exchange API.
    semaphore = asyncio.Semaphore(5)
    async with httpx.AsyncClient(timeout=20) as client:
        async def guarded(symbol: str, timeframe: str):
            async with semaphore:
                try:
                    return await scan_one(client, symbol, timeframe, balance, risk_pct)
                except Exception as exc:
                    return {"symbol": symbol, "timeframe": timeframe, "action": "ERROR",
                            "error": str(exc)}

        results = await asyncio.gather(
            *(guarded(symbol, timeframe) for symbol in UNIVERSE for timeframe in ("15m", "1h", "4h"))
        )
    return {
        "scanned": len(results),
        "successful": sum(1 for item in results if item["action"] != "ERROR"),
        "results": results,
        "disclaimer": "Market-wide technical scan only. Confirm setups independently; no trades are placed.",
    }
