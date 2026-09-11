
## Limitations and responsible use

This model produces relative risk classifications (1 = lowest, 5 = highest) for administrative units within a single geography. It is intended as a **decision-support tool**, not as the sole basis for resource allocation or operational response. In particular:

- **Class boundaries are statistical**, derived from the distribution of values in the input data. Comparing scores across geographies or non-overlapping time periods is not meaningful without re-anchoring.
- **The Vulnerability factor depends on observed damage data** (deaths, affected population, crop and infrastructure loss). Damage data is itself subject to under-reporting and reporting lag. In geographies where damage data is unavailable, the DEA-based vulnerability score should be replaced by a simpler weighted index — see [`score_vulnerability.md`](docs/score_vulnerability.md).
- **The Government Response factor reflects expenditure**, not effectiveness. A high response score indicates investment; it does not certify outcome quality.
- **Risk scores are not forecasts.** They describe conditions observed during the time window in the input data.
- **Low-risk classifications must not be used to justify withdrawal of services or preparedness investment**, particularly in areas with sparse damage-reporting infrastructure.

Operators deploying this model in real settings are encouraged to publish their input data, configuration files, and any local methodological adjustments alongside their outputs, so that the resulting scores are auditable.

---

## Privacy and applicable law

The model operates on **administrative-unit aggregates** (districts, blocks, revenue circles, villages). It does not collect, store, or process personally identifiable information about individuals. All inputs are population-level statistics, environmental measurements, or de-identified procurement records.

Where source datasets carry their own terms of use (for example, government tender records or commercial map services), downstream operators are responsible for ensuring their own deployments comply with the relevant terms and with applicable data-protection law in their jurisdiction — including, in the Indian context, the Digital Personal Data Protection Act, 2023.