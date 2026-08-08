import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function UpstreamLicenseInventory() {
  const query = useQuery({ queryKey: ["upstream-licenses"], queryFn: api.upstreamLicenses });
  return <section><h1>Upstream license inventory</h1><p>Policy {query.data?.policy_version} · no copied upstream source code.</p>
    <div className="card-grid">{query.data?.items.map((project) => <article className="card" key={project.name}><h2>{project.name}</h2>
      <p><span className="badge">{project.license}</span> <span className="badge">{project.integration_category}</span></p>
      <p>Reviewed: {project.reviewed_release} · <code>{project.reviewed_revision.slice(0, 12)}</code></p><p>{project.approved_use}</p><p className="muted">Prohibited: {project.prohibited_use}</p>
    </article>)}</div>
  </section>;
}
