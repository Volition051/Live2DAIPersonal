"""
景区导游技能定义
定义游客端所有可用的技能及其执行计划模板。
"""
from app.core.skills.definitions import Skill, PlanStep
from app.core.skills.registry import get_skill_registry


def register_tourist_skills():
    """注册游客端所有技能"""
    registry = get_skill_registry()
    registry.register_many([
        # ========== 路线规划 ==========
        Skill(
            name="route_planning",
            description="规划两个景点之间的步行路线并在地图上显示",
            triggers=["怎么走", "路线", "规划路线", "导航", "怎么去", "走哪条路", "路径",
                      "之间", "步行", "多远", "距离"],
            system_fragment=(
                "你是路线规划专家。当用户需要规划景点间路线时，"
                "必须使用 plan_route_on_map 工具，不要使用 create_plan。"
                "如果用户没有明确起点和终点，根据上下文推断（如当前位置、最近查询的景点）。"
                "景点名称不要加括号备注（如\"灵山大佛\"而不是\"灵山大佛（灵山胜境）\"）。\n"
                "【重要】表演时间、门票价格、开放时间等具体数字必须通过 search_knowledge_base 查询确认，"
                "绝对不能依赖历史对话中的数字（可能不准确），更不能自行编造。"
                "如果知识库没有查到，就告诉用户\"请咨询工作人员确认\"，不要给具体时间。"
            ),
            tools=["plan_route_on_map", "plan_multi_route_on_map",
                   "get_attraction_boundary", "zoom_to_attraction", "find_attraction_id",
                   "search_knowledge_base"],  # 路线规划也需要查知识库（表演时间、门票等）
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="规划路线并输出结果。如果景点名找不到，用 find_attraction_id 查正确名称，查不到就跳过该景点",
                    tool_hint=None,  # 不限制工具，LLM 自行选择 plan_route_on_map 或 plan_multi_route_on_map
                    expected_output="口语化的路线指引（含距离、步行时间）",
                    max_retries=3,
                ),
            ],
            scope="tourist",
            priority=10,
        ),

        # ========== 个性化推荐 ==========
        Skill(
            name="personalized_recommendation",
            description="根据用户游览记录推荐未去过的景点",
            triggers=["推荐", "有什么好玩", "还有什么没去", "建议", "哪些值得去",
                      "推荐景点", "推荐路线", "一日游", "两天", "行程", "安排"],
            system_fragment=(
                "你是个性化推荐专家。推荐时必须：\n"
                "1. 先调用 get_my_visits 查询用户已游览记录\n"
                "2. 再调用 search_knowledge_base 查询推荐景点的详细信息\n"
                "3. 综合两者给出个性化回答，优先推荐用户未游览过的同类型景点\n"
                "4. 严禁跳过工具直接编造推荐内容"
            ),
            tools=["get_my_visits", "search_knowledge_base",
                   "plan_multi_route_on_map", "get_weather", "get_attraction_boundary"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="查询用户游览记录，了解已去过的景点",
                    tool_hint="get_my_visits",
                    expected_output="用户最近的游览记录列表",
                    validation="获取到了游览记录（可能是空的）",
                ),
                PlanStep(
                    step_id=2,
                    description="根据游览记录和用户偏好，搜索知识库获取推荐景点详情",
                    tool_hint="search_knowledge_base",
                    expected_output="推荐景点的详细信息（介绍、特色、适合人群）",
                    depends_on=[1],
                ),
                PlanStep(
                    step_id=3,
                    description="综合用户偏好和景点信息，生成个性化推荐回答",
                    expected_output="包含推荐理由、景点特色、游玩建议的口语化推荐",
                    depends_on=[2],
                    validation="推荐中包含未被游览过的景点，且有数据支撑",
                ),
            ],
            scope="tourist",
            priority=9,
        ),
        # ========== 景区知识问答 ==========
        Skill(
            name="knowledge_qa",
            description="查询景区知识库回答景点介绍、政策规定等问题",
            triggers=["介绍", "讲解", "视频", "历史", "门票", "开放时间", "价格", "规定",
                      "禁止", "须知", "设施", "服务", "联系方式", "地址", "电话",
                      "灵山", "拈花", "梵宫", "大佛", "九龙", "等级", "景点",
                      "是什么", "什么意思", "在哪里", "文化", "佛教", "建筑",
                      "播放", "显示", "怎么样", "如何", "有什么"],
            system_fragment=(
                "你是景区知识专家。回答规则：\n"
                "1. 必须用 search_knowledge_base 查询后再回答\n"
                "2. 如果用户要播放视频，用 find_attraction_id 查景点ID，在回答中加 [视频:景点ID]\n"
                "3. 知识库返回空结果时，明确告知用户'知识库暂未收录该信息'\n"
                "4. 绝对禁止根据自身知识编造具体数字或条款\n"
                "5. 回答时使用口语化中文，不要用 Markdown 格式\n"
                "6. 你只负责讲解和知识问答，绝对不要规划路线"
            ),
            tools=["search_knowledge_base", "find_attraction_id", "list_attraction_videos"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="搜索知识库并回答。如果用户要看视频或景点介绍：先用 find_attraction_id 查景点ID，再在 Final Answer 中加 [视频:景点ID] 标记",
                    tool_hint=None,
                    expected_output="基于知识库的回答。如涉及具体景点必须带 [视频:景点ID]",
                    max_retries=2,
                ),
            ],
            scope="tourist",
            priority=8,
        ),

        # ========== 天气查询 ==========
        Skill(
            name="weather_query",
            description="查询景区当前天气",
            triggers=["天气", "温度", "下雨", "冷不冷", "热不热", "带伞", "穿衣",
                      "雨", "风", "晒"],
            system_fragment=(
                "你是天气助手。用口语化的方式告知用户天气情况，"
                "并根据天气给出穿衣/带伞等贴心建议。"
                "如果用户消息中附带经纬度，必须使用那些坐标调用 get_weather。"
            ),
            tools=["get_weather"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="获取天气并给出建议：调用 get_weather → 口语化播报天气 → 给出穿衣/出行建议",
                    tool_hint="get_weather",
                    expected_output="包含天气数据+穿衣建议的口语化回答",
                    max_retries=1,
                ),
            ],
            scope="tourist",
            priority=8,
        ),

        # ========== 多景点游览路线 ==========
        Skill(
            name="multi_route_planning",
            description="规划多个景点的游览顺序和路线",
            triggers=["游览顺序", "先逛", "怎么逛", "怎么玩", "游览路线",
                      "多个景点", "先去", "再去", "全部逛"],
            system_fragment=(
                "你是游览路线规划专家。规划多个景点路线时：\n"
                "1. 使用 plan_multi_route_on_map 规划最优顺序\n"
                "2. 结合 search_knowledge_base 给每个景点做简短介绍\n"
                "3. 给出合理的游览时间建议"
            ),
            tools=["plan_multi_route_on_map", "plan_route_on_map",
                   "search_knowledge_base", "find_attraction_id", "zoom_to_attraction"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="确认用户想游览的景点列表",
                    expected_output="明确的景点名称列表",
                ),
                PlanStep(
                    step_id=2,
                    description="直接用景点名称调用 plan_multi_route_on_map 绘制路线（景点名用逗号分隔，不需要先查ID）",
                    tool_hint="plan_multi_route_on_map",
                    expected_output="地图路线已绘制，返回游览顺序和总距离",
                    depends_on=[1],
                    max_retries=1,
                ),
                PlanStep(
                    step_id=3,
                    description="查询每个景点的简介",
                    tool_hint="search_knowledge_base",
                    expected_output="各景点的简要介绍",
                    depends_on=[2],
                ),
                PlanStep(
                    step_id=4,
                    description="汇总游览计划：顺序 + 每站简介 + 时间建议",
                    expected_output="完整的游览计划报告",
                    depends_on=[3],
                ),
            ],
            scope="tourist",
            priority=9,
        ),

        # ========== 简单闲聊（兜底）==========
        Skill(
            name="casual_chat",
            description="简单问候、闲聊，不需要调用工具",
            triggers=["你好", "在吗", "谢谢", "再见", "hi", "hello", "好的", "早"],
            system_fragment=(
                "你是友好热情的景区导游。简单问候和闲聊时直接回复，"
                "口语化、亲切，不需要调用任何工具。"
            ),
            tools=[],
            plan_template=[],  # 无计划 = 直接回答
            engine="direct",
            scope="tourist",
            priority=0,  # 最低优先级，只有没其他技能匹配时才用
        ),
    ])


def register_admin_skills():
    """注册管理端所有技能"""
    registry = get_skill_registry()
    registry.register_many([
        # ========== 游客统计报告 ==========
        Skill(
            name="visitor_stats_report",
            description="查询并汇总游客统计数据",
            triggers=["统计", "游客", "客流", "热门", "满意度", "消费", "性别", "年龄",
                      "报告", "运营", "数据", "分布", "排行"],
            system_fragment=(
                "你是数据分析助手。生成统计报告时：\n"
                "1. 先确定需要哪些维度的数据\n"
                "2. 依次调用相应工具获取数据\n"
                "3. 汇总时用简洁中文呈现，突出关键数字和趋势"
            ),
            tools=["visitor_gender_stats", "visitor_age_stats", "top_attractions",
                   "monthly_visitors", "spending_avg", "satisfaction_stats"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="分析问题，确定需要哪些统计维度",
                    expected_output="明确需要的统计指标列表",
                ),
                PlanStep(
                    step_id=2,
                    description="依次查询所需统计数据",
                    expected_output="各项统计数据",
                    depends_on=[1],
                ),
                PlanStep(
                    step_id=3,
                    description="汇总数据，生成结构化报告",
                    expected_output="清晰的数据报告",
                    depends_on=[2],
                ),
            ],
            scope="admin",
            priority=10,
        ),

        # ========== 知识库管理 ==========
        Skill(
            name="knowledge_base_management",
            description="查看和管理知识库状态",
            triggers=["知识库", "文档", "向量", "索引", "chunk"],
            system_fragment=(
                "你是知识库管理助手。查询知识库状态时使用相应工具获取真实数据。"
            ),
            tools=["knowledge_doc_list", "knowledge_stats", "system_health"],
            plan_template=[],
            scope="admin",
            priority=8,
        ),

        # ========== 系统健康检查 ==========
        Skill(
            name="system_health_check",
            description="检查系统各组件的健康状态",
            triggers=["健康", "状态", "运行", "检查", "系统", "正常"],
            system_fragment=(
                "你是系统运维助手。检查系统健康时使用 system_health 工具。"
            ),
            tools=["system_health"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="调用系统健康检查工具",
                    tool_hint="system_health",
                    expected_output="数据库和向量库状态",
                ),
                PlanStep(
                    step_id=2,
                    description="汇总健康状态并给出建议",
                    expected_output="系统健康报告",
                    depends_on=[1],
                ),
            ],
            scope="admin",
            priority=8,
        ),

        # ========== 项目文件查看 ==========
        Skill(
            name="project_explorer",
            description="查看项目文件结构和内容",
            triggers=["文件", "代码", "目录", "结构", "项目", "查看", "读取",
                      "源码", "实现", "函数", "class", "def", "import"],
            system_fragment=(
                "你是代码浏览助手。查看项目文件时：\n"
                "1. 先用 list_project_structure 了解目录结构\n"
                "2. 再用 read_file_content 查看具体文件\n"
                "3. 回答时注明文件路径和行号"
            ),
            tools=["list_project_structure", "read_file_content",
                   "project_structure", "update_project_description"],
            plan_template=[
                PlanStep(
                    step_id=1,
                    description="了解项目目录结构，定位目标文件",
                    tool_hint="list_project_structure",
                    expected_output="相关目录的文件结构",
                ),
                PlanStep(
                    step_id=2,
                    description="读取目标文件内容",
                    tool_hint="read_file_content",
                    expected_output="文件内容",
                    depends_on=[1],
                ),
                PlanStep(
                    step_id=3,
                    description="根据文件内容回答用户问题",
                    expected_output="基于代码的准确回答",
                    depends_on=[2],
                ),
            ],
            scope="admin",
            priority=7,
        ),
    ])
