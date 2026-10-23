"""Explicit boundary: no unvalidated estimator or confidence interval fallback."""
from ..data_contract import PrepError


def require_off(config):
    if config["inference"] != {"mode": "off", "validation_status": "pending"}:
        raise PrepError("INFERENCE_NOT_IMPLEMENTED", "No estimator has passed project validation")


def without_uncertainty():
    return dict(standard_error=None, ci_lower=None, ci_upper=None, confidence_level=None,
                method_id="", method_version="", uncertainty_status="not_run")
