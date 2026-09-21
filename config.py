# -*- coding: utf-8 -*-
"""
prognosis-analysis 配置文件
============================
所有可配置项集中于此，修改后运行 main.py 即可。
"""

# ============ 数据文件 ============
# 数据文件路径，支持 .xlsx / .xls / .csv，按扩展名自动识别
FILE_PATH = "example_data/example_data.csv"

# ============ 列名设置 ============
ID_COL = "ID"                 # 患者编号列（不参与分析）
OS_TIME_COL = "OS_time"       # 总生存时间列（单位：月）
OS_EVENT_COL = "OS_event"     # 总生存事件列（1=死亡，0=删失）
PFS_TIME_COL = "PFS_time"     # 无进展生存时间列（单位：月）；留空字符串 "" 表示跳过 PFS 分析
PFS_EVENT_COL = "PFS_event"   # 无进展生存事件列（1=进展/死亡，0=删失）

# ============ 分析变量 ============
# 单因素 Cox 分析的变量列表；空列表 = 对除 ID/时间/事件列之外的所有特征列进行分析
UNI_VARS = []

# 多因素 Cox 分析的变量列表；空列表 = 自动纳入单因素分析中 P < 0.05 的变量
MULTI_VARS = []

# 逐变量指定类型："continuous"（连续型）/ "binary"（二分类）/ "categorical"（多分类，哑变量）
# / "ordinal"（有序数值）。
# 不指定的变量自动识别：数值型且唯一值=2 → binary；数值型其他 → continuous；非数值型 → categorical
VAR_TYPES = {
    # "Stage": "categorical",
    # "Age": "continuous",
}

# 多分类/二分类变量的水平顺序（第一组为参照组）；不指定的变量按取值排序，第一组为参照
CAT_LEVELS = {
    # "Stage": ["I", "II", "III", "IV"],
}

# ============ KM 曲线设置 ============
# KM 曲线分组变量；空字符串 "" 则跳过 KM 绘图
KM_GROUP_VAR = "Gene_High"

# 是否额外绘制整体（不分组）KM 曲线：全队列一条曲线，不做 log-rank，
# 用于查看单纯的 OS / PFS 分布与中位生存期；输出文件名 KM_OS_overall / KM_PFS_overall
KM_OVERALL = True

# 需要在曲线上标注生存率的时间点（月）；空列表则不标注
KM_MARK_TIMEPOINTS = [12, 24, 36]

# ============ 输出设置 ============
# 图片导出格式："pdf" / "png" / "both"
EXPORT_FORMAT = "both"

# 图片配色风格："lancet" / "nejm" / "jama" / "nature" / "jco" / "custom"
COLOR_STYLE = "nature"

# 自定义配色（仅 COLOR_STYLE = "custom" 时生效）
KM_COLORS = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488"]

# KM 图例标签；空列表则使用分组实际取值
KM_LEGEND_LABELS = []

# 图片分辨率（DPI，期刊投稿一般要求 >= 300）
DPI = 300

# 输出目录
OUTPUT_DIR = "output"
