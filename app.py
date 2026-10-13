import io
import re
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =====================================================
# 1. 页面配置
# =====================================================

st.set_page_config(
    page_title="经营利润与成本费用分析",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.4rem;
    padding-bottom: 2rem;
}
[data-testid="stMetric"] {
    background-color: #f5f7fa;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 15px;
}
[data-testid="stMetricLabel"] {
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("经营利润与成本费用分析 Dashboard")
st.caption(
    "销售分析 | 8项核心费率 | 成本结构 | "
    "月度趋势 | 运营绩效 | 利润优化"
)

# =====================================================
# 2. 字段定义
# =====================================================

DIMENSIONS = [
    "月份",
    "部门",
    "运营人员",
    "站点"
]

# 八项重点监控指标
CORE_EXPENSES = [
    "头程净额",
    "退款收入",
    "站内推广费",
    "平台佣金",
    "站外推广费",
    "自发货运费",
    "售后费用",
    "其他费用"
]

# 实际费用项目
# 注意：退款收入不在这里重复计算
EXPENSES = [
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
    "站外仓储费"
]

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

RATE_NAMES = {
    "头程净额": "头程净额费率",
    "退款收入": "退款费率",
    "站内推广费": "站内推广费率",
    "平台佣金": "平台佣金率",
    "站外推广费": "站外推广费率",
    "自发货运费": "自发货运费率",
    "售后费用": "售后费用率",
    "其他费用": "其他费用率"
}

RATE_COLUMNS = list(RATE_NAMES.values())

REQUIRED = (
    DIMENSIONS
    + ["销售收入", "退款收入", "成本净额"]
    + EXPENSES
)

# =====================================================
# 3. 通用函数
# =====================================================

def clean_number(series):
    s = series.astype(str).str.strip()

    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("$", "", regex=False)
    s = s.str.replace("¥", "", regex=False)
    s = s.str.replace("￥", "", regex=False)

    s = s.str.replace(
        r"^\((.*)\)$",
        r"-\1",
        regex=True
    )

    s = s.replace({
        "": "0",
        "nan": "0",
        "None": "0",
        "-": "0"
    })

    return pd.to_numeric(
        s,
        errors="coerce"
    ).fillna(0)


def safe_divide(a, b):
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


def show_table(
    dataframe,
    percent_cols=None,
    money_cols=None
):
    percent_cols = percent_cols or []
    money_cols = money_cols or []

    formats = {}

    for col in percent_cols:
        if col in dataframe.columns:
            formats[col] = "{:.2%}"

    for col in money_cols:
        if col in dataframe.columns:
            formats[col] = "{:,.2f}"

    st.dataframe(
        dataframe.style.format(
            formats,
            na_rep="—"
        ),
        use_container_width=True,
        hide_index=True
    )


def aggregate_data(data, dimensions):
    """先汇总金额，再计算费率"""

    columns = [
        "销售收入",
        "退款金额",
        "分析收入",
        "成本净额",
        "分析费用",
        "分析毛利"
    ] + EXPENSES

    # 去除重复列
    columns = list(dict.fromkeys(columns))

    result = (
        data.groupby(
            dimensions,
            as_index=False
        )[columns]
        .sum()
    )

    net = result["分析收入"].replace(
        0, np.nan
    )

    gross = result["销售收入"].replace(
        0, np.nan
    )

    result["成本率"] = (
        result["成本净额"] / net
    )

    result["费用率"] = (
        result["分析费用"] / net
    )

    result["毛利率"] = (
        result["分析毛利"] / net
    )

    result["退款费率"] = (
        result["退款金额"] / gross
    )

    for item in CORE_EXPENSES:
        if item != "退款收入":
            rate_name = RATE_NAMES[item]

            result[rate_name] = (
                result[item] / net
            )

    # 七项实际费用，退款不重复计算
    actual_core = [
        x for x in CORE_EXPENSES
        if x != "退款收入"
    ]

    result["七项核心费用合计"] = (
        result[actual_core].sum(axis=1)
    )

    result["七项核心费用率"] = (
        result["七项核心费用合计"] / net
    )

    return result


# =====================================================
# 4. 数据上传
# =====================================================

st.sidebar.header("数据导入")

uploaded_file = st.sidebar.file_uploader(
    "上传经营数据",
    type=["xlsx", "csv"]
)

if uploaded_file is None:

    st.info("请在左侧上传 Excel 或 CSV 经营数据。")

    st.markdown("""
    ### 支持的分析内容

    - 8项核心费用率
    - 月度费用率趋势
    - 部门、运营人员、站点对比
    - 销售净毛利及毛利率
    - 成本费用结构
    - 毛利率变化归因
    - 利润优化与降本模拟
    - Excel 分析结果导出

    请确保 Excel 第一行为字段名称。
    """)

    st.stop()

try:

    if uploaded_file.name.lower().endswith(".csv"):

        try:
            raw = pd.read_csv(
                uploaded_file,
                encoding="utf-8-sig"
            )

        except UnicodeDecodeError:
            uploaded_file.seek(0)

            raw = pd.read_csv(
                uploaded_file,
                encoding="gb18030"
            )

    else:
        raw = pd.read_excel(uploaded_file)

except Exception as e:
    st.error(f"文件读取失败：{e}")
    st.stop()

raw.columns = [
    str(c).replace("\u3000", " ").strip()
    for c in raw.columns
]

if raw.columns.duplicated().any():
    st.error("存在重复表头，请检查 Excel。")
    st.stop()

missing = [
    c for c in REQUIRED
    if c not in raw.columns
]

if missing:
    st.error(
        "缺少必要字段：" + "、".join(missing)
    )
    st.stop()

if raw.empty:
    st.warning("上传文件没有数据。")
    st.stop()

# =====================================================
# 5. 数据清洗
# =====================================================

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

data["月份"] = data["月份"].map(
    normalize_month
)

# =====================================================
# 6. 财务计算设置
# =====================================================

st.sidebar.header("财务计算设置")

refund_mode = st.sidebar.radio(
    "退款收入记录方式",
    [
        "负数记录退款",
        "正数记录退款"
    ]
)

revenue_mode = st.sidebar.radio(
    "收入合计计算方式",
    [
        "使用原表收入合计",
        "销售收入减退款金额"
    ]
)

expense_mode = st.sidebar.radio(
    "费用合计计算方式",
    [
        "自动汇总12项费用",
        "使用原表费用合计"
    ]
)

target_margin = st.sidebar.slider(
    "目标毛利率 (%)",
    0.0,
    50.0,
    20.0,
    0.5
) / 100

alert_threshold = st.sidebar.slider(
    "核心费用率预警 (%)",
    0.0,
    30.0,
    10.0,
    0.5
) / 100

# 退款金额统一转成正数
if refund_mode == "负数记录退款":
    data["退款金额"] = -data["退款收入"]
else:
    data["退款金额"] = data["退款收入"]

# 保留原始符号异常供检查
refund_sign_errors = int(
    (data["退款金额"] < 0).sum()
)

data["计算收入"] = (
    data["销售收入"]
    - data["退款金额"]
)

data["计算费用"] = (
    data[EXPENSES].sum(axis=1)
)

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

# =====================================================
# 7. 筛选
# =====================================================

st.sidebar.header("筛选条件")

filtered = data.copy()

for col in DIMENSIONS:

    options = sorted(
        filtered[col]
        .astype(str)
        .unique()
        .tolist()
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

# =====================================================
# 8. 核心经营指标
# =====================================================

sales = filtered["销售收入"].sum()
refund = filtered["退款金额"].sum()
revenue = filtered["分析收入"].sum()

cost = filtered["成本净额"].sum()
expense = filtered["分析费用"].sum()
profit = filtered["分析毛利"].sum()

cost_rate = safe_divide(cost, revenue)
expense_rate = safe_divide(expense, revenue)
margin = safe_divide(profit, revenue)

refund_rate = safe_divide(refund, sales)

core_actual = [
    c for c in CORE_EXPENSES
    if c != "退款收入"
]

core_total = filtered[core_actual].sum().sum()

core_rate = safe_divide(
    core_total,
    revenue
)

# 八项费率数据
core_rows = []

for item in CORE_EXPENSES:

    if item == "退款收入":
        amount = refund
        rate = refund_rate
        basis = "销售收入"

    else:
        amount = filtered[item].sum()
        rate = safe_divide(
            amount,
            revenue
        )
        basis = "收入合计"

    core_rows.append({
        "费用项目": item,
        "指标名称": RATE_NAMES[item],
        "费用金额": amount,
        "费率": rate,
        "分母口径": basis
    })

core_df = pd.DataFrame(core_rows)

# =====================================================
# 9. 页面导航
# =====================================================

tabs = st.tabs([
    "经营总览",
    "8项核心费率",
    "月度趋势",
    "成本费用结构",
    "运营绩效",
    "利润优化",
    "数据核对与导出"
])

# =====================================================
# TAB 1 经营总览
# =====================================================

with tabs[0]:

    st.header("经营总览")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("销售收入", money(sales))
    c2.metric("退款金额", money(refund))
    c3.metric("收入合计", money(revenue))
    c4.metric("销售净毛利", money(profit))

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("毛利率", pct(margin))
    c2.metric("成本率", pct(cost_rate))
    c3.metric("费用率", pct(expense_rate))
    c4.metric("退款费率", pct(refund_rate))

    st.divider()

    st.subheader("经营结构")

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

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("利润目标")

    target_profit = revenue * target_margin
    gap = target_profit - profit

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "目标毛利率",
        pct(target_margin)
    )

    c2.metric(
        "实际毛利率",
        pct(margin)
    )

    c3.metric(
        "目标利润缺口",
        money(max(gap, 0))
    )

    if gap > 0:
        st.warning(
            f"距离目标毛利率还需增加利润 "
            f"{money(gap)}"
        )
    else:
        st.success("当前已达到目标毛利率。")


# =====================================================
# TAB 2 八项核心费率
# =====================================================

with tabs[1]:

    st.header("8项核心费用率分析")

    st.caption(
        "退款费率以销售收入为分母；"
        "其余7项费用率以收入合计为分母。"
    )

    # 八个指标卡片
    st.subheader("核心费率 KPI")

    cols = st.columns(4)

    for i, row in core_df.iterrows():

        with cols[i % 4]:
            st.metric(
                row["指标名称"],
                pct(row["费率"]),
                help=(
                    f"金额：{money(row['费用金额'])}\n"
                    f"分母：{row['分母口径']}"
                )
            )

    st.divider()

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "七项实际费用合计",
        money(core_total)
    )

    c2.metric(
        "七项实际费用率",
        pct(core_rate)
    )

    c3.metric(
        "退款费率",
        pct(refund_rate)
    )

    st.info(
        "退款已在净收入中扣除，因此不再加入费用合计，"
        "避免重复扣减。"
    )

    # 八项费率柱状图
    st.subheader("八项费率横向对比")

    fig = px.bar(
        core_df,
        x="指标名称",
        y="费率",
        color="指标名称",
        text="费率",
        title="核心费用率对比"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        showlegend=False,
        yaxis_tickformat=".1%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("八项费率明细")

    show_table(
        core_df,
        percent_cols=["费率"],
        money_cols=["费用金额"]
    )

    # 月度费率
    st.subheader("月度八项费率趋势")

    monthly_core = aggregate_data(
        filtered,
        ["月份"]
    ).sort_values("月份")

    fig = px.line(
        monthly_core,
        x="月份",
        y=RATE_COLUMNS,
        markers=True,
        title="月度核心费率变化趋势"
    )

    fig.update_layout(
        yaxis_tickformat=".1%",
        legend_title_text="费率指标"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("月度八项费率明细")

    show_table(
        monthly_core[
            ["月份", "销售收入", "分析收入"]
            + RATE_COLUMNS
        ],
        percent_cols=RATE_COLUMNS,
        money_cols=["销售收入", "分析收入"]
    )

    # 预警
    st.subheader("费用率预警")

    alerts = core_df[
        core_df["费率"] > alert_threshold
    ]

    if alerts.empty:
        st.success("当前没有超过预警线的指标。")
    else:
        for _, row in alerts.iterrows():
            st.warning(
                f"{row['指标名称']}："
                f"{pct(row['费率'])}，"
                f"高于预警线 {pct(alert_threshold)}"
            )

    # 多维度分析
    st.subheader("多维度核心费率分析")

    dimension = st.selectbox(
        "选择分析维度",
        ["部门", "运营人员", "站点"],
        key="core_dimension"
    )

    grouped = aggregate_data(
        filtered,
        [dimension]
    )

    selected_rate = st.selectbox(
        "选择费率指标",
        RATE_COLUMNS,
        key="core_rate_selector"
    )

    grouped = grouped.sort_values(
        selected_rate,
        ascending=False
    )

    fig = px.bar(
        grouped,
        x=dimension,
        y=selected_rate,
        color=selected_rate,
        text=selected_rate,
        title=f"{dimension} - {selected_rate}"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_tickformat=".1%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    show_table(
        grouped[
            [dimension, "分析收入"]
            + RATE_COLUMNS
        ],
        percent_cols=RATE_COLUMNS,
        money_cols=["分析收入"]
    )


# =====================================================
# TAB 3 月度趋势
# =====================================================

with tabs[2]:

    st.header("月度经营趋势")

    monthly = aggregate_data(
        filtered,
        ["月份"]
    ).sort_values("月份")

    st.subheader("收入、成本、费用及利润")

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

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("成本率、费用率、毛利率")

    fig = px.line(
        monthly,
        x="月份",
        y=["成本率", "费用率", "毛利率"],
        markers=True
    )

    fig.update_layout(
        yaxis_tickformat=".1%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("毛利率环比变化")

    monthly["毛利率环比"] = (
        monthly["毛利率"].diff()
    )

    fig = px.bar(
        monthly,
        x="月份",
        y="毛利率环比",
        text="毛利率环比"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_tickformat=".1%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("月度经营数据")

    show_table(
        monthly[
            [
                "月份",
                "销售收入",
                "退款金额",
                "分析收入",
                "成本净额",
                "分析费用",
                "分析毛利",
                "成本率",
                "费用率",
                "毛利率",
                "退款费率"
            ]
        ],
        percent_cols=[
            "成本率",
            "费用率",
            "毛利率",
            "退款费率"
        ],
        money_cols=[
            "销售收入",
            "退款金额",
            "分析收入",
            "成本净额",
            "分析费用",
            "分析毛利"
        ]
    )

    # 毛利率归因
    st.subheader("月度毛利率变化归因")

    if len(monthly) < 2:
        st.info("至少需要两个月的数据。")
    else:

        selected_month = st.selectbox(
            "选择分析月份",
            monthly["月份"].iloc[1:].tolist()
        )

        pos = monthly.index[
            monthly["月份"] == selected_month
        ][0]

        current = monthly.loc[pos]

        previous_pos = monthly.index.get_loc(pos) - 1

        previous = monthly.iloc[previous_pos]

        attribution = []

        for item in ["成本净额"] + EXPENSES:

            old_rate = safe_divide(
                previous[item],
                previous["分析收入"]
            )

            new_rate = safe_divide(
                current[item],
                current["分析收入"]
            )

            impact = old_rate - new_rate

            attribution.append({
                "项目": item,
                "上月费率": old_rate,
                "本月费率": new_rate,
                "毛利率影响(百分点)": impact * 100
            })

        attribution_df = pd.DataFrame(
            attribution
        )

        attribution_df = attribution_df.sort_values(
            "毛利率影响(百分点)"
        )

        fig = px.bar(
            attribution_df,
            x="项目",
            y="毛利率影响(百分点)",
            color="毛利率影响(百分点)",
            title="各项成本费用对毛利率变化的影响"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        show_table(
            attribution_df,
            percent_cols=[
                "上月费率",
                "本月费率"
            ]
        )

        st.caption(
            "归因基于列出的成本费用项目。"
            "若使用原表费用合计且与明细不一致，"
            "可能存在未解释的差额。"
        )


# =====================================================
# TAB 4 成本费用结构
# =====================================================

with tabs[3]:

    st.header("全部成本费用结构")

    items = ["成本净额"] + EXPENSES

    cost_df = pd.DataFrame({
        "项目": items,
        "金额": [
            filtered[c].sum()
            for c in items
        ]
    })

    cost_df["占收入比例"] = (
        cost_df["金额"].apply(
            lambda x: safe_divide(x, revenue)
        )
    )

    total_cost = cost_df["金额"].sum()

    cost_df["占总支出比例"] = (
        cost_df["金额"].apply(
            lambda x: safe_divide(x, total_cost)
        )
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
            y="项目",
            orientation="h",
            color="项目",
            title="成本费用金额排名"
        )

        fig.update_layout(
            showlegend=False,
            yaxis={
                "categoryorder": "total ascending"
            }
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with c2:

        positive = cost_df[
            cost_df["金额"] > 0
        ]

        if not positive.empty:

            fig = px.pie(
                positive,
                names="项目",
                values="金额",
                hole=0.5,
                title="成本费用构成"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    st.subheader("成本费用占比明细")

    show_table(
        cost_df,
        percent_cols=[
            "占收入比例",
            "占总支出比例"
        ],
        money_cols=["金额"]
    )


# =====================================================
# TAB 5 运营绩效
# =====================================================

with tabs[4]:

    st.header("运营绩效分析")

    dimension = st.selectbox(
        "选择绩效分析维度",
        ["部门", "运营人员", "站点"],
        key="performance_dimension"
    )

    performance = aggregate_data(
        filtered,
        [dimension]
    )

    performance = performance.sort_values(
        "分析毛利",
        ascending=False
    )

    st.subheader("经营绩效排名")

    show_table(
        performance[
            [
                dimension,
                "销售收入",
                "退款金额",
                "分析收入",
                "成本净额",
                "分析费用",
                "分析毛利",
                "毛利率",
                "退款费率",
                "七项核心费用率"
            ]
        ],
        percent_cols=[
            "毛利率",
            "退款费率",
            "七项核心费用率"
        ],
        money_cols=[
            "销售收入",
            "退款金额",
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

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("运营人员 / 站点费率对比")

    selected_rate = st.selectbox(
        "选择对比费率",
        RATE_COLUMNS,
        key="performance_rate"
    )

    fig = px.bar(
        performance.sort_values(
            selected_rate,
            ascending=False
        ),
        x=dimension,
        y=selected_rate,
        color=selected_rate,
        text=selected_rate
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_tickformat=".1%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# =====================================================
# TAB 6 利润优化
# =====================================================

with tabs[5]:

    st.header("利润优化与降本模拟")

    target_profit = revenue * target_margin
    profit_gap = target_profit - profit

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "当前毛利率",
        pct(margin)
    )

    c2.metric(
        "目标毛利率",
        pct(target_margin)
    )

    c3.metric(
        "目标利润缺口",
        money(max(profit_gap, 0))
    )

    st.divider()

    st.subheader("单项费用优化模拟")

    selected_expense = st.selectbox(
        "选择优化项目",
        ["成本净额"] + EXPENSES
    )

    saving_rate = st.slider(
        "预计降低费用比例 (%)",
        0,
        50,
        10,
        1
    ) / 100

    original = filtered[selected_expense].sum()

    saving = original * saving_rate

    new_profit = profit + saving

    new_margin = safe_divide(
        new_profit,
        revenue
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "预计节省金额",
        money(saving)
    )

    c2.metric(
        "优化后净毛利",
        money(new_profit)
    )

    c3.metric(
        "优化后毛利率",
        pct(new_margin),
        delta=(
            f"{(new_margin-margin)*100:.2f} 个百分点"
            if pd.notna(new_margin)
            and pd.notna(margin)
            else None
        )
    )

    st.divider()

    st.subheader("退款率改善模拟")

    refund_reduction = st.slider(
        "退款金额降低比例 (%)",
        0,
        50,
        10,
        1
    ) / 100

    refund_saving = refund * refund_reduction

    refund_new_profit = profit + refund_saving

    refund_new_revenue = revenue + refund_saving

    refund_new_margin = safe_divide(
        refund_new_profit,
        refund_new_revenue
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "减少退款金额",
        money(refund_saving)
    )

    c2.metric(
        "改善后利润",
        money(refund_new_profit)
    )

    c3.metric(
        "改善后毛利率",
        pct(refund_new_margin)
    )

    st.caption(
        "退款模拟假设销售收入、成本及其他费用不变，"
        "仅减少退款金额；实际经营可能存在"
        "退货回收、库存及售后费用联动。"
    )


# =====================================================
# TAB 7 数据核对与导出
# =====================================================

with tabs[6]:

    st.header("数据核对与 Excel 导出")

    st.subheader("财务数据核对")

    checks = []

    for original, calculated in [
        ("收入合计", "计算收入"),
        ("费用合计", "计算费用")
    ]:

        if original in filtered.columns:

            diff = (
                filtered[original]
                - filtered[calculated]
            ).abs()

            checks.append({
                "核对项目": original,
                "差异行数": int(
                    (diff > 0.01).sum()
                ),
                "差异绝对值合计": diff.sum()
            })

    if "销售净毛利" in filtered.columns:

        diff = (
            filtered["销售净毛利"]
            - filtered["分析毛利"]
        ).abs()

        checks.append({
            "核对项目": "销售净毛利",
            "差异行数": int(
                (diff > 0.01).sum()
            ),
            "差异绝对值合计": diff.sum()
        })

    check_df = pd.DataFrame(checks)

    if not check_df.empty:
        show_table(
            check_df,
            money_cols=["差异绝对值合计"]
        )

    if refund_sign_errors > 0:
        st.warning(
            f"原始数据有 {refund_sign_errors} 行退款符号"
            "与所选记录方式不一致，请检查。"
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
            money(
                filtered["实际回款-提成计算"].sum()
            )
        )

    st.divider()

    st.subheader("导出分析结果")

    export_monthly = aggregate_data(
        filtered,
        ["月份"]
    ).sort_values("月份")

    export_department = aggregate_data(
        filtered,
        ["部门"]
    )

    export_staff = aggregate_data(
        filtered,
        ["运营人员"]
    )

    export_site = aggregate_data(
        filtered,
        ["站点"]
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

        core_df.to_excel(
            writer,
            index=False,
            sheet_name="八项核心费率"
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

        check_df.to_excel(
            writer,
            index=False,
            sheet_name="财务核对"
        )

    st.download_button(
        label="下载完整经营分析 Excel",
        data=output.getvalue(),
        file_name="经营利润与核心费用率分析.xlsx",
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

st.divider()

st.caption(
    "经营利润与成本费用分析系统 | "
    "数据来源：上传的经营财务报表"
)
