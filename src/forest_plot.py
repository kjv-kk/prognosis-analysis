# -*- coding: utf-8 -*-
"""
森林图模块：以 matplotlib 手绘发表级森林图（单因素 / 多因素 Cox 结果）。
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator, NullFormatter
from matplotlib.transforms import blended_transform_factory

from .style import get_main_color


def _format_p(p):
    """P 值期刊格式。"""
    if p is None or not np.isfinite(p):
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def _format_hr(hr, lo, hi):
    """HR (95% CI) 文本。"""
    if hr is None or not np.isfinite(hr):
        return "-"
    if lo is not None and np.isfinite(lo) and np.isfinite(hi):
        return f"{hr:.2f} ({lo:.2f}\u2013{hi:.2f})"
    return f"{hr:.2f}"


def _display_rows(results):
    """
    把结果结构展开为森林图显示行。

    返回:
        list[dict]: 每行含 kind(header/term)、label、hr、ci_lower、ci_upper、p、variable
    """
    rows = []
    for r in results:
        meta = r.get("meta", {})
        vtype = r.get("type", "")
        if not r.get("terms"):
            # 拟合失败等异常行
            rows.append({"kind": "term", "label": r["variable"], "hr": np.nan,
                         "ci_lower": np.nan, "ci_upper": np.nan,
                         "p": r.get("p", np.nan), "variable": r["variable"],
                         "note": r.get("note", "")})
            continue
        if vtype == "categorical" and len(r["terms"]) > 1:
            ref = meta.get("ref")
            header = f"{r['variable']} (ref. {ref})" if ref is not None else r["variable"]
            rows.append({"kind": "header", "label": header, "hr": np.nan,
                         "ci_lower": np.nan, "ci_upper": np.nan, "p": r["p"],
                         "variable": r["variable"], "note": ""})
            for t in r["terms"]:
                lev = t["term"].split("[T.", 1)[-1].rstrip("]")
                rows.append({"kind": "term", "label": "  " + lev, "hr": t["hr"],
                             "ci_lower": t["ci_lower"], "ci_upper": t["ci_upper"],
                             "p": t["p"], "variable": r["variable"], "note": ""})
        elif vtype == "binary" and meta.get("level_for_1") not in (None, 1):
            label = f"{r['variable']} (1 = {meta['level_for_1']})"
            t = r["terms"][0]
            rows.append({"kind": "term", "label": label, "hr": t["hr"],
                         "ci_lower": t["ci_lower"], "ci_upper": t["ci_upper"],
                         "p": t["p"], "variable": r["variable"], "note": r.get("note", "")})
        else:
            t = r["terms"][0]
            rows.append({"kind": "term", "label": r["variable"], "hr": t["hr"],
                         "ci_lower": t["ci_lower"], "ci_upper": t["ci_upper"],
                         "p": t["p"], "variable": r["variable"], "note": r.get("note", "")})
    return rows


def plot_forest(results, config, out_base, title):
    """
    绘制森林图并导出。

    参数:
        results: Cox 结果列表（含 term 分行信息）
        config: 配置模块
        out_base: 输出路径（不含扩展名）
        title: 图标题
    """
    rows = _display_rows(results)
    if not rows:
        print("  无可用结果，跳过森林图。")
        return

    color = get_main_color(config.COLOR_STYLE, config.KM_COLORS)
    n_rows = len(rows)

    fig, ax = plt.subplots(figsize=(9, max(4.5, 0.5 * n_rows + 2.2)))
    y_positions = list(range(n_rows, 0, -1))  # 自上而下

    # 左侧文字用“轴坐标 x + 数据坐标 y”的混合坐标，避免对数轴下数据坐标 0 的问题
    left_trans = blended_transform_factory(ax.transAxes, ax.transData)

    for row, y in zip(rows, y_positions):
        if row["kind"] == "header":
            ax.text(-0.02, y, row["label"], fontsize=10, fontweight="bold",
                    ha="right", va="center", transform=left_trans, clip_on=False)
            continue
        ax.text(-0.02, y, row["label"], fontsize=10, ha="right", va="center",
                transform=left_trans, clip_on=False)
        if np.isfinite(row["hr"]):
            ax.plot([row["ci_lower"], row["ci_upper"]], [y, y], color=color,
                    lw=1.6, solid_capstyle="round", zorder=2)
            ax.scatter([row["hr"]], [y], marker="s", s=52, color=color,
                       edgecolor="black", linewidth=0.6, zorder=3)

    ax.set_ylim(0.3, n_rows + 0.9)

    # 收集有效 HR 以设定 x 轴范围（对数刻度）
    hrs = [r["hr"] for r in rows if r["kind"] == "term" and np.isfinite(r["hr"])]
    los = [r["ci_lower"] for r in rows if r["kind"] == "term" and np.isfinite(r["ci_lower"])]
    his = [r["ci_upper"] for r in rows if r["kind"] == "term" and np.isfinite(r["ci_upper"])]
    lo = min(los + hrs) if los else 0.5
    hi = max(his + hrs) if his else 2.0
    lo = max(lo * 0.8, 0.05)
    hi = min(hi * 1.2, 200.0)
    if lo > 0.8:
        lo = 0.8
    if hi < 1.2:
        hi = 1.2
    ax.set_xlim(lo, hi)
    ax.set_xscale("log")
    # 主刻度取整数值并清除次刻度，避免默认科学计数法
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    tick_pool = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50]
    ticks = [t for t in tick_pool if lo <= t <= hi]
    if not ticks:
        ticks = [1.0]
    if 1 not in ticks:
        ticks = sorted(ticks + [1])
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks], fontsize=10)
    ax.set_xlabel("Hazard Ratio (log scale)", fontsize=11)

    # HR=1 参考线
    ax.axvline(1, color="gray", ls="--", lw=1, zorder=1)

    # 右侧文字列：HR (95% CI) 与 P value（x 用轴坐标，可超出绘图区）
    trans = blended_transform_factory(ax.transAxes, ax.transData)
    head_y = n_rows + 0.6
    ax.text(1.03, head_y, "HR (95% CI)", fontsize=10, fontweight="bold",
            ha="left", va="center", transform=trans)
    ax.text(1.42, head_y, "P value", fontsize=10, fontweight="bold",
            ha="left", va="center", transform=trans)
    for row, y in zip(rows, y_positions):
        weight = "bold" if row["kind"] == "header" else "normal"
        ax.text(1.03, y, _format_hr(row["hr"], row["ci_lower"], row["ci_upper"]),
                fontsize=9, ha="left", va="center", transform=trans, fontweight=weight)
        ax.text(1.42, y, _format_p(row["p"]), fontsize=9, ha="left",
                va="center", transform=trans, fontweight=weight)

    ax.set_yticks([])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_title(title, fontsize=13, pad=16)

    fig.subplots_adjust(left=0.02, right=0.60, bottom=0.12,
                        top=min(0.94, 1 - 0.35 / (n_rows + 3)))

    fmts = ["pdf", "png"] if config.EXPORT_FORMAT == "both" else [config.EXPORT_FORMAT]
    for fmt in fmts:
        fig.savefig(f"{out_base}.{fmt}", dpi=max(config.DPI, 300), bbox_inches="tight")
    plt.close(fig)
    print(f"  森林图已保存：{out_base}.[{'/'.join(fmts)}]")
