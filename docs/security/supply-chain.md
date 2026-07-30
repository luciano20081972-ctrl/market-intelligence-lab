# Software supply chain

CI installs the Python project and frozen pnpm lock, runs `pip check`, `pip-audit --skip-editable`, `pnpm audit --audit-level critical`, creates a CycloneDX Python SBOM, and emits Python/npm license inventories. Known critical vulnerabilities fail CI unless a time-bounded, reviewed acceptance is documented in `SECURITY.md`; informational/unverified findings are reviewed rather than blindly failed.

As of 2026-07-30, the npm audit reports `GHSA-qwww-vcr4-c8h2` against React Router 7.18.x. The registry does not yet publish the advisory's stated fixed line (8.3.0 or newer). Market Intelligence Lab uses React Router only as a browser SPA and does not enable React Server Components or server actions, so the affected RSC request path is not exposed. Dependabot remains enabled and this temporary high-severity acceptance must be removed as soon as a compatible patched release is published. Critical findings remain release blockers.

The same audit reports `GHSA-mh99-v99m-4gvg` in the development-only `coverage-v8 > test-exclude > glob > minimatch > brace-expansion` path. Only repository-controlled coverage globs reach it. Forcing the patched major version is API-incompatible with the current `minimatch` release and breaks coverage collection, so it is temporarily accepted pending an upstream Vitest/test-exclude dependency update.

Dependabot opens grouped minor/patch Python and npm updates and monthly Actions updates; it never auto-merges. Coverage XML/LCOV is produced locally; Codecov upload is optional and cannot make local tests fail.
