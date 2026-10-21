# Decisions Log

Day 1: chose BIRD + Groq primary + LangGraph orchestrator

## Chunk 1: Data Exploration and Foundation Decisions

### 1. Database Selection: `formula_1`
- **Choice**: Selected `formula_1.sqlite` as the primary project database.
- **Rationale**: In the BIRD dev split, `formula_1` is the largest relational database available with 13 interconnected tables and 174 candidate questions across all difficulty levels (`dev.json`).
- **Setup**: Copied to `data/bird_L0.sqlite` and marked strictly read-only (`chmod 444`).
- **Sandbox DB**: Downloaded `data/chinook.sqlite` (11 tables) for safe guardrail unit testing in Chunk 3.

### 2. Decision on BIRD Evidence Hints
- **Decision**: Do NOT provide BIRD's hardcoded `evidence` hints to the Text-to-SQL agent during the benchmark experiment.
- **Rationale**: BIRD's `evidence` field often leaks exact column filters and mappings (e.g., hinting `"average time in milliseconds spent at pit stop refers to AVG(milliseconds)"`), which bypasses the real-world challenge of schema ambiguity. Instead, in Chunk 8, we build an automated data dictionary (`descriptions.json`) and a value grounding index to resolve ambiguity dynamically and realistically.

### 3. Ten Data Observations (Quirks of `bird_L0.sqlite`)
1. **Massive NULLs on DNF finishes (`results.position`)**: Out of 23,657 rows, 10,528 are `NULL` due to retirements, crashes, or disqualifications. Any query computing "average finish position" without filtering out `NULL` will produce skewed or incorrect statistics.
2. **Cryptic sentinel codes in `results.positionText`**: When a driver does not finish, `positionText` contains single-letter codes: `'R'` (Retired), `'D'` (Disqualified), `'N'` (Not classified), `'W'` (Withdrawn), `'F'` (Failed to qualify), `'E'` (Excluded).
3. **Inconsistent elapsed time formats in `results.time`**: Contains either absolute winning times (`'1:34:50.616'`), relative gap deltas to the leader (`'+5.478'`), or `NULL` (17,696 rows). String aggregations like `MIN()` or `SUM()` fail completely.
4. **Numeric values stored as TEXT (`results.fastestLapSpeed`)**: Lap speeds are stored as text (e.g., `'218.300'`), requiring explicit `CAST(fastestLapSpeed AS REAL)` for numeric comparisons and sorting.
5. **Split driver names & internal slugs (`drivers`)**: Driver identity is split across `forename`, `surname`, and an internal identifier `driverRef` (`'hamilton'`). Queries looking for full names require string concatenation or multi-column conditions.
6. **Sparse driver numbers (`drivers.number`)**: 804 out of 840 drivers have `NULL` numbers because permanent driver numbers were only adopted in the 2014 season.
7. **Multi-round qualifying NULL cascades (`qualifying`)**: Columns `q1`, `q2`, and `q3` have 117, 3,807, and 5,251 NULLs respectively, because eliminated drivers do not participate in later qualifying rounds.
8. **Decoupled retirement reasons (`results.statusId` -> `status.status`)**: The `results` table does not store text failure causes directly. Instead, `results.statusId` joins to a separate lookup table `status` (134 categories, e.g., `'Engine'`, `'Collision'`, `'+1 Lap'`, `'Gearbox'`). Queries asking "why did a driver retire?" must perform this relational join.
9. **Missing historical start times (`races.time`)**: 731 out of 976 races have `NULL` start times because race start times were rarely documented in early decades of Formula 1.
10. **Pit stop duration format traps (`pitStops.duration` vs `pitStops.milliseconds`)**: `pitStops` stores duration twice. The `duration` column is text with inconsistent formats: `'23.227'` for sub-minute stops, but `'1:29.401'` or `'16:44.718'` for stops exceeding a minute. Performing `AVG(duration)` fails, whereas `milliseconds` is clean integer data (`23227`, `89401`, `1004718`).
