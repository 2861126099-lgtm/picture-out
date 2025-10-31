#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 GUI 应用程序

使用方法:
    从父目录运行: python -m paper_map.gui_app
    或运行此脚本: python test_gui.py
"""

import sys
import os

if __name__ == "__main__":
    try:
        # 将父目录添加到 Python 路径
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        # 导入模块
        from paper_map.gui_app import run_app

        print("=" * 60)
        print("正在启动 Paper Map GUI 应用程序...")
        print("=" * 60)
        print("\n✨ 新功能:")
        print("1. 添加了色带宽度调整功能")
        print("   - 单图：在'色带（单图）'区域，新增'宽度比例'参数（默认0.15）")
        print("   - 多图：在'色带选项'区域，优化了共享和分图色带的宽度控制")
        print("\n2. 添加了比例尺新功能（多图页）")
        print("   - 新增'线段式'比例尺样式（更简洁）")
        print("   - 新增'使用共享比例尺'选项（只在最后一个子图显示）")
        print("   - 推荐用于横向排列多的布局（1×4, 2×4等）")
        print("\n3. 添加了自动布局优化功能（多图页）")
        print("   - 点击'自动布局'按钮自动计算wspace/hspace")
        print("   - 根据行列数智能调整间距，减少留白")
        print("   - 特别优化了横向排列多的情况")
        print("\n4. 优化了预览窗口调整")
        print("   - 改善了宽度大于高度时的窗口调整体验")
        print("\n✅ 所有原有功能保持不变！")
        print("=" * 60)
        print()

        run_app()

    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        print("\n请确保:")
        print("1. 已安装所有依赖包 (matplotlib, rasterio, geopandas等)")
        print("2. 在正确的目录下运行此脚本")
        print("3. Python版本 >= 3.7")
        print("\n或者尝试:")
        print("  cd ..")
        print("  python -m paper_map.gui_app")

