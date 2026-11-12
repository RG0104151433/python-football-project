# Sample confirmation: determine which matches belong to the study

[中文](README.md) | **English**


## Question and method

Did both teams satisfy the project's membership and historical-identity scope at the match date? After base cleaning, apply identity rules, date intervals and recorded match-level decisions. Retain match IDs and provenance.

## Adopted outcome

Of 26,055 candidate matches, 24,917 are retained and 1,138 excluded. None remain undecided within the adopted scope. The 117 owner-approved matches are included.

This adoption does not certify every historical identity, venue or match fact worldwide. It also does not automatically authorize merging rating entities.

## Materials and reproduction

- [Display material](展示素材.json).
- [Adopted identity manifest](../../data/processed/team_identity/identity-reviewed-29d880765c1623764940/identity_manifest.json).
- [Script guide](../../scripts/README.en.md#identity).

The adopted entry point is `scripts/adopt_membership_reviews.py`. Verification uses `scripts/build_team_identity.py --verify` with the actual identity manifest. Read the detailed stage instructions before rerunning publication steps.

Resolve all tables and figures through [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md), rather than file modification times.

Return to the [research overview](../README.en.md) or [paper guide](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/00_数据再次确认/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
