
import io
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==================================================
# 1. 页面设置
# ==================================================

st.set_page_config(
    page_title="经营利润与成本分析系统",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}
[data-testid="stMetric"] {
    background: #f5f7fa;
    border: 1px solid #e5e7eb;
    padding: 15px;
    border-radius: 10px;
}
[data-testid="stMetricLabel"] {
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("经营利润与成本费用分析 Dashboard")
st.caption("销售收入 · 成本结构 · 核心费用率 · 运营绩效 · 利润优化")


# ==================================================
# 2. 字段配置
# ==================================================

DIMENSIONS = [
    "月份",
    "部门",
    "运营人员",
    "站点"
]

CORE_EXPENSES = [
    "站内推广费",
    "平台佣金",
    "站外推广费",
    "自发货运费",
    "售后费用",
    "其他费用"
]

OTHER_EXPENSES = [
    "头程净额",
    "站内仓储费",
    "税费",
    "平台服务费",
    "平台运费",
    "站外仓储费"
]

ALL_EXPENSES = OTHER_EXPENSES + CORE_EXPENSES

AMOUNT_COLUMNS = [
    "销售收入",
    "退款收入",
    "收入合计",
    "成本净额",
    "头程净额",
    "站内仓储费",
    "税费",
    "平台服务费",
    "平台运费",
    "站内推广费",
    "平台佣金",
    "站外推广费",
    "自发货运费",
    "售后费用",
    "其他费用",
    "站外仓储费",
    "费用合计",
    "销售净毛利",
    "平台回款",
    "实际回款-提成计算"
]

RATE_COLUMNS = [
    "成本率",
    "费用占比",
    "毛利率",
    "成本回报率"
]

REQUIRED_COLUMNS = (
    DIMENSIONS
    + ["销售收入", "退款收入", "成本净额"]
    + ALL_EXPENSES
)

# ==================================================
# 3. 通用函数
# ==================================================

def clean_number(series):
    """金额清洗，支持逗号、货币符号和括号负数"""
    s = series.astype(str).str.strip()

    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("$", "", regex=False)
    s = s.str.replace("¥", "", regex=False)
    s = s.str.replace("￥", "", regex=False)
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)

    s = s.replace({
        "": "0",
        "nan": "0",
        "None": "0",
        "-": "0"
    })

    return pd.to_numeric(
        s, errors="coerce"
    ).fillna(0)


def safe_divide(a, b):
    """安全计算比率"""
    if abs(b) < 1e-10:
        return np.nan
    return a / b


def money(v):
    return f"{v:,.2f}"


def pct(v):
    if pd.isna(v):
        return "N/A"
    return f"{v:.2%}"


def normalize_month(v):
    """月份统一处理"""
    if pd.isna(v):
        return "未填写"

    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m")

    s = str(v).strip()

    if re.fullmatch(r"\d{6}", s):
        year = int(s[:4])
        month = int(s[4:])
        if 1 <= month <= 12:
            return f"{year}-{month:02d}"

    if re.fullmatch(r"\d{1,2}", s):
        month = int(s)
        if 1 <= month <= 12:
            return f"{month:02d}月"

    try:
        parsed = pd.to_datetime(
            s.replace("年", "-").replace("月", ""),
            errors="coerce"
        )
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m")
    except Exception:
        pass

    return s


def aggregate_rates(data, group_cols):
    """按维度汇总金额，再重新计算费率"""
    cols = [
        "分析收入",
        "成本净额",
        "分析费用",
        "分析毛利"
    ] + ALL_EXPENSES

    result = (
        data.groupby(
            group_cols,
            as_index=False
        )[cols]
        .sum()
    )

    denominator = result["分析收入"].replace(0, np.nan)

    result["成本率"] = result["成本净额"] / denominator
    result["费用率"] = result["分析费用"] / denominator
    result["毛利率"] = result["分析毛利"] / denominator

    for item in ALL_EXPENSES:
        result[item + "率"] = result[item] / denominator

    result["六项综合费用"] = result[CORE_EXPENSES].sum(axis=1)
    result["六项综合费用率"] = (
        result["六项综合费用"] / denominator
    )

    return result


def show_table(data, percent_cols=None, money_cols=None):
    percent_cols = percent_cols or []
    money_cols = money_cols or []

    formats = {}

    for c in percent_cols:
        if c in data.columns:
            formats[c] = "{:.2%}"

    for c in money_cols:
        if c in data.columns:
            formats[c] = "{:,.2f}"

    st.dataframe(
        data.style.format(formats, na_rep="—"),
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# 4. 上传数据
# ==================================================

st.sidebar.header("数据导入")

uploaded_file = st.sidebar.file_uploader(
    "上传 Excel / CSV",
    type=["xlsx", "csv"]
)

if uploaded_file is None:
    st.info("请在左侧上传经营数据 Excel 或 CSV 文件。")

    st.markdown("""
    ### 数据要求

    Excel 第一行使用以下表头：

    月份、部门、运营人员、站点、销售收入、退款收入、
    收入合计、成本净额、成本率、头程净额、
    站内仓储费、税费、平台服务费、平台运费、
    站内推广费、平台佣金、站外推广费、
    自发货运费、售后费用、其他费用、
    站外仓储费、费用合计、费用占比、
    销售净毛利、毛利率、平台回款、
    实际回款-提成计算、成本回报率。

    支持多月份、多部门、多运营人员和多站点。
    """)

    st.stop()

try:
    if uploaded_file.name.lower().endswith(".csv"):
        try:
            raw = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            raw = pd.read_csv(uploaded_file, encoding="gb18030")
    else:
        raw = pd.read_excel(uploaded_file)

except Exception as e:
    st.error(f"读取文件失败：{e}")
    st.stop()

raw.columns = [
    str(c).replace("\u3000", " ").strip()
    for c in raw.columns
]

if raw.columns.duplicated().any():
    st.error("文件存在重复表头，请先检查。")
    st.stop()

missing = [
    c for c in REQUIRED_COLUMNS
    if c not in raw.columns
]

if missing:
    st.error("缺少字段：" + "、".join(missing))
    st.stop()

if raw.empty:
    st.warning("文件没有数据。")
    st.stop()


# ==================================================
# 5. 数据清洗
# ==================================================

data = raw.copy()

for col in AMOUNT_COLUMNS:
    if col in data.columns:
        data[col] = clean_number(data[col])

for col in DIMENSIONS[1:]:
    data[col] = (
        data[col]
        .fillna("未填写")
        .astype(str)
        .str.strip()
        .replace("", "未填写")
    )

data["月份"] = data["月份"].map(normalize_month)

# ==================================================
# 6. 财务计算口径
# ==================================================

st.sidebar.header("财务计算设置")

refund_mode = st.sidebar.radio(
    "退款收入记录方式",
    [
        "退款为负数",
        "退款为正数"
    ],
    help="根据你的原始财务报表选择"
)

expense_mode = st.sidebar.radio(
    "费用合计口径",
    [
        "自动计算全部12项费用",
        "使用原表费用合计"
    ]
)

revenue_mode = st.sidebar.radio(
    "收入合计口径",
    [
        "使用原表收入合计",
        "自动计算销售减退款"
    ]
)

target_margin = st.sidebar.slider(
    "目标毛利率 (%)",
    0.0, 50.0, 20.0, 0.5
) / 100

alert_threshold = st.sidebar.slider(
    "核心费用率预警线 (%)",
    0.0, 30.0, 10.0, 0.5
) / 100

if refund_mode == "退款为负数":
    data["计算收入"] = (
        data["销售收入"] + data["退款收入"]
    )
else:
    data["计算收入"] = (
        data["销售收入"] - data["退款收入"]
    )

data["计算费用"] = data[ALL_EXPENSES].sum(axis=1)

if (
    revenue_mode == "使用原表收入合计"
    and "收入合计" in data.columns
):
    data["分析收入"] = data["收入合计"]
else:
    data["分析收入"] = data["计算收入"]

if (
    expense_mode == "使用原表费用合计"
    and "费用合计" in data.columns
):
    data["分析费用"] = data["费用合计"]
else:
    data["分析费用"] = data["计算费用"]

data["分析毛利"] = (
    data["分析收入"]
    - data["成本净额"]
    - data["分析费用"]
)


# ==================================================
# 7. 全局筛选
# ==================================================

st.sidebar.header("筛选条件")

filtered = data.copy()

for col in DIMENSIONS:
    options = sorted(
        filtered[col].astype(str).unique().tolist()
    )

    selected = st.sidebar.multiselect(
        col,
        options,
        default=options
    )

    filtered = filtered[
        filtered[col].astype(str).isin(selected)
    ]

if filtered.empty:
    st.warning("当前筛选条件下没有数据。")
    st.stop()


# ==================================================
# 8. 汇总指标
# ==================================================

revenue = filtered["分析收入"].sum()
sales = filtered["销售收入"].sum()
cost = filtered["成本净额"].sum()
expense = filtered["分析费用"].sum()
profit = filtered["分析毛利"].sum()

margin = safe_divide(profit, revenue)
cost_rate = safe_divide(cost, revenue)
expense_rate = safe_divide(expense, revenue)

core_total = filtered[CORE_EXPENSES].sum().sum()
core_rate = safe_divide(core_total, revenue)


# ==================================================
# 9. 页面导航
# ==================================================

tabs = st.tabs([
    "经营总览",
    "六项核心费用率",
    "全部成本结构",
    "月度趋势",
    "运营绩效",
    "利润优化",
    "数据核对与导出"
])


# ==================================================
# TAB 1 经营总览
# ==================================================

with tabs[0]:

    st.header("经营总览")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("销售收入", money(sales))
    c2.metric("收入合计", money(revenue))
    c3.metric("销售净毛利", money(profit))
    c4.metric("毛利率", pct(margin))

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("成本率", pct(cost_rate))
    c2.metric("总费用率", pct(expense_rate))
    c3.metric("六项综合费用率", pct(core_rate))
    c4.metric(
        "成本回报率",
        pct(safe_divide(profit, cost + expense))
    )

    st.divider()

    st.subheader("收入成本利润结构")

    overview = pd.DataFrame({
        "项目": [
            "收入合计",
            "成本净额",
            "费用合计",
            "销售净毛利"
        ],
        "金额": [
            revenue,
            cost,
            expense,
            profit
        ]
    })

    fig = px.bar(
        overview,
        x="项目",
        y="金额",
        color="项目",
        text="金额"
    )

    fig.update_traces(
        texttemplate="%{y:,.0f}",
        textposition="outside"
    )

    fig.update_layout(showlegend=False)

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("利润目标完成情况")

    if pd.notna(margin):
        gap = margin - target_margin

        st.metric(
            "当前毛利率与目标差距",
            f"{gap * 100:+.2f} 个百分点"
        )

        if gap < 0:
            st.error(
                f"当前毛利率低于目标，"
                f"需要改善 {abs(gap)*100:.2f} 个百分点。"
            )
        else:
            st.success("当前毛利率达到目标。")


# ==================================================
# TAB 2 六项核心费用率
# ==================================================

with tabs[1]:

    st.header("六项核心费用率分析")

    st.caption(
        "费用率 = 费用金额 ÷ 收入合计。"
        "所有比率均使用筛选后的汇总金额计算。"
    )

    core_amounts = filtered[CORE_EXPENSES].sum()

    core_df = pd.DataFrame({
        "费用项目": CORE_EXPENSES,
        "费用金额": [
            core_amounts[c] for c in CORE_EXPENSES
        ]
    })

    core_df["费用率"] = core_df["费用金额"].apply(
        lambda x: safe_divide(x, revenue)
    )

    # 1. 六项费用率卡片
    st.subheader("核心费用率 KPI")

    cols = st.columns(3)

    for i, row in core_df.iterrows():
        with cols[i % 3]:
            st.metric(
                row["费用项目"] + "率",
                pct(row["费用率"]),
                help=f"费用金额：{money(row['费用金额'])}"
            )

    c1, c2 = st.columns(2)

    c1.metric("六项费用合计", money(core_total))
    c2.metric("六项综合费用率", pct(core_rate))

    st.divider()

    # 2. 六项费用率柱状图
    st.subheader("各项费用率对比")

    fig = px.bar(
        core_df,
        x="费用项目",
        y="费用率",
        color="费用项目",
        text="费用率",
        title="六项费用占收入比例"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_tickformat=".1%",
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

    # 3. 六项费用构成
    st.subheader("六项费用内部构成")

    positive_core = core_df[core_df["费用金额"] > 0]

    if not positive_core.empty:
        fig = px.pie(
            positive_core,
            names="费用项目",
            values="费用金额",
            hole=0.55,
            title="六项费用金额构成"
        )

        st.plotly_chart(fig, use_container_width=True)

    # 4. 月度费用率趋势
    st.subheader("月度六项费用率趋势")

    monthly_core = aggregate_rates(
        filtered,
        ["月份"]
    ).sort_values("月份")

    rate_cols = [
        c + "率" for c in CORE_EXPENSES
    ]

    fig = px.line(
        monthly_core,
        x="月份",
        y=rate_cols + ["六项综合费用率"],
        markers=True,
        title="月度核心费用率变化"
    )

    fig.update_layout(
        yaxis_tickformat=".1%",
        legend_title_text="费用类型"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("月度费用率明细")

    monthly_display = monthly_core[
        ["月份", "分析收入"]
        + rate_cols
        + ["六项综合费用率"]
    ]

    show_table(
        monthly_display,
        percent_cols=rate_cols + ["六项综合费用率"],
        money_cols=["分析收入"]
    )

    # 5. 费用率预警
    st.subheader("费用率预警")

    alerts = core_df[
        core_df["费用率"] > alert_threshold
    ]

    if alerts.empty:
        st.success("当前没有超过设定预警线的核心费用。")
    else:
        for _, row in alerts.iterrows():
            st.warning(
                f"{row['费用项目']}率为 "
                f"{pct(row['费用率'])}，"
                f"超过预警线 {pct(alert_threshold)}"
            )

    # 6. 多维度费用率
    st.subheader("按部门、人员、站点分析费用率")

    dimension = st.selectbox(
        "选择分析维度",
        ["部门", "运营人员", "站点"],
        key="core_dimension"
    )

    group_core = aggregate_rates(
        filtered,
        [dimension]
    )

    selected_rate = st.selectbox(
        "选择费用率指标",
        rate_cols + ["六项综合费用率"],
        key="selected_core_rate"
    )

    group_core = group_core.sort_values(
        selected_rate,
        ascending=False
    )

    fig = px.bar(
        group_core,
        x=dimension,
        y=selected_rate,
        color=selected_rate,
        text=selected_rate,
        title=f"{dimension} - {selected_rate}排名"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(yaxis_tickformat=".1%")

    st.plotly_chart(fig, use_container_width=True)

    show_table(
        group_core[
            [dimension, "分析收入"]
            + rate_cols
            + ["六项综合费用率"]
        ],
        percent_cols=rate_cols + ["六项综合费用率"],
        money_cols=["分析收入"]
    )


# ==================================================
# TAB 3 全部成本结构
# ==================================================

with tabs[2]:

    st.header("全部成本费用结构")

    all_cost_items = ["成本净额"] + ALL_EXPENSES

    cost_df = pd.DataFrame({
        "费用项目": all_cost_items,
        "金额": [
            filtered[c].sum()
            for c in all_cost_items
        ]
    })

    cost_df["占收入比例"] = cost_df["金额"].apply(
        lambda x: safe_divide(x, revenue)
    )

    total_spending = cost_df["金额"].sum()

    cost_df["占总支出比例"] = cost_df["金额"].apply(
        lambda x: safe_divide(x, total_spending)
    )

    cost_df = cost_df.sort_values(
        "金额",
        ascending=False
    )

    c1, c2 = st.columns(2)

    with c1:
        fig = px.bar(
            cost_df,
            x="金额",
            y="费用项目",
            orientation="h",
            color="费用项目",
            title="成本费用金额排名"
        )

        fig.update_layout(
            showlegend=False,
            yaxis={"categoryorder": "total ascending"}
        )

        st.plotly_chart(fig, use_container_width=True)

    with c2:
        positive_costs = cost_df[
            cost_df["金额"] > 0
        ]

        if not positive_costs.empty:
            fig = px.pie(
                positive_costs,
                names="费用项目",
                values="金额",
                hole=0.5,
                title="总成本费用构成"
            )

            st.plotly_chart(fig, use_container_width=True)

    st.subheader("成本费用明细")

    show_table(
        cost_df,
        percent_cols=[
            "占收入比例",
            "占总支出比例"
        ],
        money_cols=["金额"]
    )


# ==================================================
# TAB 4 月度趋势
# ==================================================

with tabs[3]:

    st.header("月度经营趋势")

    monthly = aggregate_rates(
        filtered,
        ["月份"]
    ).sort_values("月份")

    st.subheader("月度收入、成本与利润")

    fig = px.bar(
        monthly,
        x="月份",
        y=[
            "分析收入",
            "成本净额",
            "分析费用",
            "分析毛利"
        ],
        barmode="group"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("月度成本率、费用率、毛利率")

    fig = px.line(
        monthly,
        x="月份",
        y=["成本率", "费用率", "毛利率"],
        markers=True
    )

    fig.update_layout(yaxis_tickformat=".1%")

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("毛利率环比变化")

    monthly["毛利率环比变化"] = (
        monthly["毛利率"].diff()
    )

    fig = px.bar(
        monthly,
        x="月份",
        y="毛利率环比变化",
        text="毛利率环比变化",
        title="毛利率环比变化（百分点）"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(yaxis_tickformat=".1%")

    st.plotly_chart(fig, use_container_width=True)

    show_table(
        monthly[
            [
                "月份",
                "分析收入",
                "成本净额",
                "分析费用",
                "分析毛利",
                "成本率",
                "费用率",
                "毛利率",
                "毛利率环比变化"
            ]
        ],
        percent_cols=[
            "成本率",
            "费用率",
            "毛利率",
            "毛利率环比变化"
        ],
        money_cols=[
            "分析收入",
            "成本净额",
            "分析费用",
            "分析毛利"
        ]
    )

    st.subheader("月度费用率变化归因")

    monthly_change = monthly.copy()

    change_columns = [
        "成本净额"
    ] + ALL_EXPENSES

    for item in change_columns:
        monthly_change[item + "费率变化"] = (
            monthly_change[item + "率"].diff()
            if item != "成本净额"
            else monthly_change["成本率"].diff()
        )

    selected_month = st.selectbox(
        "选择分析月份",
        monthly_change["月份"].tolist(),
        index=len(monthly_change) - 1
    )

    selected_index = monthly_change.index[
        monthly_change["月份"] == selected_month
    ][0]

    pos = monthly_change.index.get_loc(selected_index)

    if pos == 0:
        st.info("第一个月份没有上月数据，无法计算环比归因。")
    else:
        row = monthly_change.loc[selected_index]

        attribution = []

        for item in change_columns:
            change = row[item + "费率变化"]

            attribution.append({
                "成本费用项目": item,
                "费率变化（百分点）": change * 100,
                "对毛利率影响（百分点）": -change * 100
            })

        attribution_df = pd.DataFrame(attribution)

        attribution_df = attribution_df.sort_values(
            "对毛利率影响（百分点）"
        )

        st.caption(
            "基于各项成本费用占收入比例的环比变化，"
            "正值代表改善毛利率，负值代表拖累毛利率。"
        )

        fig = px.bar(
            attribution_df,
            x="成本费用项目",
            y="对毛利率影响（百分点）",
            color="对毛利率影响（百分点）",
            title="各项费用对毛利率变化的影响"
        )

        st.plotly_chart(fig, use_container_width=True)

        show_table(attribution_df)


# ==================================================
# TAB 5 运营绩效
# ==================================================

with tabs[4]:

    st.header("运营绩效分析")

    dimension = st.selectbox(
        "选择排名维度",
        ["部门", "运营人员", "站点"],
        key="performance_dimension"
    )

    performance = aggregate_rates(
        filtered,
        [dimension]
    )

    performance = performance.sort_values(
        "分析毛利",
        ascending=False
    )

    show_table(
        performance[
            [
                dimension,
                "分析收入",
                "成本净额",
                "分析费用",
                "分析毛利",
                "成本率",
                "费用率",
                "毛利率",
                "六项综合费用率"
            ]
        ],
        percent_cols=[
            "成本率",
            "费用率",
            "毛利率",
            "六项综合费用率"
        ],
        money_cols=[
            "分析收入",
            "成本净额",
            "分析费用",
            "分析毛利"
        ]
    )

    st.subheader("利润排名")

    fig = px.bar(
        performance,
        x=dimension,
        y="分析毛利",
        color="毛利率",
        text="分析毛利"
    )

    fig.update_traces(
        texttemplate="%{y:,.0f}",
        textposition="outside"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("毛利率与费用率对比")

    fig = px.scatter(
        performance,
        x="费用率",
        y="毛利率",
        size="分析收入",
        hover_name=dimension,
        title="费用率与毛利率关系",
        size_max=55
    )

    fig.update_layout(
        xaxis_tickformat=".1%",
        yaxis_tickformat=".1%"
    )

    # 收入为负数时不适合气泡大小
    if (performance["分析收入"] < 0).any():
        st.info("存在负收入分组，跳过气泡图。")
    else:
        st.plotly_chart(fig, use_container_width=True)


# ==================================================
# TAB 6 利润优化
# ==================================================

with tabs[5]:

    st.header("利润优化与降本模拟")

    target_profit = revenue * target_margin

    profit_gap = target_profit - profit

    c1, c2, c3 = st.columns(3)

    c1.metric("当前毛利率", pct(margin))
    c2.metric("目标毛利率", pct(target_margin))
    c3.metric(
        "达到目标所需增加利润",
        money(max(profit_gap, 0))
    )

    st.divider()

    st.subheader("单项费用降本模拟")

    selected_expense = st.selectbox(
        "选择优化项目",
        ["成本净额"] + ALL_EXPENSES
    )

    saving_rate = st.slider(
        "预计降低费用比例 (%)",
        0, 50, 10, 1
    ) / 100

    original_amount = filtered[selected_expense].sum()

    saved_amount = original_amount * saving_rate

    new_profit = profit + saved_amount

    new_margin = safe_divide(new_profit, revenue)

    c1, c2, c3 = st.columns(3)

    c1.metric("预计节省金额", money(saved_amount))
    c2.metric("优化后毛利", money(new_profit))
    c3.metric(
        "优化后毛利率",
        pct(new_margin),
        delta=(
            f"{(new_margin-margin)*100:.2f} 个百分点"
            if pd.notna(new_margin) and pd.notna(margin)
            else None
        )
    )

    st.divider()

    st.subheader("六项费用降本潜力")

    simulation = pd.DataFrame({
        "费用项目": CORE_EXPENSES,
        "当前金额": [
            filtered[c].sum()
            for c in CORE_EXPENSES
        ]
    })

    simulation["节省10%金额"] = (
        simulation["当前金额"] * 0.1
    )

    simulation["毛利率提升（百分点）"] = (
        simulation["节省10%金额"]
        / revenue * 100
        if revenue != 0
        else np.nan
    )

    simulation = simulation.sort_values(
        "节省10%金额",
        ascending=False
    )

    show_table(
        simulation,
        money_cols=[
            "当前金额",
            "节省10%金额"
        ]
    )

    st.caption(
        "模拟假设收入不变、其他费用不变。"
        "实际降本可能影响销量、服务质量和履约表现。"
    )


# ==================================================
# TAB 7 数据核对与导出
# ==================================================

with tabs[6]:

    st.header("数据核对与导出")

    st.subheader("财务数据核对")

    checks = []

    check_map = [
        ("收入合计", "计算收入"),
        ("费用合计", "计算费用")
    ]

    for original, calculated in check_map:
        if original in filtered.columns:
            difference = (
                filtered[original]
                - filtered[calculated]
            ).abs()

            checks.append({
                "核对项目": original,
                "差异行数": int(
                    (difference > 0.01).sum()
                ),
                "差异绝对值合计": difference.sum()
            })

    if "销售净毛利" in filtered.columns:
        difference = (
            filtered["销售净毛利"]
            - filtered["分析毛利"]
        ).abs()

        checks.append({
            "核对项目": "销售净毛利",
            "差异行数": int(
                (difference > 0.01).sum()
            ),
            "差异绝对值合计": difference.sum()
        })

    check_df = pd.DataFrame(checks)

    show_table(
        check_df,
        money_cols=["差异绝对值合计"]
    )

    st.info(
        "若原表费用合计与自动计算费用合计存在差异，"
        "请核实头程净额是否已包含在成本净额中，"
        "以及是否存在未列出的费用。"
    )

    st.subheader("平台回款")

    c1, c2 = st.columns(2)

    if "平台回款" in filtered.columns:
        c1.metric(
            "平台回款",
            money(filtered["平台回款"].sum())
        )

    if "实际回款-提成计算" in filtered.columns:
        c2.metric(
            "实际回款-提成计算",
            money(filtered["实际回款-提成计算"].sum())
        )

    st.subheader("下载分析报表")

    export_monthly = aggregate_rates(
        filtered, ["月份"]
    ).sort_values("月份")

    export_department = aggregate_rates(
        filtered, ["部门"]
    )

    export_staff = aggregate_rates(
        filtered, ["运营人员"]
    )

    export_site = aggregate_rates(
        filtered, ["站点"]
    )

    export_core = pd.DataFrame({
        "费用项目": CORE_EXPENSES,
        "费用金额": [
            filtered[c].sum()
            for c in CORE_EXPENSES
        ]
    })

    export_core["费用率"] = export_core["费用金额"].apply(
        lambda x: safe_divide(x, revenue)
    )

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        filtered.to_excel(
            writer,
            index=False,
            sheet_name="经营明细"
        )

        export_monthly.to_excel(
            writer,
            index=False,
            sheet_name="月度分析"
        )

        export_department.to_excel(
            writer,
            index=False,
            sheet_name="部门分析"
        )

        export_staff.to_excel(
            writer,
            index=False,
            sheet_name="运营人员分析"
        )

        export_site.to_excel(
            writer,
            index=False,
            sheet_name="站点分析"
        )

        export_core.to_excel(
            writer,
            index=False,
            sheet_name="六项核心费用率"
        )

        check_df.to_excel(
            writer,
            index=False,
            sheet_name="数据核对"
        )

    st.download_button(
        "下载完整经营分析 Excel",
        data=output.getvalue(),
        file_name="经营利润与费用分析.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    st.subheader("原始数据预览")

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# 页脚
# ==================================================

st.divider()

st.caption(
    "经营利润与成本费用分析系统 | "
    "数据来源：上传的财务经营报表"
)
