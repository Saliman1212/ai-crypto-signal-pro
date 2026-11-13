import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, RefreshCw, TrendingUp, TrendingDown, ShieldCheck, Zap, BarChart3, Info} from 'lucide-react';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const coins = ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT','ADAUSDT','LINKUSDT','AVAXUSDT'];
const fmt = (n, d=2) => n == null ? '—' : Number(n).toLocaleString(undefined,{maximumFractionDigits:d, minimumFractionDigits:d});
function App(){
 const [symbol,setSymbol]=useState('BTCUSDT'), [tf,setTf]=useState('1h');
 const [balance,setBalance]=useState('1000'), [risk,setRisk]=useState('1');
 const [data,setData]=useState(null), [loading,setLoading]=useState(false), [error,setError]=useState('');
 const [last,setLast]=useState(null);
 async function scan(){
  setLoading(true);setError('');
  try{
   const q=new URLSearchParams({symbol,timeframe:tf,balance,risk_pct:risk});
   const r=await fetch(`${API}/api/scan?${q}`); if(!r.ok) throw new Error((await r.json()).detail||'Unable to load market data');
   const j=await r.json();setData(j);setLast(new Date());
  }catch(e){setError(e.message);setData(null)}finally{setLoading(false)}
 }
 useEffect(()=>{scan()},[symbol,tf]);
 const action=data?.action||'—';
 return <div className="app">
  <header><div className="brand"><div className="logo"><Activity size={22}/></div><div><b>Signal<span>Pro</span></b><small>AI CRYPTO MARKET INTELLIGENCE</small></div></div><div className="live"><i/> LIVE MARKET DATA</div></header>
  <main>
   <section className="welcome"><div><div className="eyebrow">MARKET SCANNER / SPOT MARKETS</div><h1>Trade with a <em>clearer signal.</em></h1><p>Technical market analysis, risk-aware trade levels and plain-English explanations.</p></div><div className="shield"><ShieldCheck size={25}/><span>Analysis mode<br/><b>No auto-trading</b></span></div></section>
   <section className="controls panel">
    <label>ASSET<select value={symbol} onChange={e=>setSymbol(e.target.value)}>{coins.map(c=><option key={c}>{c}</option>)}</select></label>
    <label>TIMEFRAME<select value={tf} onChange={e=>setTf(e.target.value)}>{['15m','1h','4h','1d'].map(c=><option key={c}>{c}</option>)}</select></label>
    <label>ACCOUNT SIZE (USDT)<input type="number" min="0" value={balance} onChange={e=>setBalance(e.target.value)}/></label>
    <label>RISK PER TRADE (%)<input type="number" min="0" max="5" step=".25" value={risk} onChange={e=>setRisk(e.target.value)}/></label>
    <button className="scan" onClick={scan} disabled={loading}>{loading?<RefreshCw className="spin" size={17}/>:<Zap size={17}/>} {loading?'Scanning':'Scan market'}</button>
   </section>
   {error&&<div className="error"><Info size={18}/>{error}<span>Make sure the backend is running and can reach Binance.</span></div>}
   {data&&<><section className="grid">
    <div className="panel signal-card"><div className="card-top"><span>AI-ASSISTED TECHNICAL SIGNAL</span><span className="tag">{tf.toUpperCase()}</span></div>
     <div className="signal-row"><div><div className="coin">{symbol.replace('USDT','')} <small>/ USDT</small></div><div className="price">${fmt(data.price)}</div></div>
      <div className={`action ${action.toLowerCase()}`}>{action==='BUY'?<TrendingUp/>:action==='SELL'?<TrendingDown/>:<Activity/>}{action}</div></div>
     <div className="confidence"><div><span>Signal confidence</span><b>{data.confidence}%</b></div><div className="bar"><i style={{width:`${data.confidence}%`}}/></div><small>Rule-based indicator agreement · not a probability of profit</small></div>
     <div className="reason-list">{data.reasons.map((r,i)=><div key={i}><i/> {r}</div>)}</div>
    </div>
    <div className="panel levels"><div className="card-top"><span>TRADE PLAN</span><span className="tag">USDT</span></div>
     {action==='HOLD'?<div className="hold"><Activity size={28}/><b>No confirmed setup</b><span>Wait for stronger alignment before considering an entry.</span></div>:<>
      <div className="level"><span>ENTRY ZONE</span><b>${fmt(data.entry_low)} – ${fmt(data.entry_high)}</b></div>
      <div className="level"><span>STOP LOSS</span><b className="red">${fmt(data.stop_loss)}</b></div>
      <div className="level"><span>TAKE PROFIT 1</span><b className="green">${fmt(data.take_profit_1)}</b></div>
      <div className="level"><span>TAKE PROFIT 2</span><b className="green">${fmt(data.take_profit_2)}</b></div>
      <div className="size"><span>Position size estimate</span><b>{fmt(data.position_size_base,5)} {symbol.replace('USDT','')}</b></div>
     </>}
    </div>
   </section>
   <section className="metrics">
    {[['RSI (14)',fmt(data.rsi,1),data.rsi>70?'Overbought':data.rsi<30?'Oversold':'Momentum'],['MACD',fmt(data.macd,4),data.macd>data.macd_signal?'Bullish cross':'Bearish cross'],['EMA 20',`$${fmt(data.ema20)}`,'Short trend'],['EMA 50',`$${fmt(data.ema50)}`,'Medium trend'],['EMA 200',`$${fmt(data.ema200)}`,'Long trend'],['VOLUME',`${fmt(data.volume_ratio,2)}x`,'20-candle average']].map(([a,b,c])=><div className="panel metric" key={a}><span>{a}</span><b>{b}</b><small>{c}</small></div>)}
   </section>
   <section className="grid lower">
    <div className="panel"><div className="card-top"><span>MARKET STRUCTURE</span><BarChart3 size={18}/></div><div className="level"><span>NEARBY SUPPORT</span><b>${fmt(data.support)}</b></div><div className="level"><span>NEARBY RESISTANCE</span><b>${fmt(data.resistance)}</b></div><div className="level"><span>ATR (14)</span><b>${fmt(data.atr)}</b></div></div>
    <div className="panel"><div className="card-top"><span>RISK MANAGEMENT</span><ShieldCheck size={18}/></div><div className="level"><span>RISK BUDGET</span><b>${fmt(data.risk_amount)}</b></div><div className="level"><span>RISK PER TRADE</span><b>{risk}%</b></div><p className="muted">Position size is estimated from the distance between entry and stop. Adjust for fees, slippage, leverage and minimum order sizes.</p></div>
   </section>
   {data.ai_explanation&&<section className="panel explanation"><div className="card-top">AI EXPLANATION</div><p>{data.ai_explanation}</p></section>}
   <div className="updated">Updated {last?.toLocaleTimeString()} · Source: Binance public spot market data</div>
   </>}
   <footer><b><span>Signal</span>Pro</b><p>For research and paper trading only. Not financial advice. No signal guarantees a profitable outcome.</p><p>Never risk money you cannot afford to lose.</p></footer>
  </main>
 </div>
}
createRoot(document.getElementById('root')).render(<App/>);
