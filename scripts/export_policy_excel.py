# -*- coding: utf-8 -*-
"""
生成国家级房地产政策时间线 Excel 表格
包含：日期、政策名称、发布机构、核心观点、对比分析、来源链接
格式优化：表头样式、列宽、行高、自动换行、边框、配色
"""

import os
import json
import re
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter

# 政策数据（从 policies.js 提取）
POLICIES = [
    {
        'date': '2026-01-01',
        'name': '《改善和稳定房地产市场预期》（《求是》特约评论员文章）',
        'agency': '《求是》杂志',
        'category': '顶层定调',
        'url': 'http://www.qstheory.cn/20251231/f3cb83eb629f452ebf1fdbc0294557be/c.html',
        'points': '1. 明确房地产业是"国民经济的重要产业和居民财富的重要来源"，地位举足轻重\n2. 罕见承认房地产具有"显著的金融资产属性"，强调预期管理的重要性\n3. 提出"控增量、去库存、优供给"总体思路，结合城市更新、城中村改造盘活存量\n4. 测算存量住房每年约7亿平方米更新改造需求，行业仍有长期发展空间\n5. 要求政策"一次性给足，不能采取添油战术"',
        'comparison': '首次将房地产明确为"金融资产属性"，从"止跌回稳"转向"稳定"基调，强调存量提质而非增量扩张，为全年政策定下基调。'
    },
    {
        'date': '2026-03-03',
        'name': '《个人贷款业务明示综合融资成本规定》（金规〔2026〕2号）',
        'agency': '国家金融监督管理总局、中国人民银行',
        'category': '房贷融资',
        'url': 'https://www.gov.cn/gongbao/2026/issue_12806/202606/content_7072468.html',
        'points': '1. 要求贷款人向借款人展示《综合融资成本明示表》，逐项列明息费项目\n2. 覆盖全部持牌放贷机构（银行、消费金融、汽车金融、信托、小贷公司等）\n3. 现场办理需借款人签字确认，线上办理须弹窗展示并设置强制阅读时间\n4. 第三方合作机构收费全部纳入综合成本核算，杜绝"化整为零、变相抬息"\n5. 房贷纳入管理范围，新老划断，存量贷款不受影响（2026年8月1日施行）',
        'comparison': '首次将个人贷款（含房贷）息费披露"强制透明化"，从"低息营销"转向"透明定价"，保护借款人知情权。'
    },
    {
        'date': '2026-03-05',
        'name': '2026年《政府工作报告》（房地产相关部署）',
        'agency': '国务院（十四届全国人大四次会议）',
        'category': '顶层部署',
        'url': 'http://www.china.com.cn/lianghui/news/2026-03/05/content_118362687.shtml',
        'points': '1. 房地产定调由"持续用力推动止跌回稳"调整为"着力稳定房地产市场"\n2. 时隔十年再提"去库存"，提出"因城施策控增量、去库存、优供给"\n3. 首次写入"鼓励收购存量商品房重点用于保障性住房"\n4. 首次使用"深化住房公积金制度改革"（此前为"支持"）\n5. 提出"加强初婚初育家庭住房保障，支持多子女家庭改善性住房需求"\n6. 要求"进一步发挥保交房白名单制度作用"',
        'comparison': '政策姿态从"持久战"转向"精准发力"；首提存量商品房收储、首提初婚初育家庭保障，去库存重回核心议题。'
    },
    {
        'date': '2026-03-13',
        'name': '《"十五五"规划纲要》（房地产首次独立成章）',
        'agency': '全国人民代表大会',
        'category': '顶层规划',
        'url': 'https://www.gov.cn/xinwen/2026-03/13/content_118369000.htm',
        'points': '1. 房地产相关内容首次独立成章（第四十四章"推动房地产高质量发展"）\n2. 提出"加快构建房地产发展新模式，健全多主体供给、多渠道保障、租购并举的住房制度"\n3. 明确"有力有序推进现房销售"——现房销售首次写入五年规划\n4. 推行房地产开发项目公司制和融资主办银行制\n5. 明确保障性住房全流程管理、配租配售转换、公积金改革及灵活就业人员参缴等实施路径',
        'comparison': '现房销售首次写入五年规划，具有里程碑意义；从销售端规则重构倒逼开发端降杠杆，确立中长期制度框架。'
    },
    {
        'date': '2026-03-16',
        'name': '金融监管总局党委扩大会议（保交房白名单）',
        'agency': '国家金融监督管理总局',
        'category': '融资协调',
        'url': 'https://stcn.com/article/detail/3679393.html',
        'points': '1. 强调"进一步发挥保交房白名单制度作用"\n2. 提出"加快建立与房地产发展新模式相适应的融资制度"\n3. 有力有序有效推进中小金融机构风险化解，牢牢守住不"爆雷"底线\n4. 依法合规支持融资平台债务风险化解\n5. 严防严打严处非法金融活动',
        'comparison': '从被动风险兜底转向"建立与新模式相适应的融资制度"的长效机制建设，融资协调机制制度化。'
    },
    {
        'date': '2026-04-28',
        'name': '中央政治局会议（"努力稳定房地产市场"）',
        'agency': '中共中央政治局',
        'category': '顶层定调',
        'url': 'https://www.gov.cn/yaowen/2026-04/28/content_118371200.htm',
        'points': '1. 明确"努力稳定房地产市场，扎实推进城市更新"\n2. 表述从3月政府工作报告的"着力稳定"调整为"努力稳定"，强化主观能动性\n3. 将稳定房地产上升为稳定宏观经济大盘的核心抓手\n4. 定下"稳字当头、盘活存量、保障民生"总基调\n5. 为后续所有部委政策划定底层逻辑',
        'comparison': '从"着力"到"努力"一字之差，更强调地方主体责任和主观能动性，稳定房地产成为宏观稳定核心抓手。'
    },
    {
        'date': '2026-05-22',
        'name': '《城市更新"十五五"规划》（国发〔2026〕12号）',
        'agency': '国务院',
        'category': '城市更新',
        'url': 'https://www.gov.cn/gongbao/2026/issue_12786/202606/content_7071614.html',
        'points': '1. 到2030年城市更新行动取得重要进展，到2035年基本建成现代化人民城市\n2. "十五五"期间新开工改造城镇老旧小区11.5万个\n3. 继续建设改造城市地下管网约77万公里\n4. 稳步推进城中村更新改造，采取拆除新建、整治提升、拆整结合等多种方式\n5. 推进"好房子"建设，实施房屋品质提升工程\n6. 深化住房公积金制度改革，扩大使用范围，支持灵活就业人员参加\n7. 未来五年城市更新至少可完成投资15万亿元',
        'comparison': '首部国家级城市更新五年专项规划；明确量化指标；从"增量开发"全面转向"存量提质"，开辟15万亿投资空间。'
    },
    {
        'date': '2026-06-05',
        'name': '《住房公积金管理条例（修订征求意见稿）》',
        'agency': '住房和城乡建设部',
        'category': '住房公积金',
        'url': 'https://www.mohurd.gov.cn/xinwen/gzdt/art/2026/art_f22a300d9e9b4483be2c978a7cf19cb0.html',
        'points': '1. 住房公积金提取情形由6种拓展至9种，新增装修、物业费、其他住房消费情形\n2. 扩大缴存覆盖面，个体工商户、灵活就业人员可自愿参加\n3. 贷款审批时限由15日缩短为10日\n4. 健全异地协同机制，推动住房公积金互认互贷\n5. 从"购房""租房"拓展到"修房""养房"',
        'comparison': '1999年条例颁布以来重大修订；适应存量时代居住全周期需求，覆盖新就业形态，从购房租房扩展到修房养房。'
    },
    {
        'date': '2026-06-08',
        'name': '四部门联合解读《城市更新"十五五"规划》',
        'agency': '住建部、国家发改委、财政部、自然资源部',
        'category': '城市更新',
        'url': 'https://www.gov.cn/xinwen/2026zccfh/9/index.htm',
        'points': '1. 明确"十五五"期间改造50万套（间）危旧房\n2. 实施5000个社区完整社区建设改造\n3. 改造1500个老旧街区和厂区\n4. 财政部积极发挥财政职能作用，完善财政支持政策\n5. 自然资源部配套土地支持政策',
        'comparison': '城市更新从规划编制转向项目落地实施阶段，四部门协同明确财政与土地配套政策。'
    },
    {
        'date': '2026-06-15',
        'name': '住建部收购已建成存量商品房工作视频会议',
        'agency': '住房和城乡建设部',
        'category': '存量收储',
        'url': 'https://www.mohurd.gov.cn/xinwen/gzdt/202606/art_2026_shougu.html',
        'points': '1. 推动县级以上城市开展收购已建成存量商品房用作保障性住房工作\n2. 央行3000亿元保障性住房专项再贷款全额投放，年化利率1.75%\n3. 财政部放开专项债使用范围，允许用于存量房收储与旧房改造\n4. 收储以市场化自愿交易为准则，严禁强制征收、恶意压价\n5. 截至6月上旬，70余城启动收储，意向登记房源突破12万套',
        'comparison': '存量房收储正式上升为国家层面战略部署，从地方试点走向全国统一推进，资金工具箱（再贷款+专项债）齐全。'
    },
    {
        'date': '2026-07-06',
        'name': '六部委联合房地产新政（"7月王炸"）',
        'agency': '住建部、央行、财政部、金融监管总局、税务总局、自然资源部',
        'category': '综合政策包',
        'url': 'https://finance.sina.com.cn/roll/2026-07-12/doc-inihpipy5955611.shtml',
        'points': '1. 信贷端：全国统一首套房首付降至15%，二套房降至25%；首套商贷3.05%-3.45%\n2. 存量房贷利率下调：高于"LPR+30基点"的统一调整至5年期LPR水平（3.5%），9月底前完成\n3. 税费减免：取消普通/非普通住宅划分；不满2年住宅增值税从5%降至3%\n4. 存量收储：3000亿保障性住房专项再贷款全额投放，全国近80城启动收储\n5. 土地供应：去化周期超36个月城市暂停新增住宅用地出让\n6. 房企融资：白名单制度持续推进，主办银行制度正式落地',
        'comparison': '业内定义为"2015年后最强救市政策"；从单点松绑转向跨部门协同的完整政策闭环，信贷+税费+收储+土地+融资五端齐发。'
    },
    {
        'date': '2026-07-13',
        'name': '《扩大消费"十五五"规划》（国函〔2026〕66号）',
        'agency': '国务院',
        'category': '住房消费',
        'url': 'https://www.gov.cn/zhengce/2026-07/13/content_118375100.htm',
        'points': '1. 我国首部以"扩大消费"为主题的国家级五年专项规划\n2. 住房被正式纳入大宗耐用商品消费体系，位列汽车、家居家电之前\n3. 提出到2030年社会消费品零售总额达60万亿元左右\n4. 部署"好房子"建设、城中村和老旧小区改造、适老化与智能化升级\n5. 支持各地因城施策优化房地产政策，深化住房公积金制度改革',
        'comparison': '住房从"投资品"定位正式回归"消费品"，标志楼市底层逻辑根本性变革，与扩大消费战略深度绑定。'
    },
    {
        'date': '2026-07-22',
        'name': '住建部表示房地产市场进入存量时代',
        'agency': '住房和城乡建设部',
        'category': '顶层定调',
        'url': 'https://www.mohurd.gov.cn/xinwen/gzdt/202607/art_2026_cunliang.html',
        'points': '1. 明确"我国房地产市场已经从增量时代进入存量时代"\n2. 上半年二手房在新房和二手房交易总量中占比50.4%\n3. 北京、上海、江苏、广东等18个省（区、市）二手住宅交易面积超过新建商品住宅\n4. 标志着交易结构发生深刻变化\n5. 开发企业需从高周转扩张转向精细化运营和存量资产盘活',
        'comparison': '官方首次正式确认进入"存量时代"，为政策逻辑转变提供依据，二手房占比过半成为历史性拐点。'
    },
    {
        'date': '2026-07-25',
        'name': '《关于进一步加强建筑市场监管持续优化建筑市场环境的通知》（建市规〔2026〕2号）',
        'agency': '住房和城乡建设部',
        'category': '建筑市场',
        'url': 'https://www.mohurd.gov.cn/jianzhu/202607/art_2026_jianzhu.html',
        'points': '1. 全面推行工程款支付担保，推动实现"见索即付"\n2. 整治证书挂靠\n3. 规范招投标\n4. 严控发包分包\n5. 强化数字化智能监管与信用惩戒',
        'comparison': '从源头规范建筑市场秩序，保障工程款支付，间接支持保交房与建筑业良性发展。'
    },
    {
        'date': '2026-07-30',
        'name': '中央政治局会议（"稳定房地产市场"）',
        'agency': '中共中央政治局',
        'category': '顶层定调',
        'url': 'https://www.gov.cn/yaowen/2026-07/30/content_118378900.htm',
        'points': '1. 表述精简为"稳定房地产市场"\n2. 将"稳定房地产市场"放入"切实筑牢安全屏障"框架下\n3. 从"防风险"转向"筑屏障"，更具主动色彩\n4. 房地产从"需要防的风险点"变为"必须守的安全底线"\n5. 强调"两重"（国家重大战略实施和重点领域安全能力建设）和"两新"（设备更新和消费品以旧换新）提速',
        'comparison': '4月"努力稳定"→7月"稳定"，从防范化解风险框架上升到安全屏障框架，房地产成为必须守的安全底线。'
    },
    {
        'date': '2026-07-31',
        'name': '国务院常务会议审议通过《住房公积金管理条例》修订决定（草案）',
        'agency': '国务院',
        'category': '住房公积金',
        'url': 'https://news.cctv.com/2026/08/02/ARTIcuPyJtEjrr5rs0jE24aO260802.shtml',
        'points': '1. 审议通过《国务院关于修改〈住房公积金管理条例〉的决定（草案）》，公积金改革进入国务院审议阶段\n2. 明确"更好发挥住房公积金功能作用，拓宽提取和使用范围，扩大制度覆盖面，提升管理服务效能"\n3. 6月征求意见稿中"装修、物业费、其他住房消费"三类新增提取情形正式纳入决定草案\n4. 扩大制度覆盖面：2亿灵活就业人员可自愿缴存\n5. 8月2日央视网等中央媒体公开报道，住建部8月3日发布配套解读文章',
        'comparison': '从6月住建部"征求意见稿"→7月31日国务院常务会议"决定草案"，公积金改革从行业主管部门征求意见升级到国务院顶层审议，与7月30日中央政治局会议"稳定房地产市场"形成政策闭环。'
    },
    {
        'date': '2026-08-18',
        'name': '《国务院关于修改〈住房公积金管理条例〉的决定》（国务院令，9月20日起施行）',
        'agency': '国务院',
        'category': '住房公积金',
        'url': 'https://www.gov.cn/zhengce/content/202608/content_7078477.htm',
        'points': '1. 李强总理签署国务院令公布，《决定》共20条，自2026年9月20日起施行\n2. 拓宽提取和使用范围：房租提取不再设"超过家庭工资收入规定比例"门槛；新增装修自住住房、支付自住住房物业费、国务院批准的其他住房消费情形\n3. 适当拓宽投资运用渠道：公积金可用于购买政策性金融债\n4. 提升管理服务效能：简化提取手续、缩短贷款审查时限，缴存记录全国互信互认，异地贷款便捷办理\n5. 强化风险防控：建立信用记录并纳入全国信用信息共享平台，明确欺诈提取、骗取贷款的法律责任\n6. 扩大制度覆盖面：个体工商户、非全日制从业人员及其他灵活就业人员可自愿缴存',
        'comparison': '公积金改革"三级跳"完成最后一跃：6月征求意见稿→7月31日国常会决定草案→8月18日国务院令正式公布，1999年条例颁布以来最重大修订正式落地；公积金从"购房租房"专属工具升级为覆盖"修房养房"的居住全周期制度。'
    },
    {
        'date': '2026-08-21',
        'name': '《关于优化中央国家机关住房公积金政策的通知》（国机房资〔2026〕10号）',
        'agency': '中央国家机关住房资金管理中心',
        'category': '住房公积金',
        'url': 'https://www.zzz.gov.cn/html/xwzx/tzgg/19311.html',
        'points': '1. 提高最高贷款额度：单缴存人首套120万元、二套100万元；夫妻双方均缴存首套240万元、二套200万元\n2. 额度可叠加上浮：城六区外购房+20万、绿色建筑+40万、多子女家庭+40万，双缴存家庭最高上浮100万元\n3. 优化住房套数认定：在京无房或仅1套住房且公积金贷款已结清的，再次购房可申请公积金贷款\n4. 开展公积金贷款存量房"带押过户"业务\n5. 新增装修提取：额度不超过发票金额50%且最高25万元，同一住房再次提取须满10年\n6. 自2026年8月8日起施行，8月8日前已受理未放款贷款可自主选择新旧政策',
        'comparison': '国管公积金率先落实中央政治局"稳定房地产市场"要求，与8月18日国务院令修订条例形成"顶层立法+中央机关先行"呼应；贷款额度、套数认定、带押过户、装修提取四箭齐发，为地方公积金政策优化提供示范。'
    },
    {
        'date': '2026-08-28',
        'name': '"8·28"房地产新政：销售制度、信贷管理、资本市场融资三大制度系统性重塑',
        'agency': '住建部、自然资源部、金融监管总局、中国人民银行、证监会',
        'category': '综合政策包',
        'url': 'https://www.mohurd.gov.cn/gongkai/zc/wjk/art/2026/art_45644612a7064289bdc0d5b1427a25d8.html',
        'points': '1. 住建部等三部门《关于完善商品住房销售制度的通知》（建房规〔2026〕3号）：预售项目单体建筑须完成主体结构封顶，购房资金全部存入监管账户\n2. 有力有序推行现房销售：新出让土地及未取得规划许可证项目优先现房销售，实行备案管理与现房销售定金制\n3. 央行、金融监管总局《关于改革完善房地产信贷管理的意见》：个人住房贷款最长期限由30年延至40年，月房贷支出收入比≤50%、月全部债务支出收入比≤60%\n4. 开发贷实行主办银行制封闭管理：预售项目最长5年、现房项目最长7年，首次还本原则上安排在竣工备案之后；废止2003-2016年九项信贷文件\n5. 延后按揭发放时点实现"能拿房、再还贷"\n6. 证监会《关于资本市场支持构建房地产发展新模式的意见》：房企融资从主体信用转向项目信用，支持再融资、并购重组、公司债、ABS与REITs\n7. 同步发布五项专项管理办法（开发贷、个人住房贷款、商业地产贷款、城市更新项目贷款、房地产信托）\n8. 推行"交房即交证"',
        'comparison': '"7月王炸"侧重需求端刺激，"8·28"新政直击供给端制度根基——现房销售制、项目公司制、主办银行制三项基础制度同步确立，延续30余年的预售制进入尾声；被业内视为对房地产开发商业模式的全方位颠覆，影响未来3-5年行业格局。'
    },
    {
        'date': '2026-09-18',
        'name': '国新办发布会：介绍"十五五"时期住房城乡建设事业高质量发展情况',
        'agency': '国务院新闻办公室、住房和城乡建设部',
        'category': '顶层定调',
        'url': 'https://www.mohurd.gov.cn/xinwen/gzdt/art/2026/art_ade43dfa55314828ae570f79b6f2b52e.html',
        'points': '1. 住建部副部长陈绍旺系统介绍"十五五"时期住房城乡建设事业高质量发展总体安排\n2. 明确房地产发展新模式内涵：完善保障和市场两个体系，以项目公司制、主办银行制和现房销售制三项制度为重点改革基础性制度，推动"人房地钱"四要素联动\n3. 系统推进"好房子"建设：全链条全生命周期推进，统筹"四好"（好房子、好小区、好社区、好城区）建设\n4. 确认房地产进入存量时代，统筹防风险和促转型\n5. 城市更新：改造提升2万公顷公园绿地、新增15000个口袋公园、建设改造2万公里绿道，改造提升300片历史文化街区\n6. 地下管网：建设改造约77万公里，地下综合管廊投资规模超过5万亿元',
        'comparison': '"8·28"新政落地后首次国新办高规格宣介：把三项基础制度纳入"十五五"房地产新模式顶层内涵，首次系统阐述"人房地钱"要素联动机制，为销售制度改革、城市更新与"好房子"建设提供权威执行背书。'
    },
    {
        'date': '2026-09-28',
        'name': '《房地产基础性制度的改革重构》：确立项目公司制、主办银行制、现房销售制三项制度',
        'agency': '住房和城乡建设部（转载《经济日报》）',
        'category': '顶层定调',
        'url': 'https://www.mohurd.gov.cn/xinwen/gzdt/art/2026/art_0b53e820458146e683c3406b71699956.html',
        'points': '1. 以项目公司制、主办银行制和现房销售制三项制度为重点，改革完善房地产基础性制度\n2. 两大转变背景：供求关系转向供需基本平衡；二手房交易占比从2020年27%升至今年前8个月52%\n3. 开发环节项目公司制：一个项目对应一家项目公司，严禁总部违规抽挪项目资金，实现风险隔离\n4. 融资环节主办银行制：一个项目确定一家主办银行或银团，资金全部存入主办银行，双向选择、利益共享风险共担\n5. 销售环节现房销售制：落实"一手交钱一手交房"，从根本上防范交付风险\n6. 房企转向以产品立业、信用立身的"好房子"供给者',
        'comparison': '对"8·28"新政的制度逻辑进行权威定调：三项制度分别对应开发、融资、销售三个环节，均以项目为对象，构成房地产新发展模式的制度闭环，标志基础制度重构从文件发布走向官方系统阐述。'
    },
    {
        'date': '2026-09-29',
        'name': '财政部等三部门：首套购房商业贷款财政贴息（10月1日起实施）',
        'agency': '财政部、中国人民银行、金融监管总局',
        'category': '房贷融资',
        'url': 'http://m.toutiao.com/group/7694146226131911178/',
        'points': '1. 自2026年10月1日起，对新发放首套商业性个人住房贷款给予年化1个百分点财政贴息，贴息期限最长5年\n2. 适用条件：新发放商贷购买首套住房（不含存量贷款置换），建筑面积≤120平方米、房屋总价≤150万元\n3. 单户享受贴息的贷款规模上限100万元，政策实施期暂定1年，5年最多可省利息约5万元\n4. 成本分担：中央财政承担90%、地方财政承担10%，纳入预算统筹保障、据实结算\n5. 同日央行下调抵押补充贷款（PSL）利率\n6. 贴息精准聚焦下沉市场刚需，国庆假期多地楼市活跃度明显提升',
        'comparison': '继"7月王炸"降首付降利率、"8·28"制度重塑之后，财政贴息直接补贴居民月供，是财政逆周期调节从供给侧投资转向需求侧托底的新探索，定向托底库存压力较大的下沉市场。'
    }
]

# 分类颜色映射
CATEGORY_COLORS = {
    '顶层定调': '4472C4',      # 深蓝
    '顶层部署': '2E75B6',      # 中蓝
    '顶层规划': '5B9BD5',      # 浅蓝
    '城市更新': '70AD47',      # 绿色
    '房贷融资': 'ED7D31',      # 橙色
    '融资协调': 'FFC000',      # 金黄
    '住房公积金': '9B59B6',    # 紫色
    '存量收储': 'C0504D',      # 红色
    '综合政策包': 'FF0000',    # 大红
    '住房消费': '7030A0',      # 深紫
    '建筑市场': '548235',      # 深绿
}


def create_policy_excel():
    """生成格式优化的 Excel 表格"""
    
    wb = Workbook()
    ws = wb.active
    ws.title = '2026年房地产政策时间线'
    
    # ===== 样式定义 =====
    # 表头样式
    header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # 数据样式
    data_font = Font(name='微软雅黑', size=10, color='1F2937')
    data_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    date_alignment = Alignment(horizontal='center', vertical='top', wrap_text=True)
    
    # 对比分析特殊样式
    comparison_font = Font(name='微软雅黑', size=10, color='C00000', bold=True)
    
    # 边框
    thin_border = Border(
        left=Side(style='thin', color='D0D5DD'),
        right=Side(style='thin', color='D0D5DD'),
        top=Side(style='thin', color='D0D5DD'),
        bottom=Side(style='thin', color='D0D5DD')
    )
    
    # 交替行底色
    fill_even = PatternFill(start_color='F2F7FB', end_color='F2F7FB', fill_type='solid')
    fill_odd = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')
    
    # ===== 写入标题行 =====
    ws.merge_cells('A1:G1')
    ws['A1'] = '2026年国家级房地产政策时间线（1月-9月）'
    ws['A1'].font = Font(name='微软雅黑', size=14, bold=True, color='1F4E79')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws['A1'].fill = PatternFill(start_color='D6E4F0', end_color='D6E4F0', fill_type='solid')
    ws.row_dimensions[1].height = 32
    
    # ===== 写入表头 =====
    headers = ['序号', '发布日期', '政策名称', '发布机构', '政策类别', '核心观点', '对比分析']
    ws.append(headers)
    
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=2, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    ws.row_dimensions[2].height = 36
    
    # ===== 写入数据行 =====
    for idx, policy in enumerate(POLICIES, start=1):
        row_num = idx + 2  # 从第3行开始写数据
        
        # 序号
        ws.cell(row=row_num, column=1, value=idx)
        # 发布日期
        ws.cell(row=row_num, column=2, value=policy['date'])
        # 政策名称
        ws.cell(row=row_num, column=3, value=policy['name'])
        # 发布机构
        ws.cell(row=row_num, column=4, value=policy['agency'])
        # 政策类别
        ws.cell(row=row_num, column=5, value=policy['category'])
        # 核心观点
        ws.cell(row=row_num, column=6, value=policy['points'])
        # 对比分析
        ws.cell(row=row_num, column=7, value=policy['comparison'])
        
        # 设置单元格样式
        for col in range(1, 8):
            cell = ws.cell(row=row_num, column=col)
            cell.border = thin_border
            
            # 交替行底色
            if idx % 2 == 0:
                cell.fill = fill_even
            else:
                cell.fill = fill_odd
        
        # 单独设置各列样式
        ws.cell(row=row_num, column=1).alignment = date_alignment
        ws.cell(row=row_num, column=1).font = data_font
        
        ws.cell(row=row_num, column=2).alignment = date_alignment
        ws.cell(row=row_num, column=2).font = Font(name='微软雅黑', size=10, bold=True, color='1F2937')
        
        ws.cell(row=row_num, column=3).alignment = data_alignment
        ws.cell(row=row_num, column=3).font = Font(name='微软雅黑', size=10, bold=True, color='1F4E79')
        
        ws.cell(row=row_num, column=4).alignment = data_alignment
        ws.cell(row=row_num, column=4).font = data_font
        
        ws.cell(row=row_num, column=5).alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.cell(row=row_num, column=5).font = Font(name='微软雅黑', size=9, bold=True, color='FFFFFF')
        
        # 根据类别设置不同背景色
        category_color = CATEGORY_COLORS.get(policy['category'], '808080')
        ws.cell(row=row_num, column=5).fill = PatternFill(
            start_color=category_color, end_color=category_color, fill_type='solid'
        )
        
        ws.cell(row=row_num, column=6).alignment = data_alignment
        ws.cell(row=row_num, column=6).font = data_font
        
        ws.cell(row=row_num, column=7).alignment = data_alignment
        ws.cell(row=row_num, column=7).font = comparison_font
        
        # 设置行高（根据内容长度调整）
        points_len = len(policy['points'])
        comparison_len = len(policy['comparison'])
        row_height = max(60, points_len * 12 + comparison_len * 0.3 + 30)
        ws.row_dimensions[row_num].height = row_height
    
    # ===== 设置列宽 =====
    column_widths = {
        'A': 6,   # 序号
        'B': 12,  # 发布日期
        'C': 45,  # 政策名称
        'D': 28,  # 发布机构
        'E': 12,  # 政策类别
        'F': 65,  # 核心观点
        'G': 55,  # 对比分析
    }
    
    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width
    
    # ===== 冻结首行（表头）=====
    ws.freeze_panes = 'A3'
    
    # ===== 添加筛选 =====
    ws.auto_filter.ref = f'A2:G{len(POLICIES) + 2}'
    
    # ===== 添加底部说明 =====
    footer_row = len(POLICIES) + 4
    ws.merge_cells(f'A{footer_row}:G{footer_row}')
    ws.cell(row=footer_row, column=1, 
            value='数据来源：政府官网、新华社、人民网、权威媒体及行业研究机构公开报道 | 收集截止：2026-10-08')
    ws.cell(row=footer_row, column=1).alignment = Alignment(horizontal='center', vertical='center')
    ws.cell(row=footer_row, column=1).font = Font(name='微软雅黑', size=9, color='6B7280')
    
    # ===== 保存文件 =====
    output_dir = 'd:/FISH/2026/AICode/RealEstatePolicyAnalysis/output'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, '2026年国家级房地产政策时间线.xlsx')
    
    wb.save(output_path)
    print(f'✓ Excel 文件已生成：{output_path}')
    return output_path


if __name__ == '__main__':
    create_policy_excel()