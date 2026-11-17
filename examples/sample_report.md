# Sample pre-mortem report — plan DEMO-1

**Verdict:** RISKS FOUND

## Ranked failures

### drug_interaction (risk 4.00)

NSAID added to warfarin raises major-bleed risk — both prescribed together

Evidence: prescribed: ibuprofen; prescribed: warfarin; one drug newly started

Earliest warning sign: unusual bruising, nosebleed, or melaena within the first week

Story: Within the first week, Mrs Demo (synthetic) notices unusual bruising, nosebleed, or melaena within the first week. Two drugs that should never have met — ibuprofen + warfarin — were prescribed together. Either one alone was fine; together they produced the harm neither would cause alone.

### unmonitored_lab (risk 2.40)

warfarin requires monitoring (INR) but missing: INR

Evidence: prescribed: warfarin; ordered labs: none

Earliest warning sign: the monitored value drifting out of range with no test scheduled to catch it

Story: Nothing looks wrong on the outside, which is the point: warfarin needs monitoring and none was ordered. The earliest sign would have been the monitored value drifting out of range with no test scheduled to catch it.

## Minimal edits (verified)

- [VALID] **hold ibuprofen while the other drug continues** — Held ibuprofen for the duration of the interacting course; review before restarting.

- [VALID] **order monitoring labs: INR** — Ordered INR for warfarin.
