# -*- coding: utf-8 -*-
"""
示例数据生成脚本：生成约 200 例虚拟肿瘤患者数据（脱敏，无任何真实患者信息）。

用法：
    python example_data/generate_example_data.py

生成列：ID、Age、Gender、Stage、Gene_High、OS_time、OS_event、PFS_time、PFS_event
生存时间服从指数分布，受 Age / Gene_High / Stage 影响；PFS <= OS；
删失比例约 20%-30%。固定随机种子，结果可复现。
"""

import os
import sys
import numpy as np
import pandas as pd

# Windows 终端兼容：强制 stdout 使用 UTF-8，避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SEED = 42
N = 200  # 虚拟患者例数


def main():
    """生成模拟数据并保存为 CSV。"""
    rng = np.random.default_rng(SEED)

    # 基本特征（全部为模拟值）
    ids = [f"PAT{i:03d}" for i in range(1, N + 1)]
    age = np.clip(np.round(rng.normal(62, 10, N)), 30, 88).astype(int)
    gender = rng.binomial(1, 0.5, N)  # 0/1
    stage = rng.choice(["I", "II", "III", "IV"], size=N, p=[0.20, 0.30, 0.30, 0.20])
    gene_high = rng.binomial(1, 0.40, N)  # 0/1

    # 真实风险受 Age / Gene_High / Stage 影响（线性预测子）
    stage_effect = pd.Series(stage).map({"I": 0.0, "II": 0.4, "III": 0.9, "IV": 1.5}).to_numpy()
    lp = 0.030 * (age - 62) + 0.80 * gene_high + stage_effect + 0.30 * gender

    # 指数分布生存时间：baseline 风险 0.010/月，删失约 20%-30%
    base_rate = 0.010
    os_event_time = rng.exponential(1.0 / (base_rate * np.exp(lp)))
    # 均匀入组（0-12 月），随访窗口至 48 月 → 行政删失
    entry_time = rng.uniform(0, 12, N)
    window = 48.0 - entry_time

    os_time = np.minimum(os_event_time, window)
    os_event = (os_event_time <= window).astype(int)

    # PFS：进展通常早于死亡，取 OS 事件时间的一个比例，保证 PFS <= OS
    pfs_event_time = os_event_time * rng.uniform(0.40, 0.90, N)
    pfs_time = np.minimum(pfs_event_time, window)
    pfs_event = (pfs_event_time <= window).astype(int)

    df = pd.DataFrame({
        "ID": ids,
        "Age": age,
        "Gender": gender,
        "Stage": stage,
        "Gene_High": gene_high,
        "OS_time": np.round(os_time, 1),
        "OS_event": os_event,
        "PFS_time": np.round(pfs_time, 1),
        "PFS_event": pfs_event,
    })

    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "example_data.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    censor_rate = 1 - os_event.mean()
    print(f"已生成 {len(df)} 例虚拟患者数据：{out_path}")
    print(f"OS 事件率：{os_event.mean():.1%}，删失比例约 {censor_rate:.1%}")
    print(f"PFS 事件率：{pfs_event.mean():.1%}")


if __name__ == "__main__":
    main()
