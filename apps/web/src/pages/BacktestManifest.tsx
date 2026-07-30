import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api";

export function BacktestManifest() {
  const { id = "" } = useParams(); const query = useQuery({ queryKey: ["manifest", id], queryFn: () => api.backtestManifest(id) });
  return <section><h1>Reproducibility manifest</h1>{query.data?.status === "legacy_unavailable" && <p>Legacy backtest fields are unavailable; no values were invented.</p>}<pre>{JSON.stringify(query.data?.manifest, null, 2)}</pre></section>;
}
