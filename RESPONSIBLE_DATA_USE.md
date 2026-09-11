## Limitations and responsible use

This repository is an index and toolset over the CivicDataSpace ecosystem, not a single analytical model — the
considerations below apply to its parts individually.

- **`audits/cds-audit` scores are heuristics, not verdicts.** Metadata checks (units stated, abbreviations,
  purpose statements, source attribution) are pattern-based and will occasionally miss or over-flag. Always
  check the specific text an audit flags before acting on it — see that tool's own
  [README](audits/cds-audit/README.md) for what each check does and doesn't catch.
- **`canonical_entities/` boundary data reflects its source's vintage and classification choices.** For
  example, India's NIC service uses 2024 administrative boundaries with Census 2011 codes retained for joins;
  urban/rural classification follows LGD name-suffix conventions, which can misclassify edge cases. Treat it
  as a reference to join against, not ground truth to publish unreviewed.
- **Each collaborative under `collaboratives/` sets its own methodology, limitations, and responsible-use
  guidance** in its own repository — this file does not speak for them. Consult the collaborative's own docs
  (e.g. `disaster-risk-score-model`'s risk-classification caveats) before using its outputs operationally.

Operators building on any part of this ecosystem are encouraged to publish their input data, configuration,
and any local methodological adjustments alongside their outputs, so that results are auditable.

---

## Privacy and applicable law

- `audits/cds-audit` operates on dataset **metadata and file previews** from the public CivicDataSpace
  catalogue; it does not collect personal data about individuals.
- `canonical_entities/india/maps` operates on **administrative-unit aggregates and boundary geometries**, not
  individual-level data.
- Data processed by collaboratives under `collaboratives/` is governed by that collaborative's own repository
  and privacy documentation, not this one.

Where source datasets carry their own terms of use (for example, government portals or commercial map
services), downstream operators are responsible for ensuring their own use complies with the relevant terms
and with applicable data-protection law in their jurisdiction — including, in the Indian context, the Digital
Personal Data Protection Act, 2023.
