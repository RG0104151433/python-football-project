# Era tables: eras-tables-v1

CSV: UTF-8 BOM, LF, integers, lowercase booleans, decimals fixed to 10 places.
Blank numeric fields mean unavailable/not computed, never zero. Read status and uncertainty_status.
Rates: probability (0–1); contrasts and sensitivity: percentage points. No inferred intervals.
sample_name distinguishes two logical views even when their match sets/sample_id coincide.

## analysis_membership.csv

Unique key: match_id. Sort: this same key.

- data_version: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- match_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- source_record_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- date: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- analysis_era_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- in_base_venue: boolean; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- in_classified_venue: boolean; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- primary_exclusion_reason: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- exclusion_reasons: JSON array; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## era_contrasts.csv

Unique key: contrast_id reference_id estimand. Sort: this same key.

- contrast_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- earlier_era: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- later_era: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- estimand: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- reference_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- estimate: decimal; unit=see row unit. Blank when not estimated; see status.
- unit: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- standard_error: decimal; unit=see row unit. Blank when not estimated; see status.
- ci_lower: decimal; unit=see row unit. Blank when not estimated; see status.
- ci_upper: decimal; unit=see row unit. Blank when not estimated; see status.
- confidence_level: decimal; unit=probability. Blank when not estimated; see status.
- method_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- method_version: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- uncertainty_status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## era_estimates.csv

Unique key: estimate_id. Sort: this same key.

- estimate_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- analysis_era_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- estimand: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- reference_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- estimate: decimal; unit=see row unit. Blank when not estimated; see status.
- unit: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- standard_error: decimal; unit=see row unit. Blank when not estimated; see status.
- ci_lower: decimal; unit=see row unit. Blank when not estimated; see status.
- ci_upper: decimal; unit=see row unit. Blank when not estimated; see status.
- confidence_level: decimal; unit=probability. Blank when not estimated; see status.
- method_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- method_version: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- uncertainty_status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## era_summary.csv

Unique key: sample_name period_id. Sort: this same key.

- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- sample_name: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- period_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- start_date: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- end_date: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_years: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_matches: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_home_wins: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_draws: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_away_wins: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- home_win_rate: decimal; unit=probability. Blank when not estimated; see status.
- draw_rate: decimal; unit=probability. Blank when not estimated; see status.
- away_win_rate: decimal; unit=probability. Blank when not estimated; see status.
- mean_goal_difference: decimal; unit=goals. Blank when not estimated; see status.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## era_tournament_summary.csv

Unique key: sample_id analysis_era_id tournament_group. Sort: this same key.

- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- analysis_era_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- tournament_group: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_matches: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_home_wins: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_draws: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_away_wins: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- home_win_rate: decimal; unit=probability. Blank when not estimated; see status.
- draw_rate: decimal; unit=probability. Blank when not estimated; see status.
- away_win_rate: decimal; unit=probability. Blank when not estimated; see status.
- mean_goal_difference: decimal; unit=goals. Blank when not estimated; see status.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## reference_weights.csv

Unique key: reference_id tournament_group. Sort: this same key.

- reference_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- reference_sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- scheme: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- tournament_group: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- weight: decimal; unit=probability. Blank when not estimated; see status.
- reference_start: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- reference_end: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_reference_matches: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_reference_years: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- reference_years: JSON array; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- missing_years: JSON array; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## sample_flow.csv

Unique key: flow_id stage reason. Sort: this same key.

- flow_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- stage: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- parent_stage: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- reason: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_records: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- basis: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## schedule_diagnostics.csv

Unique key: sample_id analysis_era_id tournament_group metric. Sort: this same key.

- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- analysis_era_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- tournament_group: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- metric: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- value: decimal; unit=see row unit. Blank when not estimated; see status.
- unit: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## team_schedule.csv

Unique key: sample_id analysis_era_id tournament_group team_id. Sort: this same key.

- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- analysis_era_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- tournament_group: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- team_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_home: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_away: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_matches: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_distinct_opponents: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## weight_sensitivity.csv

Unique key: contrast_id weight_friendly. Sort: this same key.

- contrast_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- weight_friendly: decimal; unit=probability. Blank when not estimated; see status.
- difference_pp: decimal; unit=percentage_points. Blank when not estimated; see status.
- flip_weight: decimal; unit=probability. Blank when not estimated; see status.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## year_summary.csv

Unique key: sample_name period_id. Sort: this same key.

- sample_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- sample_name: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- period_id: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- start_date: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- end_date: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_years: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_matches: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_home_wins: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_draws: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- n_away_wins: integer; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.
- home_win_rate: decimal; unit=probability. Blank when not estimated; see status.
- draw_rate: decimal; unit=probability. Blank when not estimated; see status.
- away_win_rate: decimal; unit=probability. Blank when not estimated; see status.
- mean_goal_difference: decimal; unit=goals. Blank when not estimated; see status.
- status: string; unit=not applicable. Required unless no applicable exclusion/period; arrays use JSON.

## Definitions

pair_coverage: distinct unordered team pairs / [G(G-1)/2] within the era/group.
top_5_appearance_share: appearances by five most frequent teams / (2 * matches).
max_pair_repeats: largest count of matches for an unordered team pair.
sample_flow: upstream raw and downstream processed counts are separate accounting layers.
reference_years lists observed years; missing_years lists window years without classified matches.
observed_difference and standardized_difference: later minus earlier, in percentage points.
composition_adjustment_difference: observed_difference minus standardized_difference; not causal.
uncertainty_status=not_run: no SE/CI, method fields blank.
Statuses: ok, empty_group, missing_stratum, empty_reference, not_estimable; sensitivity flip statuses are algebraic only.
