# wysh.AI open-source release checklist

This checklist prepares the repository for publication. It does not publish
the repository or grant rights to third-party code, datasets, prompts, images,
or model weights.

## Engineering verification

Run `apps/api/scripts/run_objective_gate.py` before publishing or handing off
the isolated engineering build. It verifies repository artifacts, safe runtime
defaults, the clinical-promotion boundary, backend regression, and synthetic
bridge evidence. It also exercises decision replay rejection, sanitized
telemetry, audit-chain integrity, and provider-readiness redaction.
`PASS_WITH_BOUNDARIES` is not clinical validation or a production authorization.

For publication hygiene, also run the network-free R17 gate described in
[R17_RELEASE_CANDIDATE_READINESS.md](R17_RELEASE_CANDIDATE_READINESS.md). It
generates a dependency inventory and fails closed on missing license ownership,
rights review, secrets or generated/local release artifacts.

Build the sanitized evidence manifest after the gate:

```bash
cd apps/api
./.venv/bin/python scripts/build_release_manifest.py
```

The manifest is an auditable evidence index only. It does not publish the
repository, select a license, authorize clinical use, or alter WyshCare.

## Required before publication

- Confirm the legal copyright holder and select a project license.
- Add the selected license and any required NOTICE file.
- Run a dependency/SBOM and license review for Python, Node, CQL, and model
  runtimes.
- Confirm every model-weight and dataset term separately from source-code
  licensing.
- Remove secrets, local databases, build output, caches, and generated files.
- Verify no PHI or production credentials exist in history or artifacts.
- Preserve upstream notices for the two integrated CQL packages.
- Mark Gemini, TRION, and optional endpoint support as credential-gated.
- Keep clinical-use disclaimers, no-autonomous-action boundaries, and
  synthetic-only fixtures visible in README and documentation.
- Add a vulnerability reporting process and supported-version policy.

## Recommended default

Apache-2.0 is a candidate for original Wysh.AI source because it is permissive
and includes an express patent license, but the copyright holder must approve
the choice. Third-party components remain governed by their own licenses.

## Current gate state

The repository is `PREPARED_NOT_PUBLISHED`. It is not yet an open-source
release until license ownership, dependency notices, model/data rights, and
secret/history review are confirmed by the authorized owner.

