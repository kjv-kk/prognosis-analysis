# -*- coding: utf-8 -*-
"""
prognosis-analysis 程序入口：肿瘤预后生存分析工具。

流程：数据读取 → 检查清洗 → KM 曲线（OS/PFS）→ 单因素 Cox →
多因素 Cox → 森林图 → 结果导出 Excel。
"""

import os
import sys
import pandas as pd

# Windows 终端兼容：强制 stdout/stderr 使用 UTF-8，避免中文乱码
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from src.data_utils import read_data, check_and_clean, get_endpoint_cols
from src.km_plot import plot_km
from src.cox_analysis import univariate_cox, select_multivariable_vars, multivariate_cox
from src.forest_plot import plot_forest
from src.export_utils import export_results


def main():
    """主流程：从 config.py 读取全部配置并依次执行分析。"""
    print("=" * 60)
    print("肿瘤预后生存分析工具 prognosis-analysis")
    print("=" * 60)

    # 1. 读取数据
    print(f"\n数据文件：{config.FILE_PATH}")
    df = read_data(config.FILE_PATH)
    print(f"读取成功：{df.shape[0]} 行 × {df.shape[1]} 列")

    # 2. 数据检查与清洗
    df_clean, check_summary = check_and_clean(df, config)

    # 3. KM 曲线（OS / PFS 分别绘制）
    timepoints_parts = []
    if config.KM_GROUP_VAR:
        print("\n" + "=" * 60)
        print("【第二步】KM 曲线分析")
        print("=" * 60)
        for ep, tcol, ecol in get_endpoint_cols(config):
            print(f"\n  终点 {ep}（分组变量：{config.KM_GROUP_VAR}）：")
            tp = plot_km(df_clean, ep, tcol, ecol, config)
            if tp is not None:
                timepoints_parts.append(tp)
    else:
        print("\nconfig.KM_GROUP_VAR 为空，跳过 KM 绘图。")

    timepoints_df = (pd.concat(timepoints_parts, ignore_index=True)
                     if timepoints_parts else None)

    # 4. 单因素 Cox（默认终点 OS）
    uni_results, uni_tcol, uni_ecol = univariate_cox(df_clean, config, endpoint="OS")

    # 5. 多因素 Cox
    selected = select_multivariable_vars(uni_results, config)
    multi_results, _, _ = multivariate_cox(df_clean, config, uni_results, selected,
                                           endpoint="OS")

    # 6. 森林图
    print("\n" + "=" * 60)
    print("【第三步】森林图")
    print("=" * 60)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    plot_forest(uni_results, config,
                os.path.join(config.OUTPUT_DIR, "forest_uni"),
                title="Univariate Cox Regression (OS)")
    if multi_results is not None:
        plot_forest(multi_results, config,
                    os.path.join(config.OUTPUT_DIR, "forest_multi"),
                    title="Multivariate Cox Regression (OS)")
    else:
        print("  多因素分析未运行，跳过森林图（多因素）。")

    # 7. 导出 Excel
    print("\n" + "=" * 60)
    print("【第四步】结果导出")
    print("=" * 60)
    export_results(config.OUTPUT_DIR, check_summary, uni_results, multi_results,
                   timepoints_df, endpoint="OS")

    print("\n分析全部完成！输出目录：" + os.path.abspath(config.OUTPUT_DIR))


if __name__ == "__main__":
    main()
