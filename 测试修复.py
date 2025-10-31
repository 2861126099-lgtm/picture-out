# -*- coding: utf-8 -*-
"""
测试修复后的交互式预览窗口
"""

import matplotlib
matplotlib.use('TkAgg')  # 强制使用TkAgg后端

import matplotlib.pyplot as plt
import numpy as np
from interactive_preview import show_interactive_preview

print("=" * 60)
print("测试修复后的交互式预览窗口")
print("=" * 60)
print()

def create_test_figure():
    """创建测试图形"""
    print("创建测试图形...")
    
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), dpi=100)
    
    for i, ax in enumerate(axes):
        # 创建测试数据
        data = np.random.rand(10, 10) * (i + 1) * 30
        
        # 绘制图形
        im = ax.imshow(data, cmap='YlOrRd')
        ax.set_title(f"测试图 {i+1}")
        
        # 添加色带
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    
    fig.suptitle("测试多图布局", fontsize=14, y=0.98)
    
    print("✓ 测试图形创建成功")
    return fig

def redraw_callback(adjustments):
    """重绘回调函数"""
    print(f"重绘回调被调用，调整参数: {adjustments}")
    
    # 关闭旧图形
    plt.close('all')
    
    # 创建新图形
    return create_test_figure()

def main():
    print("\n测试步骤：")
    print("1. 创建测试图形")
    print("2. 打开交互式预览窗口")
    print("3. 检查窗口是否正确显示")
    print()
    
    # 创建测试图形
    fig = create_test_figure()
    
    print("\n正在打开交互式预览窗口...")
    print("⚠ 请注意：")
    print("  - 窗口标题应该是：'交互式预览 - 使用方向键或按钮调整位置'")
    print("  - 窗口右侧应该有控制面板")
    print("  - 应该能看到 ▲▼◀▶ 方向按钮")
    print()
    
    try:
        # 打开交互式预览窗口
        preview = show_interactive_preview(fig, redraw_callback, is_grid=True)
        
        print("✓ 交互式预览窗口已创建")
        print()
        print("=" * 60)
        print("✅ 测试成功！")
        print()
        print("请在预览窗口中测试以下功能：")
        print("1. 选择一个调整对象（色带/比例尺/北箭）")
        print("2. 点击方向按钮（▲▼◀▶）")
        print("3. 观察反馈信息（应该显示绿色的成功消息）")
        print("4. 尝试不同的步长（小/中/大）")
        print("5. 测试视图锁定功能")
        print()
        print("测试完成后，请关闭预览窗口。")
        print("然后可以再次运行此脚本，测试是否能多次运行。")
        print("=" * 60)
        
        # 等待窗口关闭
        if hasattr(preview, 'window'):
            preview.window.wait_window()
        
        print("\n窗口已关闭")
        print("正在清理资源...")
        
        # 清理所有matplotlib资源
        plt.close('all')
        
        print("✓ 资源清理完成")
        print()
        print("=" * 60)
        print("✅ 测试完成！")
        print()
        print("如果您能看到这条消息，说明：")
        print("1. ✓ 窗口正确显示")
        print("2. ✓ 窗口正确关闭")
        print("3. ✓ 资源正确释放")
        print()
        print("现在可以再次运行此脚本，测试是否能多次运行：")
        print("  python 测试修复.py")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n请将错误信息发送给我，我会进一步修复。")

if __name__ == "__main__":
    main()

