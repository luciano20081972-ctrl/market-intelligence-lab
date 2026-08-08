import { useMutation } from "@tanstack/react-query";
import { api } from "../api";

export function OptimizationExperiment() {
  const mutation = useMutation({ mutationFn: api.optimizationExperiment });
  return <section><div className="page-heading"><div><h1>Optimization experiment</h1>
    <p>skfolio adapter foundation · deterministic fixture · separated train/validation periods.</p></div>
    <button onClick={() => mutation.mutate()}>Run deterministic optimization</button></div>
    {mutation.data && <div className="card"><h2>{mutation.data.model}</h2><p>No shorting · no leverage · weights bounded to [0, 1].</p>
      <div className="metric-grid">{Object.entries(mutation.data.weights).map(([symbol, weight]) => <article className="card" key={symbol}><small>{symbol}</small><strong className="large-number">{(weight * 100).toFixed(2)}%</strong></article>)}</div>
      <p className="muted">Optimizer: {mutation.data.optimizer_version}</p></div>}
  </section>;
}
