import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function AssetDetail() {
  const { symbol = "" } = useParams();
  const [range, setRange] = useState(90);
  const asset = useQuery({ queryKey: ["asset", symbol], queryFn: () => api.asset(symbol) });
  const prices = useQuery({ queryKey: ["prices", symbol], queryFn: () => api.prices(symbol) });
  if (asset.isLoading || prices.isLoading) return <LoadingState label={`Loading ${symbol}`} />;
  const error = asset.error || prices.error;
  if (error) return <ErrorState error={error} />;
  const rows = [...prices.data!.items].reverse().slice(-range);
  const chart = rows.map(bar => ({ date: new Date(bar.event_time).toLocaleDateString(undefined, { month: "short", day: "numeric" }), close: Number(bar.close), volume: bar.volume }));
  const latest = prices.data!.items[0];
  return <section>
    <Link className="back-link" to="/assets">← Asset explorer</Link>
    <div className="asset-hero"><div><div className="symbol-line"><h1>{asset.data!.symbol}</h1><span className="tag">{asset.data!.asset_type}</span></div><p>{asset.data!.name}</p><div className="metadata"><span>{asset.data!.exchange}</span><span>{asset.data!.currency}</span><span>{asset.data!.sector ?? "Diversified"}</span><span>{asset.data!.industry ?? "—"}</span></div></div><div className="quote"><span>Latest demo close</span><strong>{latest ? `$${Number(latest.close).toFixed(2)}` : "—"}</strong><small>{latest ? new Date(latest.event_time).toLocaleString() : "No stored bars"}</small></div></div>
    <div className="range-buttons" aria-label="Select date range">{[30, 90, 120].map(days => <button className={range === days ? "active" : ""} onClick={() => setRange(days)} key={days}>{days}D</button>)}</div>
    <article className="panel chart-panel"><div className="panel-title"><div><p className="eyebrow">PRICE HISTORY</p><h2>Adjusted close</h2></div><span>{rows.length} daily observations</span></div><div className="chart"><ResponsiveContainer width="100%" height={300}><LineChart data={chart}><CartesianGrid stroke="#26313d" vertical={false} /><XAxis dataKey="date" tick={{ fill: "#8291a3", fontSize: 11 }} minTickGap={30} /><YAxis domain={["auto", "auto"]} tick={{ fill: "#8291a3", fontSize: 11 }} width={60} /><Tooltip contentStyle={{ background: "#101720", border: "1px solid #2b3744" }} /><Line type="monotone" dataKey="close" stroke="#4fd1a1" dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer></div>
      <div className="chart volume"><ResponsiveContainer width="100%" height={120}><BarChart data={chart}><XAxis dataKey="date" hide /><YAxis hide /><Tooltip contentStyle={{ background: "#101720", border: "1px solid #2b3744" }} /><Bar dataKey="volume" fill="#3d6d80" /></BarChart></ResponsiveContainer></div></article>
    <article className="panel"><div className="panel-title"><div><p className="eyebrow">PROVENANCE</p><h2>Source and freshness</h2></div></div>{latest && <dl className="detail-list compact"><div><dt>Source</dt><dd>{latest.source_name}</dd></div><div><dt>Event time</dt><dd>{new Date(latest.event_time).toLocaleString()}</dd></div><div><dt>Publication time</dt><dd>{new Date(latest.publication_time).toLocaleString()}</dd></div><div><dt>Effective time</dt><dd>{new Date(latest.effective_time).toLocaleString()}</dd></div><div><dt>Retrieved</dt><dd>{new Date(latest.retrieval_time).toLocaleString()}</dd></div><div><dt>Classification</dt><dd>Synthetic demonstration</dd></div></dl>}</article>
    <div className="table-card"><table><thead><tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>Source</th></tr></thead><tbody>{[...rows].reverse().slice(0, 30).map(bar => <tr key={bar.id}><td>{new Date(bar.event_time).toLocaleDateString()}</td><td className="number">{Number(bar.open).toFixed(2)}</td><td className="number">{Number(bar.high).toFixed(2)}</td><td className="number">{Number(bar.low).toFixed(2)}</td><td className="number">{Number(bar.close).toFixed(2)}</td><td className="number">{bar.volume.toLocaleString()}</td><td>{bar.source_name}</td></tr>)}</tbody></table></div>
  </section>;
}
