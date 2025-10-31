# -*- coding: utf-8 -*-
"""
色带导入工具 - 支持多种格式
- ArcGIS .clr 文件（文本格式）
- ArcGIS .style 文件（SQLite数据库格式）
- GMT .cpt 文件
- 通用 RGB 文本文件
"""

import os
import re
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, ListedColormap


def read_arcgis_clr(file_path):
    """
    读取 ArcGIS .clr 文件
    
    格式示例：
    0 255 255 255
    1 254 240 217
    2 253 204 138
    ...
    
    返回：(name, colormap_object)
    """
    colors = []
    values = []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                try:
                    value = float(parts[0])
                    r = int(parts[1]) / 255.0
                    g = int(parts[2]) / 255.0
                    b = int(parts[3]) / 255.0
                    
                    values.append(value)
                    colors.append((r, g, b))
                except ValueError:
                    continue
    
    if not colors:
        raise ValueError("未找到有效的颜色数据")
    
    # 创建色带
    name = os.path.splitext(os.path.basename(file_path))[0]
    
    if len(colors) <= 20:
        # 少量颜色：使用离散色带
        cmap = ListedColormap(colors, name=name)
    else:
        # 多量颜色：使用连续色带
        cmap = LinearSegmentedColormap.from_list(name, colors, N=256)
    
    return name, cmap


def read_gmt_cpt(file_path):
    """
    读取 GMT .cpt 文件
    
    格式示例：
    # COLOR_MODEL = RGB
    0 255 255 255 1 254 240 217
    1 254 240 217 2 253 204 138
    ...
    
    返回：(name, colormap_object)
    """
    colors = []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('B') or line.startswith('F') or line.startswith('N'):
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # 取第一个颜色（起始颜色）
                    r = int(parts[1]) / 255.0
                    g = int(parts[2]) / 255.0
                    b = int(parts[3]) / 255.0
                    colors.append((r, g, b))
                    
                    # 如果有第二个颜色（结束颜色），也添加
                    if len(parts) >= 8:
                        r2 = int(parts[5]) / 255.0
                        g2 = int(parts[6]) / 255.0
                        b2 = int(parts[7]) / 255.0
                        colors.append((r2, g2, b2))
                except (ValueError, IndexError):
                    continue
    
    if not colors:
        raise ValueError("未找到有效的颜色数据")
    
    name = os.path.splitext(os.path.basename(file_path))[0]
    cmap = LinearSegmentedColormap.from_list(name, colors, N=256)
    
    return name, cmap


def read_rgb_text(file_path):
    """
    读取通用 RGB 文本文件
    
    支持多种格式：
    - "255 0 0" (空格分隔)
    - "255,0,0" (逗号分隔)
    - "#FF0000" (十六进制)
    - "rgb(255,0,0)" (CSS格式)
    
    返回：(name, colormap_object)
    """
    colors = []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 尝试解析十六进制颜色
            hex_match = re.search(r'#([0-9A-Fa-f]{6})', line)
            if hex_match:
                hex_color = hex_match.group(1)
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
                colors.append((r, g, b))
                continue
            
            # 尝试解析 rgb() 格式
            rgb_match = re.search(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', line)
            if rgb_match:
                r = int(rgb_match.group(1)) / 255.0
                g = int(rgb_match.group(2)) / 255.0
                b = int(rgb_match.group(3)) / 255.0
                colors.append((r, g, b))
                continue
            
            # 尝试解析数字格式（空格或逗号分隔）
            parts = re.split(r'[,\s]+', line)
            if len(parts) >= 3:
                try:
                    r = float(parts[0])
                    g = float(parts[1])
                    b = float(parts[2])
                    
                    # 如果值大于1，假设是0-255范围
                    if r > 1.0 or g > 1.0 or b > 1.0:
                        r /= 255.0
                        g /= 255.0
                        b /= 255.0
                    
                    colors.append((r, g, b))
                except ValueError:
                    continue
    
    if not colors:
        raise ValueError("未找到有效的颜色数据")
    
    name = os.path.splitext(os.path.basename(file_path))[0]
    cmap = LinearSegmentedColormap.from_list(name, colors, N=256)
    
    return name, cmap


def read_arcgis_style_db(file_path):
    """
    读取 ArcGIS .style 文件（SQLite数据库）
    
    注意：这需要 sqlite3 模块，并且需要了解 .style 文件的内部结构
    目前暂不支持，返回错误提示
    
    返回：(name, colormap_object)
    """
    raise NotImplementedError(
        "ArcGIS .style 文件是 SQLite 数据库格式，暂不支持直接导入。\n\n"
        "建议：\n"
        "1. 在 ArcGIS 中将色带导出为 .clr 文件\n"
        "2. 或使用 ArcGIS 的 'Export Color Ramp' 功能\n"
        "3. 或手动创建 RGB 文本文件"
    )


def import_colormap_from_file(file_path):
    """
    自动识别文件格式并导入色带
    
    支持的格式：
    - .clr (ArcGIS colormap file)
    - .cpt (GMT color palette)
    - .txt, .rgb (通用 RGB 文本文件)
    - .style (ArcGIS style database - 暂不支持)
    
    返回：(name, colormap_object)
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.clr':
            return read_arcgis_clr(file_path)
        elif ext == '.cpt':
            return read_gmt_cpt(file_path)
        elif ext in ['.txt', '.rgb', '.dat']:
            return read_rgb_text(file_path)
        elif ext == '.style':
            return read_arcgis_style_db(file_path)
        else:
            # 尝试作为通用文本文件读取
            return read_rgb_text(file_path)
    except UnicodeDecodeError as e:
        if ext == '.style':
            raise ValueError(
                "无法导入配色文件：\n"
                "'utf-8' codec can't decode byte 0xb5 in position 24: invalid start byte\n\n"
                "原因：.style 文件是 SQLite 数据库格式，不是文本文件。\n\n"
                "解决方案：\n"
                "1. 在 ArcGIS 中将色带导出为 .clr 文件（文本格式）\n"
                "   - 右键点击色带 → Export Color Ramp\n"
                "   - 选择 'Colormap File (*.clr)' 格式\n\n"
                "2. 或创建 RGB 文本文件（每行一个颜色）：\n"
                "   255 0 0\n"
                "   255 128 0\n"
                "   255 255 0\n"
                "   ...\n\n"
                "3. 或使用 GMT .cpt 格式文件"
            )
        else:
            raise ValueError(f"文件编码错误：{str(e)}")


def register_imported_colormap(name, cmap, registry_dict):
    """
    将导入的色带注册到色带注册表
    
    参数：
        name: 色带名称
        cmap: matplotlib colormap 对象
        registry_dict: 色带注册表字典（如 CMAP_REGISTRY）
    
    返回：
        注册后的 key
    """
    # 生成唯一的 key
    base_key = f"imported_{name}"
    key = base_key
    counter = 1
    while key in registry_dict:
        key = f"{base_key}_{counter}"
        counter += 1
    
    # 注册到 matplotlib
    try:
        import matplotlib.pyplot as plt
        plt.register_cmap(name=key, cmap=cmap)
    except:
        pass
    
    # 添加到注册表
    registry_dict[key] = {
        "name": f"{name}（导入）",
        "group": "导入色带",
        "mpl": key
    }
    
    return key


# 创建示例 .clr 文件的函数
def create_example_clr_file(output_path):
    """创建一个示例 .clr 文件"""
    content = """# ArcGIS Colormap File (.clr)
# Format: value R G B
# R, G, B range: 0-255
0 255 255 255
1 254 240 217
2 253 204 138
3 252 141 89
4 227 74 51
5 179 0 0
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

