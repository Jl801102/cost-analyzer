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
    """
    调用AI估算单个成本项，返回包含数量、单位、单价范围、金额范围、置信度等。
    输出格式：
    {
        "quantity": 数量,
        "unit": "单位",
        "rate_min": 最小单价,
        "rate_max": 最大单价,
        "rate_best": 最佳估计单价,
        "amount_min": 最小金额,
        "amount_max": 最大金额,
        "amount_best": 最佳估计金额,
        "confidence": "高/中/低",
        "source": "依据说明",
        "factors": ["考虑了品牌溢价", "近期市场波动", ...]
    }
    """
    prompt = f"""
    你是一个资深的采购成本分析师。请估算以下物料的单个成本项，考虑所有可能的影响因素。
    物料：{material_name}
    规格/描述：{specs}
    成本项：{cost_item}

    分析时请考虑：
    - 品牌溢价（如知名品牌通常贵20-50%）
    - 工艺复杂度（如精密加工会增加人工和制造费用）
    - 质量标准（如军工级比商业级贵几倍）
    - 市场波动（如近期原材料涨价、汇率变化）
    - 不可抗力风险（如供应链中断导致的潜在加价）
    - 行业利润率、税费差异（不同行业、不同物料利润率和税率不同）

    {INDUSTRY_CONTEXT}

    请以JSON格式返回以下字段（所有字段都必须有值，不适用填null）：
    - quantity: 数量（例如原材料kg、人工小时、PCB面积㎡）
    - unit: 单位（如“kg”、“小时”、“㎡”、“个”）
    - rate_min: 最低可能的单价（元/单位）
    - rate_max: 最高可能的单价（元/单位）
    - rate_best: 最可能的单价（元/单位）
    - amount_min: 最低金额（元），等于 quantity * rate_min
    - amount_max: 最高金额（元），等于 quantity * rate_max
    - amount_best: 最可能金额（元），等于 quantity * rate_best
    - confidence: 估算的置信度（"高"、"中"、"低"），基于信息充分度
    - source: 详细说明估算依据，包括参考了哪些因素
    - factors: 一个数组，列出你考虑的关键因素（如 ["品牌溢价", "近期铜价上涨"]）

    请确保输出是一个有效的JSON，不要有其他文字。
    """
    try:
        result_text = call_qwen(prompt)
        if result_text:
            # 清理可能的 markdown 代码块
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0]
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0]
            result = json.loads(result_text.strip())
            # 确保所有字段存在
            required_fields = ['quantity', 'unit', 'rate_min', 'rate_max', 'rate_best',
                               'amount_min', 'amount_max', 'amount_best', 'confidence', 'source', 'factors']
            for field in required_fields:
                if field not in result:
                    result[field] = None
            return result
    except Exception as e:
        print(f"AI估算失败: {e}")
    # 默认返回
    return {
        "quantity": None,
        "unit": None,
        "rate_min": None,
        "rate_max": None,
        "rate_best": None,
        "amount_min": 0,
        "amount_max": 0,
        "amount_best": 0,
        "confidence": "低",
        "source": "估算失败",
        "factors": []
    }

def process_quote(quote_file, internal_file=None):
    """处理报价单，返回结果列表（增强版：优先使用内部数据）"""
    df_quote = pd.read_excel(quote_file)
    results = []

    # ---------- 新增：如果提供了内部数据文件，先加载所有内部数据 ----------
    internal_cache = {}  # 格式：{物料名称: {成本项: 明细}}
    if internal_file and os.path.exists(internal_file):
        try:
            df_internal = pd.read_excel(internal_file)
            # 假设内部数据表有列：物料名称、成本项、数量、单位、单价/费率、金额、来源备注
            for _, row in df_internal.iterrows():
                material = row['物料名称']
                if material not in internal_cache:
                    internal_cache[material] = {}
                internal_cache[material][row['成本项']] = {
                    '数量': row.get('数量'),
                    '单位': row.get('单位'),
                    '单价/费率': row.get('单价/费率'),
                    '金额': row.get('金额', 0),
                    '来源': f"内部数据：{internal_file}（{row.get('来源备注', '')}）"
                }
            print(f"已加载内部数据，共 {len(internal_cache)} 个物料")
        except Exception as e:
            print(f"读取内部数据失败：{e}")
    # ----------------------------------------------------------------

    for _, row in df_quote.iterrows():
        material = row['物料名称']
        specs = row.get('规格', '')
        quoted_price = row['单价']
        price_unit = row.get('单位报价', '元/个')

        # 识别成本项
        cost_items = identify_cost_structure(material, specs)

        breakdown = {}
        total_min = 0
        total_max = 0
        total_best = 0
        all_factors = []

        for item in cost_items:
            # ---------- 新增：优先使用内部数据 ----------
            if material in internal_cache and item in internal_cache[material]:
                data = internal_cache[material][item]
                # 使用内部数据（没有范围，所以最小/最大/最佳都设为同一值）
                amount = data['金额']
                breakdown[item] = {
                    '数量': data['数量'],
                    '单位': data['单位'],
                    '单价/费率 (最佳)': data['单价/费率'],
                    '单价范围': None,
                    '金额 (最佳)': amount,
                    '金额范围': f"{amount} - {amount}",
                    '置信度': '高（内部数据）',
                    '数据来源': data['来源'],
                    '影响因素': '内部历史数据'
                }
                total_min += amount
                total_max += amount
                total_best += amount
                # 内部数据不产生影响因素
                continue  # 跳过AI调用
            # -----------------------------------------

            # 无内部数据，调用AI估算
            est = estimate_cost_item(material, item, specs)

            # 累加区间（如果AI返回了范围）
            total_min += est.get('amount_min', 0) or 0
            total_max += est.get('amount_max', 0) or 0
            total_best += est.get('amount_best', 0) or 0

            # 收集因素
            if est.get('factors'):
                all_factors.extend(est['factors'])

            breakdown[item] = {
                '数量': est.get('quantity'),
                '单位': est.get('unit'),
                '单价/费率 (最佳)': est.get('rate_best'),
                '单价范围': f"{est.get('rate_min')} - {est.get('rate_max')}" if est.get('rate_min') and est.get('rate_max') else None,
                '金额 (最佳)': est.get('amount_best'),
                '金额范围': f"{est.get('amount_min')} - {est.get('amount_max')}" if est.get('amount_min') and est.get('amount_max') else None,
                '置信度': est.get('confidence'),
                '数据来源': est.get('source'),
                '影响因素': ', '.join(est.get('factors', [])) if est.get('factors') else None
            }

        # 总成本范围
        total_range = f"{round(total_min,2)} - {round(total_max,2)}"

        results.append({
            '物料名称': material,
            '规格': specs,
            '报价单价': quoted_price,
            '报价单位': price_unit,
            '估算总成本 (最佳)': round(total_best, 2),
            '估算总成本范围': total_range,
            '成本拆解': breakdown,
            '所有影响因素': list(set(all_factors)) if all_factors else []
        })
    return results
