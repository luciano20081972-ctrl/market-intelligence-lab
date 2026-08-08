import type { EconomicEntity } from "../types";

interface CompanyPickerProps {
  companies: EconomicEntity[];
  value: string;
  onChange: (companyId: string) => void;
}

export function CompanyPicker({ companies, value, onChange }: CompanyPickerProps) {
  return <label>Reference company
    <select
      aria-label="Reference company"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {companies.map((company) => <option key={company.id} value={company.id}>
        {company.canonical_name}
      </option>)}
    </select>
  </label>;
}
