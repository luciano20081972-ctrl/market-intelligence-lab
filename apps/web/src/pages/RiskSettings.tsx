import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function RiskSettings() {
  const { id = "" } = useParams(); const client = useQueryClient(); const [drafts, setDrafts] = useState<Record<string, string>>({});
  const query = useQuery({ queryKey: ["risk-rules", id], queryFn: () => api.riskRules(id) });
  const update = useMutation({ mutationFn: ({ ruleId, value, enabled }: { ruleId: string; value: string; enabled: boolean }) => api.updateRiskRule(id, ruleId, value, enabled), onSuccess: () => client.invalidateQueries({ queryKey: ["risk-rules", id] }) });
  if (query.isLoading) return <LoadingState label="Loading risk controls" />; if (query.error) return <ErrorState error={query.error} />;
  return <section className="narrow"><Link className="back-link" to={`/paper-portfolios/${id}`}>← Portfolio</Link><div className="page-heading"><div><p className="eyebrow">PRE-TRADE CONTROLS</p><h1>Risk settings</h1><p>Every simulated order is evaluated against these explicit portfolio-level rules.</p></div></div><div className="risk-list">{query.data!.map(rule => <article className="panel risk-row" key={rule.id}><div><h2>{rule.rule_type.replaceAll("_", " ")}</h2><p>{rule.is_enabled ? "Enabled" : "Disabled"}</p></div><label><span>Limit</span><input aria-label={rule.rule_type} type="number" min="0" step="any" value={drafts[rule.id] ?? rule.limit_value} onChange={e => setDrafts(old => ({ ...old, [rule.id]: e.target.value }))} /></label><button onClick={() => update.mutate({ ruleId: rule.id, value: drafts[rule.id] ?? rule.limit_value, enabled: rule.is_enabled })}>Save</button><button onClick={() => update.mutate({ ruleId: rule.id, value: drafts[rule.id] ?? rule.limit_value, enabled: !rule.is_enabled })}>{rule.is_enabled ? "Disable" : "Enable"}</button></article>)}</div>{update.error && <ErrorState error={update.error} />}</section>;
}
