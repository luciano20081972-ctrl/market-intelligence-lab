import { useQuery } from "@tanstack/react-query";
import { KeyboardEvent, useId, useState } from "react";
import { api } from "../api";
import type { Asset } from "../types";

interface AssetSearchProps {
  label: string;
  onSelect: (asset: Asset) => void;
  placeholder?: string;
  value?: string;
}

export function AssetSearch({ label, onSelect, placeholder = "Ticker or company", value = "" }: AssetSearchProps) {
  const [search, setSearch] = useState(value);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const listId = useId();
  const params = new URLSearchParams({ search, page_size: "8", active: "true" });
  const query = useQuery({
    queryKey: ["asset-search", search],
    queryFn: () => api.assets(params.toString()),
    enabled: search.trim().length >= 1,
    staleTime: 30_000,
  });
  const results = query.data?.items ?? [];
  function choose(asset: Asset) {
    setSearch(asset.symbol);
    setActive(0);
    setOpen(false);
    onSelect(asset);
  }
  function keyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault(); setActive(index => (index + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault(); setActive(index => (index - 1 + results.length) % results.length);
    } else if (event.key === "Enter") {
      const selected = results[active] ?? results[0];
      if (selected) { event.preventDefault(); choose(selected); }
    } else if (event.key === "Escape") {
      setSearch("");
    }
  }
  return <label className="asset-search"><span>{label}</span><input
    aria-autocomplete="list" aria-controls={listId} aria-expanded={open && results.length > 0}
    aria-label={label} autoComplete="off" value={search} placeholder={placeholder}
    onChange={event => { setSearch(event.target.value); setActive(0); setOpen(true); }} onKeyDown={keyDown}
  />
    {search && open && <div className="asset-search-results" id={listId} role="listbox">
      {query.isFetching ? <span className="asset-search-state">Searching catalog…</span> : null}
      {!query.isFetching && query.isSuccess && !results.length ? <span className="asset-search-state">No canonical assets found</span> : null}
      {results.map((asset, index) => <button aria-selected={index === active} className={index === active ? "active" : ""} key={asset.id} onMouseDown={event => event.preventDefault()} onClick={() => choose(asset)} role="option" type="button">
        <b>{asset.symbol}</b><span>{asset.name}<small>{asset.exchange} · {asset.asset_type}</small></span><i>{asset.capability.replaceAll("_", " ")}</i>
      </button>)}
    </div>}
  </label>;
}
