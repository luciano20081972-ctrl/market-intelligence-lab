import { useMutation } from "@tanstack/react-query";
import { api } from "../api";

export function AnalyticsComparison() {
  const mutation = useMutation({ mutationFn: api.analyticsComparison });
  return <section><div className="page-heading"><div><h1>Analytics comparison</h1>
    <p>Native canonical metrics reconciled with the QuantStats adapter.</p></div>
    <button onClick={() => mutation.mutate()}>Run analytics comparison</button></div>
    {mutation.data && <><div className="metric-grid"><article className="card"><small>Agreement</small><strong className="status-value">{mutation.data.agreement_status}</strong></article>
      <article className="card"><small>QuantStats</small><strong className="status-value">{mutation.data.engine_versions.quantstats}</strong></article></div>
      <div className="card"><table><thead><tr><th>Metric</th><th>Difference</th><th>Status</th><th>Methodology</th></tr></thead><tbody>
        {mutation.data.reconciliation.map((row) => <tr key={row.metric}><td>{row.metric}</td><td>{row.absolute_difference ?? "n/a"}</td><td>{row.agreement_status}</td><td>{row.methodology_note}</td></tr>)}
      </tbody></table></div></>}
    <p className="disclaimer">Research analytics only. No investment-performance guarantee.</p>
  </section>;
}
