import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# 1. 页面基本配置
st.set_page_config(
    page_title="电商成本与利润分析看板", page_icon="📊", layout="wide"
)

st.title("📊 电商多维成本与利润分析看板")
st.markdown("精准剖析各项支出占比，优化成本结构，实时监控利润率与回款表现。")


# 2. 数据加载与缓存
@st.cache_data
def load_data(file):
  if file.name.endswith(".csv"):
    return pd.read_csv(file)
  else:
    return pd.read_excel(file)


# 文件上传或加载示例数据
uploaded_file = st.file_uploader(
    "📂 请上传你的数据文件 (支持 Excel 或 CSV)", type=["xlsx", "csv"]
)

if uploaded_file is not None:
  df = load_data(uploaded_file)
else:
  st.info("💡 当前未上传文件，已自动生成模拟数据供你预览和测试功能。")
  # 生成符合你表头结构的模拟数据用于演示
  np.random.seed(42)
  n = 120
  months = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
  depts = ["运营一部", "运营二部", "跨境事业部"]
  operators = ["Alice", "Bob", "Charlie", "David", "Eva"]
  sites = ["The Home Depot", "Best Buy", "Waykar", "Serleep"]

  df = pd.DataFrame({
      "月份": np.random.choice(months, n),
      "部门": np.random.choice(depts, n),
      "运营人员": np.random.choice(operators, n),
      "站点": np.random.choice(sites, n),
      "销售收入": np.random.uniform(10000, 80000, n).round(2),
      "退款收入": np.random.uniform(200, 3000, n).round(2),
  })
  df["收入合计"] = df["销售收入"] - df["退款收入"]
  df["成本净额"] = df["收入合计"] * np.random.uniform(0.3, 0.45, n)

  # 各项费用模拟
  expense_cols = [
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
  ]
  for col in expense_cols:
    df[col] = df["收入合计"] * np.random.uniform(0.005, 0.08, n)

  df["费用合计"] = df[expense_cols].sum(axis=1)
  df["销售净毛利"] = df["收入合计"] - df["成本净额"] - df["费用合计"]
  df["毛利率"] = (df["销售净毛利"] / df["收入合计"]).round(4)
  df["成本率"] = (df["成本净额"] / df["收入合计"]).round(4)
  df["费用占比"] = (df["费用合计"] / df["收入合计"]).round(4)
  df["平台回款"] = df["收入合计"] - df["费用合计"]
  df["实际回款-提成计算"] = df["平台回款"] * 0.95
  df["成本回报率"] = (
      df["销售净毛利"] / (df["成本净额"] + df["费用合计"])
  ).round(4)

# 3. 侧边栏多维度筛选器
st.sidebar.header("🔍 多维数据筛选")

selected_months = st.sidebar.multiselect(
    "选择月份",
    options=sorted(df["月份"].dropna().unique()),
    default=df["月份"].dropna().unique(),
)
selected_depts = st.sidebar.multiselect(
    "选择部门",
    options=sorted(df["部门"].dropna().unique()),
    default=df["部门"].dropna().unique(),
)
selected_operators = st.sidebar.multiselect(
    "选择运营人员",
    options=sorted(df["运营人员"].dropna().unique()),
    default=df["运营人员"].dropna().unique(),
)
selected_sites = st.sidebar.multiselect(
    "选择站点",
    options=sorted(df["站点"].dropna().unique()),
    default=df["站点"].dropna().unique(),
)

# 过滤数据
filtered_df = df[
    df["月份"].isin(selected_months)
    & df["部门"].isin(selected_depts)
    & df["运营人员"].isin(selected_operators)
    & df["站点"].isin(selected_sites)
]

if filtered_df.empty:
  st.warning("⚠️ 当前筛选条件下没有数据，请调整侧边栏筛选选项。")
else:
  # 4. 核心 KPI 看板指标
  total_revenue = filtered_df["收入合计"].sum()
  total_cost = filtered_df["成本净额"].sum()
  total_expense = filtered_df["费用合计"].sum()
  total_net_profit = filtered_df["销售净毛利"].sum()
  avg_gross_margin = (
      total_net_profit / total_revenue if total_revenue > 0 else 0
  )
  avg_cost_ratio = total_cost / total_revenue if total_revenue > 0 else 0
  avg_expense_ratio = total_expense / total_revenue if total_revenue > 0 else 0

  kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
  kpi1.metric("收入合计", f"${total_revenue:,.2f}")
  kpi2.metric("销售净毛利", f"${total_net_profit:,.2f}")
  kpi3.metric("综合毛利率", f"{avg_gross_margin:.2%}")
  kpi4.metric("综合成本率", f"{avg_cost_ratio:.2%}")
  kpi5.metric("综合费用率", f"{avg_expense_ratio:.2%}")
  kpi6.metric(
      "成本回报率",
      f"{(total_net_profit / (total_cost + total_expense) if (total_cost + total_expense) > 0 else 0):.2%}",
  )

  st.divider()

  # 5. 各项支出占比核心分析模块
  st.subheader("💸 各项支出费用结构与占比分析")

  expense_cols = [
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
  ]

  # 聚合各项费用
  expense_sums = filtered_df[expense_cols].sum().reset_index()
  expense_sums.columns = ["费用类型", "金额"]
  expense_sums = expense_sums.sort_values(by="金额", ascending=False)
  expense_sums["占总收入比例"] = (
      expense_sums["金额"] / total_revenue if total_revenue > 0 else 0
  )
  expense_sums["占总费用比例"] = (
      expense_sums["金额"] / total_expense if total_expense > 0 else 0
  )

  col_pie, col_bar = st.columns([1.1, 1])

  with col_pie:
    fig_pie = px.pie(
        expense_sums,
        names="费用类型",
        values="金额",
        title="各项费用支出构成占比 (环形图)",
        hole=0.4,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

  with col_bar:
    fig_bar = px.bar(
        expense_sums,
        x="金额",
        y="费用类型",
        orientation="h",
        title="各项费用支出绝对金额排序",
        text_auto=".2s",
        color="金额",
        color_continuous_scale="Teal",
    )
    fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_bar, use_container_width=True)

  # 费用明细数据表格
  with st.expander("📌 查看各项费用占收入与总费用明细表"):
    st.dataframe(expense_sums, use_container_width=True)

  st.divider()

  # 6. 多维度趋势与对比分析
  st.subheader("📈 多维趋势与人员/站点表现")

  tab1, tab2, tab3 = st.tabs(["📅 月度趋势看板", "👤 运营人员绩效", "🏢 站点表现对比"])

  with tab1:
    trend_df = (
        filtered_df.groupby("月份")[
            ["收入合计", "销售净毛利", "费用合计"]
        ]
        .sum()
        .reset_index()
    )
    trend_df["毛利率"] = trend_df["销售净毛利"] / trend_df["收入合计"]
    fig_trend = px.line(
        trend_df,
        x="月份",
        y=["收入合计", "销售净毛利", "费用合计"],
        title="月度核心财务指标走势",
        markers=True,
    )
    st.plotly_chart(fig_trend, use_container_width=True)

  with tab2:
    op_df = (
        filtered_df.groupby("运营人员")[
            ["收入合计", "销售净毛利", "费用合计"]
        ]
        .sum()
        .reset_index()
    )
    op_df["毛利率"] = (op_df["销售净毛利"] / op_df["收入合计"]).round(4)
    fig_op = px.bar(
        op_df,
        x="运营人员",
        y=["收入合计", "销售净毛利"],
        barmode="group",
        title="各运营人员收入与净毛利对比",
    )
    st.plotly_chart(fig_op, use_container_width=True)

  with tab3:
    site_df = (
        filtered_df.groupby("站点")[
            ["销售净毛利", "收入合计", "成本净额", "费用合计"]
        ]
        .sum()
        .reset_index()
    )
    site_df["毛利率"] = (site_df["销售净毛利"] / site_df["收入合计"]).round(4)
    fig_site = px.bar(
        site_df,
        x="站点",
        y="毛利率",
        title="各站点平均毛利率对比",
        text_auto=".1%",
        color="毛利率",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig_site, use_container_width=True)

  st.divider()

  # 7. 详细明细数据及导出
  st.subheader("📋 详细过滤后明细数据表")
  st.dataframe(filtered_df, use_container_width=True)

  csv_data = filtered_df.to_csv(index=False).encode("utf-8-sig")
  st.download_button(
      label="📥 下载当前筛选数据 (CSV)",
      data=csv_data,
      file_name="ecommerce_cost_profit_report.csv",
      mime="text/csv",
  )
