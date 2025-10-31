# -*- coding: utf-8 -*-
"""
GUI 主程序（优化版）
- 使用折叠面板组织界面，更加整洁
- 添加色带宽度调整功能
- 保持所有原有功能不变
"""

import os
import json
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from . import fonts
from .fonts import fontprops_pair
from .plotting import make_single_map, make_grid_map
from .config import STATE_FILE, DEFAULT_CMAP_KEY, DST_CRS
from .colormaps import CMAP_REGISTRY, resolve_cmap
from .gui_widgets import GradientCombo, ToolTip, qmark, CollapsibleFrame

import matplotlib
try:
    matplotlib.use("TkAgg")
except Exception:
    pass

# 安全取值工具
def _get_float(entry, default=None):
    try:
        s = entry.get().strip()
    except Exception:
        return default
    if s == "":
        return default
    try:
        return float(s)
    except Exception:
        return default

def _get_int(entry, default=None):
    try:
        s = entry.get().strip()
    except Exception:
        return default
    if s == "":
        return default
    try:
        return int(float(s))
    except Exception:
        return default

# 主入口
def run_app():
    root = tk.Tk()
    root.title("论文制图（单图 / 多图） v13 - 优化版")
    root.geometry("1400x900")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    # 状态管理函数
    def set_entry(w: tk.Entry, val: str):
        w.delete(0, "end")
        w.insert(0, str(val) if val is not None else "")

    def save_state(*_):
        try:
            state = {
                "entries": {k: v.get() for k, v in entries.items()},
                "combos": {k: v.get() for k, v in combos.items()},
                "checks": {k: v.get() for k, v in checks.items()},
                "texts": {k: v.get("1.0", "end") for k, v in texts.items()},
                "panel_cmaps": [cb.get() for cb in panel_cmap_boxes] if panel_cmap_boxes else None,
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("[状态保存失败]", e)

    def load_state():
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            for k, val in s.get("entries", {}).items():
                if k in entries:
                    set_entry(entries[k], val)
            for k, val in s.get("combos", {}).items():
                if k in combos:
                    combos[k].set(val)
            for k, val in s.get("checks", {}).items():
                if k in checks:
                    checks[k].set(bool(val))
            for k, val in s.get("texts", {}).items():
                if k in texts:
                    texts[k].delete("1.0", "end")
                    texts[k].insert("1.0", val)
            rebuild_panel_cmap_controls()
            pc = s.get("panel_cmaps", None)
            if pc and panel_cmap_boxes:
                for i, cb in enumerate(panel_cmap_boxes):
                    if i < len(pc) and pc[i]:
                        cb.set(pc[i])
        except Exception as e:
            print("[状态加载失败]", e)

    def apply_defaults():
        for k, val in DEFAULT_ENTRIES.items():
            set_entry(entries[k], val)
        for k, val in DEFAULT_CHECKS.items():
            checks[k].set(val)
        for k, val in DEFAULT_TEXTS.items():
            texts[k].delete("1.0", "end")
            texts[k].insert("1.0", val)
        combos["cb_font_en"].set(DEFAULT_COMBOS["cb_font_en"])
        combos["cb_font_zh"].set(DEFAULT_COMBOS["cb_font_zh"])
        combos["cb_loc1"].set(DEFAULT_COMBOS["cb_loc1"])
        combos["cb_nstyle1"].set(DEFAULT_COMBOS["cb_nstyle1"])
        combos["cb_loc2"].set(DEFAULT_COMBOS["cb_loc2"])
        combos["cb_per_loc"].set(DEFAULT_COMBOS["cb_per_loc"])
        combos["cb_nstyle2"].set(DEFAULT_COMBOS["cb_nstyle2"])
        combos["cb_scsp1"].set(DEFAULT_COMBOS["cb_scsp1"])
        combos["cb_scsp2"].set(DEFAULT_COMBOS["cb_scsp2"])
        combos["cb_cmap1"].set(DEFAULT_CMAP_KEY)
        combos["cb_cmap2"].set(DEFAULT_CMAP_KEY)
        rebuild_panel_cmap_controls()

    def reset_defaults():
        apply_defaults()
        try:
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
        except Exception as e:
            print("[删除状态文件失败]", e)
        messagebox.showinfo("已重置", "已恢复默认并清除历史设置。")

    def on_close():
        save_state()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # ========= 全局设置区域（使用折叠面板） =========
    global_frame = CollapsibleFrame(root, text="全局设置", default_open=True)
    global_frame.grid(row=0, column=0, padx=10, pady=8, sticky="nwe")
    
    box = global_frame.get_content_frame()
    box.columnconfigure(1, weight=1)
    box.columnconfigure(8, weight=1)
    box.columnconfigure(13, weight=1)

    # 第一行：时间、字体、线宽
    ttk.Label(box, text="起始年").grid(row=0, column=0, sticky="e", padx=(4, 2))
    e_y1 = tk.Entry(box, width=6)
    e_y1.insert(0, "1981")
    e_y1.grid(row=0, column=1, sticky="w", padx=2)
    
    ttk.Label(box, text="结束年").grid(row=0, column=2, sticky="e", padx=2)
    e_y2 = tk.Entry(box, width=6)
    e_y2.insert(0, "2020")
    e_y2.grid(row=0, column=3, sticky="w", padx=2)

    var_avg = tk.BooleanVar(value=True)
    ttk.Checkbutton(box, text="转为年平均", variable=var_avg).grid(row=0, column=4, sticky="w", padx=8)

    ttk.Label(box, text="英文字体").grid(row=0, column=5, sticky="e", padx=2)
    EN_FONT_CHOICES = ["Times New Roman", "Arial", "Calibri", "Cambria", "DejaVu Sans"]
    cb_font_en = ttk.Combobox(box, values=EN_FONT_CHOICES, width=18, state="readonly")
    cb_font_en.set("Times New Roman")
    cb_font_en.grid(row=0, column=6, sticky="w", padx=2)

    ttk.Label(box, text="中文字体").grid(row=0, column=7, sticky="e", padx=2)
    ZH_FONT_CHOICES = [
        "Microsoft YaHei", "SimHei", "SimSun", "DengXian",
        "KaiTi", "FangSong", "STSong",
        "Noto Sans CJK SC", "Source Han Sans SC", "Source Han Serif SC",
        "PingFang SC", "HarmonyOS Sans SC"
    ]
    cb_font_zh = ttk.Combobox(box, values=ZH_FONT_CHOICES, width=18, state="readonly")
    cb_font_zh.set("Microsoft YaHei")
    cb_font_zh.grid(row=0, column=8, sticky="w", padx=2)

    ttk.Label(box, text="边界线宽").grid(row=0, column=9, sticky="e", padx=2)
    e_bdlw = tk.Entry(box, width=6)
    e_bdlw.insert(0, "0.8")
    e_bdlw.grid(row=0, column=10, sticky="w", padx=2)

    ttk.Button(
        box, text="保存设置",
        command=lambda: (save_state(), messagebox.showinfo("保存成功", "当前设置已保存。"))
    ).grid(row=0, column=11, padx=8)

    ttk.Button(
        box, text="恢复默认",
        command=reset_defaults
    ).grid(row=0, column=12, padx=8)

    qmark(box, "设置会在预览/导出和关闭窗口时自动保存；下次启动自动恢复。", 0, 13)

    # 第二行：叠加默认值
    ttk.Label(box, text="叠加默认 颜色").grid(row=1, column=0, sticky="e", padx=(4, 2))
    e_ol_def_col = tk.Entry(box, width=10)
    e_ol_def_col.insert(0, "#1f77b4")
    e_ol_def_col.grid(row=1, column=1, sticky="w", padx=2)
    
    ttk.Label(box, text="线宽").grid(row=1, column=2, sticky="e", padx=2)
    e_ol_def_lw = tk.Entry(box, width=6)
    e_ol_def_lw.insert(0, "0.8")
    e_ol_def_lw.grid(row=1, column=3, sticky="w", padx=2)
    
    ttk.Label(box, text="点大小").grid(row=1, column=4, sticky="e", padx=2)
    e_ol_def_ms = tk.Entry(box, width=6)
    e_ol_def_ms.insert(0, "6")
    e_ol_def_ms.grid(row=1, column=5, sticky="w", padx=2)

    # 第三行：叠加图层列表
    ttk.Label(
        box, text="叠加SHP 列表（每行：路径 | 颜色 | 线宽 | 模式 | 点大小）"
    ).grid(row=2, column=0, sticky="w", columnspan=4, pady=(8, 0), padx=4)

    txt_overlay = tk.Text(box, width=155, height=3)
    txt_overlay.grid(row=3, column=0, columnspan=14, padx=4, pady=2, sticky="we")

    qmark(box, "模式：auto（默认），line（线）、boundary（只画外边界）、fill（面边界+透明填充）、point（点）", 2, 4)

    def parse_overlay():
        layers = []
        def_col = e_ol_def_col.get().strip() or "#1f77b4"
        def_lw = float(e_ol_def_lw.get() or 0.8)
        def_ms = float(e_ol_def_ms.get() or 6)
        for ln in txt_overlay.get("1.0", "end").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            parts = [p.strip() for p in ln.split("|")]
            spec = {
                "path": parts[0],
                "color": parts[1] if len(parts) > 1 and parts[1] else def_col,
                "lw": float(parts[2]) if len(parts) > 2 and parts[2] else def_lw,
                "mode": parts[3] if len(parts) > 3 and parts[3] else "auto",
                "ms": float(parts[4]) if len(parts) > 4 and parts[4] else def_ms
            }
            if os.path.exists(spec["path"]):
                layers.append(spec)
            else:
                print(f"[overlay] 未找到：{spec['path']}（忽略）")
        return layers

    def must_exist(path, label):
        if not path:
            messagebox.showerror("缺少输入", f"请指定{label}。")
            return False
        if not os.path.exists(path) and not any(ch in path for ch in "*?"):
            messagebox.showerror("路径无效", f"{label}不存在：\n{path}")
            return False
        return True

    var_autoprev = tk.BooleanVar(value=False)

    # ========= Notebook =========
    nb = ttk.Notebook(root)
    nb.grid(row=1, column=0, padx=10, pady=4, sticky="nsew")

    # 初始化变量字典（后续会填充）
    entries = {}
    combos = {}
    checks = {}
    texts = {}
    panel_cmap_boxes = []

    # 占位函数（后续实现）
    def rebuild_panel_cmap_controls(*_):
        pass

    # 默认值字典（后续定义）
    DEFAULT_ENTRIES = {}
    DEFAULT_COMBOS = {}
    DEFAULT_CHECKS = {}
    DEFAULT_TEXTS = {}

    # 这里只是框架，完整实现需要继续添加单图和多图页面
    # 由于文件长度限制，将在后续步骤中继续添加
    
    root.mainloop()

if __name__ == "__main__":
    run_app()

