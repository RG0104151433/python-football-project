"""Exact finite probability checks for theory screening; no simulation or real-data CI."""
from fractions import Fraction as F
from itertools import product
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def independent_binary(probabilities):
    return [(values, math.prod(p if y else 1-p for y, p in zip(values, probabilities)))
            for values in product((0, 1), repeat=len(probabilities))]


def mean(distribution, function):
    return sum((probability * function(values) for values, probability in distribution), F(0))


def variance(distribution, coefficients):
    statistic = lambda values: sum((a*y for a, y in zip(coefficients, values)), F(0))
    expected = mean(distribution, statistic)
    return mean(distribution, lambda values: (statistic(values)-expected)**2)


def main():
    checks = []

    def check(ok, label):
        if not ok:
            raise ValueError(label)
        checks.append(label)

    same = [((0, 0), F(1, 2)), ((1, 1), F(1, 2))]
    opposite = [((0, 1), F(1, 2)), ((1, 0), F(1, 2))]
    check(variance(same, [F(1, 2)]*2) == F(1, 4), "same-shock mean variance")
    check(variance(same, [F(1), F(-1)]) == 0, "same-shock contrast cancellation")
    check(variance(opposite, [F(1, 2)]*2) == 0, "opposite-shock mean cancellation")
    check(variance(opposite, [F(1), F(-1)]) == 1, "opposite-shock contrast amplification")

    p = [F(9, 10), F(1, 10), F(9, 10), F(1, 10)]
    law = independent_binary(p)
    a = [F(1, 4)]*4
    truth = variance(law, a)
    check(sum(prob for _, prob in law) == 1, "enumerated probabilities sum to one")
    check(truth == F(9, 400), "heterogeneous independent mean true variance")
    binomial_at_average = F(1, 2)*(1-F(1, 2))/4
    heterogeneity = sum((x-F(1, 2))**2 for x in p)/16
    check(binomial_at_average-truth == heterogeneity == F(1, 25), "independent heterogeneity variance identity")

    # Matches AB, BC, CD, DA: the shared-team indicator matrix has a negative eigenvalue.
    teams = [{"A", "B"}, {"B", "C"}, {"C", "D"}, {"D", "A"}]
    W = [[int(bool(teams[i] & teams[j])) for j in range(4)] for i in range(4)]
    v = [1, -1, 1, -1]
    check([sum(W[i][j]*v[j] for j in range(4)) for i in range(4)] == [-x for x in v], "shared-team kernel has eigenvalue minus one")

    def quadratic(values, center):
        residual = [F(y)-center for y in values]
        return sum((a[i]*a[j]*W[i][j]*residual[i]*residual[j] for i in range(4) for j in range(4)), F(0))

    oracle_expected = mean(law, lambda values: quadratic(values, F(1, 2)))
    sample_expected = mean(law, lambda values: quadratic(values, sum(values, F(0))/4))
    check(oracle_expected == F(-7, 400), "oracle-cell residual graph variance can have negative expectation")
    check(sample_expected == F(-11, 320), "estimated-cell residual graph variance can have negative expectation")
    check(truth > 0 and oracle_expected < 0 and sample_expected < 0, "raw residual graph formula is not automatically conservative")

    # A verified proper coloring permits independent within-color sums.
    colors = [[0, 2], [1, 3]]
    check(all(not W[i][j] for color in colors for pos, i in enumerate(color) for j in color[pos+1:]), "proper coloring checked")
    unequal = [F(1, 2), F(-1, 3), F(1, 4), F(-1, 5)]
    Vk = [sum(float(unequal[i])**2 for i in color) for color in colors]
    C = sum(math.sqrt(x) for x in Vk)**2
    simple = len(colors)*sum(float(x)**2 for x in unequal)
    check(C <= simple+1e-14, "weighted Holder bound no worse than K times squared weights")
    for scenario, coefficients in ((law, unequal), (law, a)):
        coefficient_float = list(map(float, coefficients))
        constant = sum(math.sqrt(sum(coefficient_float[i]**2 for i in color)) for color in colors)**2
        center = float(mean(scenario, lambda values: sum((w*y for w, y in zip(coefficients, values)), F(0))))
        for k in range(1, 21):
            threshold = k/20
            actual = sum(float(prob) for values, prob in scenario
                         if abs(sum(w*y for w, y in zip(coefficient_float, values))-center) >= threshold-1e-14)
            bound = min(1., 2*math.exp(-2*threshold**2/constant))
            check(actual <= bound+1e-12, "enumerated two-sided tail below coloring bound")

    result = dict(schema_version="reliability-theory-exact-check-v1", status="passed_exact_finite_checks_only",
                  checks=len(checks), details=checks,
                  counterexample=dict(n_matches=4, outcomes="independent Bernoulli with p=(.9,.1,.9,.1)",
                                      true_variance=float(truth), binomial_variance_at_average=float(binomial_at_average),
                                      expected_oracle_center_graph_estimator=float(oracle_expected),
                                      expected_sample_center_graph_estimator=float(sample_expected),
                                      interpretation="A finite conditional-design counterexample, not a disproof of published asymptotic theorems under their assumptions"),
                  coloring_example=dict(weighted_constant=C, ordinary_K_constant=simple),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  real_data_used=False, random_draws=0, model_fitted=False,
                  mathematical_proof="General bound and conditions are in the companion theory document; enumerations are checks, not a proof for all laws",
                  formal_real_data_inference="not_run", human_review="not_performed")
    output = HERE / "exact_checks.json"
    content = json.dumps(result, ensure_ascii=False, indent=2)+"\n"
    if output.exists() and output.read_text(encoding="utf-8") != content:
        raise ValueError("Preserve prior exact checks rather than overwrite")
    output.write_text(content, encoding="utf-8", newline="\n")
    print(json.dumps({k: result[k] for k in ("status", "checks", "counterexample")}))


if __name__ == "__main__":
    main()
