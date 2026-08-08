import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";

export function UpstreamIntegrations() {
  const query = useQuery({ queryKey: ["upstream-integrations"], queryFn: api.upstreamIntegrations });
  return <section><h1>Upstream integrations status</h1><p>Replaceable adapter boundaries; core functionality survives optional dependency failure.</p>
    <div className="card-grid">{Object.entries(query.data?.items ?? {}).map(([name, item]) => <article className="card" key={name}><h2>{name}</h2>
      <p><span className="badge">{item.status}</span> {item.available ? "available" : "optional dependency unavailable"}</p><p>{item.message}</p>
      <ul>{item.capabilities.map((capability) => <li key={capability.code}>{capability.description} · {capability.fixture_tested ? "fixture-tested" : "not fixture-tested"} · {capability.live_verified ? "live-verified" : "not live-verified"}</li>)}</ul>
    </article>)}</div><div className="page-links"><Link to="/upstream/licenses">License inventory</Link><Link to="/upstream/engines">Optional engines</Link></div>
  </section>;
}
