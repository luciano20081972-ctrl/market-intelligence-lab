import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function CorporateActions() {
  const query = useQuery({ queryKey: ["corporate-actions"], queryFn: api.corporateActions });
  if (query.isLoading) return <LoadingState label="Loading corporate actions" />;
  if (query.error) return <ErrorState error={query.error} />;
  const items = query.data?.items ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">ADJUSTMENTS</p><h1>Corporate actions</h1><p>Splits, reverse splits, dividends, and symbol changes with raw prices preserved.</p></div></div>{items.length === 0 ? <EmptyState title="No corporate actions" detail="The current synthetic provider has no actions in this interval." /> : <div className="table-card"><table><thead><tr><th>Symbol</th><th>Type</th><th>Effective</th><th>Ratio / amount</th><th>Provider</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.symbol}</td><td>{item.action_type}</td><td>{new Date(item.effective_time).toLocaleString()}</td><td>{item.ratio ?? (item.amount ? item.amount + " " + item.currency : item.old_symbol && item.new_symbol ? item.old_symbol + " → " + item.new_symbol : "—")}</td><td>{item.provider_code}</td></tr>)}</tbody></table></div>}</section>;
}
