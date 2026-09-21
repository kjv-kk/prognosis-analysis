# -*- coding: utf-8 -*-
"""
Streamlit 网页入口：肿瘤预后生存分析工具。

本文件是纯交互层：上传数据、侧边栏配置、结果展示与下载；
全部分析逻辑（KM 曲线、Cox 回归、森林图、配色）复用 src/ 模块，不做改动。

本地运行：  streamlit run streamlit_app.py
部署：      推送到 GitHub 后在 Streamlit Cloud 选择本文件为主文件即可。
"""

import re
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Windows 终端中文兼容
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无界面服务器（Streamlit Cloud）也能出图
import matplotlib.pyplot as plt
from matplotlib import font_manager
import streamlit as st

import config as cli_config
from src.data_utils import check_and_clean, get_endpoint_cols
from src.km_plot import plot_km
from src.cox_analysis import univariate_cox, select_multivariable_vars, multivariate_cox
from src.forest_plot import plot_forest
from src.export_utils import export_results, _cox_rows

st.set_page_config(page_title="Prognosis Analysis", layout="wide")

# =====================================================================
# 界面语言字典：所有界面文字集中于此，禁止在代码中硬编码界面字符串
# =====================================================================
LANG = {
    "zh": {
        "lang_label": "界面语言",
        "app_title": "肿瘤预后生存分析",
        "app_caption": "上传数据 → 在侧边栏完成配置 → 点击“运行分析”。分析逻辑与命令行版（main.py）完全一致。",
        "sec_data": "数据",
        "uploader_label": "上传数据文件（.xlsx / .csv）",
        "load_example": "加载示例数据",
        "data_loaded": "数据已加载",
        "rows_cols": "{r} 行 × {c} 列",
        "colmap_expander": "列名映射（时间与事件列）",
        "col_os_time": "OS 时间列（月）",
        "col_os_event": "OS 事件列（1=死亡，0=删失）",
        "col_pfs_time": "PFS 时间列（月）",
        "col_pfs_event": "PFS 事件列（1=进展，0=删失）",
        "sec_analysis": "分析设置",
        "uni_vars_label": "单因素分析变量（不选 = 全部特征）",
        "multi_mode_label": "多因素变量选择方式",
        "multi_auto": "自动（单因素 P<0.05 的变量）",
        "multi_manual": "手动指定",
        "multi_vars_label": "多因素分析变量",
        "km_group_label": "KM 曲线分组变量",
        "no_km": "（不绘制 KM 曲线）",
        "tp_checkbox": "在 KM 曲线上标注时间点生存率",
        "tp_input_label": "时间点（月，逗号分隔，如 12, 24, 36）",
        "legend_input_label": "KM 图例文字（逗号分隔，可留空；属图表内容，不自动翻译）",
        "sec_style": "图形设置",
        "fmt_label": "图片导出格式",
        "style_label": "配色方案",
        "custom_colors_label": "自定义颜色（逗号分隔的十六进制，如 #E64B35, #4DBBD5）",
        "chart_lang_label": "图表语言（独立于界面语言）",
        "chart_en": "英文",
        "chart_zh": "中文",
        "run_button": "运行分析",
        "running": "正在分析，请稍候…",
        "done": "分析完成！结果与图表如下，可在页面底部下载。",
        "check_expander": "数据检查报告（缺失值 / 异常值剔除情况）",
        "km_header": "Kaplan-Meier 生存曲线",
        "uni_header": "单因素 Cox 回归（终点：OS）",
        "multi_header": "多因素 Cox 回归（终点：OS）",
        "forest_uni_header": "单因素森林图",
        "forest_multi_header": "多因素森林图",
        "no_multi_info": "没有可纳入的变量（无单因素 P<0.05 或所选变量均拟合失败），未运行多因素分析。",
        "no_forest_info": "无可用结果，未绘制森林图。",
        "download_header": "下载结果",
        "dl_figure": "下载图片",
        "dl_excel": "下载结果 Excel（analysis_results.xlsx）",
        "need_data": "请先在侧边栏上传数据文件，或点击“加载示例数据”。",
        "example_ok": "已加载内置示例数据（虚拟数据，非真实患者）。",
        "upload_ok": "已读取上传文件。",
        "tp_error": "时间点格式无法解析，请输入逗号分隔的数字（如 12, 24, 36）。",
        "color_error": "自定义颜色格式有误，应为 #RRGGBB 或 #RGB，已改用默认配色。",
        "font_missing": "未找到内置中文字体，图表中文可能显示为方块。",
        "note_sep": "疑似完全分离或结果退化，HR 不可靠，建议合并水平或剔除该变量",
    },
    "en": {
        "lang_label": "Interface language",
        "app_title": "Cancer Prognosis Survival Analysis",
        "app_caption": "Upload data → configure in the sidebar → click \"Run analysis\". Identical logic to the CLI version (main.py).",
        "sec_data": "Data",
        "uploader_label": "Upload data file (.xlsx / .csv)",
        "load_example": "Load example data",
        "data_loaded": "Data loaded",
        "rows_cols": "{r} rows × {c} columns",
        "colmap_expander": "Column mapping (time and event columns)",
        "col_os_time": "OS time column (months)",
        "col_os_event": "OS event column (1=death, 0=censored)",
        "col_pfs_time": "PFS time column (months)",
        "col_pfs_event": "PFS event column (1=progression, 0=censored)",
        "sec_analysis": "Analysis settings",
        "uni_vars_label": "Univariate variables (none selected = all features)",
        "multi_mode_label": "Multivariable variable selection",
        "multi_auto": "Automatic (univariate P<0.05)",
        "multi_manual": "Manual",
        "multi_vars_label": "Multivariable variables",
        "km_group_label": "KM curve grouping variable",
        "no_km": "(skip KM curves)",
        "tp_checkbox": "Mark survival rates at timepoints on KM curves",
        "tp_input_label": "Timepoints (months, comma-separated, e.g. 12, 24, 36)",
        "legend_input_label": "KM legend labels (comma-separated, optional; chart content, not auto-translated)",
        "sec_style": "Figure settings",
        "fmt_label": "Image export format",
        "style_label": "Color style",
        "custom_colors_label": "Custom colors (comma-separated hex, e.g. #E64B35, #4DBBD5)",
        "chart_lang_label": "Chart language (independent of interface language)",
        "chart_en": "English",
        "chart_zh": "Chinese",
        "run_button": "Run analysis",
        "running": "Running analysis, please wait...",
        "done": "Analysis finished! Results and figures are shown below; scroll down to download.",
        "check_expander": "Data check report (missing / invalid values removed)",
        "km_header": "Kaplan-Meier Survival Curves",
        "uni_header": "Univariate Cox Regression (endpoint: OS)",
        "multi_header": "Multivariable Cox Regression (endpoint: OS)",
        "forest_uni_header": "Univariate Forest Plot",
        "forest_multi_header": "Multivariable Forest Plot",
        "no_multi_info": "No variable could be included (no univariate P<0.05 or all selected variables failed to fit); multivariable analysis skipped.",
        "no_forest_info": "No usable result; forest plot not drawn.",
        "download_header": "Download results",
        "dl_figure": "Download figure",
        "dl_excel": "Download results Excel (analysis_results.xlsx)",
        "need_data": "Please upload a data file in the sidebar, or click \"Load example data\".",
        "example_ok": "Built-in example data loaded (simulated data, not real patients).",
        "upload_ok": "Uploaded file loaded.",
        "tp_error": "Cannot parse timepoints; enter comma-separated numbers (e.g. 12, 24, 36).",
        "color_error": "Invalid custom colors; expected #RRGGBB or #RGB. Default palette will be used.",
        "font_missing": "Bundled Chinese font not found; Chinese chart text may render as boxes.",
        "note_sep": "Possible complete separation or degenerate result; HR unreliable, consider merging levels or dropping the variable",
    },
}

# =====================================================================
# 图表内部文字字典（与 src 的 FIG_TEXTS_DEFAULT 同键），实现图表语言切换
# "en" 用 None 表示沿用 src 内置英文默认值
# =====================================================================
KM_TEXTS = {
    "en": None,
    "zh": {
        "ylabel_OS": "总生存概率",
        "ylabel_PFS": "无进展生存概率",
        "xlabel": "时间（月）",
        "no_at_risk": "风险人数",
        "logrank_prefix": "Log-rank",
        "p_lt_001": "P < 0.001",
        "p_eq": "P = {p:.3f}",
        "median_not_reached": "中位生存期未达到",
        "median_fmt": "中位 {m:.1f} {mo}（{ci} {lo:.1f}–{hi:.1f}）",
        "median_na_fmt": "中位 {m:.1f} {mo}（{ci} {na}）",
        "mo": "个月",
        "ci": "95% CI",
        "na": "NA",
        "grouped_by": "按 {var} 分组",
        "time_1yr": "1 年",
        "time_month": "{t} 个月",
        "surv_label": "{group} {time}：{pct}%",
    },
}
FOREST_TEXTS = {
    "en": None,
    "zh": {
        "xlabel": "风险比（对数刻度）",
        "col_hr": "HR (95% CI)",
        "col_p": "P 值",
        "ref_fmt": "{var}（参照：{ref}）",
    },
}
# 森林图标题属于图表内容，跟随图表语言而非界面语言
FOREST_TITLES = {
    "en": ("Univariate Cox Regression (OS)", "Multivariable Cox Regression (OS)"),
    "zh": ("单因素 Cox 回归（OS）", "多因素 Cox 回归（OS）"),
}

# =====================================================================
# 中文字体：仓库内置 NotoSansCJKsc，服务器（Streamlit Cloud）无系统
# 中文字体时也能正常显示，不出现方块乱码
# =====================================================================
FONT_PATH = BASE_DIR / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf"
CJK_FONT_NAME = None
if FONT_PATH.exists():
    try:
        font_manager.fontManager.addfont(str(FONT_PATH))
        CJK_FONT_NAME = font_manager.FontProperties(fname=str(FONT_PATH)).get_name()
    except Exception:
        CJK_FONT_NAME = None


def apply_chart_font(chart_lang):
    """按图表语言设置 matplotlib 字体：中文用仓库内置字体，英文用默认字体。"""
    if chart_lang == "zh" and CJK_FONT_NAME:
        plt.rcParams["font.family"] = CJK_FONT_NAME
        plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    else:
        plt.rcParams["font.family"] = ["DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = True


def make_cfg(**overrides):
    """以 config.py 的常量为基础，用网页端配置覆盖，生成配置对象。"""
    base = {k: getattr(cli_config, k) for k in dir(cli_config) if k.isupper()}
    base.update(overrides)
    return SimpleNamespace(**base)


@st.cache_data(show_spinner=False)
def cached_clean(df, os_t, os_e, pfs_t, pfs_e, uni_vars, multi_vars,
                 km_group, km_labels, km_tps, style, colors):
    """数据检查清洗（缓存，避免界面语言切换等无关改动时重复计算）。"""
    cfg = make_cfg(OS_TIME_COL=os_t, OS_EVENT_COL=os_e,
                   PFS_TIME_COL=pfs_t, PFS_EVENT_COL=pfs_e,
                   UNI_VARS=uni_vars, MULTI_VARS=multi_vars,
                   KM_GROUP_VAR=km_group, KM_LEGEND_LABELS=km_labels,
                   KM_MARK_TIMEPOINTS=km_tps, COLOR_STYLE=style, KM_COLORS=colors)
    return check_and_clean(df, cfg)


def parse_number_list(text):
    """把 "12, 24, 36" 解析为 [12.0, 24.0, 36.0]；空字符串返回 []。"""
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"[,，;；\s]+", text)
    return [float(p) for p in parts if p]


def parse_color_list(text):
    """解析十六进制颜色列表并校验格式；返回 None 表示格式有误。"""
    text = text.strip()
    if not text:
        return []
    colors = [c.strip() for c in re.split(r"[,，;；\s]+", text) if c.strip()]
    pattern = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
    if not all(pattern.match(c) for c in colors):
        return None
    return colors


def translate_note(note, lang):
    """把 src 分析引擎生成的中文结构化备注按界面语言显示（自由文本诊断信息保留原文）。"""
    if not note or lang == "zh":
        return note
    m = re.fullmatch(r"参照组 = (.+)", note)
    if m:
        return f"ref = {m.group(1)}"
    m = re.fullmatch(r"vs 参照组 (.+)", note)
    if m:
        return f"vs ref. {m.group(1)}"
    if note.startswith("疑似完全分离"):
        return LANG["en"]["note_sep"]
    return note


def cox_table(results, lang):
    """把 Cox 结果列表转为展示用 DataFrame（复用 src 的 _cox_rows）。"""
    df = pd.DataFrame(_cox_rows(results))
    if "Note" in df.columns:
        df["Note"] = df["Note"].map(lambda x: translate_note(x, lang))
    return df


def fig_bytes(fig, fmt):
    """Figure 导出为指定格式的字节，供 st.download_button 使用。"""
    buf = BytesIO()
    fig.savefig(buf, format=fmt, dpi=300, bbox_inches="tight", pad_inches=0.08)
    return buf.getvalue()


def excel_bytes(check_summary, uni_results, multi_results, timepoints_df):
    """复用 src.export_utils.export_results 生成 Excel 到临时目录，读取字节返回。"""
    with tempfile.TemporaryDirectory() as td:
        export_results(td, check_summary, uni_results, multi_results,
                       timepoints_df, endpoint="OS")
        return Path(td, "analysis_results.xlsx").read_bytes()


def run_analysis(df_clean, cfg, chart_lang):
    """复用 src/ 模块执行全部分析，返回图表与结果对象（不写磁盘）。"""
    apply_chart_font(chart_lang)
    km_figs, tp_parts = {}, []
    if cfg.KM_GROUP_VAR:
        for ep, tcol, ecol in get_endpoint_cols(cfg):
            fig, tp = plot_km(df_clean, ep, tcol, ecol, cfg,
                              save_path=None, fig_texts=KM_TEXTS[chart_lang])
            km_figs[ep] = fig
            if tp is not None:
                tp_parts.append(tp)
    timepoints_df = (pd.concat(tp_parts, ignore_index=True)
                     if tp_parts else None)

    uni_results, _, _ = univariate_cox(df_clean, cfg, endpoint="OS")
    selected = select_multivariable_vars(uni_results, cfg)
    multi_results, _, _ = multivariate_cox(df_clean, cfg, uni_results, selected,
                                           endpoint="OS")
    title_uni, title_multi = FOREST_TITLES[chart_lang]
    fig_forest_texts = FOREST_TEXTS[chart_lang]
    fig_forest_uni = plot_forest(uni_results, cfg, out_base=None,
                                 title=title_uni, fig_texts=fig_forest_texts)
    fig_forest_multi = (plot_forest(multi_results, cfg, out_base=None,
                                    title=title_multi, fig_texts=fig_forest_texts)
                        if multi_results is not None else None)
    return {
        "km_figs": km_figs, "timepoints_df": timepoints_df,
        "uni_results": uni_results, "multi_results": multi_results,
        "fig_forest_uni": fig_forest_uni, "fig_forest_multi": fig_forest_multi,
    }


# =====================================================================
# 页面布局：顶部标题，侧边栏配置，主区域结果
# =====================================================================
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "zh"

lang_display = st.sidebar.selectbox(
    LANG[st.session_state.ui_lang]["lang_label"],
    ["中文", "English"],
    index=0 if st.session_state.ui_lang == "zh" else 1,
    key="ui_lang_widget",
)
st.session_state.ui_lang = "zh" if lang_display == "中文" else "en"
L = LANG[st.session_state.ui_lang]

st.title(L["app_title"])
st.caption(L["app_caption"])

# ---------- 侧边栏：数据 ----------
st.sidebar.header(L["sec_data"])
uploaded = st.sidebar.file_uploader(L["uploader_label"],
                                    type=["xlsx", "csv"], key="uploader")
if st.sidebar.button(L["load_example"], key="load_example"):
    st.session_state["df"] = pd.read_csv(BASE_DIR / "example_data" / "example_data.csv")
    st.session_state["df_source"] = "example"
    st.sidebar.success(L["example_ok"])
if uploaded is not None:
    try:
        if uploaded.name.lower().endswith(".csv"):
            st.session_state["df"] = pd.read_csv(uploaded)
        else:
            st.session_state["df"] = pd.read_excel(uploaded, engine="openpyxl")
        st.session_state["df_source"] = "upload"
        st.sidebar.success(L["upload_ok"])
    except Exception as e:
        st.sidebar.error(f"{type(e).__name__}: {e}")

df = st.session_state.get("df")

if df is None:
    st.info(L["need_data"])
    st.stop()

st.sidebar.write(f"**{L['data_loaded']}：** {L['rows_cols'].format(r=df.shape[0], c=df.shape[1])}")

# ---------- 侧边栏：列名映射 ----------
C = cli_config


def _default_col(col_name):
    """列选择默认值：优先 config.py 中的列名，否则第一列。"""
    return col_name if col_name in df.columns else df.columns[0]


with st.sidebar.expander(L["colmap_expander"]):
    os_time = st.selectbox(L["col_os_time"], df.columns,
                           index=list(df.columns).index(_default_col(C.OS_TIME_COL)),
                           key="col_os_time")
    os_event = st.selectbox(L["col_os_event"], df.columns,
                            index=list(df.columns).index(_default_col(C.OS_EVENT_COL)),
                            key="col_os_event")
    pfs_time = st.selectbox(L["col_pfs_time"], df.columns,
                            index=list(df.columns).index(_default_col(C.PFS_TIME_COL)),
                            key="col_pfs_time")
    pfs_event = st.selectbox(L["col_pfs_event"], df.columns,
                             index=list(df.columns).index(_default_col(C.PFS_EVENT_COL)),
                             key="col_pfs_event")

exclude = {os_time, os_event, pfs_time, pfs_event}
if C.ID_COL in df.columns:
    exclude.add(C.ID_COL)
feature_cols = [c for c in df.columns if c not in exclude]
if not feature_cols:
    st.error("No feature columns found." if st.session_state.ui_lang == "en"
             else "未找到可用的特征列，请检查列名映射。")
    st.stop()

# ---------- 侧边栏：分析设置 ----------
st.sidebar.header(L["sec_analysis"])
uni_vars = st.sidebar.multiselect(L["uni_vars_label"], feature_cols,
                                  default=feature_cols, key="uni_vars")
uni_vars_eff = [v for v in uni_vars if v in feature_cols]

multi_mode = st.sidebar.radio(
    L["multi_mode_label"], [L["multi_auto"], L["multi_manual"]],
    key="multi_mode")
if multi_mode == L["multi_manual"]:
    multi_vars = st.sidebar.multiselect(L["multi_vars_label"], feature_cols,
                                        default=[], key="multi_vars")
    multi_vars_eff = [v for v in multi_vars if v in feature_cols]
else:
    multi_vars_eff = []

group_options = [L["no_km"]] + feature_cols
default_group = C.KM_GROUP_VAR if C.KM_GROUP_VAR in feature_cols else L["no_km"]
km_group_sel = st.sidebar.selectbox(L["km_group_label"], group_options,
                                    index=group_options.index(default_group),
                                    key="km_group")
km_group = "" if km_group_sel == L["no_km"] else km_group_sel

tp_on = st.sidebar.checkbox(L["tp_checkbox"], value=bool(C.KM_MARK_TIMEPOINTS),
                            key="tp_on", disabled=(km_group == ""))
tp_text = st.sidebar.text_input(
    L["tp_input_label"],
    value=", ".join(str(int(t)) for t in C.KM_MARK_TIMEPOINTS),
    key="tp_text", disabled=(not tp_on or km_group == ""))

legend_text = st.sidebar.text_input(
    L["legend_input_label"],
    value=", ".join(str(x) for x in C.KM_LEGEND_LABELS),
    key="legend_text", disabled=(km_group == ""))

# ---------- 侧边栏：图形设置 ----------
st.sidebar.header(L["sec_style"])
fmt_label = st.sidebar.radio(L["fmt_label"], ["PDF", "PNG", "PDF + PNG"],
                             index=2, key="export_fmt")
export_format = {"PDF": "pdf", "PNG": "png", "PDF + PNG": "both"}[fmt_label]

style_options = ["lancet", "nejm", "jama", "nature", "jco", "custom"]
style = st.sidebar.selectbox(L["style_label"], style_options,
                             index=style_options.index(C.COLOR_STYLE)
                             if C.COLOR_STYLE in style_options else 3,
                             key="color_style")
custom_colors = list(C.KM_COLORS)
if style == "custom":
    parsed = parse_color_list(st.sidebar.text_input(
        L["custom_colors_label"], value=", ".join(C.KM_COLORS),
        key="custom_colors"))
    if parsed is None:
        st.sidebar.warning(L["color_error"])
    else:
        custom_colors = parsed or list(C.KM_COLORS)

chart_lang_disp = st.sidebar.selectbox(
    L["chart_lang_label"], [L["chart_en"], L["chart_zh"]],
    index=0, key="chart_lang")
chart_lang = "zh" if chart_lang_disp == L["chart_zh"] else "en"
if chart_lang == "zh" and CJK_FONT_NAME is None:
    st.sidebar.warning(L["font_missing"])

# ---------- 解析时间点 ----------
km_tps = []
if tp_on and km_group:
    try:
        km_tps = parse_number_list(tp_text)
    except ValueError:
        st.error(L["tp_error"])
        st.stop()

# ---------- 运行分析 ----------
cfg = make_cfg(OS_TIME_COL=os_time, OS_EVENT_COL=os_event,
               PFS_TIME_COL=pfs_time, PFS_EVENT_COL=pfs_event,
               UNI_VARS=uni_vars_eff, MULTI_VARS=multi_vars_eff,
               KM_GROUP_VAR=km_group,
               KM_LEGEND_LABELS=[x.strip() for x in re.split(r"[,，;；]",
                               legend_text) if x.strip()],
               KM_MARK_TIMEPOINTS=km_tps, COLOR_STYLE=style,
               KM_COLORS=custom_colors, EXPORT_FORMAT=export_format,
               DPI=max(C.DPI, 300))

if st.button(L["run_button"], type="primary", key="run_button"):
    with st.spinner(L["running"]):
        try:
            df_clean, check_summary = cached_clean(
                df, os_time, os_event, pfs_time, pfs_event,
                tuple(uni_vars_eff), tuple(multi_vars_eff),
                km_group, tuple(cfg.KM_LEGEND_LABELS), tuple(km_tps),
                style, tuple(custom_colors))
            st.session_state["results"] = run_analysis(df_clean, cfg, chart_lang)
            st.session_state["check_summary"] = check_summary
            st.session_state["n_clean"] = len(df_clean)
            st.success(L["done"])
        except Exception as e:
            st.session_state.pop("results", None)
            st.exception(e)

# ---------- 展示结果 ----------
if "results" not in st.session_state:
    st.stop()

res = st.session_state["results"]
check_summary = st.session_state["check_summary"]
lang = st.session_state.ui_lang

with st.expander(L["check_expander"]):
    st.dataframe(pd.DataFrame(check_summary), hide_index=True)

if res["km_figs"]:
    st.subheader(L["km_header"])
    for ep, fig in res["km_figs"].items():
        st.markdown(f"**{ep}**")
        st.pyplot(fig)

st.subheader(L["uni_header"])
st.dataframe(cox_table(res["uni_results"], lang), hide_index=True)

if res["fig_forest_uni"] is not None:
    st.subheader(L["forest_uni_header"])
    st.pyplot(res["fig_forest_uni"])
else:
    st.info(L["no_forest_info"])

if res["multi_results"] is not None:
    st.subheader(L["multi_header"])
    st.dataframe(cox_table(res["multi_results"], lang), hide_index=True)
    if res["fig_forest_multi"] is not None:
        st.subheader(L["forest_multi_header"])
        st.pyplot(res["fig_forest_multi"])
else:
    st.info(L["no_multi_info"])

# ---------- 下载 ----------
st.divider()
st.subheader(L["download_header"])
figs = {}
for ep, fig in res["km_figs"].items():
    figs[f"KM_{ep}"] = fig
if res["fig_forest_uni"] is not None:
    figs["forest_uni"] = res["fig_forest_uni"]
if res["fig_forest_multi"] is not None:
    figs["forest_multi"] = res["fig_forest_multi"]

fmts = ["pdf", "png"] if export_format == "both" else [export_format]
for name, fig in figs.items():
    for fmt in fmts:
        mime = "image/png" if fmt == "png" else "application/pdf"
        st.download_button(
            label=f"{L['dl_figure']} {name}.{fmt}",
            data=fig_bytes(fig, fmt),
            file_name=f"{name}.{fmt}",
            mime=mime,
            key=f"dl_{name}_{fmt}",
        )

st.download_button(
    label=L["dl_excel"],
    data=excel_bytes(check_summary, res["uni_results"], res["multi_results"],
                     res["timepoints_df"]),
    file_name="analysis_results.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    key="dl_excel",
)
