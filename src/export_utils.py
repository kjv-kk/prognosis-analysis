# -*- coding: utf-8 -*-
"""
结果导出模块：把检查报告与 Cox 分析结果导出到 Excel。
"""

import os
import numpy as np
import pandas as pd


def _round_or_none(x, nd=4):
    """数值保留小数；缺失/非有限值返回空字符串。"""
    if x is None:
        return ""
    try:
        if not np.isfinite(x):
            return ""
        return round(float(x), nd)
    except (TypeError, ValueError):
        return ""


def _cox_rows(results):
    """
    把 Cox 结果展开为 Excel 行：每个变量先一行整体汇总，
    多分类变量再逐哑变量水平分行（HR 以参照组为基准）。

    返回:
        list[dict]: Excel 行列表
    """
    rows = []
    for r in results:
        base = {
            "Variable": r["variable"],
            "Type": r["type"],
            "n": r["n"],
            "Events": r["events"],
        }
        if not r.get("terms"):
            rows.append({
                **base,
                "Term": "Overall",
                "HR": "",
                "HR_95%CI_lower": "",
                "HR_95%CI_upper": "",
                "P": _round_or_none(r["p"]),
                "Note": r.get("note", ""),
            })
            continue
        if len(r["terms"]) == 1:
            t = r["terms"][0]
            note = r.get("note", "")
            meta = r.get("meta", {})
            if r["type"] == "binary" and meta.get("level_for_1") not in (None, 1):
                note = (note + " " if note else "") + f"1 = {meta['level_for_1']}（参照 = {meta['ref']}）"
            rows.append({
                **base,
                "Term": t["term"],
                "HR": _round_or_none(t["hr"], 3),
                "HR_95%CI_lower": _round_or_none(t["ci_lower"], 3),
                "HR_95%CI_upper": _round_or_none(t["ci_upper"], 3),
                "P": _round_or_none(t["p"]),
                "Note": note,
            })
        else:
            # 多分类：先整体行（整体似然比检验 P 值），再逐水平行
            rows.append({
                **base,
                "Term": "Overall (LR test)",
                "HR": "",
                "HR_95%CI_lower": "",
                "HR_95%CI_upper": "",
                "P": _round_or_none(r["p"]),
                "Note": f"参照组 = {r['meta'].get('ref')}",
            })
            for t in r["terms"]:
                rows.append({
                    **base,
                    "Term": t["term"],
                    "HR": _round_or_none(t["hr"], 3),
                    "HR_95%CI_lower": _round_or_none(t["ci_lower"], 3),
                    "HR_95%CI_upper": _round_or_none(t["ci_upper"], 3),
                    "P": _round_or_none(t["p"]),
                    "Note": f"vs 参照组 {r['meta'].get('ref')}",
                })
    return rows


def export_results(output_dir, check_summary, uni_results, multi_results, timepoints_df,
                   endpoint="OS"):
    """
    导出分析结果到 output/analysis_results.xlsx。

    Sheet：Data_Check（数据检查报告）、Univariate_Cox、Multivariate_Cox，
    若开启时间点标注则追加 Survival_at_Timepoints。

    参数:
        output_dir: 输出目录
        check_summary: 数据检查汇总 list[dict]
        uni_results: 单因素 Cox 结果列表
        multi_results: 多因素 Cox 结果列表（None 表示未运行）
        timepoints_df: 时间点生存率汇总 DataFrame（None 表示无）
        endpoint: Cox 分析终点名
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "analysis_results.xlsx")

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(check_summary).to_excel(writer, sheet_name="Data_Check", index=False)
        pd.DataFrame(_cox_rows(uni_results)).to_excel(writer, sheet_name="Univariate_Cox", index=False)
        if multi_results is not None:
            pd.DataFrame(_cox_rows(multi_results)).to_excel(writer, sheet_name="Multivariate_Cox", index=False)
        if timepoints_df is not None and not timepoints_df.empty:
            timepoints_df.to_excel(writer, sheet_name="Survival_at_Timepoints", index=False)

    print(f"\nExcel 结果已导出：{path}")
