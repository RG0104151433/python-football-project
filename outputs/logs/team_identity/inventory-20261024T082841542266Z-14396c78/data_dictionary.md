# Identity inventory fields

UTF-8 BOM CSV, LF; integer counts; lowercase booleans; JSON arrays; empty fields are unknown, never approval.
No eligibility/identity decisions applied. Review priority is a research queue, not a confidence score.

## team_inventory

source_team_id, source_team_label, raw_first_date, raw_last_date, raw_appearances, clean_appearances, study_appearances, study_first_date, study_last_date, upstream_rule_count, study_former_interval_appearances, study_venue_name_flag_appearances, review_priority, clue_types, identity_classification, review_status

## review_queue

source_team_id, source_team_label, review_priority, study_appearances, clue_types, entity_type, historical_name_decision, scope_decision, evidence_ids, checked_by, independently_reviewed_by, review_status, notes

## upstream_name_rules

rule_id, current_label, former_label, start_date, end_date, source_file, source_sha256, source_record_no, evidence_status

## historical_name_clues

source_record_id, match_id, date, side, source_team_id, source_team_label, rule_id, upstream_former_label, in_clean, in_study, clue_status

## venue_name_flags

match_id, source_record_id, date, home_team_id, home_team, away_team_id, away_team, country, city, in_study, flag_type, review_status

source_team_id is the existing mechanical registry ID, not a validated historical entity.
raw/clean/study appearances count team participation; each match contributes two appearances.
historical_name_clues link upstream intervals on both raw sides, including rows excluded from clean; they are not corrected facts.
in_study follows the registered analysis dates, known non-neutral venue and known tournament eligibility.
review_queue is a prefilled draft; copy it before writing evidence. This release does not read it as executable decisions.
1_study_with_clues, 2_study_unreviewed, 3_outside_study sort review work only; ordinary labels still require identity review.
