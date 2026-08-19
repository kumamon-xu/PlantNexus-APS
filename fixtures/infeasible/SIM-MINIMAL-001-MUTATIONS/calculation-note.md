# SIM-MINIMAL-001-MUTATIONS@1.0.0 Calculation Note

This bundle is a P0 correctness asset derived from the immutable positive
`SIM-MINIMAL-001@1.0.0` fixture. It does not replace or edit the Golden
Schedule. The base Import is pinned at
`sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`.

The suite uses the fixture-local `sim-minimal-records.v1` and
`golden-schedule.v1` vocabularies. Those formats are not P1 canonical records,
a PlanningProblem, a solver candidate contract, or the P2 production and
performance ScheduleValidator boundary. Each mutation is applied to a fresh
in-memory copy by operations that contain no constraint formula. The evaluator
then recomputes C-001 through C-011 directly from facts.

## Manual boundary calculations

The base has a 900-second tick and horizon `[0,16)`. The Golden assignments are
`OP-CUT-001=[0,4)`, `OP-CUT-002=[4,6)`, and `OP-HEAT-001=[8,12)`. The heat
resource is unavailable on `[4,8)`. The cross-workshop edge therefore observes
`(8 - 6) * 900 = 1800` seconds, and its declared transport lag is 900 seconds.

| Case | Mutation and independent expected result |
|---|---|
| `MUT-C001-MISSING-OPERATION` | Remove `OP-CUT-002`; assignment count is 0 instead of exactly 1, so C-001 fails. Endpoint-dependent checks skip the absent assignment. |
| `MUT-C001-DUPLICATE-OPERATION` | Copy `OP-CUT-001=[0,4)`; count 2 fails C-001, selected resource count 2 fails C-003, and the identical half-open intervals overlap, failing C-004. |
| `MUT-C003-WRONG-RESOURCE` | Assign `OP-HEAT-001` to `RES-CUT-SLOW`, outside its sole option `RES-HEAT-001`; C-003 fails. Duration evaluation has no selected option and does not invent one. |
| `MUT-C004-MACHINE-OVERLAP` | Add a valid two-tick operation on `RES-CUT-FAST=[2,4)`; it intersects `OP-CUT-001=[0,4)`, so only C-004 fails. It meets `OP-CUT-002` at tick 4 without overlap. |
| `MUT-C005-CALENDAR-OVERLAP` | Move heat to `[7,11)`; `[7,11)` intersects unavailable `[4,8)`, so C-005 fails. Duration stays 4 ticks, while precedence and transport lag are both 900 seconds and remain valid. |
| `MUT-C006-MATERIAL-EARLY` | Move the material gate for `OP-CUT-002` to 09:15 while the assignment starts 09:00; C-006 fails by 900 seconds. |
| `MUT-C007-COMPLETED-RESCHEDULED` | Add authoritative `COMPLETED` fact for `OP-CUT-001` while its future assignment remains; C-007 fails. |
| `MUT-C007-RUNNING-MOVED` | Add authoritative running fact on `RES-CUT-SLOW` with 5400 seconds remaining. Expected future occupancy is `[0,ceil(5400/900))=[0,6)`, but the candidate remains `RES-CUT-FAST=[0,4)`; C-007 fails. |
| `MUT-C008-HARD-LOCK-MOVED` | Add hard lock `RES-CUT-SLOW=[0,6)` for `OP-CUT-001`; the candidate tuple `RES-CUT-FAST=[0,4)` differs, so C-008 fails. |
| `MUT-C002-MAX-LAG` | Move heat to `[9,13)`; observed lag is `(9 - 6) * 900 = 2700` seconds, exceeding the inclusive 1800-second maximum, so C-002 fails. Duration, calendar, transport, and horizon remain valid. |
| `MUT-C009-TRANSPORT-LAG` | Raise the declared cross-workshop transport lag to 2700 seconds while observed time remains 1800 seconds; C-009 fails independently of C-002, whose 0..1800-second window still passes at its inclusive maximum. |
| `MUT-C010-WRONG-DURATION` | Extend heat from `[8,12)` to `[8,13)`; 5 observed ticks differ from `ceil(3600/900)=4`, so C-010 fails. |
| `MUT-C011-HORIZON-OVERFLOW` | Shorten both problem and candidate envelope horizon to tick 11 (10:45). Heat still ends at tick 12, so C-011 fails without truncation. |

The duplicate case intentionally yields three violations. This is not
collateral noise: one mutation simultaneously falsifies the independent
completeness, unique-selection, and capacity-one propositions. All other cases
are isolated to one C-ID. `coverage-matrix.json` records every required
mutation class and all C-001 through C-011 with no uncovered entries.

`expected-outcomes.json` commits exact `validation-report.v2` and `error.v2`
documents, including constraint, entity, observed value, expected rule, and
registered `VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED` mapping. The mutation
command validates both schemas, exact content, deterministic replay, coverage,
and Rule Sheet metadata while retaining evaluator/expected-artifact separation.
