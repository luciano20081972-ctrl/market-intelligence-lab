import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function InfrastructureServices() {
  const query = useQuery({ queryKey: ["infrastructure-services"], queryFn: api.infrastructureServices });
  return <section><h1>Infrastructure services</h1><p>Registry contains safe governance metadata only; no vendor accounts are provisioned.</p>
    <div className="card-grid">{query.data?.items.map((service) => <article className="card" key={service.service_name}><h2>{service.service_name}</h2><p><b>{service.status}</b> · verified {service.verification_date}</p><p>{service.purpose}</p><p>Free-tier risk: {service.free_tier_limits}</p><p>Failure impact: {service.failure_effect}</p><p>Replacement: {service.replacement_options}</p></article>)}</div></section>;
}
