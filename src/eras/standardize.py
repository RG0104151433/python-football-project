"""Fixed reference compositions and contrasts on exactly the same matches."""
from math import fsum

from ..data_contract import fingerprint
from .data import GROUPS, era_for, sample_id
from .inference import without_uncertainty
from .statistics import summarize


def build_reference(rows, config, scheme):
    years = sorted({r["year"] for r in rows})
    if not rows:
        weight = None
    elif scheme == "pooled_matches":
        weight = sum(r["tournament_group"] == "friendly" for r in rows) / len(rows)
    else:
        fractions = []
        for year in years:
            selected = [r for r in rows if r["year"] == year]
            fractions.append(sum(r["tournament_group"] == "friendly" for r in selected) / len(selected))
        weight = fsum(fractions) / len(fractions)
    sid = sample_id(rows, config["data_version"])
    ref_id = "reference-" + fingerprint({"sample_id": sid, "scheme": scheme, "years": years})[:20]
    all_years = list(range(int(config["analysis_start"][:4]), int(config["analysis_end"][:4]) + 1))
    reference = dict(reference_id=ref_id, reference_sample_id=sid, scheme=scheme,
                     weight_friendly=weight, years=years, missing_years=sorted(set(all_years) - set(years)))
    records = [dict(reference_id=ref_id, reference_sample_id=sid, scheme=scheme, tournament_group=g,
                    weight=None if weight is None else weight if g == "friendly" else 1 - weight,
                    reference_start=config["analysis_start"], reference_end=config["analysis_end"],
                    n_reference_matches=len(rows), n_reference_years=len(years), reference_years=years,
                    missing_years=reference["missing_years"], status="ok" if rows else "empty_reference") for g in GROUPS]
    return reference, records


def era_rates(rows, config, weight):
    rates = {}
    for era in config["eras"]:
        selected = [r for r in rows if era_for(r["date"], config) == era["id"]]
        cells = {g: summarize([r for r in selected if r["tournament_group"] == g]) for g in GROUPS}
        observed = summarize(selected)["home_win_rate"]
        missing = weight is None or (weight > 0 and cells["friendly"]["n_matches"] == 0) or (
            weight < 1 and cells["non_friendly"]["n_matches"] == 0)
        standardized = None if missing else fsum(w * cells[g]["home_win_rate"] for g, w in (
            ("friendly", weight), ("non_friendly", 1 - weight)) if w > 0)
        rates[era["id"]] = dict(observed_rate=observed, standardized_rate=standardized,
                                cells=cells, n_matches=len(selected),
                                status="ok" if standardized is not None else "missing_stratum" if selected else "empty_group")
    return rates


def difference(a, b):
    return None if a is None or b is None else (b - a) * 100


def contrasts_for(rates, config):
    results = []
    for contrast in config["primary_contrasts"]:
        a, b = rates[contrast["earlier"]], rates[contrast["later"]]
        raw = difference(a["observed_rate"], b["observed_rate"])
        adjusted = difference(a["standardized_rate"], b["standardized_rate"])
        values = {"observed_difference": raw, "standardized_difference": adjusted,
                  "composition_adjustment_difference": None if raw is None or adjusted is None else raw - adjusted}
        for estimand, value in values.items():
            results.append(dict(contrast_id=contrast["id"], earlier_era=contrast["earlier"], later_era=contrast["later"],
                                estimand=estimand, estimate=value, unit="percentage_points",
                                status="ok" if value is not None else "not_estimable", **without_uncertainty()))
    return results


def build_standardization(rows, config):
    sid = sample_id(rows, config["data_version"])
    tables = {k: [] for k in ("reference_weights", "era_estimates", "era_contrasts", "weight_sensitivity")}
    references = []
    for scheme in [config["reference_scheme"], *config["alternative_reference_schemes"]]:
        ref, ref_rows = build_reference(rows, config, scheme)
        references.append(ref)
        tables["reference_weights"].extend(ref_rows)
        rates = era_rates(rows, config, ref["weight_friendly"])
        for era_id, values in rates.items():
            for estimand in ("observed_rate", "standardized_rate"):
                tables["era_estimates"].append(dict(estimate_id=f"{ref['reference_id']}:{era_id}:{estimand}",
                    sample_id=sid, analysis_era_id=era_id, estimand=estimand, reference_id=ref["reference_id"],
                    estimate=values[estimand], unit="probability", status="ok" if values[estimand] is not None else values["status"],
                    **without_uncertainty()))
        tables["era_contrasts"].extend(dict(r, sample_id=sid, reference_id=ref["reference_id"]) for r in contrasts_for(rates, config))
    # Whole [0,1] sensitivity is algebraic, not a simultaneous confidence band.
    main = era_rates(rows, config, references[0]["weight_friendly"])
    for contrast in config["primary_contrasts"]:
        a, b = main[contrast["earlier"]], main[contrast["later"]]
        df = difference(a["cells"]["friendly"]["home_win_rate"], b["cells"]["friendly"]["home_win_rate"])
        dn = difference(a["cells"]["non_friendly"]["home_win_rate"], b["cells"]["non_friendly"]["home_win_rate"])
        flip, status = None, "missing_stratum"
        if df is not None and dn is not None:
            flip = dn / (dn - df) if dn != df else None
            status = "constant_zero" if df == dn == 0 else "constant_difference" if df == dn else "flip_in_range" if 0 <= flip <= 1 else "no_flip_in_range"
            if flip is not None and not 0 <= flip <= 1:
                flip = None
        weights = {i / 100 for i in range(101)}
        weights.update(r["weight_friendly"] for r in references if r["weight_friendly"] is not None)
        if flip is not None:
            weights.add(flip)
        for weight in sorted(weights):
            tables["weight_sensitivity"].append(dict(contrast_id=contrast["id"], sample_id=sid, weight_friendly=weight,
                difference_pp=None if df is None or dn is None else weight * df + (1 - weight) * dn,
                flip_weight=flip, status=status))
    return tables, references
