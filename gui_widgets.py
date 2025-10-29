# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from .colormaps import CMAP_REGISTRY, resolve_cmap
from .config import DEFAULT_CMAP_KEY

# 纯 Tk PhotoImage 渐变，不依赖 PIL
_GRAD_IMG_CACHE = {}  # (key,w,h)->PhotoImage
def make_gradient_image(cmap_key, width=120, height=14):
    key = (cmap_key, width, height)
    if key in _GRAD_IMG_CACHE:
        return _GRAD_IMG_CACHE[key]
    cmap = resolve_cmap(cmap_key)
    img = tk.PhotoImage(width=width, height=height)
    for x in range(width):
        v = x/(width-1) if width>1 else 0
        r,g,b,_ = cmap(v)
        r,g,b = int(round(255*r)), int(round(255*g)), int(round(255*b))
        color = f"#{r:02x}{g:02x}{b:02x}"
        for y in range(height):
            img.put(color, (x, y))
    border = "#d0d0d0"
    for x in range(width):
        img.put(border, (x, 0)); img.put(border, (x, height-1))
    for y in range(height):
        img.put(border, (0, y)); img.put(border, (width-1, y))
    _GRAD_IMG_CACHE[key] = img
    return img

class GradientCombo(tk.Frame):
    """像 Combobox 一样：get()/set()；但下拉菜单每项带渐变缩略图。"""
    def __init__(self, master, default_key=DEFAULT_CMAP_KEY, width=200, **kw):
        super().__init__(master, **kw)
        self._value = tk.StringVar(value=default_key if default_key in CMAP_REGISTRY else DEFAULT_CMAP_KEY)
        self._text = tk.StringVar(value=CMAP_REGISTRY.get(self._value.get(), {"name":self._value.get()})["name"])
        self._img = make_gradient_image(self._value.get(), width=96, height=14)
        self._btn = tk.Menubutton(self, textvariable=self._text, image=self._img, compound="left",
                                  relief="groove", anchor="w", width=width//8)
        self._btn.grid(row=0, column=0, sticky="we")
        self.columnconfigure(0, weight=1)

        self._menu = tk.Menu(self._btn, tearoff=0)
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
        if key not in CMAP_REGISTRY:
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
        self.tip = tw = tk.Toplevel(self.widget); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify="left", relief="solid",
                         borderwidth=1, background="#ffffe0", wraplength=self.wrap)
        label.pack(ipadx=6, ipady=4)
    def hide(self, _=None):
        if self.tip: self.tip.destroy(); self.tip=None

def qmark(parent, tip, r, c):
    lab = tk.Label(parent, text="？", fg="#444", cursor="question_arrow")
    lab.grid(row=r, column=c, sticky="w", padx=(2,6))
    ToolTip(lab, tip)
