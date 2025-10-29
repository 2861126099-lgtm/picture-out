# -*- coding: utf-8 -*-
"""
colormaps.py
- 集中管理色带注册表 CMAP_REGISTRY
- 支持 Matplotlib 内置名（"mpl":"Viridis"）或自定义颜色断点（"colors":[hex...]）
- 所有自定义色带都会以 256 级连续色带注册，供绘图与 GUI 下拉预览使用
"""

from matplotlib import cm as mpl_cm
from matplotlib.colors import LinearSegmentedColormap

# ---------------- 色带注册（原有 44 种 + 新增 13 个单色渐变 = 57 种） ----------------
# 每条记录： key: {'name':显示名称, 'group':分组, 'mpl':Matplotlib名 或 'colors':[hex...]}

CMAP_REGISTRY = {
    # ========= 原有：感知型顺序（6） =========
    "seq_viridis":  {"name":"viridis（感知顺序）", "group":"感知型顺序", "mpl":"viridis"},
    "seq_plasma":   {"name":"plasma（感知顺序）",  "group":"感知型顺序", "mpl":"plasma"},
    "seq_inferno":  {"name":"inferno（感知顺序）", "group":"感知型顺序", "mpl":"inferno"},
    "seq_magma":    {"name":"magma（感知顺序）",   "group":"感知型顺序", "mpl":"magma"},
    "seq_cividis":  {"name":"cividis（感知顺序）", "group":"感知型顺序", "mpl":"cividis"},
    "seq_turbo":    {"name":"turbo（感知顺序）",   "group":"感知型顺序", "mpl":"turbo"},

    # ========= 原有：主题顺序（8） =========
    "seq_ylorrd":   {"name":"YlOrRd（暖色降雨/干旱）", "group":"主题顺序", "mpl":"YlOrRd"},
    "seq_ord":      {"name":"OrRd（橙红）",          "group":"主题顺序", "mpl":"OrRd"},
    "seq_ylgn":     {"name":"YlGn（黄绿）",          "group":"主题顺序", "mpl":"YlGn"},
    "seq_ylgnbu":   {"name":"YlGnBu（黄绿-蓝）",     "group":"主题顺序", "mpl":"YlGnBu"},
    "seq_pubugn":   {"name":"PuBuGn（紫-蓝-绿）",     "group":"主题顺序", "mpl":"PuBuGn"},
    "seq_gnbu":     {"name":"GnBu（绿-蓝）",         "group":"主题顺序", "mpl":"GnBu"},
    "seq_blues":    {"name":"Blues（蓝）",           "group":"主题顺序", "mpl":"Blues"},
    "seq_oranges":  {"name":"Oranges（橙）",         "group":"主题顺序", "mpl":"Oranges"},

    # ========= 原有：发散（8） =========
    "div_rdyblu_r": {"name":"RdYlBu_r（红-黄-蓝 反转）", "group":"发散", "mpl":"RdYlBu_r"},
    "div_coolwarm": {"name":"coolwarm（冷暖）",          "group":"发散", "mpl":"coolwarm"},
    "div_spectral": {"name":"Spectral（光谱）",          "group":"发散", "mpl":"Spectral"},
    "div_brbg":     {"name":"BrBG（棕-蓝绿）",          "group":"发散", "mpl":"BrBG"},
    "div_piyg":     {"name":"PiYG（粉-绿）",            "group":"发散", "mpl":"PiYG"},
    "div_prgn":     {"name":"PRGn（紫-绿）",            "group":"发散", "mpl":"PRGn"},
    "div_puor":     {"name":"PuOr（紫-橙）",            "group":"发散", "mpl":"PuOr"},
    "div_rdbu":     {"name":"RdBu（红-蓝）",            "group":"发散", "mpl":"RdBu"},

    # ========= 原有：季节（4，自定义） =========
    "season_spring":{"name":"春（嫩绿）", "group":"季节",
                     "colors":["#f7fcf5","#d9f0d3","#a6dba0","#5aae61","#1b7837"]},
    "season_summer":{"name":"夏（湛蓝）", "group":"季节",
                     "colors":["#f7fbff","#deebf7","#9ecae1","#4292c6","#08519c"]},
    "season_autumn":{"name":"秋（橙褐）", "group":"季节",
                     "colors":["#fff5eb","#fee6ce","#fdae6b","#e6550d","#7f2704"]},
    "season_winter":{"name":"冬（冰蓝）", "group":"季节",
                     "colors":["#ffffff","#e0f3f8","#abd9e9","#74add1","#4575b4"]},

    # ========= 原有：复合事件（4，自定义） =========
    "evt_ww_ocean":{"name":"WW 暖湿（海洋蓝）", "group":"复合事件",
                    "colors":["#e0f3f8","#b2e2e2","#66c2a4","#2ca25f","#006d2c"]},
    "evt_wd_desert":{"name":"WD 暖干（沙漠橙）", "group":"复合事件",
                     "colors":["#fff7bc","#fee391","#fec44f","#fe9929","#d95f0e"]},
    "evt_cw_polar":{"name":"CW 冷湿（极地紫蓝）", "group":"复合事件",
                    "colors":["#f7f4f9","#d4b9da","#c994c7","#756bb1","#54278f"]},
    "evt_cd_drought":{"name":"CD 冷干（灰褐）", "group":"复合事件",
                      "colors":["#f7f7f7","#cccccc","#969696","#636363","#252525"]},

    # ========= 原有：论文精选·顺序（7，自定义近似） =========
    "sci_batlow": {"name":"batlow（冷蓝→黄，论文精选）", "group":"论文精选·顺序",
                   "colors":["#011959","#084594","#2E7FB8","#65ADC2","#A3D3A1","#E4E09B","#F7CB5A","#F59D15","#D14905"]},
    "sci_oslo":   {"name":"oslo（灰蓝气候风，论文精选）", "group":"论文精选·顺序",
                   "colors":["#1B2A41","#274863","#3C6E8F","#6297B0","#93B7C8","#C4CFD6","#E6E6E6","#E7D9C5","#D2B599"]},
    "sci_lapaz":  {"name":"lapaz（紫→青绿，论文精选）", "group":"论文精选·顺序",
                   "colors":["#2D004B","#5E2A84","#8F56B5","#B583D1","#D8B6E3","#E8E2F0","#D3E6E6","#A9D4C1","#6BB68E","#3A8C5C"]},
    "sci_hawaii": {"name":"hawaii（海蓝→青黄，论文精选）", "group":"论文精选·顺序",
                   "colors":["#00184F","#003D7E","#0069A6","#00A2B5","#25C4A8","#7CD6A2","#CFE29E","#F8DE8A","#F5C45B","#E78C2D"]},
    "sci_tokyo":  {"name":"tokyo（青绿→赭红，论文精选）", "group":"论文精选·顺序",
                   "colors":["#003C3C","#0C6666","#2E8E7D","#6BAB88","#A8C08E","#E0D79F","#F1C37C","#E59A5E","#C46A5B","#7A3A4E"]},
    "sci_devon":  {"name":"devon（蓝→橙，对比清晰）", "group":"论文精选·顺序",
                   "colors":["#08306B","#2171B5","#6BAED6","#BDD7E7","#EFF3FF","#FEE0B6","#FDB863","#E08214","#B35806","#7F3B08"]},
    "sci_ocean_deep":{"name":"ocean-deep（深海蓝→亮青）", "group":"论文精选·顺序",
                   "colors":["#001F3F","#003F7F","#005F9F","#007FBF","#009FDF","#20BFE7","#60D7EF","#A0E7F7","#D0F3FB","#F0FBFF"]},

    # ========= 原有：论文精选·发散（6，自定义近似） =========
    "sci_vik":   {"name":"vik（蓝→白→红，论文精选）", "group":"论文精选·发散",
                  "colors":["#00204D","#1B5E9E","#4FA7F5","#BFE5FF","#FFFFFF","#FFC4C4","#F66E6E","#C51313","#7A0202"]},
    "sci_broc":  {"name":"broc（蓝灰→棕，论文精选）", "group":"论文精选·发散",
                  "colors":["#2E4A7D","#4F77A3","#84A9C0","#BFD3D9","#E9ECEC","#E0D6CD","#C8B19A","#A07D60","#6E4E3A"]},
    "sci_cork":  {"name":"cork（青→黑→粉，论文精选）", "group":"论文精选·发散",
                  "colors":["#2C6B6F","#3F8F8F","#7FBFB1","#D8EFE8","#F6F6F6","#E9D4EA","#C29ACB","#8A5EA8","#5B2C7F"]},
    "sci_roma":  {"name":"roma（红→黑→蓝，论文精选）", "group":"论文精选·发散",
                  "colors":["#5C0000","#A82E2E","#D97C7C","#F2C6C6","#F7F7F7","#C7D8F2","#81A6D9","#2C63A8","#002B6C"]},
    "sci_burl":  {"name":"burl（棕→灰→蓝，论文精选）", "group":"论文精选·发散",
                  "colors":["#6E3B22","#9B623A","#C9936B","#E6C7A3","#F3EFE7","#CAD7E3","#96B1CC","#5E7CA3","#2E4E73"]},
    "sci_greenmagenta": {"name":"Green–Magenta（绿→灰→品红）", "group":"论文精选·发散",
                  "colors":["#0B775E","#3BA091","#84CDBD","#D6ECE1","#F7F7F7","#E7D5E8","#C39BC7","#985EA1","#6B1F7C"]},

    # ========= 原有：论文精选·海洋/冰雪（2） =========
    "sci_ice":   {"name":"ice（冰川白蓝）", "group":"论文精选·海洋/冰雪",
                  "colors":["#f7fcfd","#e0f3f8","#ccece6","#99d8c9","#66c2a4","#41ae76","#238b45","#006d2c","#00441b"]},
    "sci_deepsea":{"name":"deepsea（深海蓝）", "group":"论文精选·海洋/冰雪",
                  "colors":["#001020","#001F3A","#00335B","#004C7A","#00669A","#1987B8","#4FA9CF","#89C8E0","#BFE0EE","#E6F4F9"]},

    # ========= 原有：循环（1） =========
    "cyc_twilight":{"name":"twilight（循环，等相位数据）", "group":"循环", "mpl":"twilight"},

    # ========= 新增：单色渐变（13） =========
    "mono_grey":   {"name":"灰（单色渐变）", "group":"单色渐变",
                    "colors":["#ffffff","#ededed","#d9d9d9","#bfbfbf","#999999","#6b6b6b","#3b3b3b"]},
    "mono_red":    {"name":"红（单色渐变）", "group":"单色渐变",
                    "colors":["#fff5f5","#fccfcf","#f79a9a","#ef6b6b","#d63b3b","#a92020","#6d0f0f"]},
    "mono_orange": {"name":"橙（单色渐变）", "group":"单色渐变",
                    "colors":["#fff6ea","#ffd9b5","#ffbd7a","#ff9f3a","#ed7a00","#b75a00","#6e3700"]},
    "mono_gold":   {"name":"金黄（单色渐变）", "group":"单色渐变",
                    "colors":["#fffce6","#fff2a8","#ffe36b","#ffd138","#f0b400","#b98900","#6f4f00"]},
    "mono_green":  {"name":"绿（单色渐变）", "group":"单色渐变",
                    "colors":["#f1fbf3","#ccefd5","#9adfae","#63c986","#2ea35f","#177a41","#0c4f29"]},
    "mono_teal":   {"name":"青绿（单色渐变）", "group":"单色渐变",
                    "colors":["#effaf9","#c9ece8","#93d6cf","#5dbbb3","#2a9893","#187376","#0b4b4f"]},
    "mono_cyan":   {"name":"青（单色渐变）", "group":"单色渐变",
                    "colors":["#f0fbff","#c9ecfb","#93d5f5","#59b7e6","#2a92c6","#176a97","#0b435f"]},
    "mono_blue":   {"name":"蓝（单色渐变）", "group":"单色渐变",
                    "colors":["#f3f7ff","#d3e0ff","#a9c2ff","#7aa0f5","#4b7bdb","#2b56b0","#18336d"]},
    "mono_indigo": {"name":"靛蓝（单色渐变）", "group":"单色渐变",
                    "colors":["#f5f5ff","#d7d7fa","#b1b1f0","#8484df","#5a5ac0","#3b3b97","#24245f"]},
    "mono_purple": {"name":"紫（单色渐变）", "group":"单色渐变",
                    "colors":["#fcf5ff","#ead7fb","#d0b1f0","#b184df","#8e5ac0","#6a3b97","#40245f"]},
    "mono_magenta":{"name":"洋红（单色渐变）", "group":"单色渐变",
                    "colors":["#fff0fa","#f8c6e8","#ee99d2","#df6bb6","#c13b93","#8f1f6e","#551445"]},
    "mono_pink":   {"name":"粉（单色渐变）", "group":"单色渐变",
                    "colors":["#fff2f6","#ffd0dd","#ffabc3","#ff84a8","#f4578c","#c6366d","#7a2043"]},
    "mono_brown":  {"name":"棕（单色渐变）", "group":"单色渐变",
                    "colors":["#fbf6f2","#ead9cc","#d4b99d","#ba946d","#976f49","#6e4d2f","#402c19"]},
}

# --- 工具：根据 key 取 matplotlib colormap（自定义则动态注册） ---
_CMAP_OBJECT_CACHE = {}

def resolve_cmap(cmap_key_or_name):
    """
    输入：
        - cmap_key_or_name: 在 CMAP_REGISTRY 的 key，或 Matplotlib 已注册的 cmap 名称
    返回：
        - Matplotlib Colormap 对象
    说明：
        - 对于 'colors' 定义的自定义色带，会在首次调用时以 256 级注册并缓存。
        - 若传入的 key/名称无法解析，将回退到 'viridis'。
    """
    if cmap_key_or_name in _CMAP_OBJECT_CACHE:
        return _CMAP_OBJECT_CACHE[cmap_key_or_name]

    entry = CMAP_REGISTRY.get(cmap_key_or_name, None)
    if entry is None:
        try:
            cmobj = mpl_cm.get_cmap(cmap_key_or_name)
            _CMAP_OBJECT_CACHE[cmap_key_or_name] = cmobj
            return cmobj
        except Exception:
            cmobj = mpl_cm.get_cmap("viridis")
            _CMAP_OBJECT_CACHE[cmap_key_or_name] = cmobj
            return cmobj

    try:
        if "mpl" in entry:
            cmobj = mpl_cm.get_cmap(entry["mpl"])
        else:
            colors = entry["colors"]
            cmobj = LinearSegmentedColormap.from_list(cmap_key_or_name, colors, N=256)
    except Exception:
        cmobj = mpl_cm.get_cmap("viridis")

    _CMAP_OBJECT_CACHE[cmap_key_or_name] = cmobj
    return cmobj
