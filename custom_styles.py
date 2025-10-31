"""
自定义样式管理模块
支持导入和管理自定义的北箭和比例尺样式
"""

import os
import json
from matplotlib.patches import Polygon, Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D

# 存储自定义样式的目录
CUSTOM_STYLES_DIR = "custom_styles"
SCALE_BAR_STYLES_FILE = os.path.join(CUSTOM_STYLES_DIR, "scale_bar_styles.json")
NORTH_ARROW_STYLES_FILE = os.path.join(CUSTOM_STYLES_DIR, "north_arrow_styles.json")

# 确保目录存在
os.makedirs(CUSTOM_STYLES_DIR, exist_ok=True)


def load_custom_scale_bar_styles():
    """加载自定义比例尺样式"""
    if os.path.exists(SCALE_BAR_STYLES_FILE):
        try:
            with open(SCALE_BAR_STYLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def load_custom_north_arrow_styles():
    """加载自定义北箭样式"""
    if os.path.exists(NORTH_ARROW_STYLES_FILE):
        try:
            with open(NORTH_ARROW_STYLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_custom_scale_bar_style(name, style_dict):
    """保存自定义比例尺样式"""
    styles = load_custom_scale_bar_styles()
    styles[name] = style_dict
    with open(SCALE_BAR_STYLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)


def save_custom_north_arrow_style(name, style_dict):
    """保存自定义北箭样式"""
    styles = load_custom_north_arrow_styles()
    styles[name] = style_dict
    with open(NORTH_ARROW_STYLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)


def get_all_scale_bar_style_names():
    """获取所有比例尺样式名称（内置+自定义）"""
    builtin = ["分段式", "线段式", "标尺式"]
    custom = list(load_custom_scale_bar_styles().keys())
    return builtin + custom


def get_all_north_arrow_style_names():
    """获取所有北箭样式名称（内置+自定义）"""
    builtin = ["三角形", "箭头式"]
    custom = list(load_custom_north_arrow_styles().keys())
    return builtin + custom


def import_scale_bar_style_from_python(file_path):
    """
    从Python文件导入比例尺样式
    
    Python文件应该定义一个函数：
    def draw_custom_scale_bar(ax, extent, **kwargs):
        # 绘制代码
        pass
    
    参数说明：
    - ax: matplotlib axes对象
    - extent: (left, right, bottom, top) 地图范围
    - kwargs: 其他参数（km_length, bar_h, y_out, x_in, unit等）
    """
    import importlib.util
    
    # 加载Python模块
    spec = importlib.util.spec_from_file_location("custom_style", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # 检查是否有draw_custom_scale_bar函数
    if not hasattr(module, 'draw_custom_scale_bar'):
        raise ValueError("Python文件必须定义 draw_custom_scale_bar(ax, extent, **kwargs) 函数")
    
    # 获取样式名称（从文件名）
    style_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # 保存函数引用
    return style_name, module.draw_custom_scale_bar


def import_north_arrow_style_from_python(file_path):
    """
    从Python文件导入北箭样式
    
    Python文件应该定义一个函数：
    def draw_custom_north_arrow(ax, extent, **kwargs):
        # 绘制代码
        pass
    
    参数说明：
    - ax: matplotlib axes对象
    - extent: (left, right, bottom, top) 地图范围
    - kwargs: 其他参数（size_frac, pad_frac, txt_size, lw等）
    """
    import importlib.util
    
    # 加载Python模块
    spec = importlib.util.spec_from_file_location("custom_style", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # 检查是否有draw_custom_north_arrow函数
    if not hasattr(module, 'draw_custom_north_arrow'):
        raise ValueError("Python文件必须定义 draw_custom_north_arrow(ax, extent, **kwargs) 函数")
    
    # 获取样式名称（从文件名）
    style_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # 保存函数引用
    return style_name, module.draw_custom_north_arrow


# 存储导入的自定义绘图函数
_custom_scale_bar_functions = {}
_custom_north_arrow_functions = {}


def register_custom_scale_bar_function(name, func):
    """注册自定义比例尺绘图函数"""
    _custom_scale_bar_functions[name] = func


def register_custom_north_arrow_function(name, func):
    """注册自定义北箭绘图函数"""
    _custom_north_arrow_functions[name] = func


def get_custom_scale_bar_function(name):
    """获取自定义比例尺绘图函数"""
    return _custom_scale_bar_functions.get(name)


def get_custom_north_arrow_function(name):
    """获取自定义北箭绘图函数"""
    return _custom_north_arrow_functions.get(name)


def create_example_scale_bar_style():
    """创建示例比例尺样式文件"""
    example_code = '''"""
示例：自定义比例尺样式
文件名将作为样式名称显示在下拉框中
"""

def draw_custom_scale_bar(ax, extent, *, km_length=None, bar_h=0.012,
                          y_out=0.12, x_in=0.08, unit="km", unit_sep=" ",
                          txt_size=9, line_lw=1.2, edge_lw=0.6, segments=4):
    """
    自定义比例尺绘制函数
    
    参数：
    - ax: matplotlib axes对象
    - extent: (left, right, bottom, top) 地图范围
    - km_length: 比例尺长度（公里），None表示自动计算
    - bar_h: 比例尺高度（相对于axes高度）
    - y_out: 距离底部的距离（相对于axes高度）
    - x_in: 距离左侧的距离（相对于axes宽度）
    - unit: 单位文字
    - unit_sep: 单位与数字之间的分隔符
    - txt_size: 文字大小
    - line_lw: 线条宽度
    - edge_lw: 边框线宽
    - segments: 分段数
    """
    from matplotlib.patches import Rectangle
    import numpy as np
    
    # 这里是您的自定义绘制代码
    # 示例：绘制一个简单的线段式比例尺
    
    left, right, bottom, top = extent
    width_m = right - left
    
    # 自动计算合适的长度
    if km_length is None or km_length <= 0:
        # 简单的自动计算逻辑
        width_km = width_m / 1000.0
        nice_lengths = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
        km_length = min(nice_lengths, key=lambda x: abs(x - width_km * 0.3))
    
    length_m = km_length * 1000.0
    frac_w = length_m / width_m
    
    x0 = x_in
    y0 = -y_out
    
    # 绘制主线
    ax.plot([x0, x0+frac_w], [y0, y0], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)
    
    # 绘制端点标记
    ax.plot([x0, x0], [y0-bar_h/2, y0+bar_h/2], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)
    ax.plot([x0+frac_w, x0+frac_w], [y0-bar_h/2, y0+bar_h/2], transform=ax.transAxes,
            color='black', lw=line_lw, clip_on=False, zorder=3)
    
    # 添加文字标注
    label = f"0{unit_sep}{km_length}{unit_sep}{unit}"
    ax.text(x0+frac_w/2, y0-bar_h, label, transform=ax.transAxes,
            ha='center', va='top', fontsize=txt_size, clip_on=False, zorder=3)
'''
    
    example_file = os.path.join(CUSTOM_STYLES_DIR, "示例比例尺样式.py")
    with open(example_file, 'w', encoding='utf-8') as f:
        f.write(example_code)
    
    return example_file


def create_example_north_arrow_style():
    """创建示例北箭样式文件"""
    example_code = '''"""
示例：自定义北箭样式
文件名将作为样式名称显示在下拉框中
"""

def draw_custom_north_arrow(ax, extent, *, size_frac=0.06, pad_frac=0.08, 
                            txt_size=10, lw=1.5):
    """
    自定义北箭绘制函数
    
    参数：
    - ax: matplotlib axes对象
    - extent: (left, right, bottom, top) 地图范围
    - size_frac: 北箭大小（相对于地图高度）
    - pad_frac: 距离边缘的距离（相对于地图宽度/高度）
    - txt_size: 文字大小
    - lw: 线条宽度
    """
    from matplotlib.patches import Polygon, Rectangle
    
    # 这里是您的自定义绘制代码
    # 示例：绘制一个简单的箭头式北箭
    
    left, right, bottom, top = extent
    x = right - (right-left) * pad_frac
    y = bottom + (top-bottom) * pad_frac
    h = (top-bottom) * size_frac
    w = h * 0.25
    
    # 箭杆
    shaft_width = w * 0.2
    shaft = Rectangle((x-shaft_width/2, y), shaft_width, h*0.65,
                     transform=ax.transData, facecolor='black', edgecolor='none',
                     clip_on=False, zorder=3)
    ax.add_patch(shaft)
    
    # 箭头
    arrow_head = Polygon([[x, y+h], [x-w/2, y+h*0.6], [x+w/2, y+h*0.6]],
                         closed=True, facecolor='black', edgecolor='none',
                         clip_on=False, zorder=3)
    ax.add_patch(arrow_head)
    
    # 字母N
    ax.text(x, y - (top-bottom)*0.01, 'N', ha='center', va='top',
            fontsize=txt_size, fontweight='bold', family='serif',
            clip_on=False, zorder=3)
'''
    
    example_file = os.path.join(CUSTOM_STYLES_DIR, "示例北箭样式.py")
    with open(example_file, 'w', encoding='utf-8') as f:
        f.write(example_code)
    
    return example_file

