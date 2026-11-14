import React, {useCallback, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, RefreshCw, TrendingUp, TrendingDown, ShieldCheck, Zap, BarChart3, Info, Search, Clock3} from 'lucide-react';
import './style.css';

const API=(import.meta.env.VITE_API_URL||'http://localhost:8000').replace(/\/$/,'');
const coins=['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT','ADAUSDT','LINKUSDT','AVAXUSDT'];
const timeframes=['15m','1h','4h','1d'];
const fmt=(n,d=2)=>n==null||!Number.isFinite(Number(n))?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
const label=s=>s?s.replace('USDT',''):'—';

function App(){
 const [symbol,setSymbol]=useState('BTCUSDT'),[tf,setTf]=useState('1h');
 const [balance,setBalance]=useState('1000'),[risk,setRisk]=useState('1');
 const [data,setData]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const [last,setLast]=useState(null),[universe,setUniverse]=useState([]);
 const [universeLoading,setUniverseLoading]=useState(false),[universeError,setUniverseError]=useState('');
 const [universeLast,setUniverseLast]=useState(null);

 const scan=useCallback(async()=>{
  const cash=Number(balance),rp=Number(risk);
  if(!Number.isFinite(cash)||cash<0||!Number.isFinite(rp)||rp<0||rp>5){setError('Enter a valid account size and risk percentage between 0 and 5.');return;}
  setLoading(true);setError('');
  try{
   const q=new URLSearchParams({symbol,timeframe:tf,balance:String(cash),risk_pct:String(rp)});
   const response=await fetch(API+'/api/scan?'+q),body=await response.json();
   if(!response.ok)throw new Error(body.detail||'Unable to load market data.');
   setData(body);setLast(new Date());
  }catch(e){setError(e.message||'Connection failed. Check the API URL and backend status.');setData(null);}
  finally{setLoading(false);}
 },[symbol,tf,balance,risk]);

 const scanUniverse=useCallback(async()=>{
  const cash=Number(balance),rp=Number(risk);
  if(!Number.isFinite(cash)||cash<0||!Number.isFinite(rp)||rp<0||rp>5){setUniverseError('Enter a valid account size and risk percentage between 0 and 5.');return;}
  setUniverseLoading(true);setUniverseError('');
  try{
   const q=new URLSearchParams({balance:String(cash),risk_pct:String(rp)});
   const response=await fetch(API+'/api/scan/universe?'+q),body=await response.json();
   if(!response.ok)throw new Error(body.detail||'Market-wide scan failed.');
   setUniverse(body.results||[]);setUniverseLast(new Date());
  }catch(e){setUniverseError(e.message||'Could not complete market-wide scan.');}
  finally{setUniverseLoading(false);}
 },[balance,risk]);

 useEffect(()=>{scan();},[scan]);
 useEffect(()=>{const timer=window.setInterval(()=>scan(),60000);return()=>window.clearInterval(timer);},[scan]);
 const action=data?.action||'—';
 const sortedUniverse=universe.filter(x=>x.action!=='ERROR').sort((a,b)=>b.confidence-a.confidence);

 return <div className="app">
  <header><div className="brand"><div className="logo"><Activity size={22}/></div><div><b>Signal<span>Pro</span></b><small>CRYPTO MARKET INTELLIGENCE</small></div></div><div className="live"><i/> LIVE MARKET DATA</div></header>
  <main>
   <section className="welcome"><div><div className="eyebrow">MARKET SCANNER / SPOT MARKETS</div><h1>Trade with a <em>clearer signal.</em></h1><p>Multi-timeframe technical analysis, risk-aware trade levels and plain-English explanations.</p></div><div className="shield"><ShieldCheck size={25}/><span>Analysis mode<br/><b>No auto-trading</b></span></div></section>
   <section className="controls panel">
    <label>ASSET<select value={symbol} onChange={e=>setSymbol(e.target.value)}>{coins.map(c=><option key={c}>{c}</option>)}</select></label>
    <label>TIMEFRAME<select value={tf} onChange={e=>setTf(e.target.value)}>{timeframes.map(c=><option key={c}>{c}</option>)}</select></label>
    <label>ACCOUNT SIZE (USDT)<input type="number" min="0" step="any" value={balance} onChange={e=>setBalance(e.target.value)}/></label>
    <label>RISK PER TRADE (%)<input type="number" min="0" max="5" step=".25" value={risk} onChange={e=>setRisk(e.target.value)}/></label>
    <button className="scan" onClick={scan} disabled={loading}>{loading?<RefreshCw className="spin" size={17}/>:<Zap size={17}/>} {loading?'Scanning':'Scan asset'}</button>
   </section>
   {error&&<div className="error"><Info size={18}/>{error}<span>Confirm the backend is deployed and VITE_API_URL points to its public URL.</span></div>}
   {data&&<>
    <section className="grid">
     <div className="panel signal-card"><div className="card-top"><span>TECHNICAL SIGNAL</span><span className="tag">{tf.toUpperCase()}</span></div>
      <div className="signal-row"><div><div className="coin">{label(symbol)} <small>/ USDT</small></div><div className="price">${fmt(data.price)}</div></div>
       <div className={'action '+action.toLowerCase()}>{action==='BUY'?<TrendingUp/>:action==='SELL'?<TrendingDown/>:<Activity/>}{action}</div></div>
      <div className="confidence"><div><span>Indicator agreement score</span><b>{data.confidence}%</b></div><div className="bar"><i style={{width:data.confidence+'%'}}/></div><small>Rule-based score · not a probability of profit</small></div>
      <div className="reason-list">{data.reasons.map((r,i)=><div key={i}><i/> {r}</div>)}</div>
     </div>
     <div className="panel levels"><div className="card-top"><span>TRADE PLAN</span><span className="tag">USDT</span></div>
      {action==='HOLD'?<div className="hold"><Activity size={28}/><b>No confirmed setup</b><span>Wait for stronger alignment before considering an entry.</span></div>:<>
       <div className="level"><span>ENTRY ZONE</span><b>${fmt(data.entry_low)} – ${fmt(data.entry_high)}</b></div>
       <div className="level"><span>STOP LOSS</span><b className="red">${fmt(data.stop_loss)}</b></div>
       <div className="level"><span>TAKE PROFIT 1 (1.5R)</span><b className="green">${fmt(data.take_profit_1)}</b></div>
       <div className="level"><span>TAKE PROFIT 2 (2.5R)</span><b className="green">${fmt(data.take_profit_2)}</b></div>
       <div className="size"><span>Estimated position size</span><b>{fmt(data.position_size_base,5)} {label(symbol)}</b></div>
      </>}
     </div>
    </section>
    <section className="metrics">
     {[
      ['RSI (14)',fmt(data.rsi,1),data.rsi>70?'Overbought':data.rsi<30?'Oversold':'Momentum'],
      ['MACD',fmt(data.macd,4),data.macd>data.macd_signal?'Above signal':'Below signal'],
      ['EMA 20','$'+fmt(data.ema20),'Short trend'],['EMA 50','$'+fmt(data.ema50),'Medium trend'],
      ['EMA 200','$'+fmt(data.ema200),'Long trend'],['VOLUME',fmt(data.volume_ratio,2)+'x','20-candle average'],
      ['BB UPPER','$'+fmt(data.bb_upper),'Bollinger upper'],['BB LOWER','$'+fmt(data.bb_lower),'Bollinger lower'],
      ['ATR','$'+fmt(data.atr),fmt(data.atr_pct,2)+'% volatility']
     ].map(([a,b,c])=><div className="panel metric" key={a}><span>{a}</span><b>{b}</b><small>{c}</small></div>)}
    </section>
    <section className="grid lower">
     <div className="panel"><div className="card-top"><span>MARKET STRUCTURE</span><BarChart3 size={18}/></div><div className="level"><span>NEARBY SUPPORT</span><b>${fmt(data.support)}</b></div><div className="level"><span>NEARBY RESISTANCE</span><b>${fmt(data.resistance)}</b></div><div className="level"><span>BOLLINGER WIDTH</span><b>{fmt(data.bb_width_pct,2)}%</b></div></div>
     <div className="panel"><div className="card-top"><span>RISK MANAGEMENT</span><ShieldCheck size={18}/></div><div className="level"><span>RISK BUDGET</span><b>${fmt(data.risk_amount)}</b></div><div className="level"><span>RISK PER TRADE</span><b>{risk}%</b></div><p className="muted">Position size is an estimate. Account for fees, slippage, liquidity and exchange minimums. BUY sizing is capped by the entered spot balance.</p></div>
    </section>
    {data.ai_explanation&&<section className="panel explanation"><div className="card-top">AI EXPLANATION</div><p>{data.ai_explanation}</p></section>}
    <div className="updated"><Clock3 size={12}/> Closed-candle data: {data.data_as_of?new Date(data.data_as_of).toLocaleString():'—'} · Refreshed {last?.toLocaleTimeString()} · Binance public spot data</div>
   </>}
   <section className="panel universe-panel">
    <div className="universe-heading"><div><div className="card-top">MARKET-WIDE OPPORTUNITY SCAN</div><p className="muted">Scan 9 liquid assets across 15m, 1h and 4h (27 analyses). Results are ranked by indicator agreement.</p></div>
     <button className="scan" onClick={scanUniverse} disabled={universeLoading}>{universeLoading?<RefreshCw className="spin" size={17}/>:<Search size={17}/>} {universeLoading?'Scanning 27 markets':'Scan all markets'}</button></div>
    {universeError&&<div className="error">{universeError}</div>}
    {universe.length>0&&<>
     <div className="updated">Completed {universeLast?.toLocaleTimeString()} · {sortedUniverse.length}/27 successful</div>
     <div className="table-wrap"><table><thead><tr><th>ASSET</th><th>TF</th><th>SIGNAL</th><th>PRICE</th><th>RSI</th><th>AGREEMENT</th></tr></thead>
      <tbody>{sortedUniverse.map((item,i)=><tr key={item.symbol+'-'+item.timeframe+'-'+i}><td>{label(item.symbol)}/USDT</td><td>{item.timeframe}</td><td><span className={'table-action '+item.action.toLowerCase()}>{item.action}</span></td><td>${fmt(item.price)}</td><td>{fmt(item.rsi,1)}</td><td>{item.confidence}%</td></tr>)}</tbody></table></div>
     {universe.length>sortedUniverse.length&&<p className="muted">{universe.length-sortedUniverse.length} market requests failed. Retry the scan if needed.</p>}
    </>}
   </section>
   <footer><b><span>Signal</span>Pro</b><p>Research and paper-trading tool only. Not financial advice. No signals guarantee profit.</p><p>SELL indicates bearish bias for spot traders; the app does not place trades or open shorts.</p><p>Never risk money you cannot afford to lose.</p></footer>
  </main>
 </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
