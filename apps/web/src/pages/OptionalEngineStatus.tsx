import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function OptionalEngineStatus() {
  const status = useQuery({ queryKey: ["lean-status"], queryFn: api.leanStatus });
  const fixture = useMutation({ mutationFn: api.leanFixture });
  return <section><div className="page-heading"><div><h1>Optional engine status</h1><p>QuantConnect LEAN adapter prototype · isolated, local, disabled by default.</p></div>
    <button onClick={() => fixture.mutate()}>Run LEAN fixture prototype</button></div>
    <article className="card"><h2>LEAN</h2><p><span className="badge">{status.data?.status}</span> {status.data?.available ? "installed; execution disabled" : "optional dependency unavailable"}</p>
      <p>No live mode · no cloud dependency · no brokerage credentials.</p><p>{status.data?.message}</p></article>
    {fixture.data && <article className="card"><h2>Internal-versus-LEAN comparison</h2><pre className="json-block">{JSON.stringify(fixture.data, null, 2)}</pre></article>}
  </section>;
}
