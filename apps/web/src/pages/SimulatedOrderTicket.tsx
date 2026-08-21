import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { AssetSearch } from "../components/AssetSearch";
import { ErrorState } from "../components/States";
import type { OrderPayload } from "../types";

export function SimulatedOrderTicket() {
  const { id = "" } = useParams();
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [type, setType] = useState<OrderPayload["order_type"]>("market");
  const [quantity, setQuantity] = useState("10");
  const [limit, setLimit] = useState("");
  const [stop, setStop] = useState("");
  const [clientOrderId] = useState(() => `ui-${crypto.randomUUID()}`);
  const payload = (): OrderPayload => ({
    client_order_id: clientOrderId, symbol, side, order_type: type, quantity,
    ...(type === "limit" || type === "stop_limit" ? { limit_price: limit } : {}),
    ...(type === "stop" || type === "stop_limit" ? { stop_price: stop } : {}),
  });
  const preview = useMutation({ mutationFn: () => api.previewOrder(id, payload()) });
  const submit = useMutation({ mutationFn: (value: OrderPayload) => api.submitOrder(id, value) });
  const onSubmit = (event: FormEvent) => { event.preventDefault(); submit.mutate(payload()); };
  return <section className="narrow">
    <Link className="back-link" to={`/paper-portfolios/${id}`}>← Portfolio</Link>
    <div className="page-heading"><div><p className="eyebrow">SIMULATED EXECUTION</p><h1>Order ticket</h1><p>Preview risk checks and deterministic fill assumptions before submission.</p></div></div>
    <form className="panel research-form" onSubmit={onSubmit}>
      <div className="form-grid two">
        <AssetSearch label="Order asset" onSelect={asset => setSymbol(asset.symbol)} value={symbol} />
        <label><span>Side</span><select aria-label="Order side" value={side} onChange={event => setSide(event.target.value as "buy" | "sell")}><option value="buy">Buy</option><option value="sell">Sell</option></select></label>
        <label><span>Order type</span><select aria-label="Order type" value={type} onChange={event => setType(event.target.value as OrderPayload["order_type"])}><option value="market">Market</option><option value="limit">Limit</option><option value="stop">Stop</option><option value="stop_limit">Stop limit</option></select></label>
        <label><span>Quantity</span><input aria-label="Order quantity" required type="number" min="0.00000001" step="any" value={quantity} onChange={event => setQuantity(event.target.value)} /></label>
        {(type === "limit" || type === "stop_limit") && <label><span>Limit price</span><input aria-label="Limit price" required type="number" min="0.01" step="any" value={limit} onChange={event => setLimit(event.target.value)} /></label>}
        {(type === "stop" || type === "stop_limit") && <label><span>Stop price</span><input aria-label="Stop price" required type="number" min="0.01" step="any" value={stop} onChange={event => setStop(event.target.value)} /></label>}
      </div>
      <p className="muted">Orders require a current, stored simulation price. Stale or unavailable prices are rejected.</p>
      <div className="form-actions"><button type="button" disabled={!symbol || preview.isPending || Boolean(submit.data)} onClick={() => preview.mutate()}>Preview risk checks</button><button className="primary" type="submit" disabled={!symbol || submit.isPending || Boolean(submit.data)}>{submit.isPending ? "Submitting…" : "Submit simulated order"}</button></div>
    </form>
    {(preview.error || submit.error) && <ErrorState error={(preview.error || submit.error)!} />}
    {preview.data && <article className={`panel preview ${preview.data.outcome === "rejected" ? "rejected" : ""}`}><p className="eyebrow">PREVIEW · {preview.data.outcome}</p><h2>{preview.data.estimated_value ? `$${Number(preview.data.estimated_value).toFixed(2)} estimated value` : "PRICE DATA UNAVAILABLE OR STALE"}</h2><p>{preview.data.rejection_reasons.join(" ") || "All enabled portfolio risk checks passed."}</p></article>}
    {submit.data && <article className="panel preview"><p className="eyebrow">ORDER {submit.data.status}</p><h2>Simulation recorded</h2><p>{submit.data.rejection_reason ?? "The order passed risk validation and used stored market data."}</p><Link className="button" to={`/paper-portfolios/${id}`}>View portfolio</Link></article>}
  </section>;
}
