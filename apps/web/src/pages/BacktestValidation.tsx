import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";
import { api } from "../api";

export function BacktestValidation() {
  const { id = "" } = useParams(); const query = useQuery({ queryKey: ["validation", id], queryFn: () => api.backtestValidation(id) });
  return <section><h1>Bias and leakage validation</h1><p>Overall: <b>{query.data?.overall_status}</b></p>
    {query.data?.rules.map((rule) => <article className="card" key={rule.name}><h2>{rule.name}: {rule.status}</h2><p>{rule.message}{rule.critical ? " Critical rule." : ""}</p></article>)}</section>;
}
