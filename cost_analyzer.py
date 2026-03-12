# cost_analyzer.py
import os
import json
import pandas as pd
import dashscope
from dashscope import Generation

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 行业背景提示
INDUSTRY_CONTEXT = """
请参考2026年中国电子/机械制造行业平均水平：
- PCB单价：500-1500元/㎡（按层数、工艺）
- SMT贴片加工费：0.01-0.03元/点
- 芯片封装测试费用：约占芯片成本的20-30%
- 电子组装人工费率：40-60元/小时
- 原材料价格：钢材5-8元/kg，塑料粒子8-15元/kg
- 增值税率：13%
- 制造业平均利润率：10-20%
"""

def call_qwen(prompt):
    """调用通义千问 qwen-flash 模型，每次调用时从环境变量读取API密钥"""
    try:
        # 每次调用前从环境变量获取API密钥并设置
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            print("错误：未设置 DASHSCOPE_API_KEY 环境变量")
            return None
        dashscope.api_key = api_key

        response = Generation.call(
            model='qwen-flash',  # 免费模型
            prompt=prompt,
            result_format='message'
        )
        return response.output.choices[0].message.content
    except Exception as e:
        print(f"API调用失败: {e}")
        return None

def identify_cost_structure(material_name, specs=""):
    """AI识别成本构成项"""
    prompt = f"""
    你是一个专业的成本工程师。请分析以下物料的成本构成。
    物料名称：{material_name}
    规格/描述：{specs}

    请输出该物料最常见的成本构成项，以JSON数组形式返回。每个成本项请用中文简洁名称。
    示例：
    - 对于PCB：["基板材料", "铜箔", "钻孔费", "阻焊", "字符", "测试费", "税费", "利润"]
    - 对于芯片：["晶圆成本", "封装成本", "测试成本", "税费", "利润"]
    - 对于注塑件：["塑料粒子", "模具分摊", "注塑加工费", "后处理", "税费", "利润"]

    请确保返回的数组元素个数在4到8个之间。只返回JSON数组，不要有其他文字。
    """
    result_text = call_qwen(prompt)
    if result_text:
        try:
            # 清理可能的 markdown 代码块
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0]
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0]
            return json.loads(result_text.strip())
        except:
            pass
    # 默认返回
    return ["原材料", "人工", "制造费用", "税费", "利润"]

def estimate_cost_item(material_name, cost_item, specs=""):
    """AI估算单个成本项的数量、单价、金额"""
    prompt = f"""
    请估算以下物料的单个成本项，给出详细的数量、单价/费率，并计算金额。
    物料：{material_name}
    规格：{specs}
    成本项：{cost_item}

    {INDUSTRY_CONTEXT}

    请以JSON格式返回如下字段：
    - quantity: 数量（例如原材料kg、人工小时、PCB面积㎡，若不适用填null）
    - unit: 单位（如“kg”、“小时”、“㎡”、“个”，若不适用填null）
    - rate: 单价或费率（元/单位，若不适用填null）
    - amount: 金额（元）
    - source: 简要说明估算依据

    示例1（PCB基板）：
    {{"quantity": 0.01, "unit": "㎡", "rate": 600, "amount": 6.0, "source": "FR-4基板市场价约600元/㎡"}}

    示例2（SMT贴片）：
    {{"quantity": 100, "unit": "点", "rate": 0.02, "amount": 2.0, "source": "贴片加工费约0.02元/点"}}

    示例3（税费）：
    {{"quantity": null, "unit": null, "rate": 0.13, "amount": null, "source": "增值税率13%"}}

    请只返回JSON，不要有其他文字。
    """
    result_text = call_qwen(prompt)
    if result_text:
        try:
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0]
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0]
            return json.loads(result_text.strip())
        except:
            pass
    # 默认返回
    return {"quantity": None, "unit": None, "rate": None, "amount": 0, "source": "估算失败"}

def process_quote(quote_file, internal_file=None):
    """处理报价单，返回结果列表（增强版）"""
    df_quote = pd.read_excel(quote_file)
    results = []
    for _, row in df_quote.iterrows():
        material = row['物料名称']
        specs = row.get('规格', '')
        quoted_price = row['单价']
        price_unit = row.get('单位报价', '元/个')

        # 识别成本项
        cost_items = identify_cost_structure(material, specs)

        breakdown = {}
        # 先收集直接成本（原材料、人工、制造费用等，不含税费和利润）
        direct_cost = 0
        # 用于暂存AI估算结果，方便后续处理
        ai_results = {}

        for item in cost_items:
            if item in ["税费", "利润"]:
                continue  # 稍后单独处理
            est = estimate_cost_item(material, item, specs)
            amount = est.get('amount', 0) or 0
            direct_cost += amount
            breakdown[item] = {
                '数量': est.get('quantity'),
                '单位': est.get('unit'),
                '单价/费率': est.get('rate'),
                '金额': amount,
                '来源': est.get('source', 'AI估算') + " (qwen)"
            }
            ai_results[item] = est

        # 计算税费（基于直接成本）
        tax_rate = 0.13  # 默认13%，也可以让AI返回，但为简单直接用默认
        tax_amount = direct_cost * tax_rate
        breakdown['税费'] = {
            '数量': None,
            '单位': None,
            '单价/费率': tax_rate,
            '金额': tax_amount,
            '来源': f"增值税率{int(tax_rate*100)}%，按直接成本计算"
        }
        # 总成本（不含利润）
        total_without_profit = direct_cost + tax_amount

        # 计算利润（基于总成本）
        profit_rate = 0.15  # 行业平均利润率15%
        profit_amount = total_without_profit * profit_rate
        breakdown['利润'] = {
            '数量': None,
            '单位': None,
            '单价/费率': profit_rate,
            '金额': profit_amount,
            '来源': f"行业平均利润率{int(profit_rate*100)}%"
        }

        # 最终估算总成本
        total_est = total_without_profit + profit_amount

        results.append({
            '物料名称': material,
            '规格': specs,
            '报价单价': quoted_price,
            '报价单位': price_unit,
            '估算总成本': round(total_est, 2),
            '成本拆解': breakdown
        })
    return results