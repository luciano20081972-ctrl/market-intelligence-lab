import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function DataManifests() {
  const query = useQuery({ queryKey: ["data-manifests"], queryFn: api.dataManifests });
  if (query.isLoading) return <LoadingState label="Loading manifests" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">PROVENANCE</p><h1>Data manifests</h1>
    <p>Immutable raw-object checksums and dataset-level quality counts.</p></div></div>
    {query.data!.total === 0 ? <EmptyState title="No manifests yet" detail="Fixture capability is verified; live ingestion has not run." /> :
      query.data!.items.map(item => <article className="panel" key={item.id}><h2>{item.dataset_id}</h2>
        <p>{item.record_count.toLocaleString()} records · retrieved {new Date(item.retrieval_time).toLocaleString()}</p>
        <Link to={`/world-data/manifests/${item.id}`}>Manifest detail</Link></article>)}</section>;
}

export function DataManifestDetail() {
  const id = useParams().id ?? "";
  const query = useQuery({ queryKey: ["data-manifest", id], queryFn: () => api.dataManifest(id) });
  if (query.isLoading) return <LoadingState label="Loading manifest" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">IMMUTABLE MANIFEST</p><h1>{query.data!.dataset_id}</h1></div></div>
    <article className="panel"><pre>{JSON.stringify(query.data, null, 2)}</pre></article></section>;
}
