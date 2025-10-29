# -*- coding: utf-8 -*-
"""
paper_map.plotting — fonts & colorbar fixes
- 分别接收 font_en / font_zh，并在绘图前应用到 Matplotlib
- 单图 vmax 默认取真实最大值；多图共享色带 vmax 取所有数组的真实最大值（不再用分位数）
- 共享色带刻度最后一格对齐 vmax，避免“最大值看不到/被模糊”
- 标题 loc='center' 强制居中
"""

import os, glob, time, inspect
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.features import geometry_mask
from rasterio.transform import array_bounds
import geopandas as gpd
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
import matplotlib
try:
    matplotlib.use("TkAgg")
except Exception:
    pass
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from matplotlib import rcParams

# 统一使用项目的色带与字体工具
from .colormaps import resolve_cmap
from .config import DST_CRS, PCT_UPPER
from . import fonts as _fonts

# === 放在 plotting.py 顶部其它 import 后，如果已导入可忽略 ===
import matplotlib as mpl
from matplotlib.font_manager import FontProperties

# 放在 plotting.py 顶部 imports 之后
def _nonblocking_preview(fig):
    """在 Tk 主循环中安全地非阻塞显示一个 Matplotlib Figure。"""
    import matplotlib.pyplot as plt
    try:
        fig.canvas.draw_idle()
        # TkAgg 下有 manager
        if hasattr(fig.canvas, "manager") and fig.canvas.manager is not None:
            fig.canvas.manager.show()
        else:
            plt.show(block=False)
        fig.canvas.flush_events()
    except Exception:
        # 最兜底再试一次（有些后端不支持 manager.show）
        try:
            plt.show(block=False)
        except Exception:
            pass


def _font_props(font_en: str = "Arial", font_zh: str = "Source Han Sans SC", size=None):
    """
    返回英文与中文 FontProperties；不修改全局 rcParams，避免单图/多图相互污染。
    """
    mpl.rcParams['axes.unicode_minus'] = False
    fp_en = FontProperties(family=font_en, size=size)
    fp_zh = FontProperties(family=font_zh, size=size)
    return fp_en, fp_zh



# ---------- 工具：路径/读裁剪 ----------
def resolve_path(path_pattern: str) -> str:
    if any(ch in path_pattern for ch in "*?"):
        matches = sorted(glob.glob(path_pattern))
        if not matches:
            raise FileNotFoundError(f"未找到匹配：{path_pattern}")
        return os.path.abspath(matches[0])
    if not os.path.exists(path_pattern):
        raise FileNotFoundError(f"文件不存在：{path_pattern}")
    return os.path.abspath(path_pattern)

def _read_gdf_any(path):
    try:
        return gpd.read_file(path)
    except Exception:
        return gpd.read_file(path, engine="fiona")

def read_border_gdf(border_shp: str) -> gpd.GeoDataFrame:
    if not border_shp or not os.path.exists(border_shp):
        raise FileNotFoundError("边界SHP路径为空或文件不存在。")
    gdf = _read_gdf_any(border_shp)
    if gdf.crs is None:
        raise ValueError("边界SHP缺少CRS。")
    return gdf

def read_project_clip(raster_path, border_gdf, dst_crs, year_start, year_end, as_yearly):
    span = max(1, int(year_end) - int(year_start) + 1)
    with rasterio.open(raster_path) as src:
        a = src.read(1).astype("float32")
        if src.nodata is not None:
            a = np.where(a == src.nodata, np.nan, a)
        tfm, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
        arr = np.full((h, w), np.nan, dtype="float32")
        # 频次类数据更适合 nearest；如需平滑可改为 bilinear
        reproject(source=a, destination=arr,
                  src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tfm, dst_crs=dst_crs,
                  src_nodata=np.nan, dst_nodata=np.nan,
                  resampling=Resampling.nearest)
    g = border_gdf.to_crs(dst_crs) if border_gdf.crs != dst_crs else border_gdf
    mask = geometry_mask([geom for geom in g.geometry if geom is not None],
                         out_shape=arr.shape, transform=tfm, invert=True)
    arr = np.where(mask, arr, np.nan)
    if as_yearly:
        arr = arr / float(span)
    return arr, tfm

def extent_from_transform(arr, tfm):
    left, bottom, right, top = array_bounds(arr.shape[0], arr.shape[1], tfm)
    return [left, right, bottom, top]


# ---------- 绘制小组件 ----------
def nice_length_km(width_m):
    target = (width_m / 4.8) / 1000.0
    mag = 10 ** np.floor(np.log10(target)) if target > 0 else 1
    for k in [1, 2, 5, 10]:
        cand = k * mag
        if cand >= target:
            return int(cand)
    return max(1, int(round(target)))

def draw_scale_bar_axes(ax, extent, *, km_length=None, segments=4, bar_h=0.012,
                        y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                        txt_size=9, edge_lw=0.6, line_lw=0.7):
    left, right, bottom, top = extent
    width_m = right - left
    if km_length is None or km_length <= 0:
        km_length = nice_length_km(width_m)
    length_m = km_length * 1000.0
    frac_w = length_m / width_m

    x0 = x_in
    y0 = -y_out
    bg = Rectangle((x0-0.02, y0-0.012), frac_w+0.04, bar_h+0.05,
                   transform=ax.transAxes, facecolor='white', edgecolor='none',
                   alpha=1.0, clip_on=False, zorder=2)
    ax.add_patch(bg)

    seg_w = frac_w / max(1, segments)
    for i in range(max(1, segments)):
        rect = Rectangle((x0 + i*seg_w, y0), seg_w, bar_h,
                         transform=ax.transAxes,
                         facecolor=('black' if i % 2 == 0 else 'white'),
                         edgecolor='black', linewidth=edge_lw, clip_on=False, zorder=3)
        ax.add_patch(rect)
    ax.plot([x0, x0+frac_w], [y0+bar_h, y0+bar_h], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)
    t0 = ax.text(x0, y0-0.01, "0", transform=ax.transAxes,
                 ha='center', va='top', fontsize=txt_size, clip_on=False)
    half = (km_length//2 if km_length % 2 == 0 else round(km_length/2))
    # 这里改成使用可控的单位与分隔符
    t1 = ax.text(x0 + frac_w/2, y0-0.01, f"{half}{unit_sep}{unit}", transform=ax.transAxes,
                 ha='center', va='top', fontsize=txt_size, clip_on=False)
    t2 = ax.text(x0 + frac_w, y0-0.01, f"{km_length}{unit_sep}{unit}", transform=ax.transAxes,
                 ha='center', va='top', fontsize=txt_size, clip_on=False)
    for _t in (t0, t1, t2):
        _t.set_fontsize(txt_size)



def draw_north(ax, extent, *, size_frac=0.06, pad_frac=0.08, txt_size=10, face='black', edge='black', lw=1.2):
    left, right, bottom, top = extent
    x = right  - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac
    w = h * 0.45
    tri = Polygon([[x, y+h], [x-w, y], [x+w, y]], closed=True, facecolor=face, edgecolor=edge, lw=lw)
    ax.add_patch(tri)
    ax.text(x, y+h + (top-bottom)*0.01, 'N', ha='center', va='bottom',
            fontsize=txt_size, fontweight='bold')


# ---------- 字体应用 ----------
def _apply_fonts(font_en: str | None, font_zh: str | None):
    """
    将 GUI 选择的英/中文字体应用到 Matplotlib：
      - 通过 _fonts.apply_fonts 注册并设置 rcParams
      - 把英文字体放在 sans-serif 列表的前面，数字/英文字母优先走英文
      - 更新猴补丁使用的 EN_FONT / ZH_FONT（动态生效）
    """
    en_name, zh_name = _fonts.apply_fonts(font_en=font_en, font_zh=font_zh)

    # 关键：所有未显式指定 fontproperties 的文本都按这个“候选列表”依次找字体
    mpl.rcParams["font.family"] = [en_name, zh_name, "DejaVu Sans", "Arial Unicode MS"]

    # 兼容：有些地方家族仍写了 'sans-serif'，我们也把顺序放好
    cur = list(rcParams.get("font.sans-serif", []))
    rcParams["font.sans-serif"] = [en_name, zh_name, "DejaVu Sans", "Arial Unicode MS"] + \
                                  [f for f in cur if f not in (en_name, zh_name, "DejaVu Sans", "Arial Unicode MS")]

    rcParams["axes.unicode_minus"] = False

    # 提供给其他模块用的 FontProperties（可留用）
    en_fp, zh_fp = _fonts.fontprops_pair(font_en, font_zh)
    _fonts.EN_FONT, _fonts.ZH_FONT = en_fp, zh_fp


# ================= 实现（impl） =================
# —— 替换原有 _make_single_map_impl ——
def _make_single_map_impl(
    *, tif_path, border_shp, overlay_layers,
    year_start, year_end, as_yearly,
    font_en="Times New Roman", font_zh="Microsoft YaHei",
    out_png=None, out_pdf=None,
    fig_w=8.8, fig_h=6.6, dpi=150,
    title="图题", vmin=None, vmax=None,
    title_size=12, title_pad=6,
    border_lw=0.8,
    cmap_key="seq_ylorrd",
    cbar_loc="right",
    cbar_label_text=None, cbar_label_size=11, cbar_tick_size=10,
    scale_txt_size=9, scale_x_in=0.08, scale_y_out=0.12,
    scale_segments=4, scale_bar_h=0.012, scale_edge_lw=0.6, scale_line_lw=0.7,
    scale_km=None, scale_unit="km", scale_unit_sep=" ",
    north_txt_size=10, north_style='triangle', north_pad=0.08,
    preview=False
):
    import numpy as np
    import matplotlib.pyplot as plt

    # 字体
    _apply_fonts(font_en, font_zh)
    fp_en, fp_zh = _font_props(font_en, font_zh)

    # 数据与范围
    border_gdf = read_border_gdf(border_shp)
    arr, tfm = read_project_clip(resolve_path(tif_path), border_gdf, DST_CRS, year_start, year_end, as_yearly)
    extent = extent_from_transform(arr, tfm)

    # 自动 vmin/vmax
    if vmin is None:
        vmin = float(np.nanmin(arr))
    if vmax is None:
        vmax = float(np.nanmax(arr))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        vmin, vmax = 0.0, 1.0  # 兜底，避免空阵

    # 画图
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    im = ax.imshow(arr, extent=extent, origin='upper',
                   cmap=resolve_cmap(cmap_key), vmin=vmin, vmax=vmax)
    # 行政边界 + 叠加
    (border_gdf.to_crs(DST_CRS) if border_gdf.crs != DST_CRS else border_gdf).boundary.plot(
        ax=ax, linewidth=border_lw, edgecolor='black', zorder=3)
    _draw_overlays(ax, overlay_layers)
    ax.set_axis_off()

    # 标题
    if title:
        ax.set_title(title, fontsize=title_size, pad=title_pad, loc='center')

    # 色带
    orient = 'vertical' if cbar_loc in ('right', 'left') else 'horizontal'
    cbar = fig.colorbar(im, ax=ax, orientation=orient)
    # 统一 6 个刻度，并把两端对齐
    ticks = np.linspace(vmin, vmax, 6)
    ticks[0], ticks[-1] = vmin, vmax
    cbar.set_ticks(ticks)
    if cbar_label_text:
        cbar.set_label(cbar_label_text, fontsize=cbar_label_size, fontproperties=fp_zh)
    cbar.ax.tick_params(labelsize=cbar_tick_size)

    # 比例尺 + 北箭
    draw_scale_bar_axes(ax, extent,
                        km_length=scale_km, segments=scale_segments,
                        bar_h=scale_bar_h, y_out=scale_y_out, x_in=scale_x_in,
                        unit=scale_unit, unit_sep=scale_unit_sep,
                        txt_size=scale_txt_size, edge_lw=scale_edge_lw, line_lw=scale_line_lw)
    draw_north(ax, extent, size_frac=0.06, pad_frac=north_pad, txt_size=north_txt_size)

    if preview:
        # 预览：只显示，不关闭；把“保存/关闭”交给用户下一次操作
        _nonblocking_preview(fig)  # 如果没加小工具函数，就把它展开成上面的 3 行 try…except
        return

        # 非预览：按需保存并关闭
    _safe_save(fig, out_png)
    _safe_save(fig, out_pdf)
    plt.close(fig)


# === 覆盖原来的 _make_grid_map_impl（与字体相关的地方都显式传入 fontproperties）===
# —— 替换原有 _make_grid_map_impl ——
def _make_grid_map_impl(
    tif_list, border_shp, overlay_layers,
    year_start, year_end, as_yearly,
    fp_en, fp_zh,
    nrows, ncols, panel_titles,
    caption, caption_size, caption_y,
    title_size, title_pad,

    border_lw,
    cmap_key,
    panel_cmaps,
    share_vmax,

    use_shared_cbar,
    shared_cbar_loc, shared_cbar_frac,
    shared_cbar_label_text,
    shared_cbar_label_size, shared_cbar_tick_size,
    shared_cbar_ticks,

    per_cbar_loc, per_cbar_size,
    per_cbar_pad, per_cbar_label_text,
    per_cbar_label_size, per_cbar_tick_size,
    per_cbar_ticks, per_use_auto_vmax, per_vmax_percentile,

    scale_length, scale_unit, scale_unit_sep, scale_segments,
    scale_bar_h, scale_edge_lw, scale_line_lw, scale_txt_size,
    scale_anchor, scale_pad_x, scale_pad_y,

    north_style, north_size_frac,
    north_anchor, north_pad_x, north_pad_y, north_txt_size,

    wspace, hspace, fig_w, fig_h, dpi,
    preview, save_png, save_pdf
):
    import numpy as _np
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    border_gdf = read_border_gdf(border_shp)

    # 读所有栅格
    arrs, exts = [], []
    for p in tif_list:
        arr, tfm = read_project_clip(resolve_path(p), border_gdf, DST_CRS, year_start, year_end, as_yearly)
        arrs.append(arr)
        exts.append(extent_from_transform(arr, tfm))

    # —— 共享色带：全局 vmin/vmax（vmax 可手动 share_vmax） ——
    if use_shared_cbar:
        global_vmin = float(_np.nanmin([_np.nanmin(a) for a in arrs])) if arrs else 0.0
        _auto_vmax = float(_np.nanmax([_np.nanmax(a) for a in arrs])) if arrs else 1.0
        global_vmax = float(share_vmax) if (share_vmax is not None) else _auto_vmax
        if not _np.isfinite(global_vmin) or not _np.isfinite(global_vmax) or global_vmin >= global_vmax:
            global_vmin, global_vmax = 0.0, 1.0
        norm = Normalize(vmin=global_vmin, vmax=global_vmax)
        shared_mappable = ScalarMappable(norm=norm, cmap=resolve_cmap(cmap_key))

    # 画布
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    gs = GridSpec(nrows, ncols, figure=fig, wspace=wspace, hspace=hspace)
    axes = [fig.add_subplot(gs[i//ncols, i % ncols]) for i in range(len(tif_list))]

    for i, (ax, arr, ext) in enumerate(zip(axes, arrs, exts)):
        this_cmap_key = (panel_cmaps[i] if (panel_cmaps and i < len(panel_cmaps)) else cmap_key)

        # —— 每图自身范围 ——
        if not use_shared_cbar:
            vmin_i = float(_np.nanmin(arr)) if _np.isfinite(arr).any() else 0.0
            if per_use_auto_vmax or per_vmax_percentile is None or (not _np.isfinite(arr).any()):
                vmax_i = float(_np.nanmax(arr)) if _np.isfinite(arr).any() else 1.0
            else:
                valid = arr[_np.isfinite(arr)]
                vmax_i = float(_np.nanpercentile(valid, float(per_vmax_percentile))) if valid.size else 1.0
            if not _np.isfinite(vmin_i) or not _np.isfinite(vmax_i) or vmin_i >= vmax_i:
                vmin_i, vmax_i = 0.0, 1.0

        im = ax.imshow(
            arr, extent=ext, origin='upper',
            cmap=resolve_cmap(this_cmap_key),
            vmin=(global_vmin if use_shared_cbar else vmin_i),
            vmax=(global_vmax if use_shared_cbar else vmax_i)
        )

        # 行政边界 + 叠加
        (border_gdf.to_crs(DST_CRS) if border_gdf.crs != DST_CRS else border_gdf).boundary.plot(
            ax=ax, linewidth=border_lw, edgecolor='black', zorder=3)
        _draw_overlays(ax, overlay_layers)
        ax.set_axis_off()

        # 子图标题
        if panel_titles and i < len(panel_titles):
            ax.set_title(panel_titles[i], fontsize=title_size, pad=title_pad, loc='center')

        # —— 分图色带 ——
        if not use_shared_cbar:
            # fraction 参数解析
            if isinstance(per_cbar_size, str) and per_cbar_size.endswith('%'):
                try:
                    frac = float(per_cbar_size.strip('%'))/100.0
                except Exception:
                    frac = 0.08
            elif isinstance(per_cbar_size, (int, float)):
                frac = float(per_cbar_size)
            else:
                frac = 0.08

            cbar = fig.colorbar(im, ax=ax, location=per_cbar_loc, fraction=frac, pad=per_cbar_pad)
            Nt = int(per_cbar_ticks) if per_cbar_ticks else 6
            tks = _np.linspace(vmin_i, vmax_i, Nt)
            tks[0], tks[-1] = vmin_i, vmax_i
            cbar.set_ticks(tks)
            if per_cbar_label_text:
                cbar.set_label(per_cbar_label_text, fontsize=per_cbar_label_size)
            for t in cbar.ax.get_yticklabels():
                t.set_fontsize(per_cbar_tick_size)

        # 比例尺 + 北箭
        draw_scale_bar_axes(ax, ext,
                            km_length=scale_length, segments=scale_segments,
                            bar_h=scale_bar_h, y_out=scale_pad_y, x_in=scale_pad_x,
                            unit=scale_unit, unit_sep=scale_unit_sep,
                            txt_size=scale_txt_size, edge_lw=scale_edge_lw, line_lw=scale_line_lw)
        draw_north(ax, ext, size_frac=north_size_frac, pad_frac=max(north_pad_x, north_pad_y),
                   txt_size=north_txt_size)

    # —— 共享色带（放在最后统一添加） ——
    if use_shared_cbar:
        cbar = fig.colorbar(shared_mappable, ax=axes, location=shared_cbar_loc,
                            fraction=shared_cbar_frac, pad=0.02)
        N = int(shared_cbar_ticks) if shared_cbar_ticks else 6
        ticks = _np.linspace(global_vmin, global_vmax, N)
        ticks[0], ticks[-1] = global_vmin, global_vmax
        cbar.set_ticks(ticks)
        if shared_cbar_label_text:
            cbar.set_label(shared_cbar_label_text, fontsize=shared_cbar_label_size)
        for t in cbar.ax.get_yticklabels():
            t.set_fontsize(shared_cbar_tick_size)

    if caption:
        fig.text(0.5, caption_y, caption, ha='center', va='bottom', fontsize=caption_size)

    if preview:
        _nonblocking_preview(fig)  # 或者直接内联 try…manager.show…flush_events
        return

    if save_png:
        fig.savefig(save_png, dpi=dpi, bbox_inches="tight")
    if save_pdf:
        fig.savefig(save_pdf, dpi=dpi, bbox_inches="tight")
    plt.close(fig)



# ---------- 叠加矢量 ----------
def _draw_overlays(ax, overlay_specs):
    if not overlay_specs:
        return
    for spec in overlay_specs:
        p   = spec['path']
        col = spec.get('color', '#1f77b4')
        lw  = float(spec.get('lw', 0.8))
        mode = spec.get('mode', 'auto').lower()
        ms  = float(spec.get('ms', 6))
        try:
            g = _read_gdf_any(p)
        except Exception as e2:
            print(f"[overlay] 读取失败：{p} -> {e2}")
            continue
        if g.crs is None:
            print(f"[overlay] 缺少CRS：{p}（跳过）")
            continue
        g = g.to_crs(DST_CRS)
        if mode == 'auto':
            geom_types = set(g.geometry.geom_type)
            if any('LineString' in t for t in geom_types):
                mode = 'line'
            elif any('Polygon' in t for t in geom_types):
                mode = 'boundary'
            elif any('Point' in t for t in geom_types):
                mode = 'point'
            else:
                mode = 'boundary'
        if mode == 'line':
            g.plot(ax=ax, color=col, linewidth=lw, zorder=4)
        elif mode == 'fill':
            g.plot(ax=ax, facecolor='none', edgecolor=col, linewidth=lw, zorder=4)
        elif mode == 'point':
            g.plot(ax=ax, color=col, markersize=ms, zorder=5)
        else:
            g.boundary.plot(ax=ax, edgecolor=col, linewidth=lw, zorder=4)


# ---------- 安全保存 ----------
def _safe_save(fig, path, dpi=None, tight=False, pad=0.02):
    """安全保存：默认不裁剪（避免左右不对称）；需要时手动 tight=True。"""
    if not path:
        return
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kw = {}
    if dpi is not None:
        kw["dpi"] = dpi
    if tight:
        kw["bbox_inches"] = "tight"
        kw["pad_inches"] = pad
    fig.savefig(path, **kw)



# ================= 别名&过滤 =================
def _filter_kwargs(func, kwargs):
    sig = inspect.signature(func)
    allow = set(p.name for p in sig.parameters.values())
    return {k: v for k, v in kwargs.items() if k in allow}

def _alias_kwargs_for_multi(kwargs):
    # 基本
    if "tif_paths" in kwargs and "tif_list" not in kwargs:
        kwargs["tif_list"] = kwargs.pop("tif_paths")
    for ck in ("cmap","cmap_name","colormap","color_map","cmap_selected"):
        if ck in kwargs and "cmap_key" not in kwargs:
            kwargs["cmap_key"] = kwargs.pop(ck); break
    for tk in ("title_list","titles_list","subplot_titles","sub_titles","new_titles","title_override","panel_titles"):
        if tk in kwargs and "panel_titles" not in kwargs:
            kwargs["panel_titles"] = kwargs.pop(tk); break
    for k in ("share_cmap","share_colorbar","share_color","use_shared","use_shared_cbar"):
        if k in kwargs and "use_shared_cbar" not in kwargs:
            kwargs["use_shared_cbar"] = kwargs.pop(k); break
    if "cols" in kwargs and "ncols" not in kwargs:
        kwargs["ncols"] = kwargs.pop("cols")
    if "tick_num" in kwargs and "shared_cbar_ticks" not in kwargs:
        kwargs["shared_cbar_ticks"] = kwargs.pop("tick_num")
    if "scale_text_size" in kwargs and "scale_txt_size" not in kwargs:
        kwargs["scale_txt_size"] = kwargs.pop("scale_text_size")
    # 兼容旧参数：scale_km -> scale_length
    if "scale_km" in kwargs and "scale_length" not in kwargs:
        kwargs["scale_length"] = kwargs.pop("scale_km")

    if "per_vmax_pct" in kwargs and "per_vmax_percentile" not in kwargs:
        kwargs["per_vmax_percentile"] = kwargs.pop("per_vmax_pct")

    # 分图色带：刻度数量 & 上限百分位（决定显示的最大值）
    for k_old in ("sub_tick_num","per_tick_num","per_cbar_ticks","sub_ticks"):
        if k_old in kwargs and "per_cbar_ticks" not in kwargs:
            kwargs["per_cbar_ticks"] = kwargs.pop(k_old)
            break
    for k_old in ("sub_upper_pct","split_upper_pct","per_upper_pct","vmax_percentile","per_vmax_percentile"):
        if k_old in kwargs and "per_vmax_percentile" not in kwargs:
            kwargs["per_vmax_percentile"] = kwargs.pop(k_old)
            break
    # 颜色条控制别名
    if "shared_loc" in kwargs and "shared_cbar_loc" not in kwargs:
        kwargs["shared_cbar_loc"] = kwargs.pop("shared_loc")
    mapping = [
        ("shared_label_text","shared_cbar_label_text"),
        ("shared_label_size","shared_cbar_label_size"),
        ("shared_tick_size","shared_cbar_tick_size"),
        ("sub_loc","per_cbar_loc"),
        ("sub_pad","per_cbar_pad"),
        ("sub_label_text","per_cbar_label_text"),
        ("sub_label_size","per_cbar_label_size"),
        ("sub_tick_size","per_cbar_tick_size"),
    ]
    for old, new in mapping:
        if old in kwargs and new not in kwargs:
            kwargs[new] = kwargs.pop(old)

    # 丢弃与绘图无关的控件
    drop_keys = {
        "month_start","month_end","season_mode","season","season_list","stat_mode",
        "mask_shp","inside_mask","outside_mask","proj","crs","resample","clip",
        "layer_styles","vector_color","vector_lw","north_style2","scale_pos","scale_anchor",
        "save_svg","save_jpg","save_tif","dpi_preview","dpi_export","debug","verbose"
    }
    for k in list(kwargs.keys()):
        if k in drop_keys:
            kwargs.pop(k, None)
    return kwargs

def _alias_kwargs_for_single(kwargs):
    for ck in ("cmap","cmap_name","colormap","color_map","cmap_selected"):
        if ck in kwargs and "cmap_key" not in kwargs:
            kwargs["cmap_key"] = kwargs.pop(ck); break
    if "scale_text_size" in kwargs and "scale_txt_size" not in kwargs:
        kwargs["scale_txt_size"] = kwargs.pop("scale_text_size")
    return kwargs

# ================= 兼容导出 =================
def make_single_map(*args, **kwargs):
    kwargs = _alias_kwargs_for_single(dict(kwargs))
    kwargs = _filter_kwargs(_make_single_map_impl, kwargs)
    return _make_single_map_impl(*args, **kwargs)

# === 覆盖原来的 make_grid_map ===
def make_grid_map(
    tif_list, border_shp, overlay_layers,
    year_start, year_end, as_yearly,
    font_en="Arial", font_zh="Source Han Sans SC",
    nrows=2, ncols=2, panel_titles=None,
    caption=None, caption_size=14, caption_y=0.04,
    title_size=12, title_pad=6,

    border_lw=0.8,
    cmap_key="YlOrRd",
    panel_cmaps=None,
    share_vmax=None,

    use_shared_cbar=True,
    shared_cbar_loc="right", shared_cbar_frac=0.08,
    shared_cbar_label_text=None,
    shared_cbar_label_size=14, shared_cbar_tick_size=12,
    shared_cbar_ticks=6,

    per_cbar_loc="right", per_cbar_size="8%",
    per_cbar_pad=0.02, per_cbar_label_text=None,
    per_cbar_label_size=12, per_cbar_tick_size=10,
    per_cbar_ticks=6,
    per_use_auto_vmax=True, per_vmax_percentile=None,

    # 比例尺（所有子图同配）
    scale_length=None, scale_unit="km", scale_unit_sep=" ",
    scale_segments=4, scale_bar_h=0.008,
    scale_edge_lw=0.8, scale_line_lw=0.8, scale_txt_size=9,
    scale_anchor="SW", scale_pad_x=0.10, scale_pad_y=0.10,

    # 北箭（所有子图同配）
    north_style="triangle", north_size_frac=0.06,
    north_anchor="NE", north_pad_x=0.10, north_pad_y=0.10,
    north_txt_size=11,

    wspace=0.3, hspace=0.3,
    fig_w=12, fig_h=8, dpi=130,
    preview=True, save_png=None, save_pdf=None
):
    """
    多图接口：这里不再依赖全局 rcParams，而是把字体对象显式传下去。
    """
    _apply_fonts(font_en, font_zh)  # <<< 关键：应用 GUI 选择字体到 rcParams
    fp_en, fp_zh = _font_props(font_en, font_zh)
    return _make_grid_map_impl(
        tif_list=tif_list, border_shp=border_shp, overlay_layers=overlay_layers,
        year_start=year_start, year_end=year_end, as_yearly=as_yearly,
        fp_en=fp_en, fp_zh=fp_zh,
        nrows=nrows, ncols=ncols, panel_titles=panel_titles,
        caption=caption, caption_size=caption_size, caption_y=caption_y,
        title_size=title_size, title_pad=title_pad,

        border_lw=border_lw,
        cmap_key=cmap_key,
        panel_cmaps=panel_cmaps,
        share_vmax=share_vmax,

        use_shared_cbar=use_shared_cbar,
        shared_cbar_loc=shared_cbar_loc, shared_cbar_frac=shared_cbar_frac,
        shared_cbar_label_text=shared_cbar_label_text,
        shared_cbar_label_size=shared_cbar_label_size,
        shared_cbar_tick_size=shared_cbar_tick_size,
        shared_cbar_ticks=shared_cbar_ticks,

        per_cbar_loc=per_cbar_loc, per_cbar_size=per_cbar_size,
        per_cbar_pad=per_cbar_pad, per_cbar_label_text=per_cbar_label_text,
        per_cbar_label_size=per_cbar_label_size,
        per_cbar_tick_size=per_cbar_tick_size,
        per_cbar_ticks=per_cbar_ticks,
        per_use_auto_vmax=per_use_auto_vmax,
        per_vmax_percentile=per_vmax_percentile,

        scale_length=scale_length, scale_unit=scale_unit,
        scale_unit_sep=scale_unit_sep, scale_segments=scale_segments,
        scale_bar_h=scale_bar_h, scale_edge_lw=scale_edge_lw,
        scale_line_lw=scale_line_lw, scale_txt_size=scale_txt_size,
        scale_anchor=scale_anchor, scale_pad_x=scale_pad_x, scale_pad_y=scale_pad_y,

        north_style=north_style, north_size_frac=north_size_frac,
        north_anchor=north_anchor, north_pad_x=north_pad_x, north_pad_y=north_pad_y,
        north_txt_size=north_txt_size,

        wspace=wspace, hspace=hspace,
        fig_w=fig_w, fig_h=fig_h, dpi=dpi,
        preview=preview, save_png=save_png, save_pdf=save_pdf
    )


def plot_single(*args, **kwargs):
    return make_single_map(*args, **kwargs)

def plot_multi(*args, **kwargs):
    return make_grid_map(*args, **kwargs)

__all__ = ["make_single_map","make_grid_map","plot_single","plot_multi",
           "draw_scale_bar_axes","draw_north","resolve_cmap"]
