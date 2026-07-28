import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function AssetExplorer() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("symbol");
  const params = new URLSearchParams({ page: String(page), page_size: "10", sort_by: sort });
  if (search) params.set("search", search);
  const query = useQuery({ queryKey: ["assets", params.toString()], queryFn: () => api.assets(params.toString()) });
  return <section>
    <div className="page-heading"><div><p className="eyebrow">RESEARCH UNIVERSE</p><h1>Asset explorer</h1><p>Inspect tracked stocks and ETFs with source-aware price snapshots.</p></div></div>
    <div className="toolbar"><label className="search-field"><span>Search</span><input aria-label="Search assets" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Symbol or company" /></label><label><span>Sort by</span><select aria-label="Sort assets" value={sort} onChange={e => setSort(e.target.value)}><option value="symbol">Symbol</option><option value="name">Name</option><option value="asset_type">Asset type</option><option value="exchange">Exchange</option></select></label></div>
    {query.isLoading ? <LoadingState label="Loading assets" /> : query.error ? <ErrorState error={query.error} /> : query.data!.items.length === 0 ? <EmptyState title="No matching assets" detail="Try a broader symbol or company name." /> : <div className="table-card"><table><thead><tr><th>Symbol</th><th>Name</th><th>Type</th><th>Exchange</th><th>Sector</th><th>Latest demo price</th><th>As of</th></tr></thead><tbody>{query.data!.items.map(asset => <tr key={asset.id}><td><Link className="symbol" to={`/assets/${asset.symbol}`}>{asset.symbol}</Link></td><td>{asset.name}</td><td><span className="tag">{asset.asset_type}</span></td><td>{asset.exchange}</td><td>{asset.sector ?? "Diversified"}</td><td className="number">{asset.latest_price ? `$${Number(asset.latest_price).toFixed(2)}` : "—"}</td><td>{asset.latest_price_time ? new Date(asset.latest_price_time).toLocaleDateString() : "—"}</td></tr>)}</tbody></table>
      <div className="pagination"><span>Page {query.data!.pagination.page} of {query.data!.pagination.pages || 1} · {query.data!.pagination.total} assets</span><div><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><button disabled={page >= query.data!.pagination.pages} onClick={() => setPage(page + 1)}>Next</button></div></div></div>}
  </section>;
}
