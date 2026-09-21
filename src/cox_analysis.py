# -*- coding: utf-8 -*-
"""
Cox 分析模块：单因素 / 多因素 Cox 比例风险回归。
"""

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from scipy import stats

from .data_utils import build_design_matrix, get_feature_cols

ALPHA = 0.05  # 多因素自动纳入的 P 值阈值


def _fit_cox(durations, events, X=None):
    """
    拟合 Cox 模型，返回 (fitter, 设计矩阵列名)；无协变量时拟合空模型。

    参数:
        durations: 生存时间
        events: 事件指示（0/1）
        X: 协变量 DataFrame（可选）

    返回:
        tuple: (CoxPHFitter, term_cols)
    """
    if X is None or X.shape[1] == 0:
        df_fit = pd.DataFrame({"T": durations, "E": events})
        cph = CoxPHFitter()
        cph.fit(df_fit, duration_col="T", event_col="E")
        return cph, []
    df_fit = X.copy()
    df_fit["T"] = durations
    df_fit["E"] = events
    cph = CoxPHFitter()
    cph.fit(df_fit, duration_col="T", event_col="E")
    return cph, list(X.columns)


def _lr_test_p(full_ll, reduced_ll, df_diff):
    """
    似然比检验：2*(ll_full - ll_reduced) 服从自由度为 df_diff 的卡方分布。

    返回:
        float: P 值
    """
    stat = 2 * (full_ll - reduced_ll)
    stat = max(stat, 0.0)
    return float(stats.chi2.sf(stat, df_diff))


def _extract_terms(cph, term_cols, var_meta=None):
    """
    从拟合结果中提取各 term 的 HR、95%CI、P 值。

    返回:
        list[dict]: 每个 term 一行 {term, hr, ci_lower, ci_upper, p}
    """
    terms = []
    s = cph.summary
    for col in term_cols:
        if col not in s.index:
            terms.append({"term": col, "hr": np.nan, "ci_lower": np.nan,
                          "ci_upper": np.nan, "p": np.nan})
            continue
        terms.append({
            "term": col,
            "hr": float(s.loc[col, "exp(coef)"]),
            "ci_lower": float(s.loc[col, "exp(coef) lower 95%"]),
            "ci_upper": float(s.loc[col, "exp(coef) upper 95%"]),
            "p": float(s.loc[col, "p"]),
        })
    return terms


def _separation_note(terms):
    """
    启发式检测完全分离/退化结果：HR 或 CI 极端（接近 0 或无穷大）时给出备注。

    返回:
        str: 备注文字；无异常时返回空字符串
    """
    for t in terms:
        hr, lo, hi = t["hr"], t["ci_lower"], t["ci_upper"]
        vals = [v for v in (hr, lo, hi) if v is not None and np.isfinite(v)]
        if any(v <= 1e-6 or v >= 1e6 for v in vals):
            return "疑似完全分离或结果退化，HR 不可靠，建议合并水平或剔除该变量"
    return ""


def _result_dict(var, meta, n, events, terms, p, note=""):
    """组装单个变量的结果字典（变量级汇总 + term 级明细）。"""
    if len(terms) == 1:
        hr, lo, hi = terms[0]["hr"], terms[0]["ci_lower"], terms[0]["ci_upper"]
    else:
        # 多分类变量：变量级 HR 无单一取值，置空，P 用整体似然比检验
        hr = lo = hi = np.nan
    return {
        "variable": var,
        "type": meta["type"],
        "n": n,
        "events": events,
        "hr": hr,
        "ci_lower": lo,
        "ci_upper": hi,
        "p": p,
        "terms": terms,
        "meta": meta,
        "note": note,
    }


def univariate_cox(df, config, endpoint="OS"):
    """
    单因素 Cox 分析：对 UNI_VARS（空=全部特征）逐变量单独建模。

    多分类变量整体 P 值用整体模型 vs 空模型的似然比检验；term 级 HR/CI/P 来自
    lifelines 拟合结果，供森林图分行显示。拟合失败（如完全分离）的变量会标注并跳过。

    参数:
        df: 清洗后的数据表
        config: 配置模块
        endpoint: 分析终点（默认 OS）

    返回:
        tuple: (结果 list[dict], 时间列名, 事件列名)
    """
    print("\n" + "=" * 60)
    print(f"【单因素 Cox 分析】终点：{endpoint}")
    print("=" * 60)

    tcol = config.OS_TIME_COL if endpoint == "OS" else config.PFS_TIME_COL
    ecol = config.OS_EVENT_COL if endpoint == "OS" else config.PFS_EVENT_COL
    durations = df[tcol].astype(float)
    events = df[ecol].astype(int)

    vars_ = get_feature_cols(df, config)
    # 拟合空模型用于多分类变量的整体似然比检验
    null_cph, _ = _fit_cox(durations, events)

    results = []
    print(f"{'变量':<14}{'类型':<14}{'n':>6}{'事件':>6}{'HR':>10}{'CI下限':>10}{'CI上限':>10}{'P值':>12}")
    for var in vars_:
        try:
            X, term_cols, meta = build_design_matrix(df, var, config)
            n = int(len(X))
            n_events = int(events.sum())
            cph, _ = _fit_cox(durations, events, X)
            terms = _extract_terms(cph, term_cols)
            if meta["type"] == "categorical" and len(term_cols) > 1:
                p = _lr_test_p(cph.log_likelihood_, null_cph.log_likelihood_, len(term_cols))
            else:
                p = terms[0]["p"]
            note = _separation_note(terms)
            r = _result_dict(var, meta, n, n_events, terms, p, note=note)
            results.append(r)
            hr_s = f"{r['hr']:.3f}" if np.isfinite(r["hr"]) else "-"
            lo_s = f"{r['ci_lower']:.3f}" if np.isfinite(r["ci_lower"]) else "-"
            hi_s = f"{r['ci_upper']:.3f}" if np.isfinite(r["ci_upper"]) else "-"
            flag = "  <-- " + note if note else ""
            print(f"{var:<14}{meta['type']:<14}{n:>6}{n_events:>6}{hr_s:>10}{lo_s:>10}{hi_s:>10}{p:>12.4f}{flag}")
        except Exception as e:
            note = f"拟合失败：{type(e).__name__}: {e}"
            meta = {"variable": var, "type": config.VAR_TYPES.get(var, "auto"),
                    "ref": None, "levels": None, "level_for_1": None, "term_cols": []}
            results.append({
                "variable": var, "type": meta["type"], "n": len(df),
                "events": int(events.sum()), "hr": np.nan, "ci_lower": np.nan,
                "ci_upper": np.nan, "p": np.nan, "terms": [], "meta": meta, "note": note,
            })
            print(f"{var:<14}{meta['type']:<14}{len(df):>6}{int(events.sum()):>6}    拟合失败（已记录，详见 Excel 备注）")

    return results, tcol, ecol


def select_multivariable_vars(uni_results, config):
    """
    确定多因素模型变量：MULTI_VARS 非空时按配置，否则自动纳入单因素 P < 0.05 的变量。

    参数:
        uni_results: 单因素分析结果列表
        config: 配置模块

    返回:
        list[str]: 变量名列表
    """
    if config.MULTI_VARS:
        print(f"\n多因素分析变量（按 config.MULTI_VARS 指定）：{config.MULTI_VARS}")
        return list(config.MULTI_VARS)

    selected = [r["variable"] for r in uni_results
                if np.isfinite(r["p"]) and r["p"] < ALPHA and not r["note"]]
    print(f"\n多因素分析变量（自动纳入单因素 P < {ALPHA}）：{selected}")
    if not selected:
        print("  没有单因素 P < 0.05 的变量，多因素分析将跳过。")
    return selected


def multivariate_cox(df, config, uni_results, selected_vars, endpoint="OS"):
    """
    多因素 Cox 分析：合并所选变量的设计矩阵一次性拟合。

    连续/二分类变量每变量一行；多分类变量整体 P 值用全模型 vs
    去掉该变量全部哑变量的简化模型的似然比检验。

    参数:
        df: 清洗后的数据表
        config: 配置模块
        uni_results: 单因素结果（用于取各变量元信息）
        selected_vars: 纳入多因素模型的变量列表
        endpoint: 分析终点（默认 OS）

    返回:
        tuple: (结果 list[dict], 时间列名, 事件列名)；无可用变量时返回 (None, tcol, ecol)
    """
    print("\n" + "=" * 60)
    print(f"【多因素 Cox 分析】终点：{endpoint}")
    print("=" * 60)

    tcol = config.OS_TIME_COL if endpoint == "OS" else config.PFS_TIME_COL
    ecol = config.OS_EVENT_COL if endpoint == "OS" else config.PFS_EVENT_COL
    if not selected_vars:
        print("未选择任何变量，跳过多因素分析。")
        return None, tcol, ecol

    durations = df[tcol].astype(float)
    events = df[ecol].astype(int)

    # 合并各变量的设计矩阵
    X_all = pd.DataFrame(index=df.index)
    meta_map = {}
    for var in selected_vars:
        X, term_cols, meta = build_design_matrix(df, var, config)
        X_all = pd.concat([X_all, X], axis=1)
        meta_map[var] = (term_cols, meta)

    n = len(X_all)
    n_events = int(events.sum())
    print(f"纳入变量 {len(selected_vars)} 个，n = {n}，事件数 = {n_events}。")
    print(f"{'变量':<14}{'类型':<14}{'HR':>10}{'CI下限':>10}{'CI上限':>10}{'P值':>12}")

    try:
        full_cph, _ = _fit_cox(durations, events, X_all)
    except Exception as e:
        print(f"多因素模型整体拟合失败：{type(e).__name__}: {e}")
        return None, tcol, ecol

    results = []
    for var in selected_vars:
        term_cols, meta = meta_map[var]
        try:
            if meta["type"] == "categorical" and len(term_cols) > 1:
                # 整体 P：全模型 vs 去掉该变量全部哑变量的简化模型
                X_red = X_all.drop(columns=term_cols)
                red_cph, _ = _fit_cox(durations, events, X_red)
                p = _lr_test_p(full_cph.log_likelihood_, red_cph.log_likelihood_, len(term_cols))
            else:
                p = float(full_cph.summary.loc[term_cols[0], "p"])
            terms = _extract_terms(full_cph, term_cols)
            note = _separation_note(terms)
            r = _result_dict(var, meta, n, n_events, terms, p, note=note)
            results.append(r)
            hr_s = f"{r['hr']:.3f}" if np.isfinite(r["hr"]) else "-"
            lo_s = f"{r['ci_lower']:.3f}" if np.isfinite(r["ci_lower"]) else "-"
            hi_s = f"{r['ci_upper']:.3f}" if np.isfinite(r["ci_upper"]) else "-"
            flag = "  <-- " + note if note else ""
            print(f"{var:<14}{meta['type']:<14}{hr_s:>10}{lo_s:>10}{hi_s:>10}{p:>12.4f}{flag}")
        except Exception as e:
            note = f"该变量结果提取失败：{type(e).__name__}: {e}"
            results.append({
                "variable": var, "type": meta["type"], "n": n, "events": n_events,
                "hr": np.nan, "ci_lower": np.nan, "ci_upper": np.nan, "p": np.nan,
                "terms": [], "meta": meta, "note": note,
            })
            print(f"{var:<14}{meta['type']:<14}    结果提取失败（已记录）")

    return results, tcol, ecol
