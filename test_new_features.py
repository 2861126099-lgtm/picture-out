# -*- coding: utf-8 -*-
"""
测试新功能：
1. 线段式比例尺
2. 共享比例尺
3. 自动布局优化
"""

import sys
import os

# 确保可以导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_auto_layout():
    """测试自动布局功能"""
    import plotting
    auto_layout_spacing = plotting.auto_layout_spacing
    
    print("测试自动布局功能...")
    
    # 测试不同的行列组合
    test_cases = [
        (1, 4, False, "right"),  # 1x4 横向排列
        (2, 4, False, "right"),  # 2x4 横向排列
        (3, 4, False, "right"),  # 3x4 横向排列
        (2, 2, True, "right"),   # 2x2 共享色带
        (1, 3, False, "bottom"), # 1x3 横向排列
    ]
    
    for nrows, ncols, use_shared, loc in test_cases:
        wspace, hspace = auto_layout_spacing(nrows, ncols, use_shared, loc)
        print(f"  {nrows}x{ncols} (共享色带={use_shared}, 位置={loc}): wspace={wspace:.2f}, hspace={hspace:.2f}")
    
    print("✓ 自动布局功能测试通过\n")


def test_scale_bar_functions():
    """测试比例尺函数是否可以导入"""
    print("测试比例尺函数导入...")

    try:
        import plotting
        draw_scale_bar_axes = plotting.draw_scale_bar_axes
        draw_scale_bar_line = plotting.draw_scale_bar_line
        print("  ✓ draw_scale_bar_axes 导入成功")
        print("  ✓ draw_scale_bar_line 导入成功")

        import draw_elems
        print("  ✓ 从 draw_elems 导入成功")

        print("✓ 比例尺函数测试通过\n")
    except ImportError as e:
        print(f"  ✗ 导入失败: {e}\n")
        return False

    return True


def test_grid_map_signature():
    """测试make_grid_map函数签名"""
    print("测试make_grid_map函数签名...")

    try:
        import plotting
        import inspect
        make_grid_map = plotting.make_grid_map
        
        sig = inspect.signature(make_grid_map)
        params = list(sig.parameters.keys())
        
        # 检查新参数是否存在
        required_params = ['scale_style', 'use_shared_scale']
        missing = [p for p in required_params if p not in params]
        
        if missing:
            print(f"  ✗ 缺少参数: {missing}")
            return False
        
        print(f"  ✓ scale_style 参数存在")
        print(f"  ✓ use_shared_scale 参数存在")
        print("✓ 函数签名测试通过\n")
        return True
        
    except Exception as e:
        print(f"  ✗ 测试失败: {e}\n")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试新功能")
    print("=" * 60 + "\n")
    
    all_passed = True
    
    # 测试1: 自动布局
    try:
        test_auto_layout()
    except Exception as e:
        print(f"✗ 自动布局测试失败: {e}\n")
        all_passed = False
    
    # 测试2: 比例尺函数
    if not test_scale_bar_functions():
        all_passed = False
    
    # 测试3: 函数签名
    if not test_grid_map_signature():
        all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("✓ 所有测试通过！")
    else:
        print("✗ 部分测试失败")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

