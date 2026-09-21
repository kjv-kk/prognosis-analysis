# prognosis-analysis：肿瘤预后生存分析工具

一个**改配置即可跑**的肿瘤预后生存分析工具，面向医学研究人员。完成从数据检查清洗、
KM 曲线、单因素/多因素 Cox 回归、森林图到 Excel 结果导出的完整流程。图形文字为英文
（医学期刊惯例），控制台报告为中文。

## 功能特性

- **数据检查清洗**：自动检查时间缺失/非正值、事件非 0/1、特征缺失，打印中文报告并剔除问题行
- **KM 曲线**：OS / PFS 分别绘制，log-rank 检验 P 值，中位生存期及 95%CI，
  图下方 number at risk 风险人数表，可配置时间点生存率标注（如 1-yr: 85.2%）；
  可选整体（不分组）曲线，查看全队列单纯的 OS/PFS 分布（`KM_OVERALL`）
- **单因素 Cox**：逐变量建模，多分类变量给出整体似然比检验 P 值及各水平 HR/95%CI
- **多因素 Cox**：自动纳入单因素 P<0.05 的变量，或手动指定；多分类变量整体 P 值
  用全模型 vs 简化模型的似然比检验
- **森林图**：发表级单/多因素森林图，多分类变量以参照组为基准分行显示
- **变量编码灵活**：连续型 / 二分类 / 多分类（哑变量 one-hot，可指定参照组）/ 有序数值，
  逐变量在 `config.py` 中指定
- **结果导出**：`output/analysis_results.xlsx`（Data_Check / Univariate_Cox /
  Multivariate_Cox / Survival_at_Timepoints 四个 sheet）

## 目录结构

```
prognosis-analysis/
├── README.md              # 本文件
├── LICENSE                # MIT
├── requirements.txt       # 依赖清单
├── .gitignore
├── config.py              # 所有可配置项集中于此
├── main.py                # 程序入口
├── src/
│   ├── __init__.py
│   ├── style.py           # 期刊配色方案
│   ├── data_utils.py      # 数据读取/检查/清洗/变量编码
│   ├── km_plot.py         # KM 曲线、风险表、时间点标注
│   ├── cox_analysis.py    # 单/多因素 Cox
│   ├── forest_plot.py     # 森林图
│   └── export_utils.py    # Excel 导出
├── example_data/
│   ├── generate_example_data.py   # 生成模拟数据脚本（固定随机种子）
│   └── example_data.csv           # 示例数据（约200例虚拟病人，脱敏）
└── output/                # 分析输出目录
```

## 安装步骤

需要 Python 3.10+（开发验证环境为 Python 3.13）：

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
cd prognosis-analysis
python example_data/generate_example_data.py   # 第一步：生成示例数据
python main.py                                 # 第二步：运行全部分析
```

运行后 `output/` 目录下生成：

- `KM_OS.pdf/.png`、`KM_PFS.pdf/.png`：OS / PFS 的 KM 曲线
- `forest_uni.pdf/.png`、`forest_multi.pdf/.png`：单/多因素森林图
- `analysis_results.xlsx`：全部表格结果

## config.py 配置说明

| 配置项 | 说明 |
| --- | --- |
| `FILE_PATH` | 数据文件路径，支持 `.xlsx`/`.xls`/`.csv` 自动识别 |
| `ID_COL` | 患者编号列名（不参与分析） |
| `OS_TIME_COL` / `OS_EVENT_COL` | OS 时间/事件列名 |
| `PFS_TIME_COL` / `PFS_EVENT_COL` | PFS 时间/事件列名；`PFS_TIME_COL` 留空则跳过 PFS |
| `UNI_VARS` | 单因素分析变量列表；空列表 = 除 ID/时间/事件外的所有特征列 |
| `MULTI_VARS` | 多因素分析变量列表；空列表 = 自动纳入单因素 P<0.05 的变量 |
| `VAR_TYPES` | 逐变量指定类型：`"continuous"`/`"binary"`/`"categorical"`（哑变量）/`"ordinal"`；不指定的自动识别 |
| `CAT_LEVELS` | 多分类/二分类变量的水平顺序，**第一组为参照组**；不填则按取值排序 |
| `KM_GROUP_VAR` | KM 曲线分组变量；空字符串则跳过 KM 绘图 |
| `KM_OVERALL` | 是否额外绘制整体（不分组）KM 曲线：全队列一条曲线、不做 log-rank，用于查看单纯的 OS/PFS 分布；输出 `KM_OS_overall` / `KM_PFS_overall`；默认 `True` |
| `KM_MARK_TIMEPOINTS` | 曲线上标注生存率的时间点（月），如 `[12, 24, 36]`；空列表不标注 |
| `EXPORT_FORMAT` | 图片导出格式：`"pdf"`/`"png"`/`"both"` |
| `COLOR_STYLE` | 配色风格：`"lancet"`/`"nejm"`/`"jama"`/`"nature"`/`"jco"`/`"custom"` |
| `KM_COLORS` | 自定义色组（仅 `COLOR_STYLE="custom"` 时生效） |
| `KM_LEGEND_LABELS` | 自定义图例标签；空列表则用分组实际取值 |
| `DPI` | 图片分辨率（>=300 满足期刊要求） |
| `OUTPUT_DIR` | 输出目录 |

## 输入数据格式要求

- 必须包含列：`ID`（编号）、`OS_time`/`OS_event`（总生存时间/事件）、
  `PFS_time`/`PFS_event`（无进展生存时间/事件），列名可在 `config.py` 修改
- **时间单位：月**（KM 曲线 x 轴与时间点标注均按“月”解释）
- 事件编码：**1 = 发生事件（死亡/进展），0 = 删失**；仅接受 0/1，其他取值会在
  数据检查阶段被剔除并报告
- 生存时间必须为正数；缺失或 <=0 的行会被剔除并报告
- 支持数值型与字符串型特征列；字符串列自动按多分类变量处理
- 示例文件见 `example_data/example_data.csv`

## 常见问题（FAQ）

**1. 多分类变量（如分期）如何设置参照组？**
在 `config.py` 的 `CAT_LEVELS` 中把参照组放在第一，例如
`CAT_LEVELS = {"Stage": ["I", "II", "III", "IV"]}`（I 期为参照）。
同时用 `VAR_TYPES = {"Stage": "categorical"}` 指定为哑变量编码。
若希望把分期当连续趋势变量（每升一期 HR 的增量），改用 `"ordinal"`。

**2. 如何只跑 OS（不画 PFS 的 KM 曲线）？**
把 `PFS_TIME_COL = ""`（置为空字符串）即可跳过 PFS；Cox 回归默认只针对 OS 终点。

**3. 某个变量 Cox 拟合失败怎么办？**
常见原因：完全分离（某水平全部发生/未发生事件）、某水平例数过少、事件数不足。
工具会自动捕获异常、在控制台和 Excel 备注列标注“拟合失败”并继续其他变量。
建议合并稀有水平（调 `CAT_LEVELS` 顺序或预处理数据）、剔除该变量，或增加样本量；
多分类变量整体 P 值用似然比检验，个别 dummy 异常时可参考整体 P 值。

**4. 如何只分析部分变量？**
把要分析的变量名填入 `UNI_VARS`，例如 `UNI_VARS = ["Age", "Stage"]`；
`MULTI_VARS` 同理，留空则自动纳入单因素 P<0.05 的变量。

**5. 图片里分组标签想显示“High/Low”而不是 0/1？**
设置 `KM_LEGEND_LABELS = ["Low", "High"]`（顺序与分组排序一致）。

## 网页版（Streamlit）

除命令行外，本项目自带网页应用 `streamlit_app.py`（纯交互层，分析逻辑与 `main.py`
完全共用 `src/` 模块）。功能：上传 Excel/CSV 或一键加载示例数据、侧边栏完成全部
配置（分析变量、KM 分组、时间点标注、导出格式、期刊配色、图例文字）、中英双语界面
一键切换、图表文字独立选择中文/英文、在线查看 KM 曲线 / Cox 结果表 / 森林图，
并打包下载全部图片与结果 Excel。

**本地运行：**

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**部署到 Streamlit Cloud：**

1. 将本仓库推送到 GitHub；
2. 打开 <https://share.streamlit.io/> → "New app" → 选择该仓库，
   Main file path 填 `streamlit_app.py` → Deploy；
3. `requirements.txt` 已包含 streamlit，平台会自动安装依赖，部署后即可直接使用。

**说明：**

- **界面语言**（中文/English）与**图表语言**相互独立：界面语言切换所有页面文字；
  图表语言只影响图内文字（坐标轴、图例、标注），默认英文（医学期刊惯例）。
- 图表语言选「中文」时使用仓库内置字体 `assets/fonts/NotoSansCJKsc-Regular.otf`
  （Noto Sans CJK，可自由分发），通过 matplotlib `font_manager` 加载注册，
  因此在无中文字体的服务器（Streamlit Cloud）上也不会出现方块乱码。
- KM 图例文字（`KM_LEGEND_LABELS`）属于图表内容，由用户在界面输入，不做自动翻译。
- 网页端的列名映射在侧边栏「列名映射」中完成，适配不同来源的数据文件。

## 引用方式

如果本工具对您的研究有帮助，请引用：

> Prognosis Analysis Tool (prognosis-analysis), 2026. Available at:
> https://github.com/your-lab/prognosis-analysis

## 免责声明

本工具仅供科研使用，生成的全部结果（HR、P 值、生存曲线等）均基于统计模型，
不能替代专业医学判断。示例数据为随机生成的虚拟数据，与任何真实患者无关。
临床决策请结合专业指南与临床实际情况。
