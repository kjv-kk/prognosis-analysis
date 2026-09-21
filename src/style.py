# -*- coding: utf-8 -*-
"""
配色方案模块：参考 ggsci 期刊风格的近似十六进制色组。
"""

# 各期刊风格色板（每组 6 色）
PALETTES = {
    "lancet": ["#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F", "#FDAF91"],
    "nejm":   ["#BC3C29", "#0072B5", "#E18727", "#20854E", "#7876B1", "#6F99AD"],
    "jama":   ["#374E55", "#DF8F44", "#00A1D5", "#B24745", "#79AF97", "#6A6599"],
    "nature": ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4"],
    "jco":    ["#0073C2", "#EFC000", "#868686", "#CD534C", "#7AA6DC", "#003C67"],
}


def get_palette(style, custom_colors=None):
    """
    根据风格名返回色板列表。

    参数:
        style: 风格名，"lancet"/"nejm"/"jama"/"nature"/"jco"/"custom"
        custom_colors: COLOR_STYLE 为 "custom" 时使用的自定义色组

    返回:
        list[str]: 十六进制颜色列表
    """
    if style == "custom" and custom_colors:
        return list(custom_colors)
    if style in PALETTES:
        return PALETTES[style]
    # 非法风格名回退到 nature
    return PALETTES["nature"]


def get_main_color(style, custom_colors=None):
    """
    返回指定风格的主色（色板第一个颜色），森林图等单色系图使用。

    参数:
        style: 风格名
        custom_colors: 自定义色组

    返回:
        str: 十六进制颜色
    """
    return get_palette(style, custom_colors)[0]
