"""Rendering identity and support inventory have explicit, testable boundaries."""
import json
from pathlib import Path

import pytest

from scripts.audit_region_support import inventory
from src.regions.export import dictionary
from src.regions.io import RegionError, sha
from src.regions.rendering import pin_figure_font, rendering_environment


def test_font_identity_uses_bytes_not_machine_path(tmp_path):
    from matplotlib import font_manager
    source = Path(font_manager.findfont("DejaVu Sans"))
    left, right = tmp_path / "left.ttf", tmp_path / "right.ttf"
    left.write_bytes(source.read_bytes()); right.write_bytes(source.read_bytes())
    a, pa = rendering_environment(left, required_text="")
    b, pb = rendering_environment(right, required_text="")
    assert a == b and a["font_sha256"] == sha(left)
    assert pa != pb and str(pa) not in json.dumps(a)


def test_missing_chinese_font_fails_instead_of_silent_latin_fallback():
    from matplotlib import font_manager
    with pytest.raises(RegionError, match="No font covers"):
        rendering_environment(font_manager.findfont("DejaVu Sans"), required_text="主胜率")


def test_missing_explicit_font_is_actionable(tmp_path):
    with pytest.raises(RegionError, match="Font file not found"):
        rendering_environment(tmp_path / "absent.ttf")


def test_pinned_font_preserves_heading_size():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = Path(font_manager.findfont("DejaVu Sans"))
    fig, ax = plt.subplots()
    text = ax.set_title("heading", fontsize=17)
    pin_figure_font(fig, font)
    assert text.get_fontsize() == 17 and text.get_fontproperties().get_file() == str(font)
    plt.close(fig)


def test_dictionary_follows_protocol_target_count():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/regions_study.json").read_text(encoding="utf-8"))
    content = dictionary(config).decode("utf-8")
    assert "15个成员目标" in content and "九个成员目标" not in content


def support_example(counts, weights, adjusted="0.5"):
    summary = [dict(target_id="T", group_id="G", group_label="example", n_matches=str(sum(counts)),
                    standardized_home_win_rate=adjusted, home_win_rate="0.5", standardization_status="ok" if adjusted else "unsupported_positive_reference_layer")]
    strata = [dict(target_id="T", group_id="G", era=str(i), tournament_group="friendly", n_matches=str(n)) for i, n in enumerate(counts)]
    refs = [dict(target_id="T", era=str(i), tournament_group="friendly", weight=str(q)) for i, q in enumerate(weights)]
    return inventory(summary, strata, refs, [])


def test_positive_missing_layer_and_small_nonzero_layers_are_distinct():
    row = support_example([0, 1, 2], [.2, .3, .5], adjusted="")[0]
    assert row["missing_positive_layers"] == 1 and row["one_match_layers"] == row["two_match_layers"] == 1
    assert row["min_observed_positive_layer_n"] == 1 and row["adjusted_home_win_rate"] is None


def test_empty_zero_weight_layer_does_not_create_false_missing_support():
    row = support_example([0, 2], [0, 1])[0]
    assert row["missing_positive_layers"] == 0 and row["positive_reference_layers"] == 1
    assert row["largest_defined_layer_q_over_n"] == .5
