import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Watchlists() {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [symbols, setSymbols] = useState<Record<string, string>>({});
  const query = useQuery({ queryKey: ["watchlists"], queryFn: api.watchlists });
  const refresh = () => client.invalidateQueries({ queryKey: ["watchlists"] });
  const create = useMutation({ mutationFn: api.createWatchlist, onSuccess: () => { setName(""); refresh(); } });
  const rename = useMutation({ mutationFn: ({ id, name: value }: { id: string; name: string }) => api.renameWatchlist(id, value), onSuccess: refresh });
  const remove = useMutation({ mutationFn: api.deleteWatchlist, onSuccess: refresh });
  const addAsset = useMutation({ mutationFn: ({ id, symbol }: { id: string; symbol: string }) => api.addAsset(id, symbol), onSuccess: (_, variables) => { setSymbols(old => ({ ...old, [variables.id]: "" })); refresh(); } });
  const removeAsset = useMutation({ mutationFn: ({ id, symbol }: { id: string; symbol: string }) => api.removeAsset(id, symbol), onSuccess: refresh });
  const submit = (event: FormEvent) => { event.preventDefault(); if (name.trim()) create.mutate(name.trim()); };
  if (query.isLoading) return <LoadingState label="Loading watchlists" />;
  if (query.error) return <ErrorState error={query.error} />;
  const mutationError = create.error || rename.error || remove.error || addAsset.error || removeAsset.error;
  return <section>
    <div className="page-heading"><div><p className="eyebrow">CURATED RESEARCH</p><h1>Watchlists</h1><p>Group the tracked universe and monitor deterministic snapshots.</p></div></div>
    <form className="create-form" onSubmit={submit}><label><span>New watchlist name</span><input aria-label="New watchlist name" value={name} onChange={e => setName(e.target.value)} maxLength={100} placeholder="e.g. Semiconductors" /></label><button className="button" disabled={!name.trim() || create.isPending}>Create watchlist</button></form>
    {mutationError && <ErrorState error={mutationError} />}
    {query.data!.length === 0 ? <EmptyState title="No watchlists yet" detail="Create your first watchlist above, then add a tracked symbol." /> : <div className="watchlist-grid">{query.data!.map(list => <article className="panel watchlist" key={list.id}>
      <div className="panel-title"><div><p className="eyebrow">{list.assets.length} ASSETS</p><h2>{list.name}</h2></div><div className="actions"><button onClick={() => { const value = window.prompt("Rename watchlist", list.name); if (value?.trim()) rename.mutate({ id: list.id, name: value.trim() }); }}>Rename</button><button className="danger" onClick={() => { if (window.confirm(`Delete ${list.name}?`)) remove.mutate(list.id); }}>Delete</button></div></div>
      <form className="inline-form" onSubmit={e => { e.preventDefault(); const symbol = symbols[list.id]?.trim(); if (symbol) addAsset.mutate({ id: list.id, symbol }); }}><input aria-label={`Add asset to ${list.name}`} value={symbols[list.id] ?? ""} onChange={e => setSymbols(old => ({ ...old, [list.id]: e.target.value.toUpperCase() }))} placeholder="Add symbol" /><button>Add</button></form>
      {list.assets.length === 0 ? <p className="muted">No assets in this watchlist.</p> : <div className="watch-assets">{list.assets.map(asset => <div key={asset.symbol}><Link className="symbol" to={`/assets/${asset.symbol}`}>{asset.symbol}<small>{asset.name}</small></Link><div className="price"><b>{asset.latest_price ? `$${Number(asset.latest_price).toFixed(2)}` : "—"}</b><small>{asset.latest_price_time ? new Date(asset.latest_price_time).toLocaleDateString() : "No data"}</small></div><button aria-label={`Remove ${asset.symbol}`} onClick={() => removeAsset.mutate({ id: list.id, symbol: asset.symbol })}>×</button></div>)}</div>}
    </article>)}</div>}
  </section>;
}
