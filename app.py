# app.py
import streamlit as st
import pandas as pd
import os
import tempfile
from cost_analyzer import process_quote

st.set_page_config(page_title="智能物料成本拆解系统", layout="wide")
st.title("📊 智能物料成本拆解系统")
st.markdown("上传供应商报价单，AI自动拆解每个物料的成本构成，并生成分析报告。")

# 从环境变量读取API密钥（Streamlit Secrets 中设置）
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    st.error("系统错误：未找到API密钥配置，请联系管理员")
    st.stop()
# 设置环境变量供cost_analyzer使用
os.environ["DASHSCOPE_API_KEY"] = api_key

# 文件上传
quote_file = st.file_uploader("📄 上传供应商报价单 (Excel格式)", type=['xlsx', 'xls'])

if quote_file is not None:
    st.success(f"已上传：{quote_file.name}")
    if st.button("🚀 开始分析", type="primary"):
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(quote_file.getvalue())
            tmp_path = tmp.name

        try:
            with st.spinner("正在分析，请稍候...（调用AI可能需要几秒到十几秒）"):
                results = process_quote(tmp_path)
            st.success(f"✅ 分析完成！共处理 {len(results)} 个物料")

            # 显示每个物料的分析结果
            for res in results:
                with st.expander(f"📦 {res['物料名称']}  -  报价: {res['报价单价']} {res['报价单位']}"):
                    # 显示总成本范围和最佳估算
                    st.write(f"**估算总成本范围**: {res['估算总成本范围']} 元")
                    st.write(f"**最佳估算**: {res['估算总成本 (最佳)']} 元")
                    if res.get('所有影响因素'):
                        st.write("**考虑的影响因素**: " + ", ".join(res['所有影响因素']))

                    # 构建成本拆解表格
                    rows = []
                    for item_name, item_data in res['成本拆解'].items():
                        rows.append({
                            '成本项': item_name,
                            '数量': item_data.get('数量', ''),
                            '单位': item_data.get('单位', ''),
                            '最佳单价': item_data.get('单价/费率 (最佳)', ''),
                            '单价范围': item_data.get('单价范围', ''),
                            '最佳金额': item_data.get('金额 (最佳)', ''),
                            '金额范围': item_data.get('金额范围', ''),
                            '置信度': item_data.get('置信度', ''),
                            '影响因素': item_data.get('影响因素', ''),
                            '数据来源': item_data.get('数据来源', '')
                        })
                    df_cost = pd.DataFrame(rows)
                    st.dataframe(df_cost)

                    # 提供Excel下载
                    output_file = f"{res['物料名称']}_成本拆解.xlsx"
                    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                        # 基本信息表
                        basic = pd.DataFrame([{
                            '物料名称': res['物料名称'],
                            '规格': res['规格'],
                            '报价单价': res['报价单价'],
                            '报价单位': res['报价单位'],
                            '估算总成本': res['估算总成本 (最佳)'],
                            '估算总成本范围': res['估算总成本范围']
                        }])
                        basic.to_excel(writer, sheet_name='基本信息', index=False)
                        # 成本拆解表
                        df_cost.to_excel(writer, sheet_name='成本拆解', index=False)

                    with open(output_file, 'rb') as f:
                        st.download_button(
                            label=f"📥 下载 {res['物料名称']} 分析报告",
                            data=f,
                            file_name=output_file,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    os.unlink(output_file)  # 删除临时生成的Excel文件

        except Exception as e:
            st.error(f"分析出错：{str(e)}")
        finally:
            # 清理上传的临时文件
            os.unlink(tmp_path)
