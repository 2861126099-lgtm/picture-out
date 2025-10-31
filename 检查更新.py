# -*- coding: utf-8 -*-
"""
检查新功能是否已正确添加
"""

import sys

print("=" * 60)
print("检查新功能是否已添加")
print("=" * 60)
print()

# 检查1：导入模块
print("1. 检查模块导入...")
try:
    from interactive_preview import InteractivePreviewWindow
    print("   ✓ interactive_preview 模块导入成功")
except Exception as e:
    print(f"   ✗ 导入失败: {e}")
    sys.exit(1)

# 检查2：检查新方法是否存在
print("\n2. 检查新增方法...")
methods_to_check = [
    '_move_direction',
    '_show_feedback',
    '_toggle_view_lock',
    '_restore_view',
    '_lock_view',
    '_start_view_lock_timer'
]

all_methods = dir(InteractivePreviewWindow)
missing_methods = []

for method in methods_to_check:
    if method in all_methods:
        print(f"   ✓ {method} 存在")
    else:
        print(f"   ✗ {method} 不存在")
        missing_methods.append(method)

if missing_methods:
    print(f"\n   ⚠ 缺少 {len(missing_methods)} 个方法")
else:
    print("\n   ✓ 所有新方法都已添加")

# 检查3：检查方法签名
print("\n3. 检查方法实现...")
import inspect

try:
    # 检查 _move_direction 方法
    move_method = getattr(InteractivePreviewWindow, '_move_direction')
    sig = inspect.signature(move_method)
    params = list(sig.parameters.keys())
    if 'direction' in params:
        print("   ✓ _move_direction 方法参数正确")
    else:
        print("   ✗ _move_direction 方法参数不正确")
    
    # 检查 _show_feedback 方法
    feedback_method = getattr(InteractivePreviewWindow, '_show_feedback')
    sig = inspect.signature(feedback_method)
    params = list(sig.parameters.keys())
    if 'message' in params:
        print("   ✓ _show_feedback 方法参数正确")
    else:
        print("   ✗ _show_feedback 方法参数不正确")
        
except Exception as e:
    print(f"   ✗ 检查失败: {e}")

# 检查4：查看源代码片段
print("\n4. 查看关键代码片段...")
try:
    source = inspect.getsource(InteractivePreviewWindow._move_direction)
    if 'step_map' in source and 'small' in source:
        print("   ✓ _move_direction 包含步长控制代码")
    else:
        print("   ⚠ _move_direction 代码可能不完整")
        
    if 'feedback' in source.lower():
        print("   ✓ _move_direction 包含反馈代码")
    else:
        print("   ⚠ _move_direction 可能缺少反馈")
        
except Exception as e:
    print(f"   ✗ 无法读取源代码: {e}")

# 总结
print("\n" + "=" * 60)
if not missing_methods:
    print("✅ 所有新功能已正确添加！")
    print("\n下一步：运行 python test_new_interface.py 查看新界面")
else:
    print("❌ 部分功能缺失，请检查代码")
print("=" * 60)

