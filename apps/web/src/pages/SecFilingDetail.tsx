import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";

export function SecFilingDetail() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["sec-filing", id], queryFn: () => api.secFiling(id) });
  const filing = query.data;
  return <section><Link className="back-link" to="/sec">← SEC filings</Link>
    <h1>Filing detail</h1>{filing && <><article className="card"><h2>{filing.form_type} · {filing.accession_number}</h2>
      <p>{filing.company_name} · CIK {filing.cik}</p><dl className="detail-list compact">
        <dt>Accepted</dt><dd>{filing.accepted_at}</dd><dt>Reporting period</dt><dd>{filing.reporting_period}</dd>
        <dt>Simulation eligible</dt><dd>{filing.simulation_eligible_at}</dd><dt>Amendment</dt><dd>{filing.is_amendment ? "Yes" : "No"}</dd>
        <dt>Parser</dt><dd>{filing.parser_version}</dd><dt>EdgarTools</dt><dd>{filing.edgartools_version}</dd>
      </dl><p className="muted">Provenance checksum: {filing.content_checksum}</p></article>
      <article className="card"><h2>Parsed XBRL facts</h2><pre className="json-block">{JSON.stringify(filing.facts ?? [], null, 2)}</pre></article></>}
  </section>;
}
