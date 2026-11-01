# Dependency and License Review

No upstream source code, clinical content, model weights, or external package was copied into wysh.AI during this milestone. The standards slice is original Python code and uses the existing dependency set.

Candidate projects are recorded with `verify_before_dependency_adoption` in the machine-readable inventory. Apache-2.0 signals found in targeted CQF/Blaze pages are not treated as a complete dependency clearance: transitive dependencies, model weights, terminology distributions, data licenses, and attribution obligations still require a release-specific review.

Decision rule: keep a project as reference or isolated service until its exact commit/release, license, security posture, maintenance state, and clinical content rights are recorded. SNOMED CT and other terminology content are separately licensed from server source code.
