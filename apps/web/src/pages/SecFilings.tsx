import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";

export function SecFilings() {
  const queryClient = useQueryClient();
  const filings = useQuery({ queryKey: ["sec-filings"], queryFn: api.secFilings });
  const imported = useMutation({
    mutationFn: api.importSecFixture,
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["sec-filings"] }); },
  });
  return <section><div className="page-heading"><div><h1>SEC intelligence</h1>
    <p>Canonical SEC public data · EdgarTools adapter · deterministic fixture-tested.</p></div>
    <button onClick={() => imported.mutate()} disabled={imported.isPending}>Load deterministic fixture filings</button></div>
    {imported.isSuccess && <p role="status" className="success-message">Fixture filings loaded without network access.</p>}
    <div className="card"><h2>Filings search</h2><p className="muted">Forms 10-K, 10-Q, 8-K, 3/4/5 and 13F-HR. Live SEC retrieval is opt-in and not implied.</p>
      <table><thead><tr><th>Company</th><th>Form</th><th>Filed</th><th>Accepted / simulation eligible</th><th>Accession</th></tr></thead>
      <tbody>{filings.data?.items.map((filing) => <tr key={filing.id}><td>{filing.company_name}</td><td><span className="badge">{filing.form_type}</span></td><td>{filing.filing_date}</td><td>{filing.simulation_eligible_at}</td><td><Link className="symbol" to={`/sec/filings/${filing.id}`}>{filing.accession_number}</Link></td></tr>)}</tbody></table>
      {!filings.data?.total && <p>No filings loaded. Use the deterministic fixture to exercise the workflow.</p>}
    </div><div className="page-links"><Link to="/sec/insiders">Insider transactions</Link><Link to="/sec/holdings">Institutional holdings</Link></div>
  </section>;
}
