# -*- coding: utf-8 -*-
"""
统一字体配置（项目内置 + 系统候选）：
- 自动注册 paper_map/assets/fonts/ 下的 ttf/ttc/otf
- 智能选择中文/英文字体并设置 rcParams
- 导出 EN_FONT / ZH_FONT 供绘图代码显式使用
- 额外：对 Matplotlib 做轻量“猴补丁”
  * Axes.set_title / Axes.text / Figure.suptitle / Colorbar.set_label
    若文本包含中文且未显式传 fontproperties，则自动使用 ZH_FONT
"""

from __future__ import annotations
import os, glob, typing as _t, re

import matplotlib as mpl
from matplotlib import font_manager as fm
from matplotlib.font_manager import FontProperties

# —— 候选（前面优先） ——
EN_DEFAULTS = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]
ZH_DEFAULTS = [
    "Source Han Sans SC", "Noto Sans CJK SC",       # 开源中文（建议放到 assets/fonts）
    "Microsoft YaHei", "SimHei", "SimSun", "DengXian", "KaiTi",
    "FangSong", "STSong",
    "Arial Unicode MS",                              # 兜底的“大一统”
]

_ASSET_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

# -------------- 基础：注册 & 选择 --------------
def _register_local_fonts() -> None:
    """把项目内置字体注册给 matplotlib。不存在时安全跳过。"""
    if not os.path.isdir(_ASSET_FONT_DIR):
        return
    for ext in ("*.ttf", "*.ttc", "*.otf"):
        for p in glob.glob(os.path.join(_ASSET_FONT_DIR, ext)):
            try:
                fm.fontManager.addfont(p)
            except Exception:
                pass
    try:
        fm._rebuild()
    except Exception:
        pass

def _pick_font_by_families(candidates: _t.Sequence[str]) -> tuple[str, FontProperties]:
    """给定候选字体族名称，挑第一个可用；失败回退 DejaVu Sans。"""
    for fam in candidates:
        try:
            path = fm.findfont(FontProperties(family=fam), fallback_to_default=False)
            if path and os.path.exists(path):
                return fam, FontProperties(fname=path)
        except Exception:
            continue
    path = fm.findfont(FontProperties(family="DejaVu Sans"))
    return "DejaVu Sans", FontProperties(fname=path)

def apply_fonts(font_en: str | None = None, font_zh: str | None = None) -> tuple[str, str]:
    """配置 matplotlib 全局字体；返回 (en_name, zh_name)。"""
    _register_local_fonts()

    en_list = [font_en] + EN_DEFAULTS if font_en else EN_DEFAULTS
    zh_list = [font_zh] + ZH_DEFAULTS if font_zh else ZH_DEFAULTS

    en_name, _ = _pick_font_by_families(en_list)
    zh_name, _ = _pick_font_by_families(zh_list)

    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = [zh_name, en_name, "DejaVu Sans", "Arial Unicode MS"]
    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"]  = 42
    mpl.rcParams["svg.fonttype"] = "none"
    return en_name, zh_name

def fontprops_pair(font_en: str | None = None, font_zh: str | None = None) -> tuple[FontProperties, FontProperties]:
    """返回 (fp_en, fp_zh) 以供显式传入。"""
    apply_fonts(font_en=font_en, font_zh=font_zh)
    _, fp_en = _pick_font_by_families([font_en] + EN_DEFAULTS if font_en else EN_DEFAULTS)
    _, fp_zh = _pick_font_by_families([font_zh] + ZH_DEFAULTS if font_zh else ZH_DEFAULTS)
    return fp_en, fp_zh

# 导出常用 FontProperties（导入即可用）
EN_FONT, ZH_FONT = fontprops_pair()

# -------------- 猴补丁：自动给中文文本套中文字体 --------------
_CJK_RE = re.compile(
    r"[\u2e80-\u2eff\u2f00-\u2fdf\u3040-\u30ff\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)

def _contains_cjk(s: str) -> bool:
    return isinstance(s, str) and bool(_CJK_RE.search(s))

_PATCHED = False

def _monkey_patch_text_defaults():
    """给常用文本接口自动套上合适的 fontproperties。"""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    # Axes.set_title
    try:
        from matplotlib.axes import Axes
        _orig_set_title = Axes.set_title
        def _set_title(self, label, *args, **kwargs):
            if "fontproperties" not in kwargs:
                kwargs["fontproperties"] = ZH_FONT if _contains_cjk(label) else EN_FONT
            return _orig_set_title(self, label, *args, **kwargs)
        Axes.set_title = _set_title  # type: ignore
    except Exception:
        pass

    # Axes.text
    try:
        from matplotlib.axes import Axes
        _orig_text = Axes.text
        def _text(self, x, y, s, *args, **kwargs):
            if "fontproperties" not in kwargs and _contains_cjk(s):
                kwargs["fontproperties"] = ZH_FONT
            return _orig_text(self, x, y, s, *args, **kwargs)
        Axes.text = _text  # type: ignore
    except Exception:
        pass

    # Figure.suptitle
    try:
        from matplotlib.figure import Figure
        _orig_suptitle = Figure.suptitle
        def _suptitle(self, t, *args, **kwargs):
            if "fontproperties" not in kwargs:
                kwargs["fontproperties"] = ZH_FONT if _contains_cjk(t) else EN_FONT
            return _orig_suptitle(self, t, *args, **kwargs)
        Figure.suptitle = _suptitle  # type: ignore
    except Exception:
        pass

    # Colorbar.set_label
    try:
        from matplotlib.colorbar import Colorbar
        _orig_cbar_label = Colorbar.set_label
        def _cbar_set_label(self, s, *args, **kwargs):
            if "fontproperties" not in kwargs and _contains_cjk(s):
                kwargs["fontproperties"] = ZH_FONT
            return _orig_cbar_label(self, s, *args, **kwargs)
        Colorbar.set_label = _cbar_set_label  # type: ignore
    except Exception:
        pass

# 导入本模块时就打补丁
_monkey_patch_text_defaults()

__all__ = [
    "apply_fonts", "fontprops_pair", "EN_FONT", "ZH_FONT",
    "EN_DEFAULTS", "ZH_DEFAULTS",
]
