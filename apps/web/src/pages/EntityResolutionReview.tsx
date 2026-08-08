import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function EntityResolutionReview() {
  const queryClient = useQueryClient();
  const candidates = useQuery({ queryKey: ["resolution-candidates"], queryFn: api.resolutionCandidates });
  const mutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "confirm" | "reject" }) =>
      api.decideResolution(id, decision, `Manual ${decision} from resolution review`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["resolution-candidates"] }),
  });
  if (candidates.isLoading) return <LoadingState label="Loading resolution candidates" />;
  if (candidates.error) return <ErrorState error={candidates.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">ADMIN REVIEW</p>
    <h1>Entity Resolution Review</h1><p>Ambiguous identifiers are never merged silently.</p></div></div>
    {mutation.error ? <ErrorState error={mutation.error} /> : null}
    {!candidates.data?.items.length ? <EmptyState title="No pending candidates" detail="All ambiguous mappings have been reviewed." /> :
      <div className="table-wrap"><table><thead><tr><th>Identifier</th><th>Method</th><th>Confidence</th><th>Source</th><th>Action</th></tr></thead>
        <tbody>{candidates.data.items.map((item) => <tr key={item.id}><td>{item.namespace}: {item.value}</td>
          <td>{item.method}</td><td>{Math.round(Number(item.confidence) * 100)}%</td><td>{item.source}</td>
          <td><button disabled={mutation.isPending} onClick={() => mutation.mutate({ id: item.id, decision: "confirm" })}>Confirm</button>{" "}
            <button disabled={mutation.isPending} onClick={() => mutation.mutate({ id: item.id, decision: "reject" })}>Reject</button></td>
        </tr>)}</tbody></table></div>}
  </section>;
}
