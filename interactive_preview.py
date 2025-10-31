# -*- coding: utf-8 -*-
"""
交互式预览窗口 - 支持实时调整色带和比例尺位置
"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import os

# 位置调整参数的默认值和范围
DEFAULT_ADJUSTMENTS = {
    # 色带位置调整（相对于figure的偏移量）
    "cbar_offset_y": 0.0,  # 垂直偏移（-0.1 到 0.1）
    "cbar_offset_x": 0.0,  # 水平偏移（-0.1 到 0.1）
    
    # 比例尺位置调整
    "scale_offset_x": 0.0,  # 水平偏移（-0.2 到 0.2）
    "scale_offset_y": 0.0,  # 垂直偏移（-0.2 到 0.2）
    
    # 北箭位置调整
    "north_offset_x": 0.0,  # 水平偏移（-0.2 到 0.2）
    "north_offset_y": 0.0,  # 垂直偏移（-0.2 到 0.2）
}

ADJUSTMENT_FILE = "position_adjustments.json"


def load_adjustments():
    """加载保存的位置调整参数"""
    if os.path.exists(ADJUSTMENT_FILE):
        try:
            with open(ADJUSTMENT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_ADJUSTMENTS.copy()


def save_adjustments(adjustments):
    """保存位置调整参数"""
    try:
        with open(ADJUSTMENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(adjustments, f, indent=2)
    except Exception as e:
        print(f"保存位置调整参数失败: {e}")


class InteractivePreviewWindow:
    """交互式预览窗口 - 支持键盘快捷键调整元素位置"""
    
    def __init__(self, fig, redraw_callback, is_grid=False):
        """
        参数:
            fig: matplotlib figure对象
            redraw_callback: 重绘回调函数，接受adjustments字典作为参数
            is_grid: 是否为多图模式
        """
        self.fig = fig
        self.redraw_callback = redraw_callback
        self.is_grid = is_grid
        self.adjustments = load_adjustments()

        # 保存初始视图范围（用于恢复）
        self.initial_view_limits = {}
        self.view_lock_active = True

        # 创建窗口
        self.window = tk.Toplevel()
        self.window.title("交互式预览 - 使用方向键或按钮调整位置")

        # 设置窗口关闭处理（关键修复：确保资源释放）
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 设置窗口大小 - 固定合理大小，避免界面放大问题
        window_width = 1200
        window_height = 700

        # 居中显示
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 禁止调整窗口大小（避免界面混乱）
        self.window.resizable(False, False)

        # 强制窗口显示在最前面
        self.window.lift()
        self.window.focus_force()
        
        # 创建主容器
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧：图形显示区域
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)

        # 关键修复：完全禁用matplotlib的所有键盘绑定
        # 这些绑定会导致箭头键触发导航功能（缩放/平移）
        for key in ['keymap.home', 'keymap.back', 'keymap.forward', 'keymap.pan',
                    'keymap.zoom', 'keymap.save', 'keymap.fullscreen', 'keymap.grid',
                    'keymap.grid_minor', 'keymap.xscale', 'keymap.yscale', 'keymap.quit']:
            mpl.rcParams[key] = []  # 清空所有键盘绑定

        # 禁用matplotlib的导航工具栏
        self.canvas.toolbar = None

        # 禁用所有axes的导航和自动缩放，并保存初始视图范围
        for ax in self.fig.get_axes():
            ax.set_navigate(False)
            ax.set_autoscale_on(False)
            # 保存初始视图范围
            self.initial_view_limits[ax] = {
                'xlim': ax.get_xlim(),
                'ylim': ax.get_ylim()
            }

        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 启动视图锁定定时器
        self._start_view_lock_timer()
        
        # 右侧：控制面板
        right_frame = ttk.Frame(main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        right_frame.pack_propagate(False)
        
        # 创建控制面板
        self._create_control_panel(right_frame)
        
        # 绑定键盘事件到窗口（而不是canvas）
        self.window.bind('<Key>', self._on_key_press)
        self.window.focus_set()
        
        # 状态标签
        self.status_label = ttk.Label(self.window, text="使用方向键或按钮调整位置 | 视图锁定: 开启",
                                     relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # 当前调整模式
        self.adjust_mode = "colorbar"  # colorbar, scale, north

        # 操作计数器（用于反馈）
        self.operation_count = 0
        
    def _create_control_panel(self, parent):
        """创建控制面板"""
        # 标题
        title = ttk.Label(parent, text="位置微调控制", font=('Arial', 12, 'bold'))
        title.pack(pady=10)

        # 模式选择
        mode_frame = ttk.LabelFrame(parent, text="调整对象", padding=10)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)

        self.mode_var = tk.StringVar(value="colorbar")

        # 使用更醒目的样式
        rb1 = ttk.Radiobutton(mode_frame, text="🎨 色带位置", variable=self.mode_var,
                             value="colorbar", command=self._update_mode)
        rb1.pack(anchor=tk.W, pady=2)

        rb2 = ttk.Radiobutton(mode_frame, text="📏 比例尺位置", variable=self.mode_var,
                             value="scale", command=self._update_mode)
        rb2.pack(anchor=tk.W, pady=2)

        rb3 = ttk.Radiobutton(mode_frame, text="🧭 北箭位置", variable=self.mode_var,
                             value="north", command=self._update_mode)
        rb3.pack(anchor=tk.W, pady=2)

        # 方向控制按钮
        direction_frame = ttk.LabelFrame(parent, text="方向控制", padding=10)
        direction_frame.pack(fill=tk.X, padx=5, pady=5)

        # 步长选择
        step_control = ttk.Frame(direction_frame)
        step_control.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(step_control, text="步长:").pack(side=tk.LEFT)
        self.step_var = tk.StringVar(value="normal")
        ttk.Radiobutton(step_control, text="小", variable=self.step_var,
                       value="small").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(step_control, text="中", variable=self.step_var,
                       value="normal").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(step_control, text="大", variable=self.step_var,
                       value="large").pack(side=tk.LEFT, padx=2)

        # 方向按钮布局（十字形）
        btn_grid = ttk.Frame(direction_frame)
        btn_grid.pack(pady=5)

        # 上
        ttk.Button(btn_grid, text="▲", width=5,
                  command=lambda: self._move_direction('up')).grid(row=0, column=1, padx=2, pady=2)
        # 左
        ttk.Button(btn_grid, text="◀", width=5,
                  command=lambda: self._move_direction('left')).grid(row=1, column=0, padx=2, pady=2)
        # 中心（重置当前）
        ttk.Button(btn_grid, text="●", width=5,
                  command=self._reset_current).grid(row=1, column=1, padx=2, pady=2)
        # 右
        ttk.Button(btn_grid, text="▶", width=5,
                  command=lambda: self._move_direction('right')).grid(row=1, column=2, padx=2, pady=2)
        # 下
        ttk.Button(btn_grid, text="▼", width=5,
                  command=lambda: self._move_direction('down')).grid(row=2, column=1, padx=2, pady=2)

        # 操作反馈显示
        self.feedback_label = ttk.Label(direction_frame, text="等待操作...",
                                       foreground="blue", font=('Arial', 9))
        self.feedback_label.pack(pady=5)
        
        # 视图控制
        view_frame = ttk.LabelFrame(parent, text="视图控制", padding=10)
        view_frame.pack(fill=tk.X, padx=5, pady=5)

        self.view_lock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(view_frame, text="🔒 锁定视图（防止缩放）",
                       variable=self.view_lock_var,
                       command=self._toggle_view_lock).pack(anchor=tk.W, pady=2)

        ttk.Button(view_frame, text="🔄 恢复视图",
                  command=self._restore_view).pack(fill=tk.X, pady=2)

        # 视图状态显示
        self.view_status_label = ttk.Label(view_frame, text="视图状态: 正常",
                                          foreground="green", font=('Arial', 9))
        self.view_status_label.pack(pady=2)
        
        # 当前偏移量显示
        self.offset_frame = ttk.LabelFrame(parent, text="当前偏移量", padding=10)
        self.offset_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.offset_labels = {}
        for key in ["cbar_offset_y", "cbar_offset_x", "scale_offset_x", 
                    "scale_offset_y", "north_offset_x", "north_offset_y"]:
            label = ttk.Label(self.offset_frame, text=f"{key}: {self.adjustments[key]:.3f}")
            label.pack(anchor=tk.W)
            self.offset_labels[key] = label
        
        # 按钮区域
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=10)

        ttk.Button(button_frame, text="💾 保存图片",
                  command=self._save_image_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="💾 保存位置设置",
                  command=self._save_positions).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="🔄 重置所有位置",
                  command=self._reset_all).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="❌ 关闭",
                  command=self.window.destroy).pack(fill=tk.X, pady=2)
        
    def _update_mode(self):
        """更新调整模式"""
        self.adjust_mode = self.mode_var.get()
        mode_names = {"colorbar": "🎨 色带", "scale": "📏 比例尺", "north": "🧭 北箭"}
        mode_name = mode_names[self.adjust_mode]
        self.status_label.config(text=f"当前调整: {mode_name} | 视图锁定: {'开启' if self.view_lock_active else '关闭'}")
        self._show_feedback(f"已切换到 {mode_name}", "info")

    def _move_direction(self, direction):
        """通过按钮移动元素"""
        # 获取步长
        step_map = {"small": 0.005, "normal": 0.01, "large": 0.05}
        step = step_map.get(self.step_var.get(), 0.01)

        mode_names = {"colorbar": "色带", "scale": "比例尺", "north": "北箭"}
        mode_name = mode_names[self.adjust_mode]

        # 根据方向和模式调整位置
        moved = False
        if self.adjust_mode == "colorbar":
            if direction == 'up':
                self.adjustments["cbar_offset_y"] += step
                moved = True
            elif direction == 'down':
                self.adjustments["cbar_offset_y"] -= step
                moved = True
            elif direction == 'left':
                self.adjustments["cbar_offset_x"] -= step
                moved = True
            elif direction == 'right':
                self.adjustments["cbar_offset_x"] += step
                moved = True

        elif self.adjust_mode == "scale":
            if direction == 'up':
                self.adjustments["scale_offset_y"] += step
                moved = True
            elif direction == 'down':
                self.adjustments["scale_offset_y"] -= step
                moved = True
            elif direction == 'left':
                self.adjustments["scale_offset_x"] -= step
                moved = True
            elif direction == 'right':
                self.adjustments["scale_offset_x"] += step
                moved = True

        elif self.adjust_mode == "north":
            if direction == 'up':
                self.adjustments["north_offset_y"] += step
                moved = True
            elif direction == 'down':
                self.adjustments["north_offset_y"] -= step
                moved = True
            elif direction == 'left':
                self.adjustments["north_offset_x"] -= step
                moved = True
            elif direction == 'right':
                self.adjustments["north_offset_x"] += step
                moved = True

        if moved:
            self.operation_count += 1
            direction_names = {'up': '上', 'down': '下', 'left': '左', 'right': '右'}
            self._show_feedback(f"✓ {mode_name}向{direction_names[direction]}移动 (步长: {step:.3f})", "success")
            self._update_display()
            self._update_offset_labels()
        else:
            self._show_feedback(f"✗ 移动失败", "error")

    def _show_feedback(self, message, msg_type="info"):
        """显示操作反馈"""
        colors = {
            "success": "green",
            "error": "red",
            "warning": "orange",
            "info": "blue"
        }
        self.feedback_label.config(text=message, foreground=colors.get(msg_type, "blue"))
        # 3秒后恢复默认文本
        self.window.after(3000, lambda: self.feedback_label.config(text="等待操作...", foreground="blue"))
        
    def _on_key_press(self, event):
        """处理键盘事件"""
        step = 0.01  # 默认步长
        step_name = "中"
        if event.state & 0x0001:  # Shift键
            step = 0.05  # 大步长
            step_name = "大"

        redraw = False
        direction = None

        # Tab键切换模式
        if event.keysym == 'Tab':
            modes = ["colorbar", "scale", "north"]
            current_idx = modes.index(self.adjust_mode)
            self.adjust_mode = modes[(current_idx + 1) % len(modes)]
            self.mode_var.set(self.adjust_mode)
            self._update_mode()
            return

        mode_names = {"colorbar": "色带", "scale": "比例尺", "north": "北箭"}
        mode_name = mode_names.get(self.adjust_mode, "")

        # 方向键调整位置
        if self.adjust_mode == "colorbar":
            if event.keysym == 'Up':
                self.adjustments["cbar_offset_y"] += step
                redraw = True
                direction = "上"
            elif event.keysym == 'Down':
                self.adjustments["cbar_offset_y"] -= step
                redraw = True
                direction = "下"
            elif event.keysym == 'Left':
                self.adjustments["cbar_offset_x"] -= step
                redraw = True
                direction = "左"
            elif event.keysym == 'Right':
                self.adjustments["cbar_offset_x"] += step
                redraw = True
                direction = "右"

        elif self.adjust_mode == "scale":
            if event.keysym == 'Up':
                self.adjustments["scale_offset_y"] += step
                redraw = True
                direction = "上"
            elif event.keysym == 'Down':
                self.adjustments["scale_offset_y"] -= step
                redraw = True
                direction = "下"
            elif event.keysym == 'Left':
                self.adjustments["scale_offset_x"] -= step
                redraw = True
                direction = "左"
            elif event.keysym == 'Right':
                self.adjustments["scale_offset_x"] += step
                redraw = True
                direction = "右"

        elif self.adjust_mode == "north":
            if event.keysym == 'Up':
                self.adjustments["north_offset_y"] += step
                redraw = True
                direction = "上"
            elif event.keysym == 'Down':
                self.adjustments["north_offset_y"] -= step
                redraw = True
                direction = "下"
            elif event.keysym == 'Left':
                self.adjustments["north_offset_x"] -= step
                redraw = True
                direction = "左"
            elif event.keysym == 'Right':
                self.adjustments["north_offset_x"] += step
                redraw = True
                direction = "右"

        # 其他快捷键
        if event.keysym == 'r' and event.state & 0x0004:  # Ctrl+R
            self._reset_all()
            return
        elif event.keysym == 'r':
            self._reset_current()
            return
        elif event.keysym == 's':
            self._save_positions()
            return
        elif event.keysym == 'h':
            self._show_help()
            return

        # 重绘图形
        if redraw:
            self.operation_count += 1
            self._show_feedback(f"✓ {mode_name}向{direction}移动 (键盘, 步长{step_name}: {step:.3f})", "success")
            self._update_display()
            self._update_offset_labels()
    
    def _update_display(self):
        """更新图形显示"""
        try:
            # 调用重绘回调
            new_fig = self.redraw_callback(self.adjustments)
            if new_fig:
                # 保存旧的视图范围
                old_limits = {}
                for ax in self.fig.get_axes():
                    if ax in self.initial_view_limits:
                        old_limits[ax] = self.initial_view_limits[ax]

                # 禁用新figure所有axes的导航和自动缩放
                for i, ax in enumerate(new_fig.get_axes()):
                    ax.set_navigate(False)
                    ax.set_autoscale_on(False)

                    # 恢复视图范围
                    old_axes = list(old_limits.keys())
                    if i < len(old_axes):
                        old_ax = old_axes[i]
                        if old_ax in old_limits:
                            ax.set_xlim(old_limits[old_ax]['xlim'])
                            ax.set_ylim(old_limits[old_ax]['ylim'])
                            # 更新初始视图范围映射
                            self.initial_view_limits[ax] = old_limits[old_ax]

                # 更新figure
                self.fig = new_fig
                self.canvas.figure = new_fig

                # 重绘
                self.canvas.draw()

                # 立即锁定视图
                if self.view_lock_active:
                    self._lock_view()

        except Exception as e:
            self.status_label.config(text=f"更新失败: {str(e)}")
            self._show_feedback(f"✗ 更新失败: {str(e)}", "error")
    
    def _update_offset_labels(self):
        """更新偏移量显示"""
        for key, label in self.offset_labels.items():
            label.config(text=f"{key}: {self.adjustments[key]:.3f}")
    
    def _reset_current(self):
        """重置当前对象的位置"""
        mode_names = {"colorbar": "色带", "scale": "比例尺", "north": "北箭"}
        mode_name = mode_names[self.adjust_mode]

        if self.adjust_mode == "colorbar":
            self.adjustments["cbar_offset_y"] = 0.0
            self.adjustments["cbar_offset_x"] = 0.0
        elif self.adjust_mode == "scale":
            self.adjustments["scale_offset_x"] = 0.0
            self.adjustments["scale_offset_y"] = 0.0
        elif self.adjust_mode == "north":
            self.adjustments["north_offset_x"] = 0.0
            self.adjustments["north_offset_y"] = 0.0

        self._update_display()
        self._update_offset_labels()
        self.status_label.config(text=f"已重置{mode_name}位置")
        self._show_feedback(f"✓ 已重置{mode_name}位置", "success")
    
    def _reset_all(self):
        """重置所有位置"""
        self.adjustments = DEFAULT_ADJUSTMENTS.copy()
        self._update_display()
        self._update_offset_labels()
        self.status_label.config(text="已重置所有位置")
        self._show_feedback("✓ 已重置所有位置", "success")

    def _save_positions(self):
        """保存当前位置"""
        save_adjustments(self.adjustments)
        self.status_label.config(text="位置已保存！下次启动将自动应用")
        self._show_feedback("✓ 位置设置已保存", "success")
        messagebox.showinfo("保存成功", "位置调整参数已保存！\n下次预览时将自动应用这些设置。")

    def _toggle_view_lock(self):
        """切换视图锁定状态"""
        self.view_lock_active = self.view_lock_var.get()
        status = "开启" if self.view_lock_active else "关闭"
        self.status_label.config(text=f"视图锁定: {status}")
        self._show_feedback(f"✓ 视图锁定已{status}", "info")

        if self.view_lock_active:
            self._lock_view()
            self.view_status_label.config(text="视图状态: 已锁定", foreground="green")
        else:
            self.view_status_label.config(text="视图状态: 未锁定", foreground="orange")

    def _restore_view(self):
        """恢复初始视图范围"""
        try:
            restored = False
            for ax in self.fig.get_axes():
                if ax in self.initial_view_limits:
                    ax.set_xlim(self.initial_view_limits[ax]['xlim'])
                    ax.set_ylim(self.initial_view_limits[ax]['ylim'])
                    restored = True

            if restored:
                self.canvas.draw()
                self._show_feedback("✓ 视图已恢复到初始状态", "success")
                self.view_status_label.config(text="视图状态: 已恢复", foreground="green")
            else:
                self._show_feedback("⚠ 没有可恢复的视图", "warning")
        except Exception as e:
            self._show_feedback(f"✗ 恢复视图失败: {str(e)}", "error")

    def _lock_view(self):
        """锁定当前视图范围"""
        try:
            for ax in self.fig.get_axes():
                if ax in self.initial_view_limits:
                    ax.set_xlim(self.initial_view_limits[ax]['xlim'])
                    ax.set_ylim(self.initial_view_limits[ax]['ylim'])
        except Exception:
            pass

    def _start_view_lock_timer(self):
        """启动视图锁定定时器"""
        def check_and_lock():
            try:
                if self.view_lock_active and self.window.winfo_exists():
                    self._lock_view()
                    # 每100ms检查一次
                    self.window.after(100, check_and_lock)
            except Exception:
                # 窗口已关闭，停止定时器
                pass

        check_and_lock()

    def _on_closing(self):
        """窗口关闭时的清理操作（关键修复）"""
        try:
            # 停止视图锁定
            self.view_lock_active = False

            # 清理matplotlib资源
            import matplotlib.pyplot as plt
            plt.close(self.fig)

            # 销毁窗口
            self.window.destroy()
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            try:
                self.window.destroy()
            except:
                pass

    def _save_image_dialog(self):
        """打开保存图片对话框 - 支持多种格式和自定义设置"""
        # 创建保存对话框窗口
        dialog = tk.Toplevel(self.window)
        dialog.title("保存图片")
        dialog.geometry("450x350")
        dialog.resizable(False, False)

        # 居中显示
        dialog.transient(self.window)
        dialog.grab_set()

        # 主框架
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 文件格式选择
        format_frame = ttk.LabelFrame(main_frame, text="文件格式", padding=10)
        format_frame.pack(fill=tk.X, pady=(0, 10))

        format_var = tk.StringVar(value="png")
        formats = [
            ("PNG - 高质量位图 (推荐)", "png"),
            ("PDF - 矢量格式 (论文投稿)", "pdf"),
            ("JPG - 压缩位图", "jpg"),
            ("SVG - 可编辑矢量", "svg"),
            ("TIFF - 无损位图", "tiff")
        ]

        for text, value in formats:
            ttk.Radiobutton(format_frame, text=text, variable=format_var,
                          value=value).pack(anchor=tk.W, pady=2)

        # DPI设置
        dpi_frame = ttk.LabelFrame(main_frame, text="分辨率 (DPI)", padding=10)
        dpi_frame.pack(fill=tk.X, pady=(0, 10))

        dpi_var = tk.StringVar(value="300")
        dpi_options = [
            ("150 DPI - 屏幕预览", "150"),
            ("300 DPI - 标准打印 (推荐)", "300"),
            ("600 DPI - 高质量打印", "600"),
            ("自定义", "custom")
        ]

        for text, value in dpi_options:
            ttk.Radiobutton(dpi_frame, text=text, variable=dpi_var,
                          value=value).pack(anchor=tk.W, pady=2)

        # 自定义DPI输入框
        custom_dpi_frame = ttk.Frame(dpi_frame)
        custom_dpi_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(custom_dpi_frame, text="自定义DPI:").pack(side=tk.LEFT)
        custom_dpi_entry = ttk.Entry(custom_dpi_frame, width=10)
        custom_dpi_entry.pack(side=tk.LEFT, padx=5)
        custom_dpi_entry.insert(0, "300")

        # 其他选项
        options_frame = ttk.LabelFrame(main_frame, text="其他选项", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        tight_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="自动裁剪白边 (bbox_inches='tight')",
                       variable=tight_var).pack(anchor=tk.W)

        transparent_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="透明背景 (仅PNG/SVG)",
                       variable=transparent_var).pack(anchor=tk.W)

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def do_save():
            """执行保存操作"""
            from tkinter import filedialog

            # 获取文件格式
            fmt = format_var.get()

            # 文件类型映射
            filetypes_map = {
                "png": [("PNG图片", "*.png"), ("所有文件", "*.*")],
                "pdf": [("PDF文件", "*.pdf"), ("所有文件", "*.*")],
                "jpg": [("JPG图片", "*.jpg"), ("所有文件", "*.*")],
                "svg": [("SVG矢量图", "*.svg"), ("所有文件", "*.*")],
                "tiff": [("TIFF图片", "*.tiff *.tif"), ("所有文件", "*.*")]
            }

            # 打开文件保存对话框
            file_path = filedialog.asksaveasfilename(
                title="保存图片",
                defaultextension=f".{fmt}",
                filetypes=filetypes_map.get(fmt, [("所有文件", "*.*")])
            )

            if not file_path:
                return

            try:
                # 获取DPI
                dpi_value = dpi_var.get()
                if dpi_value == "custom":
                    try:
                        dpi = int(custom_dpi_entry.get())
                        if dpi < 50 or dpi > 1200:
                            messagebox.showerror("DPI错误", "DPI必须在50-1200之间")
                            return
                    except ValueError:
                        messagebox.showerror("DPI错误", "请输入有效的DPI数值")
                        return
                else:
                    dpi = int(dpi_value)

                # 构建保存参数
                save_kwargs = {'dpi': dpi}

                # 自动裁剪白边
                if tight_var.get():
                    save_kwargs['bbox_inches'] = 'tight'
                    save_kwargs['pad_inches'] = 0.02

                # 透明背景
                if transparent_var.get() and fmt in ['png', 'svg']:
                    save_kwargs['transparent'] = True

                # PNG特殊处理：禁用iCCP警告
                if fmt == 'png':
                    save_kwargs['pil_kwargs'] = {'optimize': True, 'icc_profile': None}

                # 保存图片
                self.fig.savefig(file_path, **save_kwargs)

                # 更新状态
                self.status_label.config(text=f"图片已保存: {os.path.basename(file_path)}")

                # 关闭对话框
                dialog.destroy()

                # 显示成功消息
                messagebox.showinfo("保存成功",
                    f"图片已保存到:\n{file_path}\n\n"
                    f"格式: {fmt.upper()}\n"
                    f"分辨率: {dpi} DPI")

            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存图片:\n{str(e)}")

        def do_cancel():
            """取消保存"""
            dialog.destroy()

        ttk.Button(button_frame, text="💾 保存", command=do_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ 取消", command=do_cancel).pack(side=tk.LEFT)

    def _show_help(self):
        """显示帮助信息"""
        help_msg = """
交互式预览 - 操作说明

【方式1：使用按钮】
1. 选择调整对象（色带/比例尺/北箭）
2. 选择步长（小/中/大）
3. 点击方向按钮（▲▼◀▶）移动
4. 点击中心按钮（●）重置当前对象

【方式2：使用键盘】
Tab: 切换调整对象
↑↓←→: 移动（中等步长）
Shift+方向键: 大幅移动
R: 重置当前对象
Ctrl+R: 重置所有位置
S: 保存位置设置
H: 显示此帮助

【视图控制】
- 勾选"锁定视图"防止缩放
- 如果视图被缩放，点击"恢复视图"
- 系统会自动锁定视图（每100ms）

【操作反馈】
- 绿色✓：操作成功
- 红色✗：操作失败
- 蓝色：信息提示
- 橙色⚠：警告

【提示】
- 所有操作都有即时反馈
- 调整完成后记得保存位置
- 视图锁定可防止意外缩放
- 如果出现缩放，立即点击"恢复视图"
        """
        messagebox.showinfo("操作帮助", help_msg.strip())


def show_interactive_preview(fig, redraw_callback, is_grid=False):
    """
    显示交互式预览窗口

    参数:
        fig: matplotlib figure对象
        redraw_callback: 重绘回调函数，接受adjustments字典，返回新的figure
        is_grid: 是否为多图模式
    """
    # 关键修复：在创建交互式预览窗口之前，关闭所有其他matplotlib窗口
    # 这样可以避免窗口冲突和资源泄漏
    import matplotlib.pyplot as plt

    # 获取所有figure编号
    all_figs = plt.get_fignums()
    current_fig_num = fig.number if hasattr(fig, 'number') else None

    # 关闭除当前figure之外的所有figure
    for fig_num in all_figs:
        if fig_num != current_fig_num:
            try:
                plt.close(fig_num)
            except:
                pass

    # 创建交互式预览窗口
    window = InteractivePreviewWindow(fig, redraw_callback, is_grid)
    return window

