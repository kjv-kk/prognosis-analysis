# -*- coding: utf-8 -*-
"""
KM 曲线模块：Kaplan-Meier 曲线、log-rank 检验、中位生存期、风险人数表、时间点生存率标注。
支持分组曲线与整体（不分组）曲线两种模式。
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

# 图表内部文字默认值（英文，医学期刊惯例）。
# 可通过 plot_km 的 fig_texts 参数传入同键字典整体或部分替换，实现图表语言切换。
FIG_TEXTS_DEFAULT = {
    "ylabel_OS": "Overall Survival Probability",      # OS 曲线 y 轴
    "ylabel_PFS": "Progression-free Survival Probability",  # PFS 曲线 y 轴
    "xlabel": "Time (months)",                        # x 轴
    "no_at_risk": "No. at risk",                      # 风险人数表标题
    "logrank_prefix": "Log-rank",                     # log-rank P 前缀
    "p_lt_001": "P < 0.001",                          # P 值 <0.001 显示
    "p_eq": "P = {p:.3f}",                            # P 值显示模板
    "median_not_reached": "median not reached",       # 中位未达到
    "median_fmt": "median {m:.1f} {mo} ({ci} {lo:.1f}\u2013{hi:.1f})",  # 中位+CI
    "median_na_fmt": "median {m:.1f} {mo} ({ci} {na})",                 # CI 缺失时
    "mo": "mo",                                       # 时间单位
    "ci": "95% CI",                                   # CI 前缀
    "na": "NA",                                       # 缺失占位
    "grouped_by": "Grouped by {var}",                 # 图例标题
    "all_patients": "All patients",                   # 整体（不分组）曲线标签
    "time_1yr": "1-yr",                               # 12 月标注
    "time_month": "{t}-month",                        # 其余月份标注模板
    "surv_label": "{group} {time}: {pct}%",           # 时间点生存率标注
}


def _merge_texts(fig_texts):
    """把调用方传入的文字字典合并到默认值上；None 时用默认英文。"""
    return {**FIG_TEXTS_DEFAULT, **(fig_texts or {})}


def _format_p(p, texts):
    """P 值格式化为期刊常用形式（文字可经 texts 自定义）。"""
    return texts["p_lt_001"] if p < 0.001 else texts["p_eq"].format(p=p)


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


def _median_text(label, med, texts):
    """拼接图例中的中位生存期文字。"""
    if med is None:
        return f"{label}: {texts['median_not_reached']}"
    m, lo, hi = med
    if np.isfinite(lo) and np.isfinite(hi):
        return f"{label}: " + texts["median_fmt"].format(
            m=m, mo=texts["mo"], ci=texts["ci"], lo=lo, hi=hi)
    return f"{label}: " + texts["median_na_fmt"].format(
        m=m, mo=texts["mo"], ci=texts["ci"], na=texts["na"])


def _number_at_risk(time_arr, grid):
    """计算各刻度时刻仍处于风险中的人数（随访时间 >= 刻度）。"""
    time_arr = np.asarray(time_arr, dtype=float)
    return [int((time_arr >= g).sum()) for g in grid]


def _time_label(t, texts):
    """时间点标注文字：12 月显示 1-yr，其余显示 x-month（均可自定义）。"""
    if t == 12:
        return texts["time_1yr"]
    return texts["time_month"].format(t=int(t))


def plot_km(df, endpoint, time_col, event_col, config, save_path=None,
            fig_texts=None, overall=False):
    """
    绘制单个终点的 KM 曲线（含 log-rank P 值、中位生存期及 95%CI、风险人数表、
    时间点生存率标注）。

    参数:
        df: 清洗后的数据表
        endpoint: 终点名（"OS"/"PFS"）
        time_col: 时间列名
        event_col: 事件列名
        config: 配置模块（duck-typed，需含 KM_GROUP_VAR/KM_LEGEND_LABELS/CAT_LEVELS/
            COLOR_STYLE/KM_COLORS/KM_MARK_TIMEPOINTS/EXPORT_FORMAT/DPI）
        save_path: 输出路径（不含扩展名）。None 时不写磁盘（返回值供图层保存，
            如 Streamlit 用 BytesIO）；有值时按 config.EXPORT_FORMAT 保存 pdf/png。
        fig_texts: 图表内部文字字典（键见 FIG_TEXTS_DEFAULT），None 用默认英文。
        overall: True 时绘制整体曲线（不分组，全队列一条曲线，不做 log-rank），
            用于查看单纯的 OS/PFS 分布；此时忽略 config.KM_GROUP_VAR。

    返回:
        tuple: (matplotlib Figure, 时间点生存率汇总 DataFrame 或 None)
    """
    texts = _merge_texts(fig_texts)
    group_var = config.KM_GROUP_VAR
    use_labels = list(config.KM_LEGEND_LABELS)

    if overall:
        # 整体模式：全队列一条曲线，仅一个虚拟分组
        d = df.dropna(subset=[time_col, event_col]).copy()
        levels = [texts["all_patients"]]
        subs = {levels[0]: d}
    else:
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
        subs = {lev: d[d[group_var] == lev] for lev in levels}

    palette = get_palette(config.COLOR_STYLE, config.KM_COLORS)
    ylabel = texts["ylabel_OS"] if endpoint == "OS" else texts["ylabel_PFS"]

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
        sub = subs[lev]
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
        legend_entries.append(_median_text(label, _median_with_ci(kmf), texts))

    # log-rank 检验：2 组用 logrank_test，>2 组用 multivariate_logrank_test；
    # 整体（1 组）模式不做检验
    if not overall and len(levels) == 2:
        (l1, l2) = levels
        res = logrank_test(
            kmfs[l1][1][time_col], kmfs[l2][1][time_col],
            event_observed_A=kmfs[l1][1][event_col],
            event_observed_B=kmfs[l2][1][event_col],
        )
        p_logrank = float(res.p_value)
    elif not overall and len(levels) > 2:
        res = multivariate_logrank_test(d[time_col], d[group_var], d[event_col])
        p_logrank = float(res.p_value)
    else:
        p_logrank = np.nan

    if np.isfinite(p_logrank):
        # 放在左下角空白区，避免与右侧时间点标注重叠
        ax.text(0.03, 0.06, texts["logrank_prefix"] + " " + _format_p(p_logrank, texts),
                transform=ax.transAxes, ha="left", va="bottom", fontsize=11)

    # 图例：显示中位生存期及 95%CI（整体模式不显示分组标题）
    handles = [plt.Line2D([0], [0], color=palette[i % len(palette)], lw=2)
               for i in range(len(levels))]
    legend_title = None if overall else texts["grouped_by"].format(var=group_var)
    ax.legend(handles, legend_entries, loc="upper right", frameon=False,
              fontsize=10, title=legend_title)

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
                txt = texts["surv_label"].format(
                    group=label, time=_time_label(t, texts), pct=f"{s*100:.1f}")
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
    ax_risk.set_xlabel(texts["xlabel"], fontsize=12)
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
    ax_risk.text(x_label, n_g + 0.42, texts["no_at_risk"], ha="right", va="center",
                 fontsize=9, fontweight="bold", clip_on=False)

    # 按配置导出（save_path 为 None 时不写磁盘，由调用层处理保存/下载）
    tp_df = pd.DataFrame(tp_records) if tp_records else None
    if save_path is not None:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        fmts = ["pdf", "png"] if config.EXPORT_FORMAT == "both" else [config.EXPORT_FORMAT]
        for fmt in fmts:
            fig.savefig(f"{save_path}.{fmt}", dpi=max(config.DPI, 300),
                        bbox_inches="tight", pad_inches=0.08)
        extra = (f"（log-rank {_format_p(p_logrank, texts)}）"
                 if np.isfinite(p_logrank) else "（整体曲线）")
        print(f"  KM 曲线已保存：{save_path}.[{'/'.join(fmts)}]{extra}")
        plt.close(fig)
    return fig, tp_df
