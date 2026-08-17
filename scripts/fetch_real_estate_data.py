# -*- coding: utf-8 -*-
"""
房地产行业数据自动获取与更新脚本

从国家统计局官网抓取最新《全国房地产市场基本情况》月度报告，自动计算单月值（累计差分）
与环比增速，并直接更新 sales.js 数据文件。

使用方法:
    py scripts/fetch_real_estate_data.py

依赖:
    pip install requests beautifulsoup4 lxml

数据来源:
    国家统计局 - 全国房地产市场基本情况（月度累计数据）
    https://www.stats.gov.cn/sj/zxfb/

工作流程:
    1. 在国家统计局发布页查找最新月度报告链接
    2. 抓取报告页面，从正文与表1提取累计指标
    3. 与历史累计数据对比，差分计算本期单月值
    4. 计算环比增速（本期单月 vs 上期单月）
    5. 自动追加到 js/data/sales.js 对应数组
    6. 保存累计数据到 scripts/cumulative_history.json 供下次差分使用

输出文件:
    scripts/fetched_data.json            - 原始抓取数据
    scripts/cumulative_history.json       - 累计数据历史（用于差分计算）
    scripts/sales_data_snippet.txt        - 累计值代码片段（供参考）
    scripts/debug_report_text.txt         - 抓取页面的原始文本（用于调试正则）
"""

import json
import re
import os
import sys
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("缺少依赖库，请先安装：")
    print("  pip install requests beautifulsoup4 lxml")
    sys.exit(1)


# ===== 配置 =====
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}
TIMEOUT = 30
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SALES_JS_PATH = os.path.join(PROJECT_DIR, 'js', 'data', 'sales.js')
INDEX_HTML_PATH = os.path.join(PROJECT_DIR, 'index.html')
HISTORY_PATH = os.path.join(SCRIPT_DIR, 'cumulative_history.json')
SNIPPET_PATH = os.path.join(SCRIPT_DIR, 'sales_data_snippet.txt')
DEBUG_PATH = os.path.join(SCRIPT_DIR, 'debug_report_text.txt')
FETCHED_JSON_PATH = os.path.join(SCRIPT_DIR, 'fetched_data.json')

STATS_BUREAU_LIST_URL = "https://www.stats.gov.cn/sj/zxfb/"
STATS_KEYWORD = "全国房地产市场基本情况"
PRICE70_KEYWORD = "70个大中城市商品住宅销售价格变动情况"

# 国家统计局 70 城房价按一线/二线/三线分类
PRICE70_TIER1 = ['北京', '上海', '广州', '深圳']
PRICE70_TIER2 = [
    '天津', '石家庄', '太原', '呼和浩特', '沈阳', '大连', '长春', '哈尔滨',
    '南京', '杭州', '宁波', '合肥', '福州', '厦门', '南昌', '济南', '青岛',
    '郑州', '武汉', '长沙', '南宁', '海口', '重庆', '成都', '贵阳', '昆明',
    '西安', '兰州', '西宁', '银川', '乌鲁木齐'
]


# ===== 字段映射表 =====
# diff 类型：单月值 = 本期累计 - 上期累计
# direct 类型：直接用累计/期末值（如施工总面积、待售面积）
# 每项: (stats_data 中的字段名, sales.js 区块标记, sales.js 数组键, 计算类型, mom 区块标记, mom 数组键)
FIELD_MAPPINGS = [
    # 投资类（差分）
    ('investment_total',          'investment:', 'total',        'diff', 'investment:', 'total'),
    ('investment_residential',   'investment:', 'residential', 'diff', 'investment:', 'residential'),
    ('investment_office',        'investment:', 'office',       'diff', 'investment:', 'office'),
    ('investment_commercial',    'investment:', 'commercial',   'diff', 'investment:', 'commercial'),
    # 销售类（差分）
    ('sales_area',               'sales:', 'area',              'diff', 'sales:', 'area'),
    ('sales_amount',             'sales:', 'amount',            'diff', 'sales:', 'amount'),
    ('sales_residential_area',   'sales:', 'residentialArea',   'diff', 'sales:', 'residentialArea'),
    ('sales_residential_amount', 'sales:', 'residentialAmount', 'diff', 'sales:', 'residentialAmount'),
    # 待售类（直接用期末值）
    ('inventory_total',          'inventory:', 'total',        'direct', 'inventory:', 'total'),
    ('inventory_residential',    'inventory:', 'residential',  'direct', 'inventory:', 'residential'),
    ('inventory_office',         'inventory:', 'office',       'direct', 'inventory:', 'office'),
    ('inventory_commercial',     'inventory:', 'commercial',   'direct', 'inventory:', 'commercial'),
    # 施工类（施工面积用累计，新开工/竣工差分）
    ('construction',             'construction:', 'construction', 'direct', 'construction:', 'construction'),
    ('new_start',                'construction:', 'newStart',     'diff',  'construction:', 'newStart'),
    ('complete',                 'construction:', 'complete',     'diff',  'construction:', 'complete'),
    # 资金类（差分）
    ('funding_total',            'funding:', 'total',    'diff', 'funding:', 'total'),
    ('funding_domestic',         'funding:', 'domestic', 'diff', 'funding:', 'domestic'),
    ('funding_foreign',          'funding:', 'foreign',  'diff', 'funding:', 'foreign'),
    ('funding_self',             'funding:', 'self',     'diff', 'funding:', 'self'),
    ('funding_deposit',          'funding:', 'deposit',  'diff', 'funding:', 'deposit'),
    ('funding_mortgage',         'funding:', 'mortgage', 'diff', 'funding:', 'mortgage'),
]


# ===== 基础工具 =====
def fetch_page(url):
    """获取网页内容，SSL 失败时二次重试"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=True)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
        except Exception as e:
            print(f"  [警告] 获取页面失败(忽略证书): {url}\n  错误: {e}")
            return None
    except Exception as e:
        print(f"  [警告] 获取页面失败: {url}\n  错误: {e}")
        return None


def to_float(v):
    """安全转换为 float，失败返回 None"""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt_num(v):
    """格式化为 sales.js 中数字字面量（保留1位小数或整数）"""
    if v is None:
        return 'null'
    if isinstance(v, float):
        # 整数则去掉小数点
        if v == int(v):
            return str(int(v))
        return str(round(v, 1))
    return str(v)


def fmt_mom(v):
    """格式化环比增速（保留1位小数，可能为 null）"""
    if v is None:
        return 'null'
    return str(round(v, 1))


# ===== 历史累计数据管理 =====
def load_history():
    """加载历史累计数据"""
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"  [警告] 读取历史文件失败: {e}")
    return {}


def save_history(history):
    """保存历史累计数据"""
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ===== 报告查找与解析 =====
def find_latest_real_estate_report():
    """在国家统计局发布页查找最新月度报告链接，返回候选列表"""
    print("\n[1/6] 搜索国家统计局最新房地产月度报告...")
    html = fetch_page(STATS_BUREAU_LIST_URL)
    if not html:
        print("  [错误] 无法访问国家统计局数据发布页")
        return []

    soup = BeautifulSoup(html, 'lxml')
    links = soup.find_all('a', href=True)

    candidates = []
    seen_urls = set()
    for link in links:
        text = link.get_text(strip=True)
        if STATS_KEYWORD in text:
            href = link.get('href', '')
            if href.startswith('/'):
                href = 'https://www.stats.gov.cn' + href
            elif not href.startswith('http'):
                href = 'https://www.stats.gov.cn/sj/zxfb/' + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            candidates.append({'title': text, 'url': href})

    if not candidates:
        print("  [警告] 未找到房地产相关报告，可能数据尚未发布")
        return []

    print(f"  在第一页找到 {len(candidates)} 条房地产相关报告:")
    for i, c in enumerate(candidates[:5]):
        print(f"    [{i+1}] {c['title']}")
        print(f"        {c['url']}")
    return candidates


def find_report_by_month(target_month, candidates=None, max_pages=3):
    """查找指定月份的报告（如 1-6月份），支持跨页搜索"""
    # 月份关键字：兼容"—"和"-"
    keywords = [
        f"1—{target_month}月份",
        f"1-{target_month}月份",
    ]

    # 先在已有候选中查找
    if candidates:
        for c in candidates:
            for kw in keywords:
                if kw in c['title']:
                    return c

    # 跨页搜索（index_1.html, index_2.html...）
    for page_idx in range(1, max_pages + 1):
        page_url = f"https://www.stats.gov.cn/sj/zxfb/index_{page_idx-1}.html" if page_idx > 1 else STATS_BUREAU_LIST_URL
        if page_idx == 1 and candidates is not None:
            continue  # 第一页已经搜索过
        print(f"  搜索第 {page_idx} 页: {page_url}")
        html = fetch_page(page_url)
        if not html:
            continue
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            for kw in keywords:
                if kw in text and STATS_KEYWORD in text:
                    href = link.get('href', '')
                    if href.startswith('/'):
                        href = 'https://www.stats.gov.cn' + href
                    elif not href.startswith('http'):
                        href = 'https://www.stats.gov.cn/sj/zxfb/' + href
                    return {'title': text, 'url': href}
    return None


def parse_stats_bureau_report(url):
    """解析国家统计局报告页面，从正文与表1提取累计指标"""
    print("\n[2/6] 解析报告内容...")
    html = fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml')

    # 正文容器备选
    content = (
        soup.find('div', class_='TRS_Editor')
        or soup.find('div', class_='content')
        or soup.find('div', class_='pages_content')
        or soup.find('article')
        or soup.find('body')
    )
    if not content:
        print("  [警告] 未找到正文容器")
        return None

    text = content.get_text('\n', strip=True)
    print(f"  正文长度: {len(text)} 字符")

    # 国家统计局页面将数字、汉字、标点分割到不同 <span>，get_text 后插入换行
    # 此处去除所有空白后做正则匹配
    text_compact = re.sub(r'\s+', '', text)
    print(f"  压缩后长度: {len(text_compact)} 字符")
    print(f"  压缩片段（前300字符）: {text_compact[:300]}")

    data = {}

    # === 正文部分正则（核心字段） ===
    text_patterns = {
        'investment_total':            r'房地产开发投资(\d+(?:\.\d+)?)亿元',
        'investment_yoy':              r'房地产开发投资\d+(?:\.\d+)?亿元.*?同比(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'investment_residential':      r'住宅投资(\d+(?:\.\d+)?)亿元',
        'investment_residential_yoy':  r'住宅投资\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'sales_area':                  r'新建商品房销售面积(\d+(?:\.\d+)?)万平方米',
        'sales_area_yoy':              r'新建商品房销售面积\d+(?:\.\d+)?万平方米.*?同比(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'sales_residential_area_yoy':  r'其中住宅销售面积(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'sales_amount':                r'新建新建商品房销售额(\d+(?:\.\d+)?)亿元',
        'sales_amount_yoy':            r'新建新建商品房销售额\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'sales_residential_amount_yoy': r'其中住宅销售额(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'inventory_total':             r'商品房待售面积(\d+(?:\.\d+)?)万平方米',
        'inventory_yoy':               r'商品房待售面积\d+(?:\.\d+)?万平方米.*?同比(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'funding_total':               r'房地产开发企业到位资金(\d+(?:\.\d+)?)亿元',
        'funding_yoy':                 r'房地产开发企业到位资金\d+(?:\.\d+)?亿元.*?同比(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'funding_domestic':            r'国内贷款(\d+(?:\.\d+)?)亿元',
        'funding_domestic_yoy':        r'国内贷款\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'funding_foreign':             r'利用外资(\d+(?:\.\d+)?)亿元',
        'funding_foreign_yoy':         r'利用外资\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'funding_self':                r'自筹资金(\d+(?:\.\d+)?)亿元',
        'funding_self_yoy':            r'自筹资金\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'funding_deposit':             r'定金及预收款(\d+(?:\.\d+)?)亿元',
        'funding_deposit_yoy':         r'定金及预收款\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'funding_mortgage':            r'个人按揭贷款(\d+(?:\.\d+)?)亿元',
        'funding_mortgage_yoy':        r'个人按揭贷款\d+(?:\.\d+)?亿元.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'construction':                r'房屋施工面积(\d+(?:\.\d+)?)万平方米',
        'construction_yoy':            r'房屋施工面积\d+(?:\.\d+)?万平方米.*?同比(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'new_start':                   r'房屋新开工面积(\d+(?:\.\d+)?)万平方米',
        'new_start_yoy':               r'房屋新开工面积\d+(?:\.\d+)?万平方米.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
        'complete':                    r'房屋竣工面积(\d+(?:\.\d+)?)万平方米',
        'complete_yoy':                r'房屋竣工面积\d+(?:\.\d+)?万平方米.*?(?:下降|增长)(\-?\d+(?:\.\d+)?)%',
    }

    for key, pattern in text_patterns.items():
        match = re.search(pattern, text_compact)
        if match:
            val = match.group(1)
            # 同比按上下文判断正负
            if 'yoy' in key and not val.startswith('-'):
                ctx = text_compact[max(0, match.start()-15):match.end()+5]
                data[key] = '-' + val if '下降' in ctx else val
            else:
                data[key] = val
        else:
            print(f"  [正文未匹配] {key}")

    # === 表1分项数据（办公楼/商业营业用房等） ===
    # 表1区域：从"房地产开发投资（亿元）"开始，到下一个"表"标记结束
    parse_table1(text_compact, data)

    # === 提取累计月份 ===
    month_patterns = [
        r'(\d+)[—\-](\d+)月份',
        r'1[—\-](\d+)月份',
    ]
    for mp in month_patterns:
        m = re.search(mp, text_compact)
        if m:
            data['cumulative_month'] = m.group(2) if m.lastindex >= 2 else m.group(1)
            break

    # === 报告标题 ===
    title_tag = soup.find('title')
    if title_tag:
        data['report_title'] = title_tag.get_text(strip=True)

    # === 保存调试文本 ===
    with open(DEBUG_PATH, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"  原始文本已保存: {DEBUG_PATH}")

    print(f"\n  累计月份: 1-{data.get('cumulative_month', '?')}")
    print(f"  开发投资: {data.get('investment_total', '?')}亿元 ({data.get('investment_yoy', '?')}%)")
    print(f"  销售面积: {data.get('sales_area', '?')}万㎡ ({data.get('sales_area_yoy', '?')}%)")
    print(f"  销售额: {data.get('sales_amount', '?')}亿元 ({data.get('sales_amount_yoy', '?')}%)")
    print(f"  待售面积: {data.get('inventory_total', '?')}万㎡")

    return data


def parse_table1(text_compact, data):
    """从表1区域提取分项数据（办公楼、商业营业用房、住宅销售面积/金额、住宅待售面积等）"""
    print("\n  解析表1分项数据...")

    # 表1起点：第一个"房地产开发投资（亿元）"
    t1_start = text_compact.find('房地产开发投资（亿元）')
    if t1_start < 0:
        # 兼容全角/半角括号
        t1_start = text_compact.find('房地产开发投资(亿元)')
    if t1_start < 0:
        print("    [警告] 未找到表1起点")
        return

    # 表1终点：到"房地产开发企业本年到位资金"为止（包含该字段）
    t1_end = text_compact.find('房地产开发企业本年到位资金（亿元）', t1_start)
    if t1_end < 0:
        t1_end = text_compact.find('房地产开发企业本年到位资金(亿元)', t1_start)
    if t1_end < 0:
        t1_end = t1_start + 1500  # 限制范围

    # 包含到位资金后到表2之前
    next_table = text_compact.find('表', t1_end)
    if next_table > 0:
        t1_end_full = next_table
    else:
        t1_end_full = t1_end + 200

    region = text_compact[t1_start:t1_end_full]
    print(f"    表1区域长度: {len(region)} 字符")

    # 表1中各分项正则
    # 格式: "房地产开发投资（亿元）43009-19.2其中：住宅33172-19.1办公楼1580-21.9商业营业用房2809-24.8"
    table1_patterns = {
        # 投资分项
        'investment_office':       r'房地产开发投资（亿元）\d+(?:\.\d+)?-?\d+(?:\.\d+)?其中：住宅\d+(?:\.\d+)?-?\d+(?:\.\d+)?办公楼(\d+(?:\.\d+)?)',
        'investment_commercial':   r'办公楼\d+(?:\.\d+)?-?\d+(?:\.\d+)?商业营业用房(\d+(?:\.\d+)?)',
        # 施工分项（不需要，sales.js 没有）
        # 新开工分项（不需要）
        # 竣工分项（不需要）
        # 销售面积分项
        'sales_residential_area':  r'新建商品房销售面积（万平方米）\d+(?:\.\d+)?-?\d+(?:\.\d+)?其中：住宅(\d+(?:\.\d+)?)',
        'sales_office_area':       r'新建商品房销售面积（万平方米）\d+(?:\.\d+)?-?\d+(?:\.\d+)?其中：住宅\d+(?:\.\d+)?-?\d+(?:\.\d+)?办公楼(\d+(?:\.\d+)?)',
        'sales_commercial_area':   r'办公楼\d+(?:\.\d+)?-?\d+(?:\.\d+)?商业营业用房(\d+(?:\.\d+)?)',
        # 销售额分项
        'sales_residential_amount': r'新建新建商品房销售额（亿元）\d+(?:\.\d+)?-?\d+(?:\.\d+)?其中：住宅(\d+(?:\.\d+)?)',
        # 待售面积分项
        'inventory_residential':   r'商品房待售面积（万平方米）\d+(?:\.\d+)?-?\d+(?:\.\d+)?其中：住宅(\d+(?:\.\d+)?)',
        'inventory_office':        r'商品房待售面积（万平方米）\d+(?:\.\d+)?-?\d+(?:\.\d+)?其中：住宅\d+(?:\.\d+)?-?\d+(?:\.\d+)?办公楼(\d+(?:\.\d+)?)',
        'inventory_commercial':    r'办公楼\d+(?:\.\d+)?-?\d+(?:\.\d+)?商业营业用房(\d+(?:\.\d+)?)',
    }

    # 注意：sales.js 中没有 sales_office_area / sales_commercial_area 字段，
    # 抓取但不使用（仅 investment 和 inventory 分项需要写入）

    # 由于表1中"办公楼""商业营业用房"出现多次（投资、施工、新开工、竣工、销售面积、销售额、待售面积），
    # 上面的精确正则可能匹配不到。改用区域子段定位法。

    # 方案：把表1按"指标段"切分，每段单独提取
    # 段1: 房地产开发投资（亿元） ... 房屋施工面积（万平方米）
    # 段2: 房屋施工面积（万平方米） ... 房屋新开工面积（万平方米）
    # 段3: 房屋新开工面积（万平方米） ... 房屋竣工面积（万平方米）
    # 段4: 房屋竣工面积（万平方米） ... 新建商品房销售面积（万平方米）
    # 段5: 新建商品房销售面积（万平方米） ... 新建新建商品房销售额（亿元）
    # 段6: 新建新建商品房销售额（亿元） ... 商品房待售面积（万平方米）
    # 段7: 商品房待售面积（万平方米） ... 房地产开发企业本年到位资金（亿元）

    segments = [
        ('investment_seg', '房地产开发投资（亿元）', '房屋施工面积（万平方米）'),
        ('construction_seg', '房屋施工面积（万平方米）', '房屋新开工面积（万平方米）'),
        ('new_start_seg', '房屋新开工面积（万平方米）', '房屋竣工面积（万平方米）'),
        ('complete_seg', '房屋竣工面积（万平方米）', '新建商品房销售面积（万平方米）'),
        ('sales_area_seg', '新建商品房销售面积（万平方米）', '新建新建商品房销售额（亿元）'),
        ('sales_amount_seg', '新建新建商品房销售额（亿元）', '商品房待售面积（万平方米）'),
        ('inventory_seg', '商品房待售面积（万平方米）', '房地产开发企业本年到位资金'),
        ('funding_seg', '房地产开发企业本年到位资金', '表'),
    ]

    # 在指定段内提取"其中：住宅""办公楼""商业营业用房"后的数字
    # 注意：text_compact 把数字与同比拼接（如 40556 0.0 → 405560.0）
    # 因此正则必须能区分值与同比。国家统计局表1同比必带1位小数（如0.0、-19.1、-5.0）
    # 用 "值(\d+)(-?\d+\.\d+)下一个关键字" 模式精确提取值
    def extract_in_segment(seg_text, name):
        """在段内提取 住宅/办公楼/商业营业用房 的值（同比要求带小数点）"""
        result = {}
        # 住宅：值后跟同比（带小数），然后是办公楼或下一个关键字
        m = re.search(r'其中：住宅(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['residential'] = m.group(1)
        # 办公楼：值后跟同比（带小数），然后是商业营业用房或下一个段关键字
        m = re.search(r'办公楼(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['office'] = m.group(1)
        # 商业营业用房：值后跟同比（带小数）
        m = re.search(r'商业营业用房(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['commercial'] = m.group(1)
        return result

    def extract_funding_in_segment(seg_text):
        """在资金段内提取 国内贷款/利用外资/自筹资金/定金及预收款/个人按揭贷款 的值"""
        result = {}
        # 国内贷款
        m = re.search(r'国内贷款(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['domestic'] = m.group(1)
        # 利用外资
        m = re.search(r'利用外资(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['foreign'] = m.group(1)
        # 自筹资金
        m = re.search(r'自筹资金(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['self'] = m.group(1)
        # 定金及预收款
        m = re.search(r'定金及预收款(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['deposit'] = m.group(1)
        # 个人按揭贷款
        m = re.search(r'个人按揭贷款(\d+)-?\d+\.\d+', seg_text)
        if m:
            result['mortgage'] = m.group(1)
        return result

    # 切分各段并提取
    for seg_name, start_kw, end_kw in segments:
        s = region.find(start_kw)
        e = region.find(end_kw, s + len(start_kw)) if s >= 0 else -1
        if s < 0:
            continue
        if e < 0:
            e = len(region)
        seg_text = region[s:e]
        result = extract_in_segment(seg_text, seg_name)
        # 把段结果映射到具体字段
        if seg_name == 'investment_seg':
            if 'office' in result:
                data['investment_office'] = result['office']
            if 'commercial' in result:
                data['investment_commercial'] = result['commercial']
        elif seg_name == 'sales_area_seg':
            if 'residential' in result:
                data['sales_residential_area'] = result['residential']
        elif seg_name == 'sales_amount_seg':
            if 'residential' in result:
                data['sales_residential_amount'] = result['residential']
        elif seg_name == 'inventory_seg':
            if 'residential' in result:
                data['inventory_residential'] = result['residential']
            if 'office' in result:
                data['inventory_office'] = result['office']
            if 'commercial' in result:
                data['inventory_commercial'] = result['commercial']
        elif seg_name == 'funding_seg':
            # 资金段用专用提取函数
            fund_result = extract_funding_in_segment(seg_text)
            if 'domestic' in fund_result and 'funding_domestic' not in data:
                data['funding_domestic'] = fund_result['domestic']
            if 'foreign' in fund_result:
                data['funding_foreign'] = fund_result['foreign']
            if 'self' in fund_result and 'funding_self' not in data:
                data['funding_self'] = fund_result['self']
            if 'deposit' in fund_result and 'funding_deposit' not in data:
                data['funding_deposit'] = fund_result['deposit']
            if 'mortgage' in fund_result and 'funding_mortgage' not in data:
                data['funding_mortgage'] = fund_result['mortgage']

    # 打印表1提取结果
    table1_fields = ['investment_office', 'investment_commercial',
                     'sales_residential_area', 'sales_residential_amount',
                     'inventory_residential', 'inventory_office', 'inventory_commercial',
                     'funding_domestic', 'funding_foreign', 'funding_self',
                     'funding_deposit', 'funding_mortgage']
    for f in table1_fields:
        if f in data:
            print(f"    [表1] {f}: {data[f]}")
        else:
            print(f"    [表1未匹配] {f}")


# ===== 70 城房价报告抓取与解析 =====
def find_latest_price70_report():
    """在国家统计局发布页查找最新 70 城房价报告链接"""
    print("\n[P70-1/4] 搜索 70 城商品住宅销售价格变动情况报告...")
    html = fetch_page(STATS_BUREAU_LIST_URL)
    if not html:
        print("  [警告] 无法访问国家统计局数据发布页（70城报告）")
        return []
    soup = BeautifulSoup(html, 'lxml')
    candidates = []
    seen = set()
    for link in soup.find_all('a', href=True):
        text = link.get_text(strip=True)
        if PRICE70_KEYWORD in text:
            href = link.get('href', '')
            if href.startswith('/'):
                href = 'https://www.stats.gov.cn' + href
            elif not href.startswith('http'):
                href = 'https://www.stats.gov.cn/sj/zxfb/' + href
            if href in seen:
                continue
            seen.add(href)
            candidates.append({'title': text, 'url': href})
    if not candidates:
        print("  [警告] 未找到 70 城房价相关报告")
        return []
    print(f"  在第一页找到 {len(candidates)} 条 70 城报告:")
    for i, c in enumerate(candidates[:5]):
        print(f"    [{i+1}] {c['title']}\n        {c['url']}")
    return candidates


def parse_price70_tier_averages(url, target_month=None):
    """解析 70 城房价报告，返回 {month, newHouse:{upCities,tier1,tier2,tier3}, secondHand:{...}}
    通过表1/表2的原始城市环比指数直接计算各线城市平均值与上涨城市数。
    """
    print("\n[P70-2/4] 解析 70 城房价报告内容...")
    html = fetch_page(url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'lxml')
    content = (
        soup.find('div', class_='TRS_Editor')
        or soup.find('div', class_='content')
        or soup.find('div', class_='pages_content')
        or soup.find('article')
        or soup.find('body')
    )
    if not content:
        print("  [警告] 未找到正文容器（70城）")
        return None
    text = content.get_text('\n', strip=True)
    text_compact = re.sub(r'\s+', '', text)
    print(f"  正文长度: {len(text)} 字符, 压缩后: {len(text_compact)}")

    # 提取月份：格式如 "2026年7月份"
    data = {'source_url': url}
    m = re.search(r'(\d{4})年(\d{1,2})月份?70个大中城市', text_compact)
    if m:
        data['year'] = m.group(1)
        data['month'] = int(m.group(2))
    elif target_month:
        data['month'] = target_month
    else:
        data['month'] = None

    def _parse_price_table(start_kw, next_kw):
        """从 start_kw 表中解析每个城市的环比指数 (指数-100 = 环比%)"""
        s = text_compact.find(start_kw)
        if s < 0:
            return {}
        e = text_compact.find(next_kw, s) if next_kw else s + 15000
        if e < 0:
            e = s + 15000
        seg = text_compact[s:e]
        num = r'\d{2,3}\.\d'
        pat = re.compile(r'([\u4e00-\u9fa5]{2,4})(' + num + r')(' + num + r')(' + num + r')')
        results = {}
        for mm in pat.finditer(seg):
            city = mm.group(1)
            mom = round(float(mm.group(2)) - 100, 1)
            results[city] = mom
        return results

    new_mom = _parse_price_table('新建商品住宅销售价格指数', '二手住宅销售价格指数')
    sec_mom = _parse_price_table('二手住宅销售价格指数', '商品住宅销售价格分类指数')

    def _tier_stats(city_mom):
        """计算各线城市平均环比、总上涨城市数"""
        all_t = PRICE70_TIER1 + PRICE70_TIER2
        t3_list = [c for c in city_mom if c not in all_t]
        vals_t1 = [city_mom[c] for c in PRICE70_TIER1 if c in city_mom]
        vals_t2 = [city_mom[c] for c in PRICE70_TIER2 if c in city_mom]
        vals_t3 = [city_mom[c] for c in t3_list]
        def _avg(v):
            return round(sum(v) / len(v), 1) if v else None
        up_t1 = sum(1 for v in vals_t1 if v > 0)
        up_t2 = sum(1 for v in vals_t2 if v > 0)
        up_t3 = sum(1 for v in vals_t3 if v > 0)
        return {
            'tier1': _avg(vals_t1),
            'tier2': _avg(vals_t2),
            'tier3': _avg(vals_t3),
            'upCities': up_t1 + up_t2 + up_t3,
            '_parsed_cities': len(city_mom),
        }

    if new_mom:
        nh = _tier_stats(new_mom)
        data['newHouse'] = nh
        print(f"  [新房] 解析城市数={nh['_parsed_cities']}, 一线={nh['tier1']}% 二线={nh['tier2']}% 三线={nh['tier3']}%, 上涨城市={nh['upCities']}")
    if sec_mom:
        sh = _tier_stats(sec_mom)
        data['secondHand'] = sh
        print(f"  [二手] 解析城市数={sh['_parsed_cities']}, 一线={sh['tier1']}% 二线={sh['tier2']}% 三线={sh['tier3']}%, 上涨城市={sh['upCities']}")
    return data


def update_sales_js_price70(price70_data):
    """将新抓取的 70 城数据追加到 sales.js 的 price70 区块"""
    print("\n[P70-3/4] 自动更新 sales.js 的 price70 区块...")
    if not os.path.exists(SALES_JS_PATH):
        print(f"  [错误] sales.js 不存在: {SALES_JS_PATH}")
        return False
    month = price70_data.get('month')
    if not month:
        print("  [错误] 未解析到月份，无法追加 price70 数据")
        return False
    with open(SALES_JS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已存在该月数据
    period_label = f"'{month}月'"
    months_info = get_array_in_block(content, 'price70:', 'months')
    if months_info and period_label in months_info['content']:
        print(f"  [提示] price70.months 已包含 {month}月 数据，跳过更新")
        return False

    # 追加 months 项
    content, ok = append_value_to_array(content, 'price70:', 'months', period_label)
    if not ok:
        print("  [失败] 未找到 price70.months 数组")
        return False

    # 追加各子字段（新房、二手）
    def _append_all(house_key, obj_data):
        nonlocal content
        success = 0
        for arr_key in ('upCities', 'tier1', 'tier2', 'tier3'):
            v = obj_data.get(arr_key)
            v_str = fmt_num(v)
            content, ok_k = append_value_to_array(
                content, 'price70:', arr_key, v_str, sub_marker=(house_key + ':')
            )
            if ok_k:
                success += 1
            else:
                print(f"  [失败] 未找到 price70.{house_key}.{arr_key}")
        return success

    nh = price70_data.get('newHouse', {})
    sh = price70_data.get('secondHand', {})
    s1 = _append_all('newHouse', nh) if nh else 0
    s2 = _append_all('secondHand', sh) if sh else 0

    # 更新 meta.note 中的 price70 说明（可选，保持简洁跳过）
    with open(SALES_JS_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  ✅ price70 更新完成：追加 {month}月 数据")
    print(f"     newHouse 成功 {s1}/4, secondHand 成功 {s2}/4")
    return True


# ===== sales.js 自动更新 =====
def get_array_in_block(content, block_marker, array_key, sub_marker=None):
    """在 sales.js 中定位数组
    - block_marker: 父级块关键字（如 'investment:'）
    - sub_marker: 子块关键字（如 'mom:'），可选。用于定位嵌套结构中的数组
    - array_key: 数组键（如 'total'）
    返回 dict 或 None
    """
    marker_pos = content.find(block_marker)
    if marker_pos < 0:
        return None
    after = content[marker_pos:]
    sub_offset = 0
    if sub_marker:
        sub_pos = after.find(sub_marker)
        if sub_pos < 0:
            return None
        sub_offset = sub_pos + len(sub_marker)
        after = after[sub_offset:]
    pattern = re.compile(rf"({array_key}:\s*)\[([^\]]*)\]")
    m = pattern.search(after)
    if not m:
        return None
    abs_start = marker_pos + sub_offset + m.start()
    abs_end = marker_pos + sub_offset + m.end()
    return {
        'start': abs_start,
        'end': abs_end,
        'prefix': m.group(1),
        'content': m.group(2),
    }


def append_value_to_array(content, block_marker, array_key, new_value_str, sub_marker=None):
    """在 sales.js 指定数组末尾追加值（new_value_str 为字符串字面量，如 '123.4' 或 'null'）"""
    info = get_array_in_block(content, block_marker, array_key, sub_marker=sub_marker)
    if not info:
        return content, False
    arr_content = info['content'].rstrip()
    if arr_content:
        new_arr = f"{arr_content}, {new_value_str}"
    else:
        new_arr = new_value_str
    new_str = f"{info['prefix']}[{new_arr}]"
    return content[:info['start']] + new_str + content[info['end']:], True


def get_last_value_in_array(content, block_marker, array_key, sub_marker=None):
    """读取 sales.js 指定数组的最后一项（float 或 None）"""
    info = get_array_in_block(content, block_marker, array_key, sub_marker=sub_marker)
    if not info:
        return None
    arr_str = info['content'].strip()
    if not arr_str:
        return None
    # 取最后一个逗号后的内容
    if ',' in arr_str:
        last = arr_str.rsplit(',', 1)[-1].strip()
    else:
        last = arr_str.strip()
    if last in ('null', 'None', ''):
        return None
    try:
        return float(last)
    except ValueError:
        return None


def update_sales_js(stats_data, history):
    """根据抓取的累计数据自动更新 sales.js"""
    print("\n[5/6] 自动更新 sales.js ...")

    cum_month_str = stats_data.get('cumulative_month')
    if not cum_month_str:
        print("  [错误] 未解析到累计月份，无法更新")
        return False
    cum_month = int(cum_month_str)
    if cum_month < 2:
        print(f"  [错误] 累计月份异常: 1-{cum_month}")
        return False

    # 读取 sales.js
    if not os.path.exists(SALES_JS_PATH):
        print(f"  [错误] sales.js 不存在: {SALES_JS_PATH}")
        return False
    with open(SALES_JS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已存在该月份数据
    period_label = f"'{cum_month}月'"
    periods_info = get_array_in_block(content, 'periods:', 'periods')
    if periods_info and period_label in periods_info['content']:
        print(f"  [提示] sales.js 已包含 {cum_month}月 数据，跳过更新（但累计数据仍会保存到历史）")
        return False

    # 从历史读取上月累计数据
    prev_month = cum_month - 1
    prev_cum_data = history.get(str(prev_month))
    if not prev_cum_data:
        print(f"  [警告] 历史中无 1-{prev_month}月 累计数据，无法差分计算单月")
        print(f"  [提示] 请先确保至少运行过一次抓取 1-{prev_month}月 数据")
        print(f"  [提示] 当前累计数据仍会保存到历史，下次抓取 1-{cum_month+1}月 时可用")
        return False

    print(f"  本期: 1-{cum_month}月累计，上月: 1-{prev_month}月累计")
    print(f"  计算单月值 = 本期累计 - 上期累计")
    print(f"  计算环比 = (本期单月 - 上期单月) / |上期单月| × 100%")
    print(f"  上月单月值优先从历史 single_month 读取，备选从 sales.js 数组末项读取")

    # 计算单月值与环比，写入 sales.js
    cur_single = {}  # 当前单月值
    prev_single = prev_cum_data.get('single_month', {})  # 上月单月值（从历史读取）

    success_count = 0
    fail_count = 0

    for fetch_key, block_marker, array_key, calc_type, mom_block, mom_key in FIELD_MAPPINGS:
        cur_cum = to_float(stats_data.get(fetch_key))

        if calc_type == 'diff':
            # 差分类型：单月 = 本期累计 - 上期累计
            prev_cum = to_float(prev_cum_data.get(fetch_key))
            if cur_cum is None or prev_cum is None:
                print(f"  [跳过] {fetch_key}: 缺累计数据 (cur={cur_cum}, prev={prev_cum})")
                content, _ = append_value_to_array(content, block_marker, array_key, 'null')
                content, _ = append_value_to_array(content, mom_block, mom_key, 'null', sub_marker='mom:')
                fail_count += 1
                continue
            single = round(cur_cum - prev_cum, 1)
            cur_single[fetch_key] = single

            # 计算环比：优先用历史 single_month，备选从 sales.js 数组末项读
            prev_single_v = prev_single.get(fetch_key)
            if prev_single_v is None:
                # 备选：从 sales.js 单月值数组末项读取（注意此时还未追加当前月，末项即上月单月）
                prev_single_v = get_last_value_in_array(content, block_marker, array_key)

            # 追加单月值到 sales.js（在读取上月单月之后，避免污染末项）
            content, ok = append_value_to_array(content, block_marker, array_key, fmt_num(single))
            if ok:
                success_count += 1
            else:
                print(f"  [失败] 未找到 {block_marker} {array_key}")
                fail_count += 1

            # 计算并追加环比到 mom 子块
            if prev_single_v is not None and prev_single_v != 0:
                mom_v = round((single - prev_single_v) / abs(prev_single_v) * 100, 1)
                print(f"  [差分] {fetch_key}: {cur_cum} - {prev_cum} = {single}（环比 {mom_v}%）")
            else:
                mom_v = None
                print(f"  [差分] {fetch_key}: {cur_cum} - {prev_cum} = {single}（环比 null）")
            content, _ = append_value_to_array(content, mom_block, mom_key, fmt_mom(mom_v), sub_marker='mom:')

        elif calc_type == 'direct':
            # 直接类型：用累计/期末值（如施工总面积、待售面积）
            if cur_cum is None:
                print(f"  [跳过] {fetch_key}: 缺数据")
                content, _ = append_value_to_array(content, block_marker, array_key, 'null')
                content, _ = append_value_to_array(content, mom_block, mom_key, 'null', sub_marker='mom:')
                fail_count += 1
                continue
            cur_single[fetch_key] = cur_cum

            # 直接字段环比：与上期累计/期末值对比
            prev_v = to_float(prev_cum_data.get(fetch_key))
            if prev_v is None:
                # 备选：从 sales.js 数组末项读取（此时还未追加当前期，末项即上期值）
                prev_v = get_last_value_in_array(content, block_marker, array_key)

            # 追加当前值
            content, ok = append_value_to_array(content, block_marker, array_key, fmt_num(cur_cum))
            if ok:
                success_count += 1
            else:
                print(f"  [失败] 未找到 {block_marker} {array_key}")
                fail_count += 1

            # 计算并追加环比到 mom 子块
            if prev_v is not None and prev_v != 0:
                mom_v = round((cur_cum - prev_v) / abs(prev_v) * 100, 1)
                print(f"  [直接] {fetch_key}: {cur_cum}（环比 {mom_v}%）")
            else:
                mom_v = None
                print(f"  [直接] {fetch_key}: {cur_cum}（环比 null）")
            content, _ = append_value_to_array(content, mom_block, mom_key, fmt_mom(mom_v), sub_marker='mom:')

    # 更新 periods
    today = datetime.now().strftime('%Y-%m-%d')

    periods_info = get_array_in_block(content, 'periods:', 'periods')
    if periods_info:
        old_periods = periods_info['content'].rstrip()
        new_periods = f"{old_periods}, '{cum_month}月'"
        new_str = f"{periods_info['prefix']}[{new_periods}]"
        content = content[:periods_info['start']] + new_str + content[periods_info['end']:]

    # 注意：price70.months 不自动更新，因为 70 城房价数据需要从单独的
    # 《70个大中城市商品住宅销售价格变动情况》报告抓取，与本报告不同源。
    # 如需更新 price70，请单独抓取70城房价报告后手动追加。

    # 更新 meta.updated
    content = re.sub(
        r"updated:\s*'\d{4}-\d{2}-\d{2}'",
        f"updated: '{today}'",
        content,
        count=1
    )

    # 更新 meta.note（说明数据已通过脚本自动更新）
    new_note = f"数据为2026年2-{cum_month}月单月值；1-{cum_month}月数据由国家统计局{today}发布，经 scripts/fetch_real_estate_data.py 自动抓取并差分计算。"
    content = re.sub(
        r"note:\s*'[^']*'",
        f"note: '{new_note}'",
        content,
        count=1
    )

    # 写回 sales.js
    with open(SALES_JS_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n  ✅ sales.js 更新完成")
    print(f"  成功追加 {success_count} 项，失败 {fail_count} 项")
    print(f"  追加 {cum_month}月 数据到 periods、各指标数组及环比数组")

    # 同步 index.html 标题月份
    update_index_html_title(cum_month)

    # 把当前单月值合并到 stats_data，保存到历史
    stats_data['single_month'] = cur_single
    stats_data['fetched_at'] = datetime.now().isoformat()
    history[str(cum_month)] = stats_data
    save_history(history)
    print(f"  累计数据与单月值已保存到历史: {HISTORY_PATH}")

    return True


def update_index_html_title(cum_month):
    """同步更新 index.html 中标题的月份引用（静态 fallback，避免未运行 JS 时显示旧月份）
    覆盖：
      - <h2 id="metricTitle">📌 核心指标概览（2026年X月单月）</h2>
      - <h3>2026年1-N月TOP10房企销售...</h3>
      - <span class="section-note">2026年1月-N月 · 按发布时间排序...</span>
    """
    print("\n  [同步] 更新 index.html 标题月份...")
    if not os.path.exists(INDEX_HTML_PATH):
        print(f"  [警告] index.html 不存在: {INDEX_HTML_PATH}")
        return False
    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 1. 核心指标概览标题：📌 核心指标概览（2026年X月单月）
    content, n1 = re.subn(
        r"(id=\"metricTitle\"[^>]*>📌 核心指标概览（2026年)\d+月(单月）)",
        rf"\g<1>{cum_month}月\g<2>",
        content,
        count=1
    )

    # 2. TOP10 房企销售标题：<h3>2026年1-X月TOP10房企销售：...
    content, n2 = re.subn(
        r"(2026年1-)\d+月(TOP10房企销售)",
        rf"\g<1>{cum_month}月\g<2>",
        content,
        count=1
    )

    # 3. 政策时间线 section-note：2026年1月-X月 · 按发布时间排序
    content, n3 = re.subn(
        r"(2026年1月-)\d+月( · 按发布时间排序)",
        rf"\g<1>{cum_month}月\g<2>",
        content,
        count=1
    )

    if content == original:
        print("  [提示] index.html 未发现需更新的月份引用（可能已是最新）")
        return False

    with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  ✅ index.html 标题月份已同步到 {cum_month} 月")
    print(f"     更新处：核心指标概览({n1})、TOP10房企({n2})、政策时间线({n3})")
    return True


# ===== cumYoy 块自动更新（顶部累计+同比模块）=====
# 累计指标卡的 9 项核心指标配置
# (item_label, stats_data 累计字段, stats_data 同比字段, unit)
CUM_YOY_ITEMS = [
    ('房地产开发投资',   'investment_total',          'investment_yoy',                '亿元'),
    ('住宅投资',         'investment_residential',    'investment_residential_yoy',    '亿元'),
    ('新建商品房销售额',     'sales_amount',              'sales_amount_yoy',              '亿元'),
    ('商品房销售面积',   'sales_area',                'sales_area_yoy',                '万㎡'),
    ('住宅销售面积',     'sales_residential_area',    'sales_residential_area_yoy',    '万㎡'),
    ('房屋新开工面积',   'new_start',                 'new_start_yoy',                 '万㎡'),
    ('房屋竣工面积',     'complete',                   'complete_yoy',                  '万㎡'),
    ('商品房待售面积',   'inventory_total',            'inventory_yoy',                 '万㎡'),
    ('房企到位资金',     'funding_total',              'funding_yoy',                   '亿元'),
]


def build_cum_yoy_block(stats_data):
    """根据抓取数据构建 cumYoy 块的完整字符串（用于整体替换）"""
    cum_month = stats_data.get('cumulative_month', '?')
    today = datetime.now().strftime('%Y-%m-%d')
    period = f"1-{cum_month}月"

    items_js = []
    for label, cum_field, yoy_field, unit in CUM_YOY_ITEMS:
        cum_v = to_float(stats_data.get(cum_field))
        yoy_v = to_float(stats_data.get(yoy_field))
        items_js.append(
            "      { label: '%s', value: %s, unit: '%s', yoy: %s }"
            % (label, fmt_num(cum_v), unit, fmt_mom(yoy_v))
        )
    items_str = ',\n'.join(items_js)

    block = (
        "  cumYoy: {\n"
        f"    period: '{period}',\n"
        f"    updated: '{today}',\n"
        "    items: [\n"
        f"{items_str}\n"
        "    ]\n"
        "  }"
    )
    return block, period


def update_sales_js_cumYoy(stats_data):
    """整体覆盖 sales.js 的 cumYoy 块"""
    print("\n[cumYoy] 更新 sales.js 的 cumYoy 块（累计+同比）...")
    cum_month = stats_data.get('cumulative_month')
    if not cum_month:
        print("  [错误] 未解析到累计月份，跳过 cumYoy 更新")
        return False
    if not os.path.exists(SALES_JS_PATH):
        print(f"  [错误] sales.js 不存在: {SALES_JS_PATH}")
        return False
    with open(SALES_JS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    new_block, period = build_cum_yoy_block(stats_data)

    # 匹配整个 cumYoy 块：从 "cumYoy: {" 到对应 "  }" 结束（同级缩进2空格）
    # 用 [^\n]* 匹配单行属性，到 items 数组结束后的 "    ]\n  }" 为止
    pattern = re.compile(
        r"  cumYoy: \{[\s\S]*?\n  \}",
        re.MULTILINE
    )
    if not pattern.search(content):
        print("  [警告] 未找到 cumYoy 块（sales.js 可能未初始化该块）")
        return False

    new_content = pattern.sub(new_block, content, count=1)
    if new_content == content:
        print("  [提示] cumYoy 块内容未变化")
        return False

    with open(SALES_JS_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✅ cumYoy 块已更新为 {period}（{len(CUM_YOY_ITEMS)} 项核心指标）")
    return True


# ===== 输出片段（参考用） =====
def generate_sales_js_snippet(stats_data):
    """生成累计值代码片段（供参考）"""
    print("\n[6/6] 生成累计值代码片段（参考）...")
    if not stats_data:
        print("  [警告] 无有效数据")
        return

    cum_month = stats_data.get('cumulative_month', '?')
    snippet = f"""// ===== 自动抓取累计数据（{datetime.now().strftime('%Y-%m-%d %H:%M')}）=====
// 数据来源: 国家统计局 {stats_data.get('report_title', f'1-{cum_month}月份全国房地产市场基本情况')}
// 累计月份: 1-{cum_month}
// 说明: 以下为累计值，单月值已自动追加到 sales.js 各数组

// 开发投资（累计，亿元）
investment_cumulative: {{
  total: {stats_data.get('investment_total', 'null')},
  residential: {stats_data.get('investment_residential', 'null')},
  office: {stats_data.get('investment_office', 'null')},
  commercial: {stats_data.get('investment_commercial', 'null')},
  yoy: {{
    total: {stats_data.get('investment_yoy', 'null')},
    residential: {stats_data.get('investment_residential_yoy', 'null')}
  }}
}},

// 商品房销售（累计）
sales_cumulative: {{
  area: {stats_data.get('sales_area', 'null')},
  amount: {stats_data.get('sales_amount', 'null')},
  residentialArea: {stats_data.get('sales_residential_area', 'null')},
  residentialAmount: {stats_data.get('sales_residential_amount', 'null')},
  yoy: {{
    area: {stats_data.get('sales_area_yoy', 'null')},
    amount: {stats_data.get('sales_amount_yoy', 'null')}
  }}
}},

// 待售面积（期末，万㎡）
inventory_cumulative: {{
  total: {stats_data.get('inventory_total', 'null')},
  residential: {stats_data.get('inventory_residential', 'null')},
  office: {stats_data.get('inventory_office', 'null')},
  commercial: {stats_data.get('inventory_commercial', 'null')}
}},

// 到位资金（累计，亿元）
funding_cumulative: {{
  total: {stats_data.get('funding_total', 'null')},
  domestic: {stats_data.get('funding_domestic', 'null')},
  foreign: {stats_data.get('funding_foreign', 'null')},
  self: {stats_data.get('funding_self', 'null')},
  deposit: {stats_data.get('funding_deposit', 'null')},
  mortgage: {stats_data.get('funding_mortgage', 'null')}
}},

// 开工竣工（累计，万㎡）
construction_cumulative: {{
  construction: {stats_data.get('construction', 'null')},
  newStart: {stats_data.get('new_start', 'null')},
  complete: {stats_data.get('complete', 'null')}
}}
// ===== 抓取数据结束 =====
"""
    with open(SNIPPET_PATH, 'w', encoding='utf-8') as f:
        f.write(snippet)
    print(f"  数据片段已保存: {SNIPPET_PATH}")

    # 同时保存原始 JSON
    with open(FETCHED_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)
    print(f"  原始 JSON 已保存: {FETCHED_JSON_PATH}")


# ===== 主流程 =====
def main():
    print("=" * 60)
    print("  房地产行业数据自动获取与更新脚本")
    print("  数据来源: 国家统计局")
    print("  自动更新: js/data/sales.js")
    print("=" * 60)
    print(f"  执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 查找最新报告
    candidates = find_latest_real_estate_report()
    if not candidates:
        print("\n  [提示] 国家统计局可能尚未发布最新月度数据。")
        print("  通常每月 15 日左右发布上月累计数据。")
        print("  请访问 https://www.stats.gov.cn/sj/zxfb/ 手动查看。")
        return

    latest = candidates[0]
    print(f"\n  最新报告: {latest['title']}")

    # 2. 解析最新报告
    stats_data = parse_stats_bureau_report(latest['url'])
    if not stats_data:
        print("  [错误] 解析报告失败")
        return

    # 3. 加载历史
    history = load_history()
    print(f"\n[3/6] 加载历史累计数据...")
    print(f"  历史记录月份: {sorted(history.keys()) if history else '（无）'}")

    cum_month = stats_data.get('cumulative_month')
    if not cum_month:
        print("  [错误] 未解析到累计月份，无法继续")
        return

    # 4. 如果历史中无上月累计数据，自动抓取上月报告
    prev_month = int(cum_month) - 1
    if prev_month >= 2 and str(prev_month) not in history:
        print(f"\n[4/6] 历史中无 1-{prev_month}月 累计数据，自动抓取上月报告...")
        prev_report = find_report_by_month(prev_month, candidates=candidates)
        if prev_report:
            print(f"  找到上月报告: {prev_report['title']}")
            prev_stats = parse_stats_bureau_report(prev_report['url'])
            if prev_stats and prev_stats.get('cumulative_month') == str(prev_month):
                # 保存上月累计数据到历史（不包含 single_month，下次运行时通过 sales.js 反推）
                history[str(prev_month)] = {
                    k: v for k, v in prev_stats.items()
                    if k not in ('single_month', 'fetched_at')
                }
                history[str(prev_month)]['fetched_at'] = datetime.now().isoformat()
                save_history(history)
                print(f"  ✅ 1-{prev_month}月 累计数据已保存到历史")
            else:
                print(f"  [警告] 上月报告解析失败或月份不匹配")
        else:
            print(f"  [警告] 未找到 1-{prev_month}月 报告")
    else:
        print(f"\n[4/6] 历史中已有 1-{prev_month}月 累计数据，跳过抓取上月报告")

    # 5. 保存本月累计数据到历史
    if cum_month not in history:
        history[cum_month] = {
            k: v for k, v in stats_data.items()
            if k not in ('single_month', 'fetched_at')
        }
        history[cum_month]['fetched_at'] = datetime.now().isoformat()
        save_history(history)
        print(f"\n[5/6] 本月累计数据已保存到历史（1-{cum_month}月）")
    else:
        print(f"\n[5/6] 1-{cum_month}月 累计数据已存在历史中，跳过保存")

    # 6. 自动更新 sales.js（开发投资 / 销售 / 开工竣工 / 资金 等）
    updated = update_sales_js(stats_data, history)

    # 6.1 自动更新 cumYoy 块（顶部累计+同比模块）
    cum_yoy_updated = update_sales_js_cumYoy(stats_data)

    # 7. 抓取并更新 70 城房价数据（来自单独报告）
    price70_updated = False
    p70_candidates = find_latest_price70_report()
    if p70_candidates:
        p70_latest = p70_candidates[0]
        print(f"\n  最新 70 城报告: {p70_latest['title']}")
        p70_data = parse_price70_tier_averages(p70_latest['url'])
        if p70_data and (p70_data.get('newHouse') or p70_data.get('secondHand')):
            price70_updated = update_sales_js_price70(p70_data)
            # 同时保存 70 城数据到 fetched JSON
            stats_data['price70'] = {
                'month': p70_data.get('month'),
                'year': p70_data.get('year'),
                'newHouse': {k: v for k, v in p70_data.get('newHouse', {}).items() if not k.startswith('_')},
                'secondHand': {k: v for k, v in p70_data.get('secondHand', {}).items() if not k.startswith('_')},
                'source_url': p70_data.get('source_url'),
                'fetched_at': datetime.now().isoformat(),
            }
        else:
            print("  [警告] 70 城报告解析失败或无有效数据")
    else:
        print("\n[P70-SKIP] 未找到 70 城房价报告（可能尚未发布）")

    # 8. 生成代码片段（参考用）
    generate_sales_js_snippet(stats_data)

    # 总结
    print("\n" + "=" * 60)
    print("  ✅ 数据获取完成！")
    if updated:
        print(f"  sales.js 已自动追加 1-{cum_month}月 的单月值与环比")
    else:
        print(f"  sales.js 销售/投资数据未更新（可能已包含该月数据或历史不足）")
    if cum_yoy_updated:
        print(f"  cumYoy 块已更新为 1-{cum_month}月 累计值与同比（顶部累计指标概览）")
    if price70_updated:
        m = stats_data.get('price70', {}).get('month') or '?'
        print(f"  price70 已自动追加 {m}月 的各线城市环比与上涨城市数")
    else:
        print(f"  price70 未更新（可能已包含该月数据或未抓取）")
    print("=" * 60)


if __name__ == '__main__':
    main()
