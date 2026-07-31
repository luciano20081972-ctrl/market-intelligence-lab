import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function PaperPortfolios() {
  const client = useQueryClient(); const [name, setName] = useState(""); const [cash, setCash] = useState("100000");
  const query = useQuery({ queryKey: ["paper-portfolios"], queryFn: api.paperPortfolios });
  const create = useMutation({ mutationFn: () => api.createPaperPortfolio(name.trim(), cash), onSuccess: () => { setName(""); client.invalidateQueries({ queryKey: ["paper-portfolios"] }); } });
  if (query.isLoading) return <LoadingState label="Loading paper portfolios" />;
  if (query.error) return <ErrorState error={query.error} />;
  const submit = (event: FormEvent) => { event.preventDefault(); if (name.trim()) create.mutate(); };
  return <section><div className="page-heading"><div><p className="eyebrow">SIMULATION ONLY</p><h1>Paper portfolios</h1><p>Practice long-only order workflows against stored price bars. No broker connection exists.</p></div></div>
    <form className="create-form" onSubmit={submit}><label><span>Portfolio name</span><input aria-label="Portfolio name" value={name} onChange={e => setName(e.target.value)} placeholder="Research sandbox" /></label><label><span>Starting cash</span><input aria-label="Starting cash" type="number" min="1" step="0.01" value={cash} onChange={e => setCash(e.target.value)} /></label><button disabled={!name.trim() || create.isPending}>Create portfolio</button></form>{create.error && <ErrorState error={create.error} />}
    {!query.data!.length ? <EmptyState title="No paper portfolios" detail="Create a simulated portfolio to begin." /> : <div className="portfolio-grid">{query.data!.map(portfolio => <Link className="panel portfolio-card" key={portfolio.id} to={`/paper-portfolios/${portfolio.id}`}><div className="panel-title"><div><p className="eyebrow">{portfolio.status}</p><h2>{portfolio.name}</h2></div><span className="tag">{portfolio.open_order_count} open</span></div><strong className="portfolio-value">${Number(portfolio.portfolio_value).toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong><dl className="detail-list"><div><dt>Cash</dt><dd>${Number(portfolio.cash_balance).toLocaleString(undefined, { maximumFractionDigits: 2 })}</dd></div><div><dt>Exposure</dt><dd>{(Number(portfolio.exposure) * 100).toFixed(1)}%</dd></div><div><dt>Unrealized P&amp;L</dt><dd>${Number(portfolio.unrealized_pnl).toFixed(2)}</dd></div></dl></Link>)}</div>}
  </section>;
}
