# -*- coding: utf-8 -*-
"""
诊断交互式预览窗口问题
"""

import sys
import traceback

print("=" * 60)
print("诊断交互式预览窗口问题")
print("=" * 60)
print()

# 测试1：检查tkinter
print("1. 检查tkinter...")
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    print("   ✓ tkinter 可用")
    
    # 测试Toplevel
    test_window = tk.Toplevel()
    test_window.title("测试窗口")
    test_window.geometry("300x200")
    
    label = tk.Label(test_window, text="如果您能看到这个窗口，说明tkinter正常工作")
    label.pack(pady=50)
    
    def close_test():
        test_window.destroy()
        root.quit()
    
    tk.Button(test_window, text="关闭", command=close_test).pack()
    
    print("   ✓ 测试窗口已创建")
    print("   ⚠ 请查看是否有测试窗口弹出")
    print("   ⚠ 如果看到窗口，请点击'关闭'按钮")
    
    root.mainloop()
    
    print("   ✓ tkinter 测试完成")
    
except Exception as e:
    print(f"   ✗ tkinter 测试失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试2：检查matplotlib
print("\n2. 检查matplotlib...")
try:
    import matplotlib
    matplotlib.use('TkAgg')  # 强制使用TkAgg后端
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    print(f"   ✓ matplotlib 可用 (后端: {matplotlib.get_backend()})")
except Exception as e:
    print(f"   ✗ matplotlib 导入失败: {e}")
    sys.exit(1)

# 测试3：检查interactive_preview模块
print("\n3. 检查interactive_preview模块...")
try:
    from interactive_preview import InteractivePreviewWindow, show_interactive_preview
    print("   ✓ interactive_preview 模块导入成功")
except Exception as e:
    print(f"   ✗ interactive_preview 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试4：创建简单的测试图形
print("\n4. 创建测试图形...")
try:
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    ax.plot([1, 2, 3, 4], [1, 4, 2, 3])
    ax.set_title("测试图形")
    print("   ✓ 测试图形创建成功")
except Exception as e:
    print(f"   ✗ 创建图形失败: {e}")
    sys.exit(1)

# 测试5：尝试打开交互式预览窗口
print("\n5. 尝试打开交互式预览窗口...")
print("   ⚠ 请注意屏幕上是否有新窗口弹出")
print("   ⚠ 窗口标题应该是：'交互式预览 - 使用方向键或按钮调整位置'")
print()

try:
    def dummy_redraw(adjustments):
        """虚拟重绘函数"""
        return fig
    
    # 创建新的tk根窗口
    root2 = tk.Tk()
    root2.withdraw()
    
    # 打开交互式预览
    preview = show_interactive_preview(fig, dummy_redraw, is_grid=False)
    
    print("   ✓ 交互式预览窗口已创建")
    print()
    print("=" * 60)
    print("✅ 如果您看到了带右侧控制面板的窗口，说明功能正常！")
    print("❌ 如果只看到普通的图片窗口，说明有问题。")
    print("=" * 60)
    print()
    print("请关闭预览窗口以继续...")
    
    # 等待窗口关闭
    if hasattr(preview, 'window'):
        preview.window.wait_window()
    
    root2.mainloop()
    
except Exception as e:
    print(f"   ✗ 打开预览窗口失败: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)

