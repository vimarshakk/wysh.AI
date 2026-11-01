# Security policy

Please do not submit PHI, production credentials, patient identifiers, or
restricted datasets in issues, pull requests, fixtures, logs, or model prompts.

This repository is not authorized for production clinical use. Security
reports must be sent through the project owner's approved private security
channel once configured; do not disclose exploitable details in a public issue.
Until that channel is configured, record only sanitized reproduction steps and
the affected local file or test in the repository's controlled engineering
review process.

Security-sensitive changes must preserve:

- synthetic-only defaults and production fail-closed behavior;
- signed, scoped authorization before inference;
- no raw prompts, evidence payloads, or credentials in telemetry;
- explicit abstention on unavailable, unsafe, contradictory, or ungrounded
  model output;
- persistent human review before any clinical workflow action.

See `docs/SECURITY.md` for the implementation data policy.
