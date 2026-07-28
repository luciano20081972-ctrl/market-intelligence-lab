import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function StrategyLab() {
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const [strategyId, setStrategyId] = useState("");
  const [symbols, setSymbols] = useState("AAPL,MSFT");
  const [benchmark, setBenchmark] = useState("SPY");
  const [start, setStart] = useState("2025-01-02");
  const [end, setEnd] = useState("2025-06-18");
  const [cash, setCash] = useState("100000");
  const [commission, setCommission] = useState("1");
  const [spread, setSpread] = useState("2");
  const [slippage, setSlippage] = useState("1");
  const [maxPosition, setMaxPosition] = useState("0.40");
  const [maxExposure, setMaxExposure] = useState("1.00");
  const [parameters, setParameters] = useState("{}");
  const [validation, setValidation] = useState("");
  const run = useMutation({
    mutationFn: api.createBacktest,
    onSuccess: result => navigate(`/backtests/${result.id}`),
  });
  if (query.isLoading) return <LoadingState label="Loading strategy catalog" />;
  if (query.error) return <ErrorState error={query.error} />;
  const strategies = query.data!.items;
  const selected = strategyId || strategies[0]?.latest_version.id || "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(parameters) as Record<string, unknown>;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error();
    } catch {
      setValidation("Strategy parameters must be a valid JSON object.");
      return;
    }
    setValidation("");
    run.mutate({
      strategy_version_id: selected,
      parameters: parsed,
      symbols: symbols.split(",").map(value => value.trim().toUpperCase()).filter(Boolean),
      benchmark_symbol: benchmark.trim().toUpperCase(),
      start_time: `${start}T21:00:00Z`, end_time: `${end}T21:00:00Z`,
      initial_cash: cash, commission, spread_bps: spread, slippage_bps: slippage,
      execution_delay: 1, max_position_pct: maxPosition, max_total_exposure: maxExposure,
    });
  };
  return <section>
    <div className="page-heading"><div><p className="eyebrow">TRANSPARENT RESEARCH</p><h1>Strategy Lab</h1><p>Inspect deterministic rules and launch reproducible, no-lookahead simulations.</p></div><Link className="button" to="/backtests">Backtest history</Link></div>
    <form className="panel research-form" onSubmit={submit}>
      <div className="form-grid"><label><span>Strategy</span><select aria-label="Strategy" value={selected} onChange={e => { setStrategyId(e.target.value); const value = strategies.find(item => item.latest_version.id === e.target.value); setParameters(JSON.stringify(value?.latest_version.parameters ?? {}, null, 2)); }}>{strategies.map(strategy => <option key={strategy.id} value={strategy.latest_version.id}>{strategy.name} · v{strategy.latest_version.version}</option>)}</select></label><label><span>Symbols</span><input aria-label="Symbols" required value={symbols} onChange={e => setSymbols(e.target.value)} /></label><label><span>Benchmark</span><input aria-label="Benchmark" required value={benchmark} onChange={e => setBenchmark(e.target.value)} /></label><label><span>Initial cash</span><input aria-label="Initial cash" type="number" min="1" required value={cash} onChange={e => setCash(e.target.value)} /></label><label><span>Start date</span><input aria-label="Start date" type="date" required value={start} onChange={e => setStart(e.target.value)} /></label><label><span>End date</span><input aria-label="End date" type="date" required value={end} onChange={e => setEnd(e.target.value)} /></label><label><span>Commission</span><input aria-label="Commission" type="number" min="0" step="any" required value={commission} onChange={e => setCommission(e.target.value)} /></label><label><span>Spread (bps)</span><input aria-label="Spread" type="number" min="0" step="any" required value={spread} onChange={e => setSpread(e.target.value)} /></label><label><span>Slippage (bps)</span><input aria-label="Slippage" type="number" min="0" step="any" required value={slippage} onChange={e => setSlippage(e.target.value)} /></label><label><span>Max position (decimal)</span><input aria-label="Maximum position" type="number" min="0.0001" max="1" step="any" required value={maxPosition} onChange={e => setMaxPosition(e.target.value)} /></label><label><span>Max exposure (decimal)</span><input aria-label="Maximum exposure" type="number" min="0.0001" max="1" step="any" required value={maxExposure} onChange={e => setMaxExposure(e.target.value)} /></label><label className="parameter-field"><span>Parameters (JSON)</span><textarea aria-label="Strategy parameters" value={parameters} onChange={e => setParameters(e.target.value)} /></label></div>
      {validation && <p className="validation-error" role="alert">{validation}</p>}
      <div className="form-actions"><p className="muted">Shared cash · next eligible bar · commission, spread, and slippage included.</p><button disabled={run.isPending || !selected}>{run.isPending ? "Running…" : "Run backtest"}</button></div>
    </form>
    {run.error && <ErrorState error={run.error} />}
    <div className="strategy-grid">{strategies.map(strategy => <article className="panel strategy-card" key={strategy.id}><div className="panel-title"><div><p className="eyebrow">{strategy.strategy_type.replaceAll("_", " ")}</p><h2>{strategy.name}</h2></div><span className="tag">v{strategy.latest_version.version}</span></div><p>{strategy.description}</p><dl className="detail-list"><div><dt>Parameters</dt><dd>{Object.keys(strategy.latest_version.parameters).length || "None"}</dd></div><div><dt>Built in</dt><dd>{strategy.is_builtin ? "Yes" : "No"}</dd></div></dl><details><summary>Calculation notes</summary><p>{strategy.latest_version.calculation_notes}</p></details></article>)}</div>
  </section>;
}
