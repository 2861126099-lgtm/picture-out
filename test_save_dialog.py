# -*- coding: utf-8 -*-
"""
测试保存对话框功能
"""

import matplotlib.pyplot as plt
import numpy as np
from interactive_preview import show_interactive_preview

def create_test_figure():
    """创建一个测试图形"""
    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    
    # 创建一些测试数据
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    
    ax.plot(x, y, 'b-', linewidth=2, label='sin(x)')
    ax.set_xlabel('X轴', fontsize=12)
    ax.set_ylabel('Y轴', fontsize=12)
    ax.set_title('测试图形 - 保存对话框功能', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    return fig

def redraw_callback(adjustments):
    """重绘回调函数（用于测试）"""
    # 这里简单返回原图，实际使用中会根据adjustments重新绘制
    return create_test_figure()

if __name__ == "__main__":
    print("创建测试图形...")
    fig = create_test_figure()
    
    print("打开交互式预览窗口...")
    print("点击'💾 保存图片'按钮测试新的保存对话框功能")
    
    show_interactive_preview(fig, redraw_callback, is_grid=False)
    
    plt.show()

