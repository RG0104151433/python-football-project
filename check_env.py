"""Validate the local setup with synthetic data; this is not a football experiment.

Run from either IDE or with .venv/Scripts/python.exe check_env.py.
Only writes files inside outputs/environment_check beside this script.
"""

import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import struct
import sys


PACKAGES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "scipy": "scipy",
    "scikit-learn": "sklearn",
    "requests": "requests",
    "pytest": "pytest",
    "ipykernel": "ipykernel",
    "jupyterlab": "jupyterlab",
}


def main():
    root = Path(__file__).resolve().parent
    print("Python:", sys.executable)
    print("Version:", platform.python_version())
    bits = struct.calcsize("P") * 8
    print("Architecture:", bits)
    if sys.version_info[:2] != (3, 14):
        raise RuntimeError("This setup guide requires Python 3.14.x.")
    if bits != 64:
        raise RuntimeError("A 64-bit interpreter is required.")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Select the project .venv interpreter first.")
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        raise RuntimeError("The selected environment is not this project's .venv.")

    # Set the plotting backend before importing plotting packages.
    import matplotlib

    matplotlib.use("Agg")
    versions = {}
    for distribution, module in PACKAGES.items():
        importlib.import_module(module)
        versions[distribution] = importlib.metadata.version(distribution)
        print(f"OK {distribution}: {versions[distribution]}")

    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import numpy as np
    import pandas as pd
    from scipy.stats import norm
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss

    output = root / "outputs" / "environment_check"
    output.mkdir(parents=True, exist_ok=True)
    # Artificial, deliberately simple examples only test library integration.
    frame = pd.DataFrame({
        "elo_difference": [-300, -220, -140, -40, 0, 40, 140, 220, 300],
        "outcome": ["away", "away", "away", "draw", "draw", "draw",
                    "home", "home", "home"],
    })
    csv_path = output / "synthetic_matches.csv"
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    restored = pd.read_csv(csv_path, encoding="utf-8-sig")
    pd.testing.assert_frame_equal(frame, restored)
    if not np.isclose(norm.cdf(0), 0.5):
        raise RuntimeError("SciPy numerical check failed.")

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(restored[["elo_difference"]], restored["outcome"])
    # New synthetic inputs exercise predict_proba; no research score is reported.
    probes = pd.DataFrame({"elo_difference": [-200, 0, 200]})
    probabilities = model.predict_proba(probes)
    if not np.isfinite(probabilities).all():
        raise RuntimeError("Non-finite probabilities.")
    if (probabilities < 0).any() or not np.allclose(probabilities.sum(axis=1), 1):
        raise RuntimeError("Invalid probability vectors.")
    loss = log_loss(["away", "draw", "home"], probabilities, labels=model.classes_)
    if not np.isfinite(loss):
        raise RuntimeError("Metric calculation failed.")

    counts = restored["outcome"].value_counts().reindex(["away", "draw", "home"])
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts.index, counts.values)
    ax.set_title("Environment check: synthetic outcomes")
    ax.set_xlabel("Synthetic outcome")
    ax.set_ylabel("Number of synthetic examples")
    fig.tight_layout()
    figure_path = output / "environment_check.png"
    fig.savefig(figure_path, dpi=150)
    plt.close(fig)

    installed_fonts = {font.name for font in font_manager.fontManager.ttflist}
    chinese_fonts = sorted(installed_fonts.intersection({
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC",
    }))
    report = {
        "purpose": "Environment validation using synthetic data only",
        "python": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
        "architecture_bits": bits,
        "package_versions": versions,
        "available_chinese_fonts": chinese_fonts,
        "checks": ["project_venv", "imports", "csv_roundtrip", "scipy",
                   "classifier", "probabilities", "metric", "save_figure"],
    }
    report_path = output / "environment_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print("Chinese fonts:", chinese_fonts or "Not found; English plots still work")
    for path in (csv_path, figure_path, report_path):
        print("Saved:", path)
    print("ENVIRONMENT CHECK PASSED")


if __name__ == "__main__":
    main()
