# R17 — Release-candidate readiness

R17 is an engineering publication-readiness gate for wysh.AI. It does not
publish the repository, select a license, authorize clinical use, or approve
model/data rights.

Run:

```bash
cd apps/api
./.venv/bin/python scripts/run_open_source_release_gate.py
```

The network-free gate audits required documentation, secret-like material,
generated/local artifacts and dependency manifests. It writes:

- `artifacts/opensource-release/release-gate.json`
- `artifacts/opensource-release/dependency-inventory.json`

After the gate, build the sanitized evidence manifest:

```bash
./.venv/bin/python scripts/build_release_manifest.py
```

This writes `artifacts/opensource-release/release-manifest.json`, containing
SHA-256 hashes of named synthetic engineering evidence and explicit
non-authorizing release flags. It contains no model output, patient data,
credentials, or publication action.

The gate remains fail-closed until the authorized owner confirms the license,
dependency/SBOM review, dataset rights, model-weight rights and release
artifact hygiene. It is separate from the synthetic engineering gate.
