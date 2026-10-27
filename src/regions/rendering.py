"""Bind chart rendering to actual font bytes, without copying system fonts."""
import platform
from pathlib import Path
import zlib

from .io import require, sha


def rendering_environment(font_file=None, required_text="主胜率国家队欧洲亚洲非洲美洲大洋洲"):
    from matplotlib import font_manager, ft2font

    if font_file:
        candidates = [Path(font_file).expanduser().resolve()]
        require(candidates[0].is_file(), "REG_FONT", "Font file not found: " + str(candidates[0]))
    else:
        candidates = []
        for family in ("Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei"):
            try:
                candidate = Path(font_manager.findfont(family, fallback_to_default=False)).resolve()
                if candidate not in candidates:
                    candidates.append(candidate)
            except ValueError:
                continue
    needed = {ord(c) for c in required_text if 0x3400 <= ord(c) <= 0x9FFF}
    for candidate in candidates:
        try:
            face = ft2font.FT2Font(str(candidate))
            if not needed.issubset(face.get_charmap()):
                continue
            environment = dict(schema_version="regions-rendering-v1", backend="Agg",
                               font_family=face.family_name, font_sha256=sha(candidate),
                               freetype=ft2font.__freetype_version__,
                               zlib=zlib.ZLIB_RUNTIME_VERSION, platform=platform.system())
            return environment, candidate
        except (OSError, RuntimeError):
            continue
    require(False, "REG_FONT", "No font covers required Chinese labels. Install a supported CJK font or pass --font-file PATH. No system font is copied into this repository.")


def pin_figure_font(figure, font_file):
    """Use the bound file for every text object and preserve individual text sizes."""
    from matplotlib.text import Text
    for text in figure.findobj(match=Text):
        properties = text.get_fontproperties().copy()
        properties.set_file(str(font_file))
        text.set_fontproperties(properties)
