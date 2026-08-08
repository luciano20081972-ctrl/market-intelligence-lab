import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function SecInstitutionalHoldings() {
  const query = useQuery({ queryKey: ["sec-holdings"], queryFn: api.secInstitutionalHoldings });
  return <section><h1>Institutional holdings</h1><p>13F normalized holdings · third-party adapter · fixture-tested.</p>
    <div className="card"><table><thead><tr><th>Issuer</th><th>CUSIP</th><th>As of</th><th>Shares</th><th>Value USD</th></tr></thead>
    <tbody>{query.data?.items.map((item) => <tr key={item.id}><td>{item.issuer_name}</td><td>{item.cusip}</td><td>{item.as_of_date}</td><td>{item.shares}</td><td>{item.value_usd}</td></tr>)}</tbody></table></div>
  </section>;
}
