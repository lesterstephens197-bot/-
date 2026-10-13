
import io
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="经营利润与费用分析",
    page_icon="📊",
    layout="wide"
)

st.title("经营利润与费用分析 Dashboard")
st.caption("按月份、部门、运营人员和站点分析成本结构、利润率与回款")

# =========================
# 1. 字段定义
# =========================

DIM = ["月份", "部门", "运营人员", "站点"]

AMOUNTS = [
    "销售收入", "退款收入", "收入合计",
    "成本净额", "头程净额", "站内仓储费",
    "税费", "平台服务费", "平台运费",
    "站内推广费", "平台佣金", "站外推广费",
    "自发货运费", "售后费用", "其他费用",
    "站外仓储费", "费用合计", "销售净毛利",
    "平台回款", "实际回款-提成计算"
]

EXPENSES = [
    "头程净额", "站内仓储费", "税费",
    "平台服务费", "平台运费", "站内推广费",
    "平台佣金", "站外推广费", "自发货运费",
    "售后费用", "其他费用", "站外仓储费"
]

COST_ITEMS = ["成本净额"] + EXPENSES

REQUIRED = (
    DIM
    + ["销售收入", "退款收入", "成本净额"]
    + EXPENSES
)


# =========================
# 2. 计算函数
# =========================

def to_number(series):
    """清理金额字段中的货币符号、逗号等"""
    s = series.astype(str)

    for symbol in [",", "¥", "$", "%"]:
        s = s.str.replace(symbol, "", regex=False)

    s = s.str.strip()

    s = s.replace({
        "": "0",
        "nan": "0",
        "None": "0",
        "-": "0"
    })

    return pd.to_numeric(
        s, errors="coerce"
    ).fillna(0)


def safe_ratio(a, b):
    if abs(b) < 1e-9:
        return np.nan
    return float(a / b)


def money(value):
    return f"{value:,.2f}"


def percent(value):
    if pd.isna(value):
        return "N/A"
    return f"{value:.2%}"


def normalize_month(value):
    """统一月份格式"""
    if pd.isna(value):
        return "未填写"

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m")

    s = str(value).strip()

    if not s:
        return "未填写"

    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]

    if s.isdigit() and len(s) == 6:
        year = int(s[:4])
        month = int(s[4:])
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return f"{year}-{month:02d}"

    if s.isdigit() and 1 <= int(s) <= 12:
        return f"{int(s):02d}月"

    try:
        if any(x in s for x in ["-", "/", "年"]):
            parsed = pd.to_datetime(
                s.replace("年", "-").replace("月", ""),
                errors="coerce"
            )
            if pd.notna(parsed):
                return parsed.strftime("%Y-%m")
    except Exception:
        pass

    return s


# =========================
# 3. 上传数据
# =========================

with st.expander("数据口径与计算规则"):
    st.markdown("""
    **默认计算规则**

    - 收入合计 = 销售收入 + 退款收入
    - 费用合计 = 12项费用之和，包含头程净额
    - 销售净毛利 = 收入合计 - 成本净额 - 费用合计
    - 成本率 = 成本净额 / 收入合计
    - 费用率 = 费用合计 / 收入合计
    - 毛利率 = 销售净毛利 / 收入合计
    - 成本回报率 = 销售净毛利 / (成本净额 + 费用合计)

    **注意**

    退款收入默认采用负数表示。

    如果原始报表的费用合计不包含头程净额，
    或者成本回报率使用不同定义，
    请根据实际财务口径调整。

    所有汇总比率均根据汇总金额重新计算，
    不直接平均原始数据中的百分比。
    """)

uploaded_file = st.file_uploader(
    "上传经营数据 Excel 或 CSV",
    type=["xlsx", "csv"]
)

if uploaded_file is None:
    st.info("请先上传经营数据文件。")
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

raw = raw.loc[:, ~raw.columns.duplicated()].copy()

missing = [
    c for c in REQUIRED
    if c not in raw.columns
]

if missing:
    st.error("缺少必要字段：" + "、".join(missing))
    st.stop()

if raw.empty:
    st.warning("上传文件没有数据。")
    st.stop()


# =========================
# 4. 数据清洗
# =========================

df = raw.copy()

for col in AMOUNTS:
    if col in df.columns:
        df[col] = to_number(df[col])

for col in DIM[1:]:
    df[col] = (
        df[col]
        .fillna("未填写")
        .astype(str)
        .str.strip()
        .replace("", "未填写")
    )

df["月份"] = df["月份"].map(normalize_month)

df["计算收入合计"] = (
    df["销售收入"] + df["退款收入"]
)

df["计算费用合计"] = df[EXPENSES].sum(axis=1)

df["计算销售净毛利"] = (
    df["计算收入合计"]
    - df["成本净额"]
    - df["计算费用合计"]
)


# =========================
# 5. 侧边栏筛选
# =========================

st.sidebar.header("数据筛选")

for col in DIM:
    options = sorted(
        df[col].astype(str).unique().tolist()
    )

    selected = st.sidebar.multiselect(
        col,
        options,
        default=options
    )

    df = df[
        df[col].astype(str).isin(selected)
    ]

if df.empty:
    st.warning("当前筛选条件下没有数据。")
    st.stop()

st.sidebar.header("分析设置")

revenue_basis = st.sidebar.radio(
    "收入合计口径",
    ["原表优先", "重新计算"]
)

expense_basis = st.sidebar.radio(
    "费用合计口径",
    ["重新计算", "原表优先"]
)

target_margin = st.sidebar.slider(
    "目标毛利率 (%)",
    0.0, 50.0, 20.0, 0.5
) / 100

warning_rate = st.sidebar.slider(
    "单项费用率预警 (%)",
    0.0, 30.0, 10.0, 0.5
) / 100


# =========================
# 6. 确定分析口径
# =========================

if (
    revenue_basis == "原表优先"
    and "收入合计" in df.columns
):
    df["分析收入"] = df["收入合计"]
else:
    df["分析收入"] = df["计算收入合计"]

if (
    expense_basis == "原表优先"
    and "费用合计" in df.columns
):
    df["分析费用"] = df["费用合计"]
else:
    df["分析费用"] = df["计算费用合计"]

df["分析毛利"] = (
    df["分析收入"]
    - df["成本净额"]
    - df["分析费用"]
)

revenue = df["分析收入"].sum()
cost = df["成本净额"].sum()
expenses = df["分析费用"].sum()
profit = df["分析毛利"].sum()

margin = safe_ratio(profit, revenue)
cost_rate = safe_ratio(cost, revenue)
expense_rate = safe_ratio(expenses, revenue)


# =========================
# 7. 经营总览
# =========================

st.header("一、经营总览")

cols = st.columns(6)

metrics = [
    ("收入合计", money(revenue)),
    ("成本净额", money(cost)),
    ("费用合计", money(expenses)),
    ("销售净毛利", money(profit)),
    ("毛利率", percent(margin)),
    ("费用率", percent(expense_rate))
]

for col, (label, value) in zip(cols, metrics):
    col.metric(label, value)

st.divider()


# =========================
# 8. 成本费用结构分析
# =========================

st.header("二、成本费用结构分析")

expense_data = (
    df[COST_ITEMS]
    .sum()
    .rename_axis("费用项目")
    .reset_index(name="金额")
)

expense_data["占收入比例"] = (
    expense_data["金额"].apply(
        lambda x: safe_ratio(x, revenue)
    )
)

total_spending = expense_data["金额"].sum()

expense_data["占总支出比例"] = (
    expense_data["金额"].apply(
        lambda x: safe_ratio(x, total_spending)
    )
)

expense_data = expense_data.sort_values(
    "金额",
    ascending=False
)

left, right = st.columns(2)

with left:
    fig = px.bar(
        expense_data,
        x="金额",
        y="费用项目",
        orientation="h",
        color="费用项目",
        title="各项成本费用金额"
    )

    fig.update_layout(
        showlegend=False,
        yaxis={"categoryorder": "total ascending"}
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

with right:
    pie_data = expense_data[
        expense_data["金额"] > 0
    ]

    if not pie_data.empty:
        fig = px.pie(
            pie_data,
            values="金额",
            names="费用项目",
            hole=0.5,
            title="成本费用构成"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

st.subheader("各项费用占比明细")

st.dataframe(
    expense_data.style.format(
        {
            "金额": "{:,.2f}",
            "占收入比例": "{:.2%}",
            "占总支出比例": "{:.2%}"
        },
        na_rep="—"
    ),
    use_container_width=True,
    hide_index=True
)


# =========================
# 9. 费用异常预警
# =========================

st.header("三、费用异常预警")

alerts = expense_data[
    (expense_data["占收入比例"] > warning_rate)
    & (expense_data["费用项目"] != "成本净额")
]

if alerts.empty:
    st.success("当前没有超过预警阈值的费用项目。")
else:
    for _, row in alerts.iterrows():
        st.warning(
            f"{row['费用项目']}："
            f"占收入 {percent(row['占收入比例'])}，"
            f"超过设定阈值 {percent(warning_rate)}"
        )


# =========================
# 10. 月度经营趋势
# =========================

st.header("四、月度经营趋势")

monthly = (
    df.groupby("月份", as_index=False)[
        ["分析收入", "成本净额", "分析费用", "分析毛利"]
    ]
    .sum()
    .sort_values("月份")
)

monthly["毛利率"] = monthly.apply(
    lambda r: safe_ratio(
        r["分析毛利"], r["分析收入"]
    ),
    axis=1
)

monthly["成本率"] = monthly.apply(
    lambda r: safe_ratio(
        r["成本净额"], r["分析收入"]
    ),
    axis=1
)

monthly["费用率"] = monthly.apply(
    lambda r: safe_ratio(
        r["分析费用"], r["分析收入"]
    ),
    axis=1
)

left, right = st.columns(2)

with left:
    fig = px.bar(
        monthly,
        x="月份",
        y=[
            "分析收入",
            "成本净额",
            "分析费用",
            "分析毛利"
        ],
        barmode="group",
        title="月度收入、成本、费用及利润"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

with right:
    fig = px.line(
        monthly,
        x="月份",
        y=["毛利率", "成本率", "费用率"],
        markers=True,
        title="月度经营比率趋势"
    )

    fig.update_layout(
        yaxis_tickformat=".0%"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

st.dataframe(
    monthly.style.format(
        {
            "分析收入": "{:,.2f}",
            "成本净额": "{:,.2f}",
            "分析费用": "{:,.2f}",
            "分析毛利": "{:,.2f}",
            "毛利率": "{:.2%}",
            "成本率": "{:.2%}",
            "费用率": "{:.2%}"
        },
        na_rep="—"
    ),
    use_container_width=True,
    hide_index=True
)


# =========================
# 11. 部门、人员、站点分析
# =========================

st.header("五、运营绩效分析")

group_dimension = st.selectbox(
    "选择分析维度",
    ["部门", "运营人员", "站点", "月份"]
)

ranking = (
    df.groupby(group_dimension, as_index=False)[
        ["分析收入", "成本净额", "分析费用", "分析毛利"]
    ]
    .sum()
)

ranking["毛利率"] = ranking.apply(
    lambda r: safe_ratio(
        r["分析毛利"], r["分析收入"]
    ),
    axis=1
)

ranking["费用率"] = ranking.apply(
    lambda r: safe_ratio(
        r["分析费用"], r["分析收入"]
    ),
    axis=1
)

ranking = ranking.sort_values(
    "分析毛利",
    ascending=False
)

st.dataframe(
    ranking.style.format(
        {
            "分析收入": "{:,.2f}",
            "成本净额": "{:,.2f}",
            "分析费用": "{:,.2f}",
            "分析毛利": "{:,.2f}",
            "毛利率": "{:.2%}",
            "费用率": "{:.2%}"
        },
        na_rep="—"
    ),
    use_container_width=True,
    hide_index=True
)

fig = px.bar(
    ranking,
    x=group_dimension,
    y="分析毛利",
    color="毛利率",
    title=f"按{group_dimension}对比销售净毛利"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# =========================
# 12. 利润目标与降本模拟
# =========================

st.header("六、利润目标与降本模拟")

allowed_spending = revenue * (1 - target_margin)

headroom = allowed_spending - (cost + expenses)

st.metric(
    "目标毛利率下的成本费用剩余空间",
    money(headroom)
)

if headroom < 0:
    st.error(
        f"要达到 {percent(target_margin)} 的目标毛利率，"
        f"需要减少成本费用 {money(abs(headroom))}"
    )
else:
    st.success(
        f"当前已满足目标毛利率，"
        f"成本费用空间为 {money(headroom)}"
    )

selected_item = st.selectbox(
    "选择需要优化的成本费用",
    COST_ITEMS
)

saving_percent = st.slider(
    "预计节省比例 (%)",
    0, 50, 10, 1
) / 100

original_amount = df[selected_item].sum()

saving = original_amount * saving_percent

new_profit = profit + saving

new_margin = safe_ratio(new_profit, revenue)

c1, c2, c3 = st.columns(3)

c1.metric(
    "预计节省金额",
    money(saving)
)

c2.metric(
    "优化后销售净毛利",
    money(new_profit),
    delta=money(saving)
)

c3.metric(
    "优化后毛利率",
    percent(new_margin),
    delta=(
        f"{saving / revenue * 100:.2f} 个百分点"
        if revenue != 0 else None
    )
)

st.caption(
    "此模拟仅调整所选费用，"
    "未考虑销量变化、广告带来的增量销售或费用联动。"
)


# =========================
# 13. 数据质量检查
# =========================

st.header("七、原始数据核对")

checks = []

for original, calculated in [
    ("收入合计", "计算收入合计"),
    ("费用合计", "计算费用合计"),
    ("销售净毛利", "计算销售净毛利")
]:
    if original in df.columns:
        diff = (
            df[original] - df[calculated]
        ).abs()

        checks.append({
            "核对字段": original,
            "差异行数": int((diff > 0.01).sum()),
            "差异绝对值合计": float(diff.sum())
        })

checks_df = pd.DataFrame(checks)

if not checks_df.empty:
    st.dataframe(
        checks_df,
        use_container_width=True,
        hide_index=True
    )

if (df["退款收入"] > 0).any():
    st.warning(
        "发现正数退款收入，请确认原表是否以正数记录退款。"
    )


# =========================
# 14. 回款分析
# =========================

st.header("八、平台回款分析")

c1, c2 = st.columns(2)

if "平台回款" in df.columns:
    c1.metric(
        "平台回款",
        money(df["平台回款"].sum())
    )

if "实际回款-提成计算" in df.columns:
    c2.metric(
        "实际回款-提成计算",
        money(df["实际回款-提成计算"].sum())
    )


# =========================
# 15. 导出 Excel
# =========================

st.header("九、导出分析结果")

output = io.BytesIO()

with pd.ExcelWriter(
    output,
    engine="openpyxl"
) as writer:

    df.to_excel(
        writer,
        index=False,
        sheet_name="筛选明细"
    )

    expense_data.to_excel(
        writer,
        index=False,
        sheet_name="费用结构"
    )

    monthly.to_excel(
        writer,
        index=False,
        sheet_name="月度趋势"
    )

    ranking.to_excel(
        writer,
        index=False,
        sheet_name="运营绩效"
    )

    checks_df.to_excel(
        writer,
        index=False,
        sheet_name="数据核对"
    )

st.download_button(
    label="下载经营分析 Excel",
    data=output.getvalue(),
    file_name="经营利润与成本分析.xlsx",
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    )
)

st.caption("经营利润与成本费用分析系统")
