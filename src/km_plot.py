# -*- coding: utf-8 -*-
"""
KM 曲线模块：Kaplan-Meier 曲线、log-rank 检验、中位生存期、风险人数表、时间点生存率标注。
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无界面环境下也能出图
import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test, multivariate_logrank_test
from lifelines.utils import median_survival_times

from .style import get_palette

# 风险人数表的刻度（月）
RISK_TABLE_TICKS = [0, 12, 24, 36, 48, 60]


def _format_p(p):
    """P 值格式化为期刊常用形式。"""
    return "P < 0.001" if p < 0.001 else f"P = {p:.3f}"


def _survival_ci_at(kmf, t):
    """
    取 KM 拟合曲线在 t 时刻的生存率及 95%CI（阶梯函数，取 <=t 的最后一个取值）。

    返回:
        tuple: (survival, ci_lower, ci_upper)，无法取值时为 np.nan
    """
    ci = kmf.confidence_interval_
    idx = np.asarray(ci.index, dtype=float)
    pos = np.searchsorted(idx, t, side="right") - 1
    if pos < 0:
        return np.nan, np.nan, np.nan
    row = ci.iloc[pos]
    s = float(kmf.predict(t))
    return s, float(row.iloc[0]), float(row.iloc[1])


def _median_with_ci(kmf):
    """
    计算中位生存期及 95%CI。

    返回:
        tuple: (median, lower, upper)；中位未达到返回 None；
        CI 无法计算时对应位置为 np.nan。
    """
    med = float(kmf.median_survival_time_)
    if not np.isfinite(med):
        return None
    lower, upper = np.nan, np.nan
    try:
        ci_med = median_survival_times(kmf.confidence_interval_)
        lower = float(ci_med.iloc[0, 0])
        upper = float(ci_med.iloc[0, 1])
    except Exception:
        pass
    return med, lower, upper


def _median_text(label, med):
    """拼接图例中的中位生存期文字。"""
    if med is None:
        return f"{label}: median not reached"
    m, lo, hi = med
    if np.isfinite(lo) and np.isfinite(hi):
        return f"{label}: median {m:.1f} mo (95% CI {lo:.1f}\u2013{hi:.1f})"
    return f"{label}: median {m:.1f} mo (95% CI NA)"


def _number_at_risk(time_arr, grid):
    """计算各刻度时刻仍处于风险中的人数（随访时间 >= 刻度）。"""
    time_arr = np.asarray(time_arr, dtype=float)
    return [int((time_arr >= g).sum()) for g in grid]


def _time_label(t):
    """时间点标注文字：12 月显示 1-yr，其余显示 x-month。"""
    if t == 12:
        return "1-yr"
    return f"{int(t)}-month"


def plot_km(df, endpoint, time_col, event_col, config):
    """
    绘制单个终点的 KM 曲线（含 log-rank P 值、中位生存期及 95%CI、风险人数表、
    时间点生存率标注），并按配置导出 pdf/png。

    参数:
        df: 清洗后的数据表
        endpoint: 终点名（"OS"/"PFS"）
        time_col: 时间列名
        event_col: 事件列名
        config: 配置模块

    返回:
        pd.DataFrame: 时间点生存率汇总（Endpoint/Group/Time/Survival_%/CI_lower_%/CI_upper_%），
        未开启标注或无分组变量时返回 None
    """
    group_var = config.KM_GROUP_VAR
    use_labels = list(config.KM_LEGEND_LABELS)

    # 去掉分组变量或终点列缺失的行
    d = df.dropna(subset=[group_var, time_col, event_col]).copy()

    # 分组顺序：优先 CAT_LEVELS，否则按取值排序
    levels = list(pd.unique(d[group_var]))
    custom = config.CAT_LEVELS.get(group_var)
    if custom:
        levels = [l for l in custom if l in set(levels)]
    else:
        try:
            levels = sorted(levels)
        except TypeError:
            levels = sorted(levels, key=lambda x: str(x))

    palette = get_palette(config.COLOR_STYLE, config.KM_COLORS)
    ylabel = ("Overall Survival Probability" if endpoint == "OS"
              else "Progression-free Survival Probability")

    # 统一 x 轴范围：覆盖最大随访时间与标注时间点，并留右侧标注空间
    max_time = float(d[time_col].max())
    mark = [t for t in list(config.KM_MARK_TIMEPOINTS) if t <= max_time]
    xmax = max([max_time] + mark) * 1.18

    fig, (ax, ax_risk) = plt.subplots(
        2, 1, figsize=(8, 6.5),
        gridspec_kw={"height_ratios": [4.2, 1.0], "hspace": 0.05},
    )

    kmfs = {}
    legend_entries = []
    for i, lev in enumerate(levels):
        sub = d[d[group_var] == lev]
        kmf = KaplanMeierFitter()
        kmf.fit(sub[time_col], sub[event_col], label=str(lev))
        kmfs[lev] = (kmf, sub)
        color = palette[i % len(palette)]
        sf = kmf.survival_function_
        ax.step(sf.index, sf.iloc[:, 0], where="post", color=color, lw=2)
        ax.fill_between(
            kmf.confidence_interval_.index,
            kmf.confidence_interval_.iloc[:, 0],
            kmf.confidence_interval_.iloc[:, 1],
            color=color, alpha=0.12, step="post", linewidth=0,
        )
        label = use_labels[i] if i < len(use_labels) else str(lev)
        legend_entries.append(_median_text(label, _median_with_ci(kmf)))

    # log-rank 检验：2 组用 logrank_test，>2 组用 multivariate_logrank_test
    if len(levels) == 2:
        (l1, l2) = levels
        res = logrank_test(
            kmfs[l1][1][time_col], kmfs[l2][1][time_col],
            event_observed_A=kmfs[l1][1][event_col],
            event_observed_B=kmfs[l2][1][event_col],
        )
        p_logrank = float(res.p_value)
    elif len(levels) > 2:
        res = multivariate_logrank_test(d[time_col], d[group_var], d[event_col])
        p_logrank = float(res.p_value)
    else:
        p_logrank = np.nan

    if np.isfinite(p_logrank):
        # 放在左下角空白区，避免与右侧时间点标注重叠
        ax.text(0.03, 0.06, "Log-rank " + _format_p(p_logrank),
                transform=ax.transAxes, ha="left", va="bottom", fontsize=11)

    # 图例：显示中位生存期及 95%CI
    handles = [plt.Line2D([0], [0], color=palette[i % len(palette)], lw=2)
               for i in range(len(levels))]
    ax.legend(handles, legend_entries, loc="upper right", frameon=False,
              fontsize=10, title=f"Grouped by {group_var}")

    # 时间点标注：竖虚线 + 各组生存率（各组错开避免重叠）
    tp_records = []
    if mark:
        for t in mark:
            ax.axvline(t, color="gray", ls="--", lw=1, alpha=0.6, zorder=0)
        offsets = np.linspace(0.14, -0.05, max(len(levels), 1))
        for i, lev in enumerate(levels):
            kmf = kmfs[lev][0]
            label = use_labels[i] if i < len(use_labels) else str(lev)
            for t in mark:
                s, lo, hi = _survival_ci_at(kmf, t)
                if not np.isfinite(s):
                    continue
                txt = f"{label} {_time_label(t)}: {s*100:.1f}%"
                ax.annotate(txt, xy=(t, s), xytext=(t + xmax * 0.012, s + offsets[i]),
                            fontsize=8.5, color=palette[i % len(palette)])
                tp_records.append({
                    "Endpoint": endpoint,
                    "Group": label,
                    "Time": t,
                    "Survival_%": round(s * 100, 1),
                    "CI_lower_%": round(lo * 100, 1) if np.isfinite(lo) else np.nan,
                    "CI_upper_%": round(hi * 100, 1) if np.isfinite(hi) else np.nan,
                })

    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_ylim(0, 1.02)
    ax.set_xlim(0, xmax)
    ax.set_xticklabels([])  # 刻度标签统一放到下方风险表轴，避免错位
    ax.tick_params(axis="x", length=4)
    ax.spines[["top", "right"]].set_visible(False)

    # 下方风险人数表（与主图共用 x 范围）
    n_g = len(levels)
    ax_risk.set_ylim(0.2, n_g + 0.9)
    ax_risk.set_xlim(0, xmax)
    ax_risk.set_yticks([])
    ax_risk.spines[["top", "right", "left"]].set_visible(False)
    grid = [g for g in RISK_TABLE_TICKS if g <= xmax]
    ax_risk.set_xticks(grid)
    ax_risk.set_xticklabels([str(g) for g in grid], fontsize=9)
    ax_risk.set_xlabel("Time (months)", fontsize=12)
    x_label = -xmax * 0.028
    for i, lev in enumerate(levels):
        times = kmfs[lev][1][time_col]
        counts = _number_at_risk(times, grid)
        y = n_g - i
        label = use_labels[i] if i < len(use_labels) else str(lev)
        ax_risk.text(x_label, y, str(label), ha="right", va="center",
                     fontsize=9, clip_on=False)
        for g, c in zip(grid, counts):
            ax_risk.text(g, y, str(c), ha="center", va="center", fontsize=9)
    ax_risk.text(x_label, n_g + 0.42, "No. at risk", ha="right", va="center",
                 fontsize=9, fontweight="bold", clip_on=False)

    # 按配置导出
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    base = os.path.join(config.OUTPUT_DIR, f"KM_{endpoint}")
    fmts = ["pdf", "png"] if config.EXPORT_FORMAT == "both" else [config.EXPORT_FORMAT]
    for fmt in fmts:
        fig.savefig(f"{base}.{fmt}", dpi=max(config.DPI, 300),
                    bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"  KM 曲线已保存：{base}.[{'/'.join(fmts)}]（log-rank {_format_p(p_logrank)}）")

    if tp_records:
        return pd.DataFrame(tp_records)
    return None
