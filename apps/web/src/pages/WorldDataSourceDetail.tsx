import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function WorldDataSourceDetail() {
  const id = decodeURIComponent(useParams().id ?? "");
  const source = useQuery({ queryKey: ["world-source", id], queryFn: () => api.worldDataSource(id) });
  const health = useQuery({ queryKey: ["world-source-health", id], queryFn: () => api.worldDataSourceHealth(id) });
  if (source.isLoading || health.isLoading) return <LoadingState label="Loading source health" />;
  if (source.error) return <ErrorState error={source.error} />;
  if (health.error) return <ErrorState error={health.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">SOURCE DETAIL</p><h1>{source.data!.title}</h1>
    <p>Official source · {source.data!.temporal_mode} · no investment recommendation.</p></div></div>
    <article className="panel"><pre>{JSON.stringify(health.data, null, 2)}</pre></article></section>;
}
