# -*- coding: utf-8 -*-
import os

# 统一投影（与旧版一致）
DST_CRS = "+proj=aea +lat_1=25 +lat_2=47 +lat_0=0 +lon_0=105 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"

# 默认色带键
DEFAULT_CMAP_KEY = "seq_ylorrd"

# 自动确定 vmax 用的上分位
PCT_UPPER = 98.0

# GUI 状态文件
STATE_FILE = os.path.join(os.path.expanduser("~"), ".paper_map_gui_state_v12.json")
