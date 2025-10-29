# -*- coding: utf-8 -*-
"""
GUI 主程序（完整文件）
- 单图 / 多图 出图
- 共享/分图色带；分图各自 vmax（百分位）；分图色带刻度个数
- 比例尺：单位、是否留空格、大小与锚点（通过 plotting/draw_elems 实现）
- 北箭：样式、字号、边距
- 渐变色带可视化下拉
- 状态保存/恢复；一键重置
"""

import os
import json
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from . import fonts           # 触发注册/rcParams
from .fonts import fontprops_pair  # 若需要单独取 (en, zh)

# ==== 项目内部模块 ====
from .plotting import make_single_map, make_grid_map
from .config import STATE_FILE, DEFAULT_CMAP_KEY, DST_CRS  # DST_CRS 仅用于提示
from .colormaps import CMAP_REGISTRY, resolve_cmap

# ==== Matplotlib 后端（用于生成下拉渐变）====
import matplotlib
try:
    matplotlib.use("TkAgg")
except Exception:
    pass

# —— 安全取值工具：避免空字符串导致 float()/int() 报错 ——
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


# ---------------- 工具：渐变缩略图（纯 Tk PhotoImage） ----------------
_GRAD_IMG_CACHE = {}  # (key,w,h)->PhotoImage

def make_gradient_image(cmap_key, width=120, height=14):
    key = (cmap_key, width, height)
    if key in _GRAD_IMG_CACHE:
        return _GRAD_IMG_CACHE[key]
    cmap = resolve_cmap(cmap_key)
    img = tk.PhotoImage(width=width, height=height)
    for x in range(width):
        v = x/(width-1) if width>1 else 0
        rgba = cmap(v)
        r,g,b = [int(round(255*c)) for c in rgba[:3]]
        color = f"#{r:02x}{g:02x}{b:02x}"
        for y in range(height):
            img.put(color, (x, y))
    # 边框
    border = "#d0d0d0"
    for x in range(width):
        img.put(border, (x, 0))
        img.put(border, (x, height-1))
    for y in range(height):
        img.put(border, (0, y))
        img.put(border, (width-1, y))
    _GRAD_IMG_CACHE[key] = img
    return img

class GradientCombo(tk.Frame):
    """像 Combobox 一样使用：get()/set()；但下拉每项带渐变缩略图。"""
    def __init__(self, master, default_key=DEFAULT_CMAP_KEY, width=200, **kw):
        super().__init__(master, **kw)
        self._value = tk.StringVar(value=default_key if default_key in CMAP_REGISTRY else DEFAULT_CMAP_KEY)
        self._text  = tk.StringVar(value=CMAP_REGISTRY.get(self._value.get(), {"name":self._value.get()})["name"])
        self._img   = make_gradient_image(self._value.get(), width=96, height=14)

        self._btn = tk.Menubutton(self, textvariable=self._text, image=self._img,
                                  compound="left", relief="groove", anchor="w", width=width//8)
        self._btn.grid(row=0, column=0, sticky="we")
        self.columnconfigure(0, weight=1)

        self._menu = tk.Menu(self._btn, tearoff=0)
        # 按分组生成子菜单
        groups = {}
        for key, ent in CMAP_REGISTRY.items():
            grp = ent["group"]
            if grp not in groups:
                groups[grp] = tk.Menu(self._menu, tearoff=0)
                self._menu.add_cascade(label=grp, menu=groups[grp])
            img = make_gradient_image(key, width=96, height=14)
            groups[grp].add_command(
                label=ent["name"], image=img, compound="left",
                command=lambda k=key: self._select(k)
            )
        self._btn["menu"] = self._menu

    def _select(self, key):
        self._value.set(key)
        self._text.set(CMAP_REGISTRY.get(key, {"name":key})["name"])
        self._img = make_gradient_image(key, width=96, height=14)
        self._btn.configure(image=self._img)
        self.event_generate("<<PaletteChanged>>")

    def get(self):
        return self._value.get()

    def set(self, key):
        if key not in CMAP_REGISTRY and key not in matplotlib.cm.cmap_d:
            key = DEFAULT_CMAP_KEY
        self._select(key)

class ToolTip:
    def __init__(self, widget, text, wrap=360):
        self.widget = widget; self.text = text; self.wrap = wrap; self.tip=None
        widget.bind("<Enter>", self.show); widget.bind("<Leave>", self.hide)
    def show(self, _=None):
        if self.tip: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify="left", relief="solid",
                         borderwidth=1, background="#ffffe0", wraplength=self.wrap)
        label.pack(ipadx=6, ipady=4)
    def hide(self, _=None):
        if self.tip: self.tip.destroy(); self.tip=None

def qmark(parent, tip, r, c):
    lab = tk.Label(parent, text="？", fg="#444", cursor="question_arrow")
    lab.grid(row=r, column=c, sticky="w", padx=(2,6))
    ToolTip(lab, tip)

# ======================= 主入口 =======================
def run_app():
    root = tk.Tk()
    root.title("论文制图（单图 / 多图） v12")
    root.geometry("1380x1040")
    root.columnconfigure(0, weight=1)

    # ---------- 状态管理 ----------
    def set_entry(w: tk.Entry, val: str):
        w.delete(0, "end"); w.insert(0, str(val) if val is not None else "")

    def save_state(*_):
        try:
            state = {
                "entries": {k: v.get() for k,v in entries.items()},
                "combos":  {k: v.get() for k,v in combos.items()},  # GradientCombo/ttk.Combobox 统一 get()
                "checks":  {k: v.get() for k,v in checks.items()},
                "texts":   {k: v.get("1.0","end") for k,v in texts.items()},
                "panel_cmaps": [cb.get() for cb in panel_cmap_boxes] if panel_cmap_boxes else None,
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("[状态保存失败]", e)

    def load_state():
        if not os.path.exists(STATE_FILE): return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            for k, val in s.get("entries", {}).items():
                if k in entries: set_entry(entries[k], val)
            for k, val in s.get("combos", {}).items():
                if k in combos: combos[k].set(val)
            for k, val in s.get("checks", {}).items():
                if k in checks: checks[k].set(bool(val))
            for k, val in s.get("texts", {}).items():
                if k in texts:
                    texts[k].delete("1.0","end"); texts[k].insert("1.0", val)
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
            texts[k].delete("1.0","end"); texts[k].insert("1.0", val)
        combos["cb_font_en"].set(DEFAULT_COMBOS["cb_font_en"])
        combos["cb_font_zh"].set(DEFAULT_COMBOS["cb_font_zh"])
        combos["cb_loc1"].set(DEFAULT_COMBOS["cb_loc1"])
        combos["cb_nstyle1"].set(DEFAULT_COMBOS["cb_nstyle1"])
        combos["cb_loc2"].set(DEFAULT_COMBOS["cb_loc2"])
        combos["cb_per_loc"].set(DEFAULT_COMBOS["cb_per_loc"])
        combos["cb_nstyle2"].set(DEFAULT_COMBOS["cb_nstyle2"])
        combos["cb_scsp1"].set(DEFAULT_COMBOS["cb_scsp1"])
        combos["cb_scsp2"].set(DEFAULT_COMBOS["cb_scsp2"])
        # 可视化色带默认
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
        save_state(); root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # ========= 全局设置 =========
    box = ttk.LabelFrame(root, text="全局设置（时间/单位、字体、边界线宽、叠加图层默认值）")
    box.grid(row=0, column=0, padx=10, pady=8, sticky="nwe")

    # 让某些列可伸缩，文本框/多行文本更好排版
    for i in range(0, 14):
        box.columnconfigure(i, weight=0)
    box.columnconfigure(1, weight=1)  # 年份后面的输入框
    box.columnconfigure(8, weight=1)  # 中文字体下拉
    box.columnconfigure(10, weight=0)  # 线宽输入框
    box.columnconfigure(13, weight=1)  # 尾部说明/整体拉伸

    ttk.Label(box, text="起始年").grid(row=0, column=0, sticky="e")
    e_y1 = tk.Entry(box, width=6);
    e_y1.insert(0, "1981");
    e_y1.grid(row=0, column=1, sticky="w")
    ttk.Label(box, text="结束年").grid(row=0, column=2, sticky="e")
    e_y2 = tk.Entry(box, width=6);
    e_y2.insert(0, "2020");
    e_y2.grid(row=0, column=3, sticky="w")

    var_avg = tk.BooleanVar(value=True)
    ttk.Checkbutton(box, text="转为年平均（除以年数）", variable=var_avg).grid(row=0, column=4, sticky="w", padx=8)

    ttk.Label(box, text="英文字体").grid(row=0, column=5, sticky="e")
    EN_FONT_CHOICES = ["Times New Roman", "Arial", "Calibri", "Cambria", "DejaVu Sans"]
    cb_font_en = ttk.Combobox(box, values=EN_FONT_CHOICES, width=20, state="readonly")
    cb_font_en.set("Times New Roman")
    cb_font_en.grid(row=0, column=6, sticky="w")

    # 常用中文字体候选（跨 Windows / macOS / Adobe / Noto）
    ZH_FONT_CHOICES = [
        "Microsoft YaHei", "SimHei", "SimSun", "DengXian",
        "KaiTi", "FangSong", "STSong",
        "Noto Sans CJK SC", "Source Han Sans SC", "Source Han Serif SC",
        "PingFang SC", "HarmonyOS Sans SC"
    ]

    ttk.Label(box, text="中文字体").grid(row=0, column=7, sticky="e")
    # 这里假定 ZH_FONT_CHOICES 已在上文定义
    cb_font_zh = ttk.Combobox(box, values=ZH_FONT_CHOICES, width=20, state="readonly")
    cb_font_zh.set("Microsoft YaHei")
    cb_font_zh.grid(row=0, column=8, sticky="w")

    # —— 挪到 9/10 列，避免与中文字体重叠 —— #
    ttk.Label(box, text="行政边界线宽").grid(row=0, column=9, sticky="e")
    e_bdlw = tk.Entry(box, width=6)
    e_bdlw.insert(0, "0.8")
    e_bdlw.grid(row=0, column=10, sticky="w")

    # 按钮（不能用 ...，要写真实的 command）
    ttk.Button(
        box, text="保存设置",
        command=lambda: (save_state(), messagebox.showinfo("保存成功", "当前设置已保存。"))
    ).grid(row=0, column=11, padx=8)

    ttk.Button(
        box, text="恢复默认（Reset）",
        command=reset_defaults
    ).grid(row=0, column=12, padx=8)

    qmark(box, "设置会在预览/导出和关闭窗口时自动保存；下次启动自动恢复。", 0, 13)

    # 叠加默认
    ttk.Label(box, text="叠加默认 颜色").grid(row=1, column=0, sticky="e")
    e_ol_def_col = tk.Entry(box, width=10);
    e_ol_def_col.insert(0, "#1f77b4");
    e_ol_def_col.grid(row=1, column=1, sticky="w")
    ttk.Label(box, text="线宽").grid(row=1, column=2, sticky="e")
    e_ol_def_lw = tk.Entry(box, width=6);
    e_ol_def_lw.insert(0, "0.8");
    e_ol_def_lw.grid(row=1, column=3, sticky="w")
    ttk.Label(box, text="点大小").grid(row=1, column=4, sticky="e")
    e_ol_def_ms = tk.Entry(box, width=6);
    e_ol_def_ms.insert(0, "6");
    e_ol_def_ms.grid(row=1, column=5, sticky="w")

    ttk.Label(
        box, text="叠加SHP 列表（每行：路径 | 颜色 | 线宽 | 模式 | 点大小）"
    ).grid(row=2, column=0, sticky="w", columnspan=4, pady=(8, 0))

    # 占满整行，便于粘长路径；sticky="we" 需要上面的 columnconfigure 支持
    txt_overlay = tk.Text(box, width=155, height=4)
    txt_overlay.grid(row=3, column=0, columnspan=14, padx=4, pady=2, sticky="we")

    qmark(box, "模式：auto（默认），line（线）、boundary（只画外边界）、fill（面边界+透明填充）、point（点）", 2, 4)

    def parse_overlay():
        layers=[]
        def_col = e_ol_def_col.get().strip() or "#1f77b4"
        def_lw  = float(e_ol_def_lw.get() or 0.8)
        def_ms  = float(e_ol_def_ms.get() or 6)
        for ln in txt_overlay.get("1.0","end").splitlines():
            ln=ln.strip()
            if not ln: continue
            parts=[p.strip() for p in ln.split("|")]
            spec = {
                "path": parts[0],
                "color": parts[1] if len(parts)>1 and parts[1] else def_col,
                "lw": float(parts[2]) if len(parts)>2 and parts[2] else def_lw,
                "mode": parts[3] if len(parts)>3 and parts[3] else "auto",
                "ms": float(parts[4]) if len(parts)>4 and parts[4] else def_ms
            }
            if os.path.exists(spec["path"]):
                layers.append(spec)
            else:
                print(f"[overlay] 未找到：{spec['path']}（忽略）")
        return layers

    def must_exist(path, label):
        if not path:
            messagebox.showerror("缺少输入", f"请指定{label}。"); return False
        if not os.path.exists(path) and not any(ch in path for ch in "*?"):
            messagebox.showerror("路径无效", f"{label}不存在：\n{path}"); return False
        return True

    # 是否自动预览（切换参数后自动刷新）
    var_autoprev = tk.BooleanVar(value=False)

    # ========= Notebook =========
    nb = ttk.Notebook(root); nb.grid(row=1, column=0, padx=10, pady=4, sticky="nwe")

    # =================================== 单图页 ===================================
    page1 = ttk.Frame(nb); nb.add(page1, text="单图")
    page1.columnconfigure(0, weight=1)

    A1 = ttk.LabelFrame(page1, text="数据与导出")
    A1.grid(row=0, column=0, padx=6, pady=6, sticky="we")
    A1.columnconfigure(1, weight=1)

    ttk.Label(A1, text="TIF/通配符").grid(row=0, column=0, sticky="e")
    e_tif = tk.Entry(A1); e_tif.grid(row=0, column=1, sticky="we", padx=4)
    ttk.Button(A1, text="浏览",
               command=lambda: (lambda p:(e_tif.delete(0,"end"), e_tif.insert(0,p)))(filedialog.askopenfilename(title="选择TIF", filetypes=[("GeoTIFF","*.tif;*.tiff"),("所有文件","*.*")]))).grid(row=0, column=2, padx=4)

    ttk.Label(A1, text="边界SHP").grid(row=1, column=0, sticky="e")
    e_shp1 = tk.Entry(A1); e_shp1.grid(row=1, column=1, sticky="we", padx=4)
    ttk.Button(A1, text="浏览",
               command=lambda: (lambda p:(e_shp1.delete(0,"end"), e_shp1.insert(0,p)))(filedialog.askopenfilename(title="选择SHP", filetypes=[("Shapefile","*.shp"),("所有文件","*.*")]))).grid(row=1, column=2, padx=4)

    ttk.Label(A1, text="导出 PNG").grid(row=2, column=0, sticky="e")
    e_png1 = tk.Entry(A1); e_png1.insert(0, r"E:\map_outputs\single.png"); e_png1.grid(row=2, column=1, sticky="we", padx=4)
    ttk.Label(A1, text="导出 PDF").grid(row=3, column=0, sticky="e")
    e_pdf1 = tk.Entry(A1); e_pdf1.insert(0, r"E:\map_outputs\single.pdf"); e_pdf1.grid(row=3, column=1, sticky="we", padx=4)

    B1 = ttk.LabelFrame(page1, text="面板标题 / 画布")
    B1.grid(row=1, column=0, padx=6, pady=6, sticky="we")
    ttk.Label(B1, text="标题").grid(row=0, column=0, sticky="e")
    e_title = tk.Entry(B1, width=50); e_title.insert(0, "(b) WD 暖干（平均发生天数）"); e_title.grid(row=0, column=1, sticky="w", padx=4)
    ttk.Label(B1, text="字号").grid(row=0, column=2, sticky="e")
    e_tsize = tk.Entry(B1, width=6); e_tsize.insert(0, "12"); e_tsize.grid(row=0, column=3, sticky="w")
    ttk.Label(B1, text="与图距").grid(row=0, column=4, sticky="e")
    e_tpad = tk.Entry(B1, width=6); e_tpad.insert(0, "6"); e_tpad.grid(row=0, column=5, sticky="w")

    ttk.Label(B1, text="配色").grid(row=0, column=6, sticky="e")
    cb_cmap1 = GradientCombo(B1, default_key=DEFAULT_CMAP_KEY, width=200)
    cb_cmap1.grid(row=0, column=7, sticky="we", padx=(0,6))

    ttk.Label(B1, text="预览 宽×高 / DPI").grid(row=1, column=0, sticky="e")
    e_figw1 = tk.Entry(B1, width=6); e_figw1.insert(0, "8.8"); e_figw1.grid(row=1, column=1, sticky="w")
    e_figh1 = tk.Entry(B1, width=6); e_figh1.insert(0, "6.6"); e_figh1.grid(row=1, column=2, sticky="w")
    e_dpi1  = tk.Entry(B1, width=6); e_dpi1.insert(0, "150"); e_dpi1.grid(row=1, column=3, sticky="w")

    C1 = ttk.LabelFrame(page1, text="色带（单图）")
    ttk.Label(C1, text="色阶上限(空=自动)").grid(row=1, column=3, sticky="e")
    e_vmax1 = tk.Entry(C1, width=8);
    e_vmax1.insert(0, "");
    e_vmax1.grid(row=1, column=4, sticky="w")

    C1.grid(row=2, column=0, padx=6, pady=6, sticky="we")
    ttk.Label(C1, text="位置").grid(row=0, column=0, sticky="e")
    cb_loc1 = ttk.Combobox(C1, values=["right","left","top","bottom"], width=8, state="readonly")
    cb_loc1.set("right"); cb_loc1.grid(row=0, column=1, sticky="w")
    ttk.Label(C1, text="厚度%").grid(row=0, column=2, sticky="e")
    e_cbw = tk.Entry(C1, width=6); e_cbw.insert(0, "1.6"); e_cbw.grid(row=0, column=3, sticky="w")
    ttk.Label(C1, text="与图距").grid(row=0, column=4, sticky="e")
    e_cbpad = tk.Entry(C1, width=6); e_cbpad.insert(0, "0.02"); e_cbpad.grid(row=0, column=5, sticky="w")
    ttk.Label(C1, text="标签文本").grid(row=0, column=6, sticky="e")
    e_cblabtxt1 = tk.Entry(C1, width=16); e_cblabtxt1.insert(0, ""); e_cblabtxt1.grid(row=0, column=7, sticky="w")
    ttk.Label(C1, text="标签字号/刻度字号").grid(row=1, column=0, sticky="e")
    e_cblab1 = tk.Entry(C1, width=6); e_cblab1.insert(0, "11"); e_cblab1.grid(row=1, column=1, sticky="w")
    e_cbtick1 = tk.Entry(C1, width=6); e_cbtick1.insert(0, "10"); e_cbtick1.grid(row=1, column=2, sticky="w")

    # =================================== 单图页：子图元素（比例尺 & 北箭） ===================================
    D1 = ttk.LabelFrame(page1, text="子图元素（比例尺 & 北箭）")
    D1.grid(row=3, column=0, padx=6, pady=6, sticky="we")

    # 比例尺：长度(单位)/字号/段数
    ttk.Label(D1, text="比例尺 长度(单位)/字号/段数").grid(row=0, column=0, sticky="e")
    e_sckm1 = tk.Entry(D1, width=8); e_sckm1.insert(0, "")           # 长度（空=自动）
    e_sckm1.grid(row=0, column=1, sticky="w")
    e_scsize1 = tk.Entry(D1, width=6); e_scsize1.insert(0, "9")      # 字号
    e_scsize1.grid(row=0, column=2, sticky="w")
    e_scseg1 = tk.Entry(D1, width=6); e_scseg1.insert(0, "4")        # 段数
    e_scseg1.grid(row=0, column=3, sticky="w")

    # 线宽/边框/条高
    ttk.Label(D1, text="线宽/边框/条高").grid(row=0, column=4, sticky="e")
    e_sclw1 = tk.Entry(D1, width=6); e_sclw1.insert(0, "0.7")
    e_sclw1.grid(row=0, column=5, sticky="w")
    e_scedge1 = tk.Entry(D1, width=6); e_scedge1.insert(0, "0.6")
    e_scedge1.grid(row=0, column=6, sticky="w")
    e_sch1 = tk.Entry(D1, width=6); e_sch1.insert(0, "0.012")
    e_sch1.grid(row=0, column=7, sticky="w")

    # 左距/距底
    ttk.Label(D1, text="左距/距底").grid(row=0, column=8, sticky="e")
    e_scx1 = tk.Entry(D1, width=6); e_scx1.insert(0, "0.08")
    e_scx1.grid(row=0, column=9, sticky="w")
    e_scy1 = tk.Entry(D1, width=6); e_scy1.insert(0, "0.12")
    e_scy1.grid(row=0, column=10, sticky="w")

    # —— 新增：单位 & 空格 —— #
    ttk.Label(D1, text="单位").grid(row=0, column=11, sticky="e")
    e_scunit1 = tk.Entry(D1, width=6); e_scunit1.insert(0, "km")
    e_scunit1.grid(row=0, column=12, sticky="w")

    ttk.Label(D1, text="空格").grid(row=0, column=13, sticky="e")
    cb_scsp1 = ttk.Combobox(D1, values=["无","有"], width=4, state="readonly")
    cb_scsp1.set("无"); cb_scsp1.grid(row=0, column=14, sticky="w")

    # 北箭 字号/样式/距边
    ttk.Label(D1, text="北箭 字号/样式/距边").grid(row=1, column=0, sticky="e")
    e_nsize1 = tk.Entry(D1, width=6); e_nsize1.insert(0, "10")
    e_nsize1.grid(row=1, column=1, sticky="w")
    cb_nstyle1 = ttk.Combobox(D1, values=["triangle","arrow","compass"], width=10, state="readonly")
    cb_nstyle1.set("triangle"); cb_nstyle1.grid(row=1, column=2, sticky="w")
    e_npad1 = tk.Entry(D1, width=6); e_npad1.insert(0, "0.08")
    e_npad1.grid(row=1, column=3, sticky="w")

    E1 = ttk.LabelFrame(page1, text="预览 / 导出")
    E1.grid(row=4, column=0, padx=6, pady=6, sticky="we")

    def preview_single():
        shp = e_shp1.get().strip()
        tif = e_tif.get().strip()
        if not must_exist(shp, "边界SHP（单图）") or not tif:
            return
        save_state()

        # —— 读取画布尺寸（英寸）与基准 DPI ——
        fig_w_in = _get_float(e_figw1, 8.8)
        fig_h_in = _get_float(e_figh1, 6.6)
        dpi_base = _get_int(e_dpi1, 150)

        # —— 工具条“预览(px)” → 计算预览用 DPI（只作用于预览） ——
        px_w = _get_int(e_prev_w1, None)  # ← 工具条上的“宽(px)”输入框
        px_h = _get_int(e_prev_h1, None)  # ← 工具条上的“高(px)”输入框
        dpi_eff = dpi_base
        cand = []
        if px_w is not None and fig_w_in:
            cand.append(px_w / float(fig_w_in))
        if px_h is not None and fig_h_in:
            cand.append(px_h / float(fig_h_in))
        if cand:
            dpi_eff = int(max(50, min(800, min(cand))))  # 合理范围，避免过大/过小

        make_single_map(
            tif_path=tif,
            border_shp=shp,
            overlay_layers=parse_overlay(),

            year_start=_get_int(e_y1, 1981),
            year_end=_get_int(e_y2, 2020),
            as_yearly=var_avg.get(),

            font_en=cb_font_en.get(),
            font_zh=cb_font_zh.get(),

            # 标题 / 边界
            title=e_title.get().strip(),
            title_size=_get_int(e_tsize, 12),
            title_pad=_get_float(e_tpad, 6),
            border_lw=_get_float(e_bdlw, 0.8),

            # 色带（vmax 留空=自动用真实最大值）
            cmap_key=cb_cmap1.get(),
            vmax=_get_float(e_vmax1, None),
            cbar_loc=cb_loc1.get(),
            cbar_label_text=(e_cblabtxt1.get().strip() or None),
            cbar_label_size=_get_int(e_cblab1, 11),
            cbar_tick_size=_get_int(e_cbtick1, 10),

            # —— 比例尺（和绘图层参数名一一对应）——
            scale_km=_get_int(e_sckm1, None),
            scale_segments=_get_int(e_scseg1, 4),
            scale_bar_h=_get_float(e_sch1, 0.012),
            scale_edge_lw=_get_float(e_scedge1, 0.6),
            scale_line_lw=_get_float(e_sclw1, 0.7),
            scale_txt_size=_get_int(e_scsize1, 9),
            scale_x_in=_get_float(e_scx1, 0.08),  # ← 你的“x 内距”
            scale_y_out=_get_float(e_scy1, 0.12),  # ← 你的“y 外距”（>0轴外，<0轴内）

            # —— 北箭（绘图层用一个 pad 值控制位置）——
            north_txt_size=_get_int(e_nsize1, 10),
            north_pad=_get_float(e_npad1, 0.08),

            # 画布尺寸 + “预览(px)”得到的 DPI
            fig_w=fig_w_in, fig_h=fig_h_in, dpi=dpi_eff,
            preview=True
        )

    def export_single():
        shp = e_shp1.get().strip(); tif = e_tif.get().strip()
        if not must_exist(shp,"边界SHP（单图）") or not tif: return
        save_state()

        make_single_map(
            tif_path=tif,
            border_shp=shp,
            overlay_layers=parse_overlay(),
            year_start=int(e_y1.get()),
            year_end=int(e_y2.get()),
            as_yearly=var_avg.get(),
            font_en=cb_font_en.get(), font_zh=cb_font_zh.get(),


            title=e_title.get().strip(), title_size=int(e_tsize.get()), title_pad=float(e_tpad.get()),
            border_lw=float(e_bdlw.get()),

            cmap_key=cb_cmap1.get(),
            vmax=(float(e_vmax1.get()) if e_vmax1.get().strip() else None),
            cbar_loc=cb_loc1.get(),
            cbar_size=f"{float(e_cbw.get())}%",
            cbar_pad=float(e_cbpad.get()),
            cbar_label_text=(e_cblabtxt1.get().strip() or None),
            cbar_label_size=int(e_cblab1.get()),
            cbar_tick_size=int(e_cbtick1.get()),

            # 比例尺
            scale_length=(float(e_sckm1.get()) if e_sckm1.get().strip() else None),
            scale_unit=(e_scunit1.get().strip() or "km"),
            scale_unit_sep=(" " if cb_scsp1.get()=="有" else ""),
            scale_segments=int(e_scseg1.get()),
            scale_bar_h=float(e_sch1.get()),
            scale_edge_lw=float(e_scedge1.get()),
            scale_line_lw=float(e_sclw1.get()),
            scale_txt_size=int(e_scsize1.get()),
            scale_anchor="SW",
            scale_pad_x=float(e_scx1.get()),
            scale_pad_y=float(e_scy1.get()),

            # 北箭
            north_style=cb_nstyle1.get(),
            north_size_frac=0.06,
            north_anchor="NE",
            north_pad_x=float(e_npad1.get()),
            north_pad_y=float(e_npad1.get()),
            north_txt_size=int(e_nsize1.get()),

            fig_w=float(e_figw1.get()), fig_h=float(e_figh1.get()), dpi=int(e_dpi1.get()),
            out_png=e_png1.get().strip(), out_pdf=e_pdf1.get().strip(), preview=False
        )

    bar1 = ttk.Frame(E1)
    bar1.grid(row=0, column=0, columnspan=12, sticky="w", pady=(2, 6))

    ttk.Button(bar1, text="预览单图", command=preview_single).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(bar1, text="导出单图", command=export_single).grid(row=0, column=1, padx=(0, 16))
    ttk.Checkbutton(bar1, text="自动预览", variable=var_autoprev).grid(row=0, column=2, padx=(0, 0))
    # —— 单图 工具条 bar1 ——（如果已建 bar1，只需把下面这几行补上）
    ttk.Label(bar1, text="预览(px)").grid(row=0, column=3, padx=(16, 6))
    e_prev_w1 = tk.Entry(bar1, width=6);
    e_prev_w1.insert(0, "")
    e_prev_w1.grid(row=0, column=4)
    ttk.Label(bar1, text="×").grid(row=0, column=5, padx=4)
    e_prev_h1 = tk.Entry(bar1, width=6);
    e_prev_h1.insert(0, "")
    e_prev_h1.grid(row=0, column=6)

    # =================================== 多图页 ===================================
    page2 = ttk.Frame(nb); nb.add(page2, text="多图")
    page2.columnconfigure(0, weight=1)

    A2 = ttk.LabelFrame(page2, text="数据与导出")
    A2.grid(row=0, column=0, padx=6, pady=6, sticky="we")
    A2.columnconfigure(1, weight=1)

    ttk.Label(A2, text="边界SHP（留空沿用单图）").grid(row=0, column=0, sticky="e")
    e_shp2 = tk.Entry(A2); e_shp2.grid(row=0, column=1, sticky="we", padx=4)
    ttk.Button(A2, text="浏览",
               command=lambda: (lambda p:(e_shp2.delete(0,"end"), e_shp2.insert(0,p)))(filedialog.askopenfilename(title="选择SHP", filetypes=[("Shapefile","*.shp"),("所有文件","*.*")]))).grid(row=0, column=2, padx=4)

    ttk.Label(A2, text="TIF列表（每行一个，可*.tif）").grid(row=1, column=0, sticky="ne")
    txt_list = tk.Text(A2, height=7); txt_list.grid(row=1, column=1, columnspan=2, sticky="we", padx=4)
    def pick_multi_tifs_append():
        ps = filedialog.askopenfilenames(title="追加TIF（可多选）",
                                         filetypes=[("GeoTIFF","*.tif;*.tiff"),("所有文件","*.*")])
        if ps:
            cur = txt_list.get("1.0","end").strip()
            if cur and not cur.endswith("\n"):
                txt_list.insert("end","\n")
            for p in ps: txt_list.insert("end", p+"\n")
    ttk.Button(A2, text="选择文件(追加)", command=pick_multi_tifs_append).grid(row=1, column=3, padx=4)
    ttk.Button(A2, text="清空列表", command=lambda: txt_list.delete("1.0","end")).grid(row=1, column=4, padx=4)

    ttk.Label(A2, text="导出 PNG").grid(row=2, column=0, sticky="e")
    e_png2 = tk.Entry(A2); e_png2.insert(0, r"E:\map_outputs\compound_2x2.png"); e_png2.grid(row=2, column=1, sticky="we", padx=4)
    ttk.Label(A2, text="导出 PDF").grid(row=3, column=0, sticky="e")
    e_pdf2 = tk.Entry(A2); e_pdf2.insert(0, r"E:\map_outputs\compound_2x2.pdf"); e_pdf2.grid(row=3, column=1, sticky="we", padx=4)

    B2 = ttk.LabelFrame(page2, text="布局与说明")
    B2.grid(row=1, column=0, padx=6, pady=6, sticky="we")
    ttk.Label(B2, text="行×列").grid(row=0, column=0, sticky="e")
    e_rows = tk.Entry(B2, width=6); e_rows.insert(0, "2"); e_rows.grid(row=0, column=1, sticky="w")
    e_cols = tk.Entry(B2, width=6); e_cols.insert(0, "2"); e_cols.grid(row=0, column=2, sticky="w")
    ttk.Label(B2, text="子图间距 wspace/hspace").grid(row=0, column=3, sticky="e")
    e_wspace = tk.Entry(B2, width=6); e_wspace.insert(0, "0.12"); e_wspace.grid(row=0, column=4, sticky="w")
    e_hspace = tk.Entry(B2, width=6); e_hspace.insert(0, "0.22"); e_hspace.grid(row=0, column=5, sticky="w")
    ttk.Label(B2, text="配色（全局）").grid(row=0, column=6, sticky="e")
    cb_cmap2 = GradientCombo(B2, default_key=DEFAULT_CMAP_KEY, width=220)
    cb_cmap2.grid(row=0, column=7, sticky="we", padx=(0,6))

    ttk.Label(B2, text="面板标题（|分隔）").grid(row=1, column=0, sticky="e")
    e_titles = tk.Entry(B2, width=72); e_titles.insert(0, "(a) WW 暖湿|(b) WD 暖干|(c) CW 冷湿|(d) CD 冷干"); e_titles.grid(row=1, column=1, columnspan=6, sticky="we")
    ttk.Label(B2, text="子图标题 字号/与图距").grid(row=2, column=0, sticky="e")
    e_tsz2 = tk.Entry(B2, width=6); e_tsz2.insert(0, "11"); e_tsz2.grid(row=2, column=1, sticky="w")
    e_tpad2 = tk.Entry(B2, width=6); e_tpad2.insert(0, "5"); e_tpad2.grid(row=2, column=2, sticky="w")

    ttk.Label(B2, text="总说明文字").grid(row=3, column=0, sticky="e")
    e_caption = tk.Entry(B2, width=72); e_caption.insert(0, "复合极端事件多年平均发生天数（1981–2020）"); e_caption.grid(row=3, column=1, columnspan=5, sticky="we")
    ttk.Label(B2, text="字号").grid(row=3, column=6, sticky="e")
    e_capsize = tk.Entry(B2, width=6); e_capsize.insert(0, "12"); e_capsize.grid(row=3, column=7, sticky="w")
    ttk.Label(B2, text="Y位置(0-1)").grid(row=3, column=8, sticky="e")
    e_capy = tk.Entry(B2, width=6); e_capy.insert(0, "0.02"); e_capy.grid(row=3, column=9, sticky="w")

    # 共享 / 分图 色带
    C2 = ttk.LabelFrame(page2, text="色带选项")
    C2.grid(row=2, column=0, padx=6, pady=6, sticky="we")
    var_shared = tk.BooleanVar(value=True)
    ttk.Checkbutton(C2, text="使用共享色带（取消则每幅各自一条）", variable=var_shared).grid(row=0, column=0, sticky="w", columnspan=3)

    ttk.Label(C2, text="共享：位置/厚度占比/刻度数").grid(row=1, column=0, sticky="e")
    cb_loc2 = ttk.Combobox(C2, values=["bottom","top","right","left"], width=8, state="readonly"); cb_loc2.set("right"); cb_loc2.grid(row=1, column=1, sticky="w")
    e_cbfrac = tk.Entry(C2, width=6); e_cbfrac.insert(0, "0.10"); e_cbfrac.grid(row=1, column=2, sticky="w")
    e_ticks = tk.Entry(C2, width=6); e_ticks.insert(0, "6"); e_ticks.grid(row=1, column=3, sticky="w")
    ttk.Label(C2, text="共享：标签文本/字号/刻度字号").grid(row=1, column=4, sticky="e")
    e_cblabtxt2 = tk.Entry(C2, width=18); e_cblabtxt2.insert(0, ""); e_cblabtxt2.grid(row=1, column=5, sticky="w")
    e_cblab2 = tk.Entry(C2, width=6); e_cblab2.insert(0, "11"); e_cblab2.grid(row=1, column=6, sticky="w")
    e_cbtick2 = tk.Entry(C2, width=6); e_cbtick2.insert(0, "10"); e_cbtick2.grid(row=1, column=7, sticky="w")
    ttk.Label(C2, text="共享：色阶上限（空=自动）").grid(row=1, column=8, sticky="e")
    e_vmax = tk.Entry(C2, width=8); e_vmax.grid(row=1, column=9, sticky="w")

    # 分图参数（新增：各自最大值百分位与刻度个数；恢复：标签文本/字号/刻度字号）
    ttk.Label(C2, text="分图：位置/厚度%/与图距").grid(row=2, column=0, sticky="e")
    cb_per_loc = ttk.Combobox(C2, values=["right","left","top","bottom"], width=8, state="readonly"); cb_per_loc.set("right"); cb_per_loc.grid(row=2, column=1, sticky="w")
    e_per_size = tk.Entry(C2, width=6); e_per_size.insert(0, "1.6"); e_per_size.grid(row=2, column=2, sticky="w")
    e_per_pad  = tk.Entry(C2, width=6); e_per_pad.insert(0, "0.02"); e_per_pad.grid(row=2, column=3, sticky="w")

    ttk.Label(C2, text="分图：上限百分位(%)").grid(row=2, column=4, sticky="e")
    e_per_pct = tk.Entry(C2, width=6); e_per_pct.insert(0, "100"); e_per_pct.grid(row=2, column=5, sticky="w")

    ttk.Label(C2, text="分图：刻度个数").grid(row=2, column=6, sticky="e")
    e_per_nticks = tk.Entry(C2, width=6); e_per_nticks.insert(0, "6"); e_per_nticks.grid(row=2, column=7, sticky="w")

    ttk.Label(C2, text="分图：标签文本/字号/刻度字号").grid(row=3, column=0, sticky="e")
    e_per_labtxt = tk.Entry(C2, width=18); e_per_labtxt.insert(0, ""); e_per_labtxt.grid(row=3, column=1, sticky="w")
    e_per_lab = tk.Entry(C2, width=6); e_per_lab.insert(0, "11"); e_per_lab.grid(row=3, column=2, sticky="w")
    e_per_tick = tk.Entry(C2, width=6); e_per_tick.insert(0, "10"); e_per_tick.grid(row=3, column=3, sticky="w")

    # === 每幅配色（动态生成；仅在“取消共享色带”时展开） ===
    C3 = ttk.LabelFrame(page2, text="每幅配色（不统一时分别选择）")
    C3.grid(row=4, column=0, padx=6, pady=6, sticky="we")
    panel_cmap_boxes = []  # 动态 GradientCombo 列表

    def rebuild_panel_cmap_controls(*_):
        for w in C3.winfo_children():
            w.destroy()
        panel_cmap_boxes.clear()
        try:
            nrows, ncols = int(e_rows.get()), int(e_cols.get())
        except Exception:
            nrows, ncols = 0, 0
        total = max(0, nrows * ncols)

        if var_shared.get():
            ttk.Label(C3, text="已勾选【使用共享色带】。如需分别设置，请先取消该选项。", foreground="#666").grid(row=0, column=0, sticky="w", padx=4, pady=4)
            return

        ttk.Label(C3, text=f"面板数：{total}（按 行×列 = {nrows}×{ncols} 自动生成）").grid(row=0, column=0, columnspan=8, sticky="w", padx=4, pady=(2,6))
        per_row = 2 if ncols <= 2 else 3
        for i in range(total):
            r = 1 + (i // per_row)
            c = (i % per_row)
            cell = ttk.Frame(C3)
            cell.grid(row=r, column=c, padx=6, pady=4, sticky="w")
            ttk.Label(cell, text=f"面板 {i+1}").grid(row=0, column=0, sticky="e", padx=(0,6))
            gc = GradientCombo(cell, default_key=cb_cmap2.get(), width=240)
            gc.grid(row=0, column=1, sticky="w")
            panel_cmap_boxes.append(gc)

        # 批量操作
        def set_all_to_global():
            g = cb_cmap2.get()
            for cb in panel_cmap_boxes:
                cb.set(g)
        def copy_first_to_all():
            if not panel_cmap_boxes: return
            g = panel_cmap_boxes[0].get()
            for cb in panel_cmap_boxes[1:]:
                cb.set(g)
        btnf = ttk.Frame(C3)
        btnf.grid(row=(1 + (total-1)//per_row + 1), column=0, columnspan=per_row, sticky="w", pady=(6,2))
        ttk.Button(btnf, text="全设为全局配色", command=set_all_to_global).grid(row=0, column=0, padx=4)
        ttk.Button(btnf, text="复制第一个到全部", command=copy_first_to_all).grid(row=0, column=1, padx=4)

    # 事件：当 行/列/共享开关/全局配色 变化时，重建或更新默认值
    for w in (e_rows, e_cols):
        w.bind("<KeyRelease>", lambda e: rebuild_panel_cmap_controls())
        w.bind("<FocusOut>",  lambda e: rebuild_panel_cmap_controls())
    var_shared.trace_add("write", lambda *_: rebuild_panel_cmap_controls())
    cb_cmap2.bind("<<PaletteChanged>>", lambda e: rebuild_panel_cmap_controls())

    # =================================== 多图页：子图元素（比例尺 & 北箭） ===================================
    D2 = ttk.LabelFrame(page2, text="子图元素（比例尺 & 北箭）")
    D2.grid(row=3, column=0, padx=6, pady=6, sticky="we")

    # 比例尺：长度(单位)/字号/段数
    ttk.Label(D2, text="比例尺 长度(单位)/字号/段数").grid(row=0, column=0, sticky="e")
    e_sckm2 = tk.Entry(D2, width=8); e_sckm2.insert(0, "")
    e_sckm2.grid(row=0, column=1, sticky="w")
    e_scsize2 = tk.Entry(D2, width=6); e_scsize2.insert(0, "9")
    e_scsize2.grid(row=0, column=2, sticky="w")
    e_scseg2 = tk.Entry(D2, width=6); e_scseg2.insert(0, "4")
    e_scseg2.grid(row=0, column=3, sticky="w")

    # 线宽/边框/条高
    ttk.Label(D2, text="线宽/边框/条高").grid(row=0, column=4, sticky="e")
    e_sclw2 = tk.Entry(D2, width=6); e_sclw2.insert(0, "0.7")
    e_sclw2.grid(row=0, column=5, sticky="w")
    e_scedge2 = tk.Entry(D2, width=6); e_scedge2.insert(0, "0.6")
    e_scedge2.grid(row=0, column=6, sticky="w")
    e_sch2 = tk.Entry(D2, width=6); e_sch2.insert(0, "0.012")
    e_sch2.grid(row=0, column=7, sticky="w")

    # 左距/距底
    ttk.Label(D2, text="左距/距底").grid(row=0, column=8, sticky="e")
    e_scx2 = tk.Entry(D2, width=6); e_scx2.insert(0, "0.08")
    e_scx2.grid(row=0, column=9, sticky="w")
    e_scy2 = tk.Entry(D2, width=6); e_scy2.insert(0, "0.12")
    e_scy2.grid(row=0, column=10, sticky="w")

    # —— 新增：单位 & 空格 —— #
    ttk.Label(D2, text="单位").grid(row=0, column=11, sticky="e")
    e_scunit2 = tk.Entry(D2, width=6); e_scunit2.insert(0, "km")
    e_scunit2.grid(row=0, column=12, sticky="w")

    ttk.Label(D2, text="空格").grid(row=0, column=13, sticky="e")
    cb_scsp2 = ttk.Combobox(D2, values=["无","有"], width=4, state="readonly")
    cb_scsp2.set("无"); cb_scsp2.grid(row=0, column=14, sticky="w")

    # 北箭 字号/样式/距边
    ttk.Label(D2, text="北箭 字号/样式/距边").grid(row=1, column=0, sticky="e")
    e_nsize2 = tk.Entry(D2, width=6); e_nsize2.insert(0, "10")
    e_nsize2.grid(row=1, column=1, sticky="w")
    cb_nstyle2 = ttk.Combobox(D2, values=["triangle","arrow","compass"], width=10, state="readonly")
    cb_nstyle2.set("triangle"); cb_nstyle2.grid(row=1, column=2, sticky="w")
    e_npad2 = tk.Entry(D2, width=6); e_npad2.insert(0, "0.08")
    e_npad2.grid(row=1, column=3, sticky="w")

    E2 = ttk.LabelFrame(page2, text="预览 / 导出")
    E2.grid(row=5, column=0, padx=6, pady=6, sticky="we")
    ttk.Label(E2, text="预览 宽×高 / DPI").grid(row=0, column=0, sticky="e")
    e_figw2 = tk.Entry(E2, width=6); e_figw2.insert(0, "11.5"); e_figw2.grid(row=0, column=1, sticky="w")
    e_figh2 = tk.Entry(E2, width=6); e_figh2.insert(0, "8.8"); e_figh2.grid(row=0, column=2, sticky="w")
    e_dpi2  = tk.Entry(E2, width=6); e_dpi2.insert(0, "130"); e_dpi2.grid(row=0, column=3, sticky="w")

    def _parse_tif_list():
        return [ln.strip() for ln in txt_list.get("1.0","end").splitlines() if ln.strip()]
    def _get_multi_shp():
        shp_multi = e_shp2.get().strip()
        return (shp_multi if shp_multi else e_shp1.get().strip(),
                "边界SHP（多图）" if shp_multi else "边界SHP（单图）")

    def preview_grid():
        # —— 基本校验 ——
        shp, label = _get_multi_shp()
        if not shp:
            messagebox.showerror("缺少输入", f"请指定{label}。");
            return
        if not os.path.exists(shp):
            messagebox.showerror("路径无效", f"{label}不存在：\n{shp}");
            return

        tlist = _parse_tif_list()
        if not tlist:
            messagebox.showerror("缺少输入", "TIF列表为空。");
            return

        nrows, ncols = _get_int(e_rows, 2), _get_int(e_cols, 2)
        if len(tlist) != nrows * ncols:
            messagebox.showerror("数量不符", f"TIF个数={len(tlist)}，行×列={nrows * ncols}。");
            return

        titles = [s.strip() for s in e_titles.get().split("|")] if e_titles.get().strip() else None
        save_state()

        # —— 读取画布尺寸（英寸）和基准 DPI ——
        fig_w_in = _get_float(e_figw2, 11.5)
        fig_h_in = _get_float(e_figh2, 8.8)
        dpi_base = _get_int(e_dpi2, 130)

        # —— 预览像素框（工具条右侧）→ 计算预览用 DPI（只作用于预览） ——
        px_w = _get_int(e_prev_w2, None)  # e_prev_w2/e_prev_h2 由你在工具条里创建
        px_h = _get_int(e_prev_h2, None)

        dpi_eff = dpi_base
        cand = []
        if px_w is not None and fig_w_in:
            cand.append(px_w / float(fig_w_in))
        if px_h is not None and fig_h_in:
            cand.append(px_h / float(fig_h_in))
        if cand:
            # 给个合理范围，避免太夸张
            dpi_eff = int(max(50, min(800, min(cand))))

        make_grid_map(
            # 数据与时间
            tif_list=tlist, border_shp=shp, overlay_layers=parse_overlay(),
            year_start=_get_int(e_y1, 1981), year_end=_get_int(e_y2, 2020), as_yearly=var_avg.get(),

            # 字体
            font_en=cb_font_en.get(), font_zh=cb_font_zh.get(),

            # 布局与标题
            nrows=nrows, ncols=ncols, panel_titles=titles,
            caption=e_caption.get().strip(), caption_size=_get_int(e_capsize, 12), caption_y=_get_float(e_capy, 0.02),
            title_size=_get_int(e_tsz2, 11), title_pad=_get_float(e_tpad2, 5),

            # 边界/色带（主色带 + 面板色带）
            border_lw=_get_float(e_bdlw, 0.8),
            cmap_key=cb_cmap2.get(),
            panel_cmaps=([cb.get() for cb in panel_cmap_boxes] if not var_shared.get() else None),

            # 共享/分图色带控制
            share_vmax=_get_float(e_vmax, None),  # 共享上限：空=自动（全局真实最大值）
            use_shared_cbar=var_shared.get(),
            shared_cbar_loc=cb_loc2.get(),
            shared_cbar_label_text=(e_cblabtxt2.get().strip() or None),
            shared_cbar_label_size=_get_int(e_cblab2, 11),
            shared_cbar_tick_size=_get_int(e_cbtick2, 10),
            shared_cbar_ticks=_get_int(e_ticks, 6),

            per_cbar_loc=cb_per_loc.get(),
            per_cbar_pad=_get_float(e_per_pad, 0.04),
            per_cbar_label_text=(e_per_labtxt.get().strip() or None),
            per_cbar_label_size=_get_int(e_per_lab, 11),
            per_cbar_tick_size=_get_int(e_per_tick, 10),
            per_cbar_ticks=_get_int(e_per_nticks, 6),
            # 关键：留空(None) = 用每幅真实最大值；填 98/95 等才按百分位
            per_vmax_percentile=_get_float(e_per_pct, None),

            # —— 比例尺（参数名已映射到绘图层）——
            # —— 比例尺（对齐 plotting.make_grid_map 新接口）——
            scale_length=_get_float(e_sckm2, None),
            scale_unit=(e_scunit2.get().strip() or "km"),
            scale_unit_sep=(" " if cb_scsp2.get() == "有" else ""),
            scale_segments=_get_int(e_scseg2, 4),
            scale_bar_h=_get_float(e_sch2, 0.012),
            scale_edge_lw=_get_float(e_scedge2, 0.6),
            scale_line_lw=_get_float(e_sclw2, 0.7),
            scale_txt_size=_get_int(e_scsize2, 9),
            scale_anchor="SW",
            scale_pad_x=_get_float(e_scx2, 0.08),
            scale_pad_y=_get_float(e_scy2, 0.12),

            # —— 北箭（对齐新接口）——
            north_style=cb_nstyle2.get(),
            north_size_frac=0.06,
            north_anchor="NE",
            north_pad_x=_get_float(e_npad2, 0.08),
            north_pad_y=_get_float(e_npad2, 0.08),
            north_txt_size=_get_int(e_nsize2, 10),

            # 画布尺寸 + 预览用 DPI
            fig_w=fig_w_in, fig_h=fig_h_in, dpi=dpi_eff,
            wspace=_get_float(e_wspace, 0.12), hspace=_get_float(e_hspace, 0.22),

            preview=True
        )

    def export_grid():
        shp, label = _get_multi_shp()
        if not shp:
            messagebox.showerror("缺少输入", f"请指定{label}。"); return
        if not os.path.exists(shp):
            messagebox.showerror("路径无效", f"{label}不存在：\n{shp}"); return
        tlist = _parse_tif_list()
        if not tlist:
            messagebox.showerror("缺少输入","TIF列表为空。"); return
        nrows, ncols = int(e_rows.get()), int(e_cols.get())
        if len(tlist) != nrows*ncols:
            messagebox.showerror("数量不符", f"TIF个数={len(tlist)}，行×列={nrows*ncols}。"); return
        vmax = float(e_vmax.get()) if e_vmax.get().strip() else None
        titles = [s.strip() for s in e_titles.get().split("|")] if e_titles.get().strip() else None
        save_state()

        make_grid_map(
            tif_list=tlist, border_shp=shp, overlay_layers=parse_overlay(),
            year_start=int(e_y1.get()), year_end=int(e_y2.get()), as_yearly=var_avg.get(),
            font_en=cb_font_en.get(),  # 改回 font_en（与函数定义匹配）
            font_zh=cb_font_zh.get(),  # 保持 font_zh（与单图函数一致）


            nrows=nrows, ncols=ncols, panel_titles=titles,
            caption=e_caption.get().strip(), caption_size=int(e_capsize.get()), caption_y=float(e_capy.get()),
            title_size=int(e_tsz2.get()), title_pad=float(e_tpad2.get()),

            border_lw=float(e_bdlw.get()),
            cmap_key=cb_cmap2.get(),
            panel_cmaps=([cb.get() for cb in panel_cmap_boxes] if not var_shared.get() else None),
            share_vmax=vmax,

            use_shared_cbar=var_shared.get(),
            shared_cbar_loc=cb_loc2.get(), shared_cbar_frac=float(e_cbfrac.get()),
            shared_cbar_label_text=(e_cblabtxt2.get().strip() or None),
            shared_cbar_label_size=int(e_cblab2.get()), shared_cbar_tick_size=int(e_cbtick2.get()),
            shared_cbar_ticks=int(e_ticks.get()),

            per_cbar_loc=cb_per_loc.get(), per_cbar_size=f"{float(e_per_size.get())}%",
            per_cbar_pad=float(e_per_pad.get()), per_cbar_label_text=(e_per_labtxt.get().strip() or None),
            per_cbar_label_size=int(e_per_lab.get()), per_cbar_tick_size=int(e_per_tick.get()),
            per_cbar_ticks=int(e_per_nticks.get() or 6),
            per_use_auto_vmax=True, per_vmax_percentile=(float(e_per_pct.get()) if e_per_pct.get().strip() else None),

            # 比例尺（对所有子图）
            scale_length=(float(e_sckm2.get()) if e_sckm2.get().strip() else None),
            scale_unit=(e_scunit2.get().strip() or "km"),
            scale_unit_sep=(" " if cb_scsp2.get()=="有" else ""),
            scale_segments=int(e_scseg2.get()),
            scale_bar_h=float(e_sch2.get()),
            scale_edge_lw=float(e_scedge2.get()),
            scale_line_lw=float(e_sclw2.get()),
            scale_txt_size=int(e_scsize2.get()),
            scale_anchor="SW",
            scale_pad_x=float(e_scx2.get()),
            scale_pad_y=float(e_scy2.get()),

            # 北箭
            north_style=cb_nstyle2.get(),
            north_size_frac=0.06,
            north_anchor="NE",
            north_pad_x=float(e_npad2.get()),
            north_pad_y=float(e_npad2.get()),
            north_txt_size=int(e_nsize2.get()),

            wspace=float(e_wspace.get()), hspace=float(e_hspace.get()),
            fig_w=float(e_figw2.get()), fig_h=float(e_figh2.get()), dpi=int(e_dpi2.get()),
            save_png=e_png2.get().strip(), save_pdf=e_pdf2.get().strip(), preview=False

        )

    # 工具条容器：独立一行，避免和右侧输入控件冲突
    # 工具条：预览/导出/自动预览 + 预览大小(px)
    bar2 = ttk.Frame(E2)
    bar2.grid(row=0, column=0, columnspan=20, sticky="ew", pady=(2, 6))
    bar2.grid_columnconfigure(99, weight=1)  # 右侧留弹性空白

    ttk.Button(bar2, text="预览多图", command=preview_grid).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(bar2, text="导出多图", command=export_grid).grid(row=0, column=1, padx=(0, 16))
    ttk.Checkbutton(bar2, text="自动预览", variable=var_autoprev).grid(row=0, column=2, padx=(0, 16))

    # <<< 新增：预览像素大小 >>>
    ttk.Label(bar2, text="预览(px)").grid(row=0, column=3, padx=(0, 6))
    e_prev_w2 = tk.Entry(bar2, width=6);
    e_prev_w2.insert(0, "")  # 例如可填 1200
    e_prev_w2.grid(row=0, column=4)
    ttk.Label(bar2, text="×").grid(row=0, column=5, padx=4)
    e_prev_h2 = tk.Entry(bar2, width=6);
    e_prev_h2.insert(0, "")  # 例如可填 900
    e_prev_h2.grid(row=0, column=6)

    # ------- 注册控件 -------
    entries = {
        "e_y1": e_y1, "e_y2": e_y2, "e_bdlw": e_bdlw,
        "e_ol_def_col": e_ol_def_col, "e_ol_def_lw": e_ol_def_lw, "e_ol_def_ms": e_ol_def_ms,
        "e_tif": e_tif, "e_shp1": e_shp1, "e_png1": e_png1, "e_pdf1": e_pdf1,
        "e_title": e_title, "e_tsize": e_tsize, "e_tpad": e_tpad,
        "e_figw1": e_figw1, "e_figh1": e_figh1, "e_dpi1": e_dpi1,
        "e_cbw": e_cbw, "e_cbpad": e_cbpad, "e_cblabtxt1": e_cblabtxt1, "e_cblab1": e_cblab1, "e_cbtick1": e_cbtick1,
        "e_sckm1": e_sckm1, "e_scsize1": e_scsize1, "e_scseg1": e_scseg1,
        "e_sclw1": e_sclw1, "e_scedge1": e_scedge1, "e_sch1": e_sch1,
        "e_scx1": e_scx1, "e_scy1": e_scy1, "e_nsize1": e_nsize1, "e_npad1": e_npad1,
        "e_scunit1": e_scunit1,"e_vmax1": e_vmax1,
        "e_prev_w1": e_prev_w1,"e_prev_h1": e_prev_h1,

        "e_shp2": e_shp2, "e_png2": e_png2, "e_pdf2": e_pdf2,
        "e_rows": e_rows, "e_cols": e_cols, "e_wspace": e_wspace, "e_hspace": e_hspace,
        "e_titles": e_titles, "e_tsz2": e_tsz2, "e_tpad2": e_tpad2,
        "e_caption": e_caption, "e_capsize": e_capsize, "e_capy": e_capy,
        "e_cbfrac": e_cbfrac, "e_ticks": e_ticks, "e_cblabtxt2": e_cblabtxt2, "e_cblab2": e_cblab2, "e_cbtick2": e_cbtick2,
        "e_vmax": e_vmax, "e_per_size": e_per_size, "e_per_pad": e_per_pad,
        "e_per_labtxt": e_per_labtxt, "e_per_lab": e_per_lab, "e_per_tick": e_per_tick,
        "e_sckm2": e_sckm2, "e_scsize2": e_scsize2, "e_scseg2": e_scseg2,
        "e_sclw2": e_sclw2, "e_scedge2": e_scedge2, "e_sch2": e_sch2,
        "e_scx2": e_scx2, "e_scy2": e_scy2, "e_nsize2": e_nsize2, "e_npad2": e_npad2,
        "e_figw2": e_figw2, "e_figh2": e_figh2, "e_dpi2": e_dpi2,
        "e_scunit2": e_scunit2,
        "e_per_pct": e_per_pct, "e_per_nticks": e_per_nticks,
    }
    combos = {
        "cb_font_en": cb_font_en,"cb_font_zh": cb_font_zh, "cb_loc1": cb_loc1, "cb_nstyle1": cb_nstyle1,
        "cb_loc2": cb_loc2, "cb_per_loc": cb_per_loc, "cb_nstyle2": cb_nstyle2,
        "cb_cmap1": cb_cmap1, "cb_cmap2": cb_cmap2,
        "cb_scsp1": cb_scsp1, "cb_scsp2": cb_scsp2,
    }
    checks = { "var_avg": var_avg, "var_shared": var_shared }
    texts = { "txt_overlay": txt_overlay, "txt_list": txt_list }
    # --- 自动预览：当字体/色带变更时，若当前页启用自动预览则即时刷新 ---
    def _autoprev_single(*_):
        if var_autoprev.get():
            preview_single()
    def _autoprev_grid(*_):
        if var_autoprev.get():
            preview_grid()

    # 字体改变 -> 自动预览（根据当前选中的页判断）
    def _route_auto_preview(*_):
        try:
            cur = nb.index(nb.select())
        except Exception:
            cur = 0
        if cur == 0:
            _autoprev_single()
        else:
            _autoprev_grid()

    cb_font_en.bind("<<ComboboxSelected>>", _route_auto_preview)
    cb_font_zh.bind("<<ComboboxSelected>>", _route_auto_preview)
    cb_cmap1.bind("<<PaletteChanged>>",   lambda e: _autoprev_single())
    cb_cmap2.bind("<<PaletteChanged>>",   lambda e: _autoprev_grid())


    # ------- 默认值 -------
    DEFAULT_ENTRIES = {
        "e_y1":"1981","e_y2":"2020","e_bdlw":"0.8",
        "e_ol_def_col":"#1f77b4","e_ol_def_lw":"0.8","e_ol_def_ms":"6",
        "e_tif":"", "e_shp1":"", "e_png1":r"E:\map_outputs\single.png","e_pdf1":r"E:\map_outputs\single.pdf",
        "e_title":"(b) WD 暖干（平均发生天数）","e_tsize":"12","e_tpad":"6",
        "e_figw1":"8.8","e_figh1":"6.6","e_dpi1":"150",
        "e_cbw":"1.6","e_cbpad":"0.02","e_cblabtxt1":"","e_cblab1":"11","e_cbtick1":"10",
        "e_sckm1":"", "e_scsize1":"9","e_scseg1":"4",
        "e_sclw1":"0.7","e_scedge1":"0.6","e_sch1":"0.012",
        "e_scx1":"0.08","e_scy1":"0.12","e_nsize1":"10","e_npad1":"0.08",
        "e_scunit1":"km","e_vmax1":"","e_prev_w1": "","e_prev_h1": "",

        "e_shp2":"", "e_png2":r"E:\map_outputs\compound_2x2.png","e_pdf2":r"E:\map_outputs\compound_2x2.pdf",
        "e_rows":"2","e_cols":"2","e_wspace":"0.12","e_hspace":"0.22",
        "e_titles":"(a) WW 暖湿|(b) WD 暖干|(c) CW 冷湿|(d) CD 冷干",
        "e_tsz2":"11","e_tpad2":"5",
        "e_caption":"复合极端事件多年平均发生天数（1981–2020）","e_capsize":"12","e_capy":"0.02",
        "e_cbfrac":"0.10","e_ticks":"6","e_cblabtxt2":"","e_cblab2":"11","e_cbtick2":"10",
        "e_vmax":"", "e_per_size":"1.6","e_per_pad":"0.02",
        "e_sckm2":"", "e_scsize2":"9","e_scseg2":"4",
        "e_sclw2":"0.7","e_scedge2":"0.6","e_sch2":"0.012",
        "e_scx2":"0.08","e_scy2":"0.12","e_nsize2":"10","e_npad2":"0.08",
        "e_figw2":"11.5","e_figh2":"8.8","e_dpi2":"130",
        "e_scunit2":"km",
        "e_per_pct":"", "e_per_nticks":"6",
        "e_per_labtxt":"", "e_per_lab":"11", "e_per_tick":"10",
    }
    DEFAULT_COMBOS = {
        "cb_font_en": "Times New Roman","cb_font_zh": "Microsoft YaHei", "cb_loc1":"right", "cb_nstyle1":"triangle",
        "cb_loc2":"right", "cb_per_loc":"right", "cb_nstyle2":"triangle",
        "cb_scsp1":"无", "cb_scsp2":"无",
    }
    DEFAULT_CHECKS = { "var_avg": True, "var_shared": True }
    DEFAULT_TEXTS = { "txt_overlay":"", "txt_list":"" }

    # 启动时加载历史状态（如有），并构建每幅配色模块
    apply_defaults()
    load_state()
    rebuild_panel_cmap_controls()

    root.mainloop()


if __name__ == "__main__":
    run_app()
