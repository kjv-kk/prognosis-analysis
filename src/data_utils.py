# -*- coding: utf-8 -*-
"""
数据工具模块：数据读取、检查清洗、变量编码。
"""

import os
import numpy as np
import pandas as pd


def read_data(path):
    """
    按扩展名自动识别并读取数据文件（.xlsx/.xls/.csv）。

    参数:
        path: 数据文件路径

    返回:
        pd.DataFrame: 读取的数据表
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if ext == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"不支持的数据文件格式：{ext}（仅支持 .xlsx/.xls/.csv）")


def get_endpoint_cols(config):
    """
    获取已启用的终点（时间列、事件列、终点名）列表。

    参数:
        config: 配置模块

    返回:
        list[tuple]: [(终点名, 时间列, 事件列), ...]，如未配置 PFS 则只含 OS
    """
    endpoints = [("OS", config.OS_TIME_COL, config.OS_EVENT_COL)]
    if getattr(config, "PFS_TIME_COL", "") and getattr(config, "PFS_EVENT_COL", ""):
        endpoints.append(("PFS", config.PFS_TIME_COL, config.PFS_EVENT_COL))
    return endpoints


def get_feature_cols(df, config):
    """
    获取分析特征列列表（排除 ID/时间/事件列）。

    参数:
        df: 数据表
        config: 配置模块

    返回:
        list[str]: 特征列名列表；若 config.UNI_VARS 非空则直接使用
    """
    if config.UNI_VARS:
        return list(config.UNI_VARS)
    exclude = {config.ID_COL}
    for _, tcol, ecol in get_endpoint_cols(config):
        exclude.add(tcol)
        exclude.add(ecol)
    return [c for c in df.columns if c not in exclude]


def check_and_clean(df, config):
    """
    数据检查与清洗：分别对每个终点检查时间缺失/<=0、事件非 0/1、特征缺失，
    打印中文检查报告，剔除问题行后返回清洗结果。

    参数:
        df: 原始数据表
        config: 配置模块

    返回:
        tuple: (清洗后的 pd.DataFrame, 检查汇总 list[dict])
    """
    print("=" * 60)
    print("【第一步】数据检查与清洗")
    print("=" * 60)

    n_total = len(df)
    summary = [{"检查项": "原始数据总行数", "问题行数": "", "处理方式": ""}]
    print(f"原始数据共 {n_total} 行、{df.shape[1]} 列。")

    problem_mask = pd.Series(False, index=df.index)

    # 逐终点检查时间与事件列
    for ep, tcol, ecol in get_endpoint_cols(config):
        if tcol not in df.columns:
            raise KeyError(f"找不到时间列：{tcol}（终点 {ep}），请检查 config.py 列名设置")
        if ecol not in df.columns:
            raise KeyError(f"找不到事件列：{ecol}（终点 {ep}），请检查 config.py 列名设置")

        time_num = pd.to_numeric(df[tcol], errors="coerce")
        bad_time = time_num.isna() | (time_num <= 0)
        n_bad_time = int(bad_time.sum())
        summary.append({
            "检查项": f"{ep}：时间缺失或非正值（{tcol}）",
            "问题行数": n_bad_time,
            "处理方式": "剔除" if n_bad_time > 0 else "无",
        })
        print(f"  - {ep} 时间列 {tcol}：缺失或 <=0 共 {n_bad_time} 行" +
              ("，已剔除" if n_bad_time > 0 else ""))
        problem_mask = problem_mask | bad_time

        evt_num = pd.to_numeric(df[ecol], errors="coerce")
        bad_evt = evt_num.isna() | (~evt_num.isin([0, 1]))
        n_bad_evt = int(bad_evt.sum())
        summary.append({
            "检查项": f"{ep}：事件取值非 0/1（{ecol}）",
            "问题行数": n_bad_evt,
            "处理方式": "剔除" if n_bad_evt > 0 else "无",
        })
        print(f"  - {ep} 事件列 {ecol}：非 0/1 取值共 {n_bad_evt} 行" +
              ("，已剔除" if n_bad_evt > 0 else ""))
        problem_mask = problem_mask | bad_evt

    # 特征缺失检查
    feat_cols = get_feature_cols(df, config)
    n_feat_missing = 0
    for col in feat_cols:
        if col not in df.columns:
            raise KeyError(f"配置的分析变量不存在于数据中：{col}")
        m = df[col].isna()
        n_m = int(m.sum())
        if n_m > 0:
            print(f"  - 特征 {col}：缺失 {n_m} 行，已剔除")
        n_feat_missing += n_m
        problem_mask = problem_mask | m
    summary.append({
        "检查项": "分析特征缺失（各特征合计）",
        "问题行数": n_feat_missing,
        "处理方式": "剔除含缺失特征的行" if n_feat_missing > 0 else "无",
    })

    n_drop = int(problem_mask.sum())
    df_clean = df.loc[~problem_mask].copy()
    # 统一时间与事件列为数值型，便于后续分析
    for _, tcol, ecol in get_endpoint_cols(config):
        df_clean[tcol] = pd.to_numeric(df_clean[tcol])
        df_clean[ecol] = pd.to_numeric(df_clean[ecol]).astype(int)

    summary.append({"检查项": "合计剔除行数", "问题行数": n_drop, "处理方式": "剔除"})
    summary.append({"检查项": "清洗后剩余行数", "问题行数": len(df_clean), "处理方式": "用于后续分析"})
    print(f"共剔除 {n_drop} 行，清洗后剩余 {len(df_clean)} 行，用于后续分析。")

    if len(df_clean) == 0:
        raise ValueError("清洗后无可用数据，请检查数据文件与 config.py 配置！")
    return df_clean, summary


def _detect_var_type(df, var, config):
    """自动识别变量类型：数值型且唯一值=2→binary；数值型其他→continuous；非数值型→categorical。"""
    ser = df[var].dropna()
    if pd.api.types.is_numeric_dtype(ser):
        return "binary" if ser.nunique() == 2 else "continuous"
    return "categorical"


def _ordered_levels(df, var, config):
    """
    获取变量水平顺序：优先使用 config.CAT_LEVELS，否则按取值排序。
    只保留数据中实际出现的水平。
    """
    present = list(pd.unique(df[var].dropna()))
    custom = config.CAT_LEVELS.get(var) if hasattr(config, "CAT_LEVELS") else None
    if custom:
        # 配置中给出但未在数据出现的水平给出提示
        missing = [l for l in custom if l not in present]
        if missing:
            print(f"  提示：变量 {var} 的配置水平 {missing} 在数据中未出现，已忽略。")
        return [l for l in custom if l in present]
    try:
        return sorted(present)
    except TypeError:
        return sorted(present, key=lambda x: str(x))


def build_design_matrix(df, var, config):
    """
    把单个变量转换为 Cox 模型可用的数值设计矩阵。

    编码规则：
      - continuous：原样作为数值列；
      - binary：确保编码为 0/1（非 0/1 取值按水平排序，第一水平=0 参照，第二水平=1）；
      - categorical：哑变量 one-hot 编码（以排序第一组为参照，可用 CAT_LEVELS 指定顺序），
        列名形如 "Stage[T.II]"，内部使用 pd.get_dummies(drop_first=True) 实现；
      - ordinal：按水平顺序映射为 0,1,2,... 的有序数值列。

    参数:
        df: 清洗后的数据表
        var: 变量名
        config: 配置模块

    返回:
        tuple: (X_df, term_cols, var_meta)
            X_df — 仅含该变量数值列的 DataFrame（索引与 df 对齐）
            term_cols — 进入模型的列名列表
            var_meta — 元信息 dict（类型、参照水平、编码为 1 的水平、全部水平等）
    """
    vtype = config.VAR_TYPES.get(var) if hasattr(config, "VAR_TYPES") else None
    if vtype is None:
        vtype = _detect_var_type(df, var, config)

    var_meta = {
        "variable": var,
        "type": vtype,
        "ref": None,
        "levels": None,
        "level_for_1": None,
        "term_cols": [],
    }
    X = pd.DataFrame(index=df.index)

    if vtype == "continuous":
        X[var] = pd.to_numeric(df[var]).astype(float)
        var_meta["term_cols"] = [var]

    elif vtype == "binary":
        vals = pd.unique(df[var].dropna())
        if set(pd.unique(pd.Series(vals).astype(str))) <= {"0", "1"} or set(vals) <= {0, 1}:
            # 已是 0/1 编码
            X[var] = pd.to_numeric(df[var]).astype(float)
            var_meta.update(ref=0, levels=[0, 1], level_for_1=1)
        else:
            levels = _ordered_levels(df, var, config)
            if len(levels) != 2:
                raise ValueError(
                    f"变量 {var} 被指定/识别为二分类，但实际有 {len(levels)} 个水平：{levels}")
            ref, lev1 = levels[0], levels[1]
            X[var] = (df[var] == lev1).astype(float)
            var_meta.update(ref=ref, levels=levels, level_for_1=lev1)
            print(f"  提示：二分类变量 {var} 已因子化为 0/1（1 = {lev1}，0 = {ref} 参照）。")
        var_meta["term_cols"] = [var]

    elif vtype == "categorical":
        levels = _ordered_levels(df, var, config)
        ref = levels[0]
        # 使用 get_dummies 实现 one-hot 编码，并按 CAT_LEVELS 顺序重排列
        dummies = pd.get_dummies(df[var], prefix=var, drop_first=False, dtype=float)
        term_cols = []
        for lev in levels[1:]:
            col = f"{var}[T.{lev}]"
            raw_col = f"{var}_{lev}"
            if raw_col in dummies.columns:
                X[col] = dummies[raw_col].astype(float)
            else:
                X[col] = (df[var] == lev).astype(float)
            term_cols.append(col)
        var_meta.update(ref=ref, levels=levels, term_cols=term_cols)

    elif vtype == "ordinal":
        levels = _ordered_levels(df, var, config)
        mapping = {lev: i for i, lev in enumerate(levels)}
        X[var] = df[var].map(mapping).astype(float)
        var_meta.update(ref=levels[0], levels=levels, term_cols=[var])

    else:
        raise ValueError(f"变量 {var} 的类型配置无效：{vtype}")

    return X, var_meta["term_cols"], var_meta
