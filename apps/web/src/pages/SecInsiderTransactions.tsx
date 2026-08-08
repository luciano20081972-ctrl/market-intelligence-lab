import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function SecInsiderTransactions() {
  const query = useQuery({ queryKey: ["sec-insiders"], queryFn: api.secInsiderTransactions });
  return <section><h1>Insider transactions</h1><p>Forms 3, 4 and 5 · third-party adapter · fixture-tested.</p>
    <div className="card"><table><thead><tr><th>Owner</th><th>Relationship</th><th>Date</th><th>Code</th><th>Shares</th><th>Price</th></tr></thead>
    <tbody>{query.data?.items.map((item) => <tr key={item.id}><td>{item.owner_name}</td><td>{item.relationship}</td><td>{item.transaction_date}</td><td>{item.transaction_code}</td><td>{item.shares}</td><td>{item.price ?? "—"}</td></tr>)}</tbody></table></div>
  </section>;
}
