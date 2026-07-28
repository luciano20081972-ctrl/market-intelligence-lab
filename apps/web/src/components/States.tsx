export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return <div className="state-card" role="status"><span className="spinner" />{label}…</div>;
}

export function ErrorState({ error }: { error: Error }) {
  return <div className="state-card error" role="alert"><strong>Unable to load data</strong><span>{error.message}</span></div>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="state-card"><strong>{title}</strong><span>{detail}</span></div>;
}

export function DemoWarning() {
  return <div className="demo-warning" role="note"><span>DEMO</span>Synthetic demonstration data — not live market data.</div>;
}
