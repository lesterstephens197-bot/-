
import io
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =====================================================
# 1. 页面设置
# =====================================================

st.set_page_config(
    page_title="13%利润率考核与成本管控",
    page_icon="📊",
    layout="wide"
)

st.title("经营利润率考核与成本管控 Dashboard")

st.caption(
    "按月份 / 部门 / 运营人员 / 站点"
    "追踪利润率是否达到 13%"
)

# 固定考核目标
TARGET = 0.13

# =====================================================
# 2. Excel 字段定义
# =====================================================

DIMS = [
    "月份",
    "部门",
    "运营人员",
    "站点"
]

COSTS = [
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
    "站外仓储费"
]

# 不包含产品成本的费用
EXPENSES = [
    x for x in COSTS
    if x != "成本净额"
]

# 重点监控的9项费率
WATCH = [
    "退款费率",
    "成本费率",
    "头程费率",
    "站内推广费率",
    "平台佣金费率",
    "站外推广费率",
    "自发货运费率",
    "售后费率",
    "其他费率"
]

RATE_MAP = {
    "成本费率": "成本净额",
    "头程费率": "头程净额",
    "站内推广费率": "站内推广费",
    "平台佣金费率": "平台佣金",
    "站外推广费率": "站外推广费",
    "自发货运费率": "自发货运费",
    "售后费率": "售后费用",
    "其他费率": "其他费用"
}

# 与你的Excel表头保持一致
HEADERS = [
    "月份",
    "部门",
    "运营人员",
    "站点",
    "销售收入",
    "退款收入",
    "收入合计",
    "退款费率",
    "成本净额",
    "成本费率",
    "头程净额",
    "头程费率",
    "站内仓储费",
    "税费",
    "平台服务费",
    "平台运费",
    "站内推广费",
    "站内推广费率",
    "平台佣金",
    "平台佣金费率",
    "站外推广费",
    "站外推广费率",
    "自发货运费",
    "自发货运费率",
    "售后费用",
    "售后费率",
    "其他费用",
    "其他费率",
    "站外仓储费",
    "费用合计",
    "费用占比",
    "销售净毛利",
    "毛利率",
    "平台回款",
    "实际回款-提成计算",
    "成本回报率"
]

MONEY = [
    "销售收入",
    "退款收入",
    "收入合计",
    "费用合计",
    "销售净毛利",
    "平台回款",
    "实际回款-提成计算"
] + COSTS

RATE_INPUTS = [
    x for x in HEADERS
    if "率" in x or x == "费用占比"
]

# =====================================================
# 3. 通用函数
# =====================================================

def numeric(series):
    """清理金额中的符号"""

    s = series.astype(str)

    s = s.str.replace(
        ",", "", regex=False
    )

    s = s.str.replace(
        r"[¥￥$%\s]", "", regex=True
    )

    s = s.str.replace(
        r"^\((.*)\)$",
        r"-\1",
        regex=True
    )

    return pd.to_numeric(
        s,
        errors="coerce"
    )


def month_string(v):
    """统一月份格式"""

    if pd.isna(v):
        return "未填写"

    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m")

    s = str(v).strip()

    if re.fullmatch(r"\d{6}", s):
        return s[:4] + "-" + s[4:]

    if re.fullmatch(r"\d{4}[-/]\d{1,2}", s):
        a, b = re.split("[-/]", s)
        return f"{a}-{int(b):02d}"

    if re.fullmatch(r"\d{4}年\d{1,2}月?", s):
        a, b = re.findall(r"\d+", s)
        return f"{a}-{int(b):02d}"

    if re.fullmatch(r"\d{1,2}", s):
        return f"{int(s):02d}月"

    return s


def divide(a, b):
    """安全除法"""

    if isinstance(b, pd.Series):
        return a / b.replace(0, np.nan)

    return a / b if b else np.nan


def fmt(v):
    return "—" if pd.isna(v) else f"{v:,.2f}"


def pf(v):
    return "—" if pd.isna(v) else f"{v:.2%}"


def group_metrics(df, by):
    """先汇总金额，再计算费率"""

    amounts = list(dict.fromkeys(
        [
            "销售收入",
            "退款金额",
            "净收入",
            "分析费用",
            "利润",
            "平台回款",
            "实际回款-提成计算"
        ] + COSTS
    ))

    g = df.groupby(
        by,
        dropna=False,
        as_index=False
    )[amounts].sum()

    # 计算各项费用率
    for rate, col in RATE_MAP.items():
        g[rate] = divide(
            g[col],
            g["净收入"]
        )

    # 退款费率
    g["退款费率"] = divide(
        g["退款金额"],
        g["销售收入"]
    )

    # 费用率
    g["费用占比"] = divide(
        g["分析费用"],
        g["净收入"]
    )

    # 毛利率
    g["毛利率"] = divide(
        g["利润"],
        g["净收入"]
    )

    # 成本回报率
    g["成本回报率"] = divide(
        g["利润"],
        g["成本净额"] + g["分析费用"]
    )

    # 13%利润目标
    g["利润目标"] = g["净收入"] * TARGET

    # 目标缺口
    g["利润缺口"] = np.maximum(
        g["利润目标"] - g["利润"],
        0
    )

    # 安全利润空间
    g["利润安全空间"] = (
        g["利润"] - g["利润目标"]
    )

    # 达标判断
    g["考核结果"] = np.where(
        g["净收入"] <= 0,
        "不可评估",
        np.where(
            g["毛利率"] >= TARGET,
            "达标",
            "未达标"
        )
    )

    return g


def show(df):
    """统一表格格式"""

    formats = {
        c: "{:.2%}"
        for c in df.columns
        if c in WATCH or c in [
            "毛利率",
            "费用占比",
            "成本回报率"
        ]
    }

    for c in df.columns:
        if c in MONEY or c in [
            "退款金额",
            "净收入",
            "分析费用",
            "利润",
            "利润目标",
            "利润缺口",
            "利润安全空间"
        ]:
            formats[c] = "{:,.2f}"

    st.dataframe(
        df.style.format(
            formats,
            na_rep="—"
        ),
        hide_index=True,
        use_container_width=True
    )


# =====================================================
# 4. 侧边栏：数据导入
# =====================================================

with st.sidebar:

    st.header("数据与考核设置")

    file = st.file_uploader(
        "上传 Excel / CSV",
        type=["xlsx", "csv"]
    )

    refund_sign = st.radio(
        "退款收入记录方式",
        [
            "负数表示退款",
            "正数表示退款"
        ]
    )

    revenue_mode = st.radio(
        "净收入口径",
        [
            "优先使用原表收入合计",
            "销售收入减退款金额"
        ]
    )

    expense_mode = st.radio(
        "费用口径",
        [
            "优先使用原表费用合计",
            "自动汇总12项费用"
        ]
    )

    st.info(
        "考核目标固定为毛利率 ≥ 13%。"
        "退款费率以销售收入为分母，"
        "其余费率以净收入为分母。"
    )


# =====================================================
# 5. 读取Excel
# =====================================================

if file is None:

    st.info(
        "上传报表后即可查看利润率达标情况、"
        "费用率趋势、异常归因及降本方案。"
    )

    template = pd.DataFrame(
        columns=HEADERS
    )

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        template.to_excel(
            writer,
            index=False,
            sheet_name="经营数据"
        )

    st.download_button(
        "下载标准Excel模板",
        data=output.getvalue(),
        file_name="经营数据模板.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    st.stop()


try:

    if file.name.lower().endswith(".csv"):

        try:
            raw = pd.read_csv(
                file,
                encoding="utf-8-sig"
            )

        except UnicodeDecodeError:

            file.seek(0)

            raw = pd.read_csv(
                file,
                encoding="gb18030"
            )

    else:
        raw = pd.read_excel(file)

except Exception as exc:

    st.error(f"读取失败：{exc}")
    st.stop()


# 清理表头空格
raw.columns = [
    str(c).replace(
        "\u3000", " "
    ).strip()
    for c in raw.columns
]

if raw.columns.duplicated().any():

    st.error("发现重复表头，请检查文件。")
    st.stop()


required = DIMS + [
    "销售收入",
    "退款收入"
] + COSTS

missing = [
    c for c in required
    if c not in raw.columns
]

if missing:

    st.error(
        "缺少必需字段：" + ", ".join(missing)
    )

    st.stop()


if raw.empty:

    st.warning("表格没有数据")
    st.stop()


# =====================================================
# 6. 数据清洗
# =====================================================

df = raw.copy()

for c in MONEY:

    if c in df.columns:

        v = numeric(df[c])

        df[c] = v.fillna(0)


for c in RATE_INPUTS:

    if c in df.columns:
        df[c] = numeric(df[c])


for c in DIMS[1:]:

    df[c] = (
        df[c]
        .fillna("未填写")
        .astype(str)
        .str.strip()
        .replace("", "未填写")
    )


df["月份"] = df["月份"].map(
    month_string
)


# =====================================================
# 7. 退款、收入、费用、利润计算
# =====================================================

if refund_sign == "负数表示退款":

    df["退款金额"] = -df["退款收入"]

else:

    df["退款金额"] = df["退款收入"]


# 计算净收入
df["计算净收入"] = (
    df["销售收入"] - df["退款金额"]
)

# 计算费用
df["计算费用"] = df[EXPENSES].sum(axis=1)

# 净收入
if (
    revenue_mode.startswith("优先")
    and "收入合计" in df
):

    df["净收入"] = df["收入合计"]

else:

    df["净收入"] = df["计算净收入"]


# 分析费用
if (
    expense_mode.startswith("优先")
    and "费用合计" in df
):

    df["分析费用"] = df["费用合计"]

else:

    df["分析费用"] = df["计算费用"]


# 净毛利
df["利润"] = (
    df["净收入"]
    - df["成本净额"]
    - df["分析费用"]
)


# 回款字段
for c in [
    "平台回款",
    "实际回款-提成计算"
]:

    if c not in df:
        df[c] = 0.0


# =====================================================
# 8. 全局筛选
# =====================================================

with st.sidebar:

    st.header("全局筛选")

    for c in DIMS:

        options = sorted(
            df[c].unique().tolist()
        )

        chosen = st.multiselect(
            c,
            options,
            default=options
        )

        df = df[
            df[c].isin(chosen)
        ]


if df.empty:

    st.warning("筛选后没有数据")
    st.stop()


# =====================================================
# 9. 核心汇总
# =====================================================

revenue = df["净收入"].sum()

profit = df["利润"].sum()

expense = df["分析费用"].sum()

cost = df["成本净额"].sum()

sales = df["销售收入"].sum()

refunds = df["退款金额"].sum()


margin = divide(
    profit,
    revenue
)

gap = max(
    TARGET * revenue - profit,
    0
)

cushion = (
    profit - TARGET * revenue
)


if revenue <= 0:

    status = "不可评估"

else:

    status = (
        "达标"
        if margin >= TARGET
        else "未达标"
    )


# =====================================================
# 10. 页面导航
# =====================================================

pages = st.tabs([
    "考核总览",
    "9项关键费率",
    "月度趋势与归因",
    "部门/人员/站点",
    "13%降本模拟",
    "数据核对与导出"
])


# =====================================================
# TAB 1：考核总览
# =====================================================

with pages[0]:

    st.subheader("利润率 13% 考核看板")

    a, b, c, d = st.columns(4)

    a.metric(
        "实际毛利率",
        pf(margin)
    )

    b.metric(
        "考核线",
        "13.00%"
    )

    c.metric(
        "考核状态",
        status
    )

    d.metric(
        "利润缺口",
        fmt(gap)
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "净收入",
        fmt(revenue)
    )

    b.metric(
        "销售净毛利",
        fmt(profit)
    )

    c.metric(
        "总费用率",
        pf(divide(expense, revenue))
    )

    d.metric(
        "利润安全空间",
        fmt(cushion)
    )

    if status == "达标":

        st.success(
            f"当前达标，高于13%考核线 "
            f"{((margin-TARGET)*100):.2f} 个百分点。"
        )

    elif status == "未达标":

        st.error(
            f"当前未达标，至少需改善利润 "
            f"{fmt(gap)}（假设收入不变）。"
        )

    else:

        st.warning(
            "净收入非正，无法评估利润率。"
        )

    st.caption(
        "利润安全空间 = 实际利润 − 13% × 净收入；"
        "正数为可承受的利润下降空间，"
        "负数为利润缺口。"
    )

    # 利润率仪表盘
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=(
                float(margin * 100)
                if pd.notna(margin)
                else 0
            ),
            number={
                "suffix": "%"
            },
            gauge={
                "axis": {
                    "range": [
                        0,
                        max(
                            30,
                            float(margin * 100) * 1.2
                            if pd.notna(margin)
                            else 30
                        )
                    ]
                },
                "threshold": {
                    "line": {
                        "color": "red",
                        "width": 4
                    },
                    "value": 13
                }
            }
        )
    )

    fig.update_layout(
        height=310
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# =====================================================
# TAB 2：9项关键费率
# =====================================================

with pages[1]:

    st.subheader(
        "9项关键费率"
    )

    st.caption(
        "包含退款、成本、头程和六项经营费用"
    )

    values = {}

    for name, col in RATE_MAP.items():

        values[name] = divide(
            df[col].sum(),
            revenue
        )

    values["退款费率"] = divide(
        refunds,
        sales
    )

    ordered = [
        "退款费率",
        "成本费率",
        "头程费率",
        "站内推广费率",
        "平台佣金费率",
        "站外推广费率",
        "自发货运费率",
        "售后费率",
        "其他费率"
    ]

    # 费率KPI
    cols = st.columns(3)

    for i, name in enumerate(ordered):

        cols[i % 3].metric(
            name,
            pf(values[name])
        )

    # 费率明细
    rate_df = pd.DataFrame({
        "指标": ordered,
        "费率": [
            values[k]
            for k in ordered
        ]
    })

    rate_df["金额"] = [
        refunds
        if x == "退款费率"
        else df[RATE_MAP[x]].sum()
        for x in ordered
    ]

    rate_df["分母"] = [
        "销售收入"
        if x == "退款费率"
        else "净收入"
        for x in ordered
    ]

    # 费率对比图
    fig = px.bar(
        rate_df,
        x="指标",
        y="费率",
        text="费率",
        title="关键费率对比"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_tickformat=".0%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.dataframe(
        rate_df.style.format({
            "费率": "{:.2%}",
            "金额": "{:,.2f}"
        }, na_rep="—"),
        hide_index=True,
        use_container_width=True
    )

    st.info(
        "退款已从净收入扣除，"
        "不能再将退款费率与其他费用率直接相加，"
        "否则会重复计算。"
    )

    # 全部成本费用明细
    cost_structure = pd.DataFrame({
        "项目": COSTS,
        "金额": [
            df[c].sum()
            for c in COSTS
        ]
    })

    cost_structure["占净收入"] = divide(
        cost_structure["金额"],
        revenue
    )

    st.subheader("全部成本费用明细")

    st.dataframe(
        cost_structure.style.format({
            "金额": "{:,.2f}",
            "占净收入": "{:.2%}"
        }, na_rep="—"),
        hide_index=True,
        use_container_width=True
    )


# =====================================================
# TAB 3：月度趋势与归因
# =====================================================

with pages[2]:

    st.subheader(
        "月度毛利率与13%考核线"
    )

    monthly = group_metrics(
        df,
        ["月份"]
    ).sort_values(
        "月份"
    ).reset_index(drop=True)

    monthly["考核线"] = TARGET

    fig = px.line(
        monthly,
        x="月份",
        y=[
            "毛利率",
            "考核线"
        ],
        markers=True
    )

    fig.update_layout(
        yaxis_tickformat=".0%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # 月度费率走势
    st.subheader("月度关键费率走势")

    chosen_rates = st.multiselect(
        "选择费率",
        WATCH,
        default=[
            "退款费率",
            "头程费率",
            "站内推广费率",
            "平台佣金费率"
        ]
    )

    if chosen_rates:

        fig = px.line(
            monthly,
            x="月份",
            y=chosen_rates,
            markers=True
        )

        fig.update_layout(
            yaxis_tickformat=".0%"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # 月度考核表
    show(
        monthly[
            [
                "月份",
                "净收入",
                "利润",
                "毛利率",
                "利润缺口",
                "利润安全空间",
                "考核结果"
            ] + WATCH
        ]
    )

    # 毛利率归因
    st.subheader("毛利率环比变化归因")

    if len(monthly) < 2:

        st.info(
            "至少两个月数据才可进行环比归因。"
        )

    else:

        selected = st.selectbox(
            "分析月份",
            monthly["月份"].iloc[1:].tolist()
        )

        idx = monthly.index[
            monthly["月份"] == selected
        ][0]

        cur = monthly.iloc[idx]

        prev = monthly.iloc[idx - 1]

        changes = []

        for item in COSTS:

            old = divide(
                prev[item],
                prev["净收入"]
            )

            new = divide(
                cur[item],
                cur["净收入"]
            )

            changes.append({
                "项目": item,
                "上月费率": old,
                "本月费率": new,
                "对毛利率影响(百分点)": (
                    old - new
                ) * 100
            })

        # 未归类费用差额
        if (
            prev["净收入"] != 0
            and cur["净收入"] != 0
        ):

            residual = (
                (
                    prev["分析费用"]
                    - prev[EXPENSES].sum()
                ) / prev["净收入"]
                -
                (
                    cur["分析费用"]
                    - cur[EXPENSES].sum()
                ) / cur["净收入"]
            )

        else:
            residual = np.nan

        changes.append({
            "项目": "未归类费用差额",
            "上月费率": np.nan,
            "本月费率": np.nan,
            "对毛利率影响(百分点)": (
                residual * 100
            )
        })

        attribution = pd.DataFrame(
            changes
        ).sort_values(
            "对毛利率影响(百分点)"
        )

        fig = px.bar(
            attribution,
            x="项目",
            y="对毛利率影响(百分点)",
            title=(
                "正数改善利润率，"
                "负数拖累利润率"
            )
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.dataframe(
            attribution.style.format({
                "上月费率": "{:.2%}",
                "本月费率": "{:.2%}",
                "对毛利率影响(百分点)": "{:.2f}"
            }, na_rep="—"),
            hide_index=True,
            use_container_width=True
        )


# =====================================================
# TAB 4：部门、人员、站点
# =====================================================

with pages[3]:

    st.subheader(
        "部门、运营人员、站点的13%考核表现"
    )

    dimension = st.selectbox(
        "考核维度",
        [
            "部门",
            "运营人员",
            "站点"
        ]
    )

    ranked = group_metrics(
        df,
        [dimension]
    ).sort_values(
        "毛利率",
        ascending=False,
        na_position="last"
    )

    show(
        ranked[
            [
                dimension,
                "净收入",
                "利润",
                "毛利率",
                "利润缺口",
                "利润安全空间",
                "考核结果"
            ] + WATCH
        ]
    )

    # 绩效排名图
    fig = px.bar(
        ranked,
        x=dimension,
        y="毛利率",
        color="考核结果",
        text="毛利率"
    )

    fig.add_hline(
        y=TARGET,
        line_dash="dash",
        line_color="red",
        annotation_text="13%考核线"
    )

    fig.update_traces(
        texttemplate="%{y:.2%}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_tickformat=".0%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# =====================================================
# TAB 5：13%降本模拟
# =====================================================

with pages[4]:

    st.subheader(
        "达到13%需要节省多少？"
    )

    st.metric(
        "当前利润缺口",
        fmt(gap)
    )

    if revenue <= 0:

        st.warning(
            "净收入非正，无法模拟。"
        )

    else:

        options = [
            "成本净额"
        ] + EXPENSES

        selected = st.selectbox(
            "选择优化项目",
            options
        )

        reduction = st.slider(
            "费用减少比例 (%)",
            0,
            60,
            10
        ) / 100

        amount = df[selected].sum()

        saved = (
            max(amount, 0) * reduction
        )

        after_profit = profit + saved

        after_margin = divide(
            after_profit,
            revenue
        )

        a, b, c = st.columns(3)

        a.metric(
            "预计节省",
            fmt(saved)
        )

        b.metric(
            "优化后毛利率",
            pf(after_margin)
        )

        c.metric(
            "优化后利润缺口",
            fmt(
                max(
                    TARGET * revenue - after_profit,
                    0
                )
            )
        )

        if after_margin >= TARGET:

            st.success(
                "此模拟情景达到13%考核线。"
            )

        else:

            st.warning(
                "此模拟情景仍低于13%。"
            )

        # 各项费用降本潜力
        st.subheader(
            "各项费用独立优化至13%所需降幅"
        )

        opportunities = []

        for item in options:

            amount = df[item].sum()

            needed = (
                divide(gap, amount)
                if amount > 0
                else np.nan
            )

            opportunities.append({
                "费用项目": item,
                "当前金额": amount,
                "单独达标所需降幅": needed,
                "单独降本能否达标": (
                    bool(
                        amount >= gap
                        and amount > 0
                    )
                    if gap > 0
                    else True
                )
            })

        opportunities = pd.DataFrame(
            opportunities
        ).sort_values(
            "当前金额",
            ascending=False
        )

        st.dataframe(
            opportunities.style.format({
                "当前金额": "{:,.2f}",
                "单独达标所需降幅": "{:.2%}"
            }, na_rep="—"),
            hide_index=True,
            use_container_width=True
        )

        st.caption(
            "模拟假设净收入及其他成本不变，"
            "不考虑降价、广告投入变化对销量的影响。"
        )


# =====================================================
# TAB 6：数据核对与导出
# =====================================================

with pages[5]:

    st.subheader(
        "财务口径与数据质量核对"
    )

    checks = []

    for source, calc in [
        ("收入合计", "计算净收入"),
        ("费用合计", "计算费用")
    ]:

        if source in df:

            diff = (
                df[source] - df[calc]
            ).abs()

            checks.append({
                "核对项": source,
                "差异行数": int(
                    (diff > 0.01).sum()
                ),
                "差异绝对值合计": float(
                    diff.sum()
                )
            })

    if "销售净毛利" in df:

        diff = (
            df["销售净毛利"]
            - df["利润"]
        ).abs()

        checks.append({
            "核对项": "销售净毛利",
            "差异行数": int(
                (diff > 0.01).sum()
            ),
            "差异绝对值合计": float(
                diff.sum()
            )
        })

    checks = pd.DataFrame(checks)

    show(checks)

    if (df["退款金额"] < 0).any():

        st.warning(
            "部分退款金额为负，"
            "请检查左侧的退款正负号设置。"
        )

    st.caption(
        "原表费率字段仅用于原始记录；"
        "看板按汇总金额重新计算。"
    )

    # 回款数据
    st.subheader("平台回款分析")

    a, b = st.columns(2)

    a.metric(
        "平台回款",
        fmt(df["平台回款"].sum())
    )

    b.metric(
        "实际回款-提成计算",
        fmt(
            df["实际回款-提成计算"].sum()
        )
    )

    # Excel导出
    st.subheader("导出分析结果")

    export = io.BytesIO()

    with pd.ExcelWriter(
        export,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="筛选后明细",
            index=False
        )

        group_metrics(
            df,
            ["月份"]
        ).to_excel(
            writer,
            sheet_name="月度考核",
            index=False
        )

        for dim, sheet in [
            ("部门", "部门考核"),
            ("运营人员", "人员考核"),
            ("站点", "站点考核")
        ]:

            group_metrics(
                df,
                [dim]
            ).to_excel(
                writer,
                sheet_name=sheet,
                index=False
            )

        rate_df = pd.DataFrame({
            "指标": WATCH,
            "费率": [
                divide(refunds, sales)
                if x == "退款费率"
                else divide(
                    df[RATE_MAP[x]].sum(),
                    revenue
                )
                for x in WATCH
            ]
        })

        rate_df.to_excel(
            writer,
            sheet_name="关键费率",
            index=False
        )

        checks.to_excel(
            writer,
            sheet_name="口径核对",
            index=False
        )

    st.download_button(
        "下载经营分析 Excel",
        data=export.getvalue(),
        file_name="13percent_profit_dashboard.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

# =====================================================
# END
# =====================================================
