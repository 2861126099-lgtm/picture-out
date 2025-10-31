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
            # 确保窗口可以自由调整大小
            try:
                if hasattr(fig.canvas.manager, "window"):
                    fig.canvas.manager.window.resizable(True, True)
            except Exception:
                pass
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


def auto_layout_spacing(nrows, ncols, use_shared_cbar=False, shared_cbar_loc="right"):
    """
    根据行列数自动计算合适的wspace和hspace，减少留白

    参数:
        nrows: 行数
        ncols: 列数
        use_shared_cbar: 是否使用共享色带
        shared_cbar_loc: 共享色带位置

    返回:
        (wspace, hspace) 元组
    """
    # 基础间距
    base_wspace = 0.05
    base_hspace = 0.15

    # 根据列数调整横向间距：列数越多，间距越小
    if ncols >= 4:
        wspace = 0.02
    elif ncols == 3:
        wspace = 0.05
    elif ncols == 2:
        wspace = 0.08
    else:
        wspace = 0.12

    # 根据行数调整纵向间距：行数越多，间距越小
    if nrows >= 3:
        hspace = 0.12
    elif nrows == 2:
        hspace = 0.18
    else:
        hspace = 0.22

    # 如果使用共享色带且在右侧，稍微增加横向间距以避免拥挤
    if use_shared_cbar and shared_cbar_loc in ["right", "left"]:
        wspace = max(wspace, 0.05)

    return wspace, hspace


def optimize_layout(nrows, ncols, use_shared_cbar=False, shared_cbar_loc="right",
                   use_shared_scale=False, dpi=150):
    """
    根据行列数优化整体布局，计算最优的图片尺寸、间距和元素位置

    核心思想：
    1. 每个子图保持合理的宽高比（约1.2:1，适合中国地图）
    2. 根据行列数计算总图尺寸，让子图尽可能大
    3. 为色带、标题、比例尺等元素预留空间
    4. 减少留白，让图片铺满

    参数:
        nrows: 行数
        ncols: 列数
        use_shared_cbar: 是否使用共享色带
        shared_cbar_loc: 共享色带位置 (right/left/top/bottom)
        use_shared_scale: 是否使用共享比例尺
        dpi: DPI设置

    返回:
        dict: {
            'fig_width': 图片宽度(英寸),
            'fig_height': 图片高度(英寸),
            'wspace': 子图横向间距,
            'hspace': 子图纵向间距,
            'scale_bar_params': 比例尺参数建议,
            'preview_width': 预览宽度建议,
            'preview_height': 预览高度建议
        }
    """
    # 单个子图的基准尺寸（英寸）
    # 这个尺寸保证了每个子图有足够的显示空间
    base_subplot_width = 3.5  # 每个子图基准宽度
    base_subplot_height = 3.0  # 每个子图基准高度

    # 根据列数调整子图宽度（列数多时，每个子图可以稍小）
    if ncols >= 4:
        subplot_width = 3.2
        wspace = 0.02
    elif ncols == 3:
        subplot_width = 3.5
        wspace = 0.05
    elif ncols == 2:
        subplot_width = 4.0
        wspace = 0.08
    else:
        subplot_width = 5.0
        wspace = 0.12

    # 根据行数调整子图高度和间距
    if nrows >= 3:
        subplot_height = 2.8
        hspace = 0.15
    elif nrows == 2:
        subplot_height = 3.0
        hspace = 0.20
    else:
        subplot_height = 3.5
        hspace = 0.25

    # 计算子图区域总尺寸
    # GridSpec的wspace和hspace是相对于子图宽度/高度的比例
    # 总宽度 = ncols * subplot_width * (1 + wspace * (ncols-1) / ncols)
    subplot_area_width = ncols * subplot_width * (1 + wspace * (ncols - 1) / ncols)
    subplot_area_height = nrows * subplot_height * (1 + hspace * (nrows - 1) / nrows)

    # 为边距和元素预留空间
    left_margin = 0.5
    right_margin = 0.5
    top_margin = 0.8  # 为标题预留
    bottom_margin = 1.0  # 为说明文字和色带预留

    # 如果使用共享色带，根据位置调整边距
    if use_shared_cbar:
        if shared_cbar_loc == "right":
            right_margin = 1.2  # 为右侧色带预留更多空间
        elif shared_cbar_loc == "left":
            left_margin = 1.2
        elif shared_cbar_loc == "bottom":
            bottom_margin = 1.5  # 为底部色带预留更多空间
        elif shared_cbar_loc == "top":
            top_margin = 1.2

    # 计算总图尺寸
    fig_width = subplot_area_width + left_margin + right_margin
    fig_height = subplot_area_height + top_margin + bottom_margin

    # 计算预览尺寸（像素）
    # 使用实际DPI来计算，确保预览清晰
    # 提升预览质量，使用更高的DPI
    preview_width = int(fig_width * dpi)  # 使用完整DPI，不缩小
    preview_height = int(fig_height * dpi)

    # 比例尺参数建议
    scale_bar_params = {
        'y_out': 0.10 if nrows == 1 else 0.08,  # 单行时比例尺离图远一点
        'txt_size': 9 if ncols <= 3 else 8,  # 列数多时字号小一点
    }

    return {
        'fig_width': round(fig_width, 2),
        'fig_height': round(fig_height, 2),
        'wspace': round(wspace, 3),
        'hspace': round(hspace, 3),
        'scale_bar_params': scale_bar_params,
        'preview_width': preview_width,
        'preview_height': preview_height,
    }

def draw_scale_bar_axes(ax, extent, *, km_length=None, segments=4, bar_h=0.012,
                        y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                        txt_size=9, edge_lw=0.6, line_lw=0.7):
    """
    绘制分段式比例尺（黑白相间）
    格式：0      50      100 km
          ■□■□
    - 经典样式
    - 数字和单位清晰分离
    """
    left, right, bottom, top = extent
    width_m = right - left
    if km_length is None or km_length <= 0:
        km_length = nice_length_km(width_m)
    length_m = km_length * 1000.0
    frac_w = length_m / width_m

    x0 = x_in
    y0 = -y_out

    # 调整字体大小，避免过大
    actual_txt_size = min(txt_size, 9)

    # 绘制分段矩形
    seg_w = frac_w / max(1, segments)
    for i in range(max(1, segments)):
        rect = Rectangle((x0 + i*seg_w, y0), seg_w, bar_h,
                         transform=ax.transAxes,
                         facecolor=('black' if i % 2 == 0 else 'white'),
                         edgecolor='black', linewidth=edge_lw, clip_on=False, zorder=3)
        ax.add_patch(rect)

    # 顶部边线
    ax.plot([x0, x0+frac_w], [y0+bar_h, y0+bar_h], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)

    # 标注 - 左侧显示0
    ax.text(x0, y0-0.008, "0", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)

    # 标注 - 中间显示一半（只显示数字，不显示单位）
    half = (km_length//2 if km_length % 2 == 0 else round(km_length/2))
    ax.text(x0 + frac_w/2, y0-0.008, f"{half}", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)

    # 标注 - 右侧显示总长度和单位（分开显示）
    ax.text(x0 + frac_w, y0-0.008, f"{km_length}{unit_sep}{unit}", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)



def draw_scale_bar_line(ax, extent, *, km_length=None, bar_h=0.003,
                        y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                        txt_size=9, line_lw=1.5, tick_lw=0.8):
    """
    绘制简洁的线段式比例尺
    格式：0        60 km
          └────────┘
    - 符合学术规范
    - 数字和单位分开显示，清晰易读
    """
    left, right, bottom, top = extent
    width_m = right - left
    if km_length is None or km_length <= 0:
        km_length = nice_length_km(width_m)
    length_m = km_length * 1000.0
    frac_w = length_m / width_m

    x0 = x_in
    y0 = -y_out

    # 调整字体大小，避免过大
    actual_txt_size = min(txt_size, 9)

    # 主横线
    ax.plot([x0, x0+frac_w], [y0, y0], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3, solid_capstyle='butt')

    # 左端刻度线
    tick_h = bar_h * 2
    ax.plot([x0, x0], [y0, y0-tick_h], transform=ax.transAxes,
            color='black', lw=tick_lw, clip_on=False, zorder=3)

    # 右端刻度线
    ax.plot([x0+frac_w, x0+frac_w], [y0, y0-tick_h], transform=ax.transAxes,
            color='black', lw=tick_lw, clip_on=False, zorder=3)

    # 标注 - 左侧显示0
    ax.text(x0, y0-tick_h-0.008, "0", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)

    # 标注 - 右侧显示数值和单位（分开显示，避免混在一起）
    # 数值在左，单位在右，中间有空格
    label_text = f"{km_length}{unit_sep}{unit}"
    ax.text(x0 + frac_w, y0-tick_h-0.008, label_text, transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)


def draw_scale_bar_ruler(ax, extent, *, km_length=None, bar_h=0.008,
                         y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                         txt_size=9, line_lw=1.2, tick_lw=0.8, num_ticks=5):
    """
    绘制学术论文标准标尺式比例尺
    格式：0    50    100    150    200 km
          |     |     |      |      |
          ─────────────────────────────
    - 符合学术规范
    - 数字和单位清晰分离
    """
    left, right, bottom, top = extent
    width_m = right - left
    if km_length is None or km_length <= 0:
        km_length = nice_length_km(width_m)
    length_m = km_length * 1000.0
    frac_w = length_m / width_m

    x0 = x_in
    y0 = -y_out

    # 调整字体大小，避免过大
    actual_txt_size = min(txt_size, 9)

    # 主横线
    ax.plot([x0, x0+frac_w], [y0, y0], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3, solid_capstyle='butt')

    # 绘制刻度和标注
    tick_height = bar_h * 1.2
    for i in range(num_ticks):
        frac = i / (num_ticks - 1) if num_ticks > 1 else 0
        x_tick = x0 + frac * frac_w
        value = int(km_length * frac)

        # 刻度线（向下延伸）
        ax.plot([x_tick, x_tick], [y0, y0-tick_height], transform=ax.transAxes,
                color='black', lw=tick_lw, clip_on=False, zorder=3)

        # 刻度标注（在刻度线下方）
        if i == num_ticks - 1:
            # 最后一个刻度：显示总长度和单位（分开显示）
            label = f"{value}{unit_sep}{unit}"
        else:
            # 其他刻度：只显示数字
            label = f"{value}"

        ax.text(x_tick, y0-tick_height-0.006, label, transform=ax.transAxes,
                ha='center', va='top', fontsize=actual_txt_size,
                fontweight='normal', clip_on=False, zorder=3)


def draw_scale_bar_double(ax, extent, *, km_length=None, bar_h=0.010,
                          y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                          txt_size=9, line_lw=1.2, segments=4):
    """
    绘制双线式比例尺
    格式：━━━━━━━━━━━━
          ━━━━━━━━━━━━
          0           100 km
    - 双线设计，更醒目
    - 适合高级论文
    """
    left, right, bottom, top = extent
    width_m = right - left
    if km_length is None or km_length <= 0:
        km_length = nice_length_km(width_m)
    length_m = km_length * 1000.0
    frac_w = length_m / width_m

    x0 = x_in
    y0 = -y_out

    # 调整字体大小
    actual_txt_size = min(txt_size, 9)

    # 上横线
    ax.plot([x0, x0+frac_w], [y0+bar_h, y0+bar_h], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3, solid_capstyle='butt')

    # 下横线
    ax.plot([x0, x0+frac_w], [y0, y0], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3, solid_capstyle='butt')

    # 左端竖线
    ax.plot([x0, x0], [y0, y0+bar_h], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)

    # 右端竖线
    ax.plot([x0+frac_w, x0+frac_w], [y0, y0+bar_h], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)

    # 中间分段线
    seg_w = frac_w / max(1, segments)
    for i in range(1, segments):
        x_seg = x0 + i * seg_w
        ax.plot([x_seg, x_seg], [y0, y0+bar_h], transform=ax.transAxes,
                color='black', lw=line_lw*0.7, clip_on=False, zorder=3)

    # 标注
    ax.text(x0, y0-0.008, "0", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)

    ax.text(x0+frac_w, y0-0.008, f"{km_length}{unit_sep}{unit}", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)


def draw_scale_bar_minimal(ax, extent, *, km_length=None, bar_h=0.003,
                           y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                           txt_size=9, line_lw=2.0):
    """
    绘制极简式比例尺
    格式：━━━━━━━━━━
          100 km
    - 只有一条粗线和标注
    - 最简洁的样式
    """
    left, right, bottom, top = extent
    width_m = right - left
    if km_length is None or km_length <= 0:
        km_length = nice_length_km(width_m)
    length_m = km_length * 1000.0
    frac_w = length_m / width_m

    x0 = x_in
    y0 = -y_out

    # 调整字体大小
    actual_txt_size = min(txt_size, 9)

    # 粗横线
    ax.plot([x0, x0+frac_w], [y0, y0], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3, solid_capstyle='butt')

    # 标注（居中显示）
    ax.text(x0+frac_w/2, y0-0.008, f"{km_length}{unit_sep}{unit}", transform=ax.transAxes,
            ha='center', va='top', fontsize=actual_txt_size,
            fontweight='normal', clip_on=False, zorder=3)


def draw_north(ax, extent, *, size_frac=0.06, pad_frac=0.08, txt_size=10, face='black', edge='black', lw=1.2):
    """绘制三角形北箭（传统样式）"""
    left, right, bottom, top = extent
    x = right  - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac
    w = h * 0.45
    tri = Polygon([[x, y+h], [x-w, y], [x+w, y]], closed=True, facecolor=face, edgecolor=edge, lw=lw)
    ax.add_patch(tri)
    ax.text(x, y+h + (top-bottom)*0.01, 'N', ha='center', va='bottom',
            fontsize=txt_size, fontweight='bold')


def draw_north_arrow(ax, extent, *, size_frac=0.06, pad_frac=0.08, txt_size=10, lw=1.5):
    """
    绘制学术论文标准北箭样式（简洁箭头）
    - 简洁的箭头 + 字母N
    - 符合学术规范，类似参考图片
    """
    left, right, bottom, top = extent
    x = right - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac
    w = h * 0.25  # 更窄的箭头

    # 箭杆（细长的矩形）
    shaft_width = w * 0.2
    shaft = Rectangle((x-shaft_width/2, y), shaft_width, h*0.65,
                     transform=ax.transData, facecolor='black', edgecolor='none',
                     clip_on=False, zorder=3)
    ax.add_patch(shaft)

    # 箭头头部（三角形）
    arrow_head = Polygon([[x, y+h], [x-w/2, y+h*0.6], [x+w/2, y+h*0.6]],
                         closed=True, facecolor='black', edgecolor='none',
                         clip_on=False, zorder=3)
    ax.add_patch(arrow_head)

    # 字母N（在箭头下方）
    ax.text(x, y - (top-bottom)*0.01, 'N', ha='center', va='top',
            fontsize=txt_size, fontweight='bold', family='serif',
            clip_on=False, zorder=3)


def draw_north_compass(ax, extent, *, size_frac=0.06, pad_frac=0.08, txt_size=10, lw=1.2):
    """
    绘制指南针式北箭
    - 带圆圈的指南针样式
    - 专业地图常用样式
    """
    from matplotlib.patches import Circle, FancyArrowPatch
    from matplotlib.patches import Arc

    left, right, bottom, top = extent
    x = right - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac
    r = h * 0.4  # 圆圈半径

    # 外圆
    circle = Circle((x, y + h/2), r, fill=False, edgecolor='black',
                   linewidth=lw, transform=ax.transData, clip_on=False, zorder=3)
    ax.add_patch(circle)

    # 北箭（指向上方）
    arrow_len = r * 0.7
    arrow = FancyArrowPatch((x, y + h/2 - arrow_len*0.3),
                           (x, y + h/2 + arrow_len*0.7),
                           arrowstyle='->', mutation_scale=15,
                           linewidth=lw*1.2, color='black',
                           transform=ax.transData, clip_on=False, zorder=4)
    ax.add_patch(arrow)

    # 字母N（在圆圈上方）
    ax.text(x, y + h/2 + r + (top-bottom)*0.015, 'N',
            ha='center', va='bottom',
            fontsize=txt_size, fontweight='bold', family='serif',
            clip_on=False, zorder=3)


def draw_north_star(ax, extent, *, size_frac=0.06, pad_frac=0.08, txt_size=10, lw=1.0):
    """
    绘制星形北箭
    - 四角星形样式
    - 高级论文常用
    """
    import numpy as np

    left, right, bottom, top = extent
    x = right - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac

    # 绘制四角星（主要突出北方）
    # 北方箭头（最长）
    north_len = h * 0.8
    north_arrow = Polygon([[x, y+north_len],
                          [x-h*0.15, y+north_len*0.5],
                          [x, y+north_len*0.6],
                          [x+h*0.15, y+north_len*0.5]],
                         closed=True, facecolor='black', edgecolor='black',
                         linewidth=lw, clip_on=False, zorder=3)
    ax.add_patch(north_arrow)

    # 南方箭头（较短）
    south_len = h * 0.4
    south_arrow = Polygon([[x, y-south_len*0.2],
                          [x-h*0.1, y+south_len*0.3],
                          [x, y+south_len*0.2],
                          [x+h*0.1, y+south_len*0.3]],
                         closed=True, facecolor='white', edgecolor='black',
                         linewidth=lw, clip_on=False, zorder=3)
    ax.add_patch(south_arrow)

    # 东西箭头（更短）
    ew_len = h * 0.3
    # 东
    east_arrow = Polygon([[x+ew_len, y+h*0.3],
                         [x+ew_len*0.4, y+h*0.3-ew_len*0.15],
                         [x+ew_len*0.5, y+h*0.3],
                         [x+ew_len*0.4, y+h*0.3+ew_len*0.15]],
                        closed=True, facecolor='white', edgecolor='black',
                        linewidth=lw*0.8, clip_on=False, zorder=3)
    ax.add_patch(east_arrow)

    # 西
    west_arrow = Polygon([[x-ew_len, y+h*0.3],
                         [x-ew_len*0.4, y+h*0.3-ew_len*0.15],
                         [x-ew_len*0.5, y+h*0.3],
                         [x-ew_len*0.4, y+h*0.3+ew_len*0.15]],
                        closed=True, facecolor='white', edgecolor='black',
                        linewidth=lw*0.8, clip_on=False, zorder=3)
    ax.add_patch(west_arrow)

    # 字母N
    ax.text(x, y+north_len + (top-bottom)*0.01, 'N',
            ha='center', va='bottom',
            fontsize=txt_size, fontweight='bold', family='serif',
            clip_on=False, zorder=3)


def draw_north_simple_arrow(ax, extent, *, size_frac=0.06, pad_frac=0.08, txt_size=10, lw=1.5):
    """
    绘制极简箭头式北箭
    - 只有一个简单的箭头和N
    - 最简洁的样式
    """
    from matplotlib.patches import FancyArrowPatch

    left, right, bottom, top = extent
    x = right - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac

    # 简单箭头
    arrow = FancyArrowPatch((x, y), (x, y+h),
                           arrowstyle='->', mutation_scale=20,
                           linewidth=lw*1.5, color='black',
                           transform=ax.transData, clip_on=False, zorder=3)
    ax.add_patch(arrow)

    # 字母N
    ax.text(x, y+h + (top-bottom)*0.01, 'N',
            ha='center', va='bottom',
            fontsize=txt_size, fontweight='bold', family='serif',
            clip_on=False, zorder=3)


# 辅助函数：根据样式绘制比例尺
def _draw_scale_bar(ax, extent, style, km_length, segments, bar_h, y_out, x_in,
                    unit, unit_sep, txt_size, line_lw, edge_lw):
    """根据样式选择合适的比例尺绘制函数（支持自定义样式）"""
    # 先检查是否是自定义样式
    try:
        import custom_styles
        custom_func = custom_styles.get_custom_scale_bar_function(style)
        if custom_func:
            custom_func(ax, extent, km_length=km_length, segments=segments,
                       bar_h=bar_h, y_out=y_out, x_in=x_in,
                       unit=unit, unit_sep=unit_sep,
                       txt_size=txt_size, line_lw=line_lw, edge_lw=edge_lw)
            return
    except:
        pass

    # 内置样式
    if style == "线段式":
        draw_scale_bar_line(ax, extent,
                           km_length=km_length,
                           bar_h=bar_h, y_out=y_out, x_in=x_in,
                           unit=unit, unit_sep=unit_sep,
                           txt_size=txt_size, line_lw=line_lw, tick_lw=edge_lw)
    elif style == "标尺式":
        draw_scale_bar_ruler(ax, extent,
                            km_length=km_length,
                            bar_h=bar_h, y_out=y_out, x_in=x_in,
                            unit=unit, unit_sep=unit_sep,
                            txt_size=txt_size, line_lw=line_lw, tick_lw=edge_lw)
    elif style == "双线式":
        draw_scale_bar_double(ax, extent,
                             km_length=km_length, segments=segments,
                             bar_h=bar_h, y_out=y_out, x_in=x_in,
                             unit=unit, unit_sep=unit_sep,
                             txt_size=txt_size, line_lw=line_lw)
    elif style == "极简式":
        draw_scale_bar_minimal(ax, extent,
                              km_length=km_length,
                              bar_h=bar_h, y_out=y_out, x_in=x_in,
                              unit=unit, unit_sep=unit_sep,
                              txt_size=txt_size, line_lw=line_lw)
    else:  # 默认"分段式"
        draw_scale_bar_axes(ax, extent,
                           km_length=km_length, segments=segments,
                           bar_h=bar_h, y_out=y_out, x_in=x_in,
                           unit=unit, unit_sep=unit_sep,
                           txt_size=txt_size, edge_lw=edge_lw, line_lw=line_lw)


# 辅助函数：根据样式绘制北箭
def _draw_north_arrow(ax, extent, style, size_frac, pad_x, pad_y, txt_size):
    """根据样式选择合适的北箭绘制函数（支持自定义样式）"""
    # 先检查是否是自定义样式
    try:
        import custom_styles
        custom_func = custom_styles.get_custom_north_arrow_function(style)
        if custom_func:
            pad_frac = max(pad_x, pad_y)
            custom_func(ax, extent, size_frac=size_frac, pad_frac=pad_frac, txt_size=txt_size)
            return
    except:
        pass

    # 内置样式
    pad_frac = max(pad_x, pad_y)
    if style == "箭头式" or style == "简洁箭头":
        draw_north_arrow(ax, extent, size_frac=size_frac, pad_frac=pad_frac, txt_size=txt_size)
    elif style == "指南针式":
        draw_north_compass(ax, extent, size_frac=size_frac, pad_frac=pad_frac, txt_size=txt_size)
    elif style == "星形":
        draw_north_star(ax, extent, size_frac=size_frac, pad_frac=pad_frac, txt_size=txt_size)
    elif style == "极简箭头":
        draw_north_simple_arrow(ax, extent, size_frac=size_frac, pad_frac=pad_frac, txt_size=txt_size)
    else:  # 默认"三角形"
        draw_north(ax, extent, size_frac=size_frac, pad_frac=pad_frac, txt_size=txt_size)


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
    cbar_fraction=0.15,  # 新增：色带宽度比例
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

    # 色带（添加宽度控制）
    orient = 'vertical' if cbar_loc in ('right', 'left') else 'horizontal'
    # 使用 fraction 参数控制色带宽度
    cbar = fig.colorbar(im, ax=ax, orientation=orient, fraction=cbar_fraction)
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
    shared_cbar_shrink,  # 色带长度占比（百分比）
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
    scale_style, use_shared_scale,

    north_style, north_size_frac,
    north_anchor, north_pad_x, north_pad_y, north_txt_size,
    use_shared_north,

    wspace, hspace, fig_w, fig_h, dpi,
    preview, save_png, save_pdf,

    # 新增：位置调整参数
    position_adjustments=None
):
    import numpy as _np
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    # 加载位置调整参数
    if position_adjustments is None:
        try:
            from interactive_preview import load_adjustments
            position_adjustments = load_adjustments()
        except:
            position_adjustments = {}

    # 提取调整参数
    cbar_offset_y = position_adjustments.get("cbar_offset_y", 0.0)
    cbar_offset_x = position_adjustments.get("cbar_offset_x", 0.0)
    scale_offset_x = position_adjustments.get("scale_offset_x", 0.0)
    scale_offset_y = position_adjustments.get("scale_offset_y", 0.0)
    north_offset_x = position_adjustments.get("north_offset_x", 0.0)
    north_offset_y = position_adjustments.get("north_offset_y", 0.0)

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

    # 画布 - 设置最大打开图形数量警告阈值
    import matplotlib
    matplotlib.rcParams['figure.max_open_warning'] = 50  # 提高警告阈值
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)

    # ========== 迭代优化的留白控制方案 ==========
    # 核心思路：根据实际元素需求精确计算边距（英寸），然后转换为相对比例

    # 基础边距（英寸）
    margin_left_inch = 0.1    # 左边距0.1英寸
    margin_right_inch = 0.1   # 右边距0.1英寸
    margin_top_inch = 0.2     # 上边距0.2英寸（为标题预留）
    margin_bottom_inch = 0.15 # 底部边距0.15英寸

    # 根据共享色带位置调整边距（为色带预留空间）
    if use_shared_cbar:
        if shared_cbar_loc == "right":
            margin_right_inch = fig_w * 0.15  # 右侧色带需要更多空间
        elif shared_cbar_loc == "left":
            margin_left_inch = fig_w * 0.15
        elif shared_cbar_loc == "bottom":
            margin_bottom_inch = fig_h * 0.15
        elif shared_cbar_loc == "top":
            margin_top_inch = fig_h * 0.12

    # 如果有说明文字，底部需要更多空间
    if caption:
        margin_bottom_inch = max(margin_bottom_inch, 0.5)

    # 转换为相对比例（0-1范围）
    gs_left = margin_left_inch / fig_w
    gs_right = 1.0 - (margin_right_inch / fig_w)
    gs_top = 1.0 - (margin_top_inch / fig_h)
    gs_bottom = margin_bottom_inch / fig_h

    # 确保边距在合理范围内
    gs_left = max(0.01, min(0.2, gs_left))
    gs_right = max(0.8, min(0.99, gs_right))
    gs_top = max(0.8, min(0.99, gs_top))
    gs_bottom = max(0.01, min(0.2, gs_bottom))

    gs = GridSpec(nrows, ncols, figure=fig,
                  left=gs_left, right=gs_right, top=gs_top, bottom=gs_bottom,
                  wspace=wspace, hspace=hspace)
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

        # 比例尺：如果使用共享比例尺，只在最后一个子图显示
        if use_shared_scale:
            # 只在最后一个子图（右下角）显示比例尺
            if i == len(tif_list) - 1:
                # 应用位置调整
                adjusted_scale_pad_x = scale_pad_x + scale_offset_x
                adjusted_scale_pad_y = scale_pad_y + scale_offset_y
                _draw_scale_bar(ax, ext, scale_style, scale_length, scale_segments,
                               scale_bar_h, adjusted_scale_pad_y, adjusted_scale_pad_x, scale_unit,
                               scale_unit_sep, scale_txt_size, scale_line_lw, scale_edge_lw)
        else:
            # 每个子图都显示比例尺
            adjusted_scale_pad_x = scale_pad_x + scale_offset_x
            adjusted_scale_pad_y = scale_pad_y + scale_offset_y
            _draw_scale_bar(ax, ext, scale_style, scale_length, scale_segments,
                           scale_bar_h, adjusted_scale_pad_y, adjusted_scale_pad_x, scale_unit,
                           scale_unit_sep, scale_txt_size, scale_line_lw, scale_edge_lw)

        # 北箭：如果使用共享北箭，只在最后一个子图显示
        if use_shared_north:
            # 只在最后一个子图（右上角）显示北箭
            if i == len(tif_list) - 1:
                # 应用位置调整
                adjusted_north_pad_x = north_pad_x + north_offset_x
                adjusted_north_pad_y = north_pad_y + north_offset_y
                _draw_north_arrow(ax, ext, north_style, north_size_frac,
                                 adjusted_north_pad_x, adjusted_north_pad_y, north_txt_size)
        else:
            # 每个子图都显示北箭
            adjusted_north_pad_x = north_pad_x + north_offset_x
            adjusted_north_pad_y = north_pad_y + north_offset_y
            _draw_north_arrow(ax, ext, north_style, north_size_frac,
                             adjusted_north_pad_x, adjusted_north_pad_y, north_txt_size)

    # —— 共享色带（放在最后统一添加） ——
    if use_shared_cbar:
        # 根据用户设置的百分比计算shrink值
        # shared_cbar_shrink: 30-100的百分比值
        shrink_value = float(shared_cbar_shrink) / 100.0 if shared_cbar_shrink else 0.80
        # 限制在合理范围内
        shrink_value = max(0.3, min(1.0, shrink_value))

        # 使用更可靠的方法：手动创建colorbar的axes
        from mpl_toolkits.axes_grid1 import make_axes_locatable

        if shared_cbar_loc in ['bottom', 'top']:
            # 底部/顶部色带：使用shrink参数控制长度
            # 计算居中位置
            if shared_cbar_loc == 'bottom':
                # 智能计算色带位置，避免与标题重叠
                # 色带应该放在GridSpec底部边距的中间位置
                cbar_height = 0.015  # 色带高度（相对于figure）

                # 计算色带底部位置：在gs_bottom范围内居中
                # 如果有caption，需要更多空间
                if caption:
                    # caption在最底部，色带在caption上方
                    cbar_bottom = gs_bottom * 0.6  # 色带在底部边距的60%位置
                else:
                    # 没有caption，色带在底部边距中间
                    cbar_bottom = (gs_bottom - cbar_height) / 2.0

                # 应用用户调整的偏移量
                cbar_bottom += cbar_offset_y

                # 确保色带不会太靠下
                cbar_bottom = max(0.01, cbar_bottom)

                left_margin = (1.0 - shrink_value) / 2.0  # 居中
                left_margin += cbar_offset_x  # 应用水平偏移
                cbar_ax = fig.add_axes([left_margin, cbar_bottom, shrink_value, cbar_height])
                cbar = fig.colorbar(shared_mappable, cax=cbar_ax, orientation='horizontal')

            elif shared_cbar_loc == 'top':
                # 顶部色带：在GridSpec顶部边距的中间位置
                cbar_height = 0.015
                cbar_top = gs_top + (1.0 - gs_top - cbar_height) / 2.0
                cbar_top = min(0.98, cbar_top)

                left_margin = (1.0 - shrink_value) / 2.0
                cbar_ax = fig.add_axes([left_margin, cbar_top, shrink_value, cbar_height])
                cbar = fig.colorbar(shared_mappable, cax=cbar_ax, orientation='horizontal')
            else:
                # 备用方案
                cbar = fig.colorbar(shared_mappable, ax=axes, location=shared_cbar_loc,
                                    fraction=shared_cbar_frac, pad=0.02, shrink=shrink_value)
        else:
            # 左侧/右侧色带：使用标准方法
            cbar = fig.colorbar(shared_mappable, ax=axes, location=shared_cbar_loc,
                                fraction=shared_cbar_frac, pad=0.02, shrink=shrink_value)

        N = int(shared_cbar_ticks) if shared_cbar_ticks else 6
        ticks = _np.linspace(global_vmin, global_vmax, N)
        ticks[0], ticks[-1] = global_vmin, global_vmax
        cbar.set_ticks(ticks)
        if shared_cbar_label_text:
            cbar.set_label(shared_cbar_label_text, fontsize=shared_cbar_label_size)

        # 设置刻度标签字体大小
        if shared_cbar_loc in ['bottom', 'top']:
            for t in cbar.ax.get_xticklabels():
                t.set_fontsize(shared_cbar_tick_size)
        else:
            for t in cbar.ax.get_yticklabels():
                t.set_fontsize(shared_cbar_tick_size)

    if caption:
        fig.text(0.5, caption_y, caption, ha='center', va='bottom', fontsize=caption_size)

    if preview:
        # 返回 figure 对象，供交互式预览使用
        # 不调用 _nonblocking_preview，避免显示matplotlib的普通窗口
        return fig

    # 使用 _safe_save 保存图片（修复PNG警告）
    _safe_save(fig, save_png, dpi=dpi, tight=True)
    _safe_save(fig, save_pdf, dpi=dpi, tight=True)
    plt.close(fig)
    return None



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

    # 修复PNG警告：禁用iCCP配置文件
    if path.lower().endswith('.png'):
        kw["pil_kwargs"] = {"optimize": True, "icc_profile": None}

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
    shared_cbar_shrink=75,  # 色带长度占比（百分比，30-100）
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
    scale_style="分段式", use_shared_scale=False,

    # 北箭（所有子图同配）
    north_style="triangle", north_size_frac=0.06,
    north_anchor="NE", north_pad_x=0.10, north_pad_y=0.10,
    north_txt_size=11,
    use_shared_north=False,

    wspace=0.3, hspace=0.3,
    fig_w=12, fig_h=8, dpi=150,  # 提升默认DPI从130到150
    preview=True, save_png=None, save_pdf=None,

    # 新增：位置调整参数
    position_adjustments=None
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
        shared_cbar_shrink=shared_cbar_shrink,
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
        scale_style=scale_style, use_shared_scale=use_shared_scale,

        north_style=north_style, north_size_frac=north_size_frac,
        north_anchor=north_anchor, north_pad_x=north_pad_x, north_pad_y=north_pad_y,
        north_txt_size=north_txt_size,
        use_shared_north=use_shared_north,

        wspace=wspace, hspace=hspace,
        fig_w=fig_w, fig_h=fig_h, dpi=dpi,
        preview=preview, save_png=save_png, save_pdf=save_pdf,
        position_adjustments=position_adjustments
    )


def plot_single(*args, **kwargs):
    return make_single_map(*args, **kwargs)

def plot_multi(*args, **kwargs):
    return make_grid_map(*args, **kwargs)

__all__ = ["make_single_map","make_grid_map","plot_single","plot_multi",
           "draw_scale_bar_axes","draw_scale_bar_line","draw_scale_bar_ruler",
           "draw_north","draw_north_arrow","resolve_cmap","optimize_layout"]
