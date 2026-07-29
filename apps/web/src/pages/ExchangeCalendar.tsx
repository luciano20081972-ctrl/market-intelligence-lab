import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function ExchangeCalendar() {
  const query = useQuery({ queryKey: ["exchange-calendar"], queryFn: api.exchangeCalendar });
  if (query.isLoading) return <LoadingState label="Loading exchange calendar" />;
  if (query.error) return <ErrorState error={query.error} />;
  const items = query.data?.items ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">TRADING SESSIONS</p><h1>Exchange calendar</h1><p>Timezone-aware XNYS sessions exclude weekends and holidays and identify early closes.</p></div></div>{items.length === 0 ? <EmptyState title="No sessions" detail="Seed the exchange calendar before importing market bars." /> : <div className="table-card"><table><thead><tr><th>Date</th><th>Open</th><th>Close</th><th>Timezone</th><th>Session</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.session_date}</td><td>{new Date(item.open_time).toLocaleTimeString()}</td><td>{new Date(item.close_time).toLocaleTimeString()}</td><td>{item.timezone}</td><td>{item.is_early_close ? "Early close" : item.status}</td></tr>)}</tbody></table></div>}</section>;
}
