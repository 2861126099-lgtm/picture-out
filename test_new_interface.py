# -*- coding: utf-8 -*-
"""
测试新的预览界面功能
- 方向按钮
- 视图锁定
- 操作反馈
"""

import matplotlib.pyplot as plt
import numpy as np
from interactive_preview import show_interactive_preview

def create_test_figure():
    """创建一个测试图形（模拟多图布局）"""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), dpi=100)
    
    # 创建三个不同的图
    for i, ax in enumerate(axes):
        # 创建测试数据
        x = np.linspace(0, 10, 100)
        y = np.sin(x + i * np.pi / 3)
        
        ax.plot(x, y, linewidth=2, label=f'数据 {i+1}')
        ax.set_xlabel('X轴', fontsize=10)
        ax.set_ylabel('Y轴', fontsize=10)
        ax.set_title(f'子图 {i+1}', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    fig.suptitle('测试图形 - 新界面功能', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    return fig

def redraw_callback(adjustments):
    """重绘回调函数"""
    # 这里简单返回原图，实际使用中会根据adjustments重新绘制
    print(f"重绘回调被调用，当前调整参数: {adjustments}")
    return create_test_figure()

if __name__ == "__main__":
    print("=" * 60)
    print("测试新的预览界面功能")
    print("=" * 60)
    print()
    print("新功能测试清单：")
    print("1. ✓ 方向按钮（▲▼◀▶）")
    print("2. ✓ 步长选择（小/中/大）")
    print("3. ✓ 操作反馈（绿色✓/红色✗）")
    print("4. ✓ 视图锁定（防止缩放）")
    print("5. ✓ 视图恢复（一键恢复）")
    print()
    print("测试步骤：")
    print("1. 选择一个调整对象（色带/比例尺/北箭）")
    print("2. 点击方向按钮，观察反馈信息")
    print("3. 尝试不同的步长设置")
    print("4. 测试视图锁定功能")
    print("5. 如果视图缩放，点击'恢复视图'")
    print()
    print("=" * 60)
    print()
    
    # 创建测试图形
    print("创建测试图形...")
    fig = create_test_figure()
    
    # 打开交互式预览窗口
    print("打开交互式预览窗口...")
    print()
    print("提示：")
    print("- 使用方向按钮或键盘方向键调整位置")
    print("- 观察反馈区域的提示信息")
    print("- 测试视图锁定和恢复功能")
    print("- 按 H 键查看完整帮助")
    print()
    
    show_interactive_preview(fig, redraw_callback, is_grid=True)
    
    plt.show()

