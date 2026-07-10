"""
TouristAgent — 景区智能导游
继承 BaseAgent，只定义角色 prompt、工具和前后处理。
"""
import re
import logging
from typing import List, Dict, Optional, Callable

from app.core.base_agent import BaseAgent, AgentResult
from app.core.tools import AVAILABLE_TOOLS, make_plan_tools
from app.services.rag import retrieve_context

logger = logging.getLogger(__name__)


# ==================== 精简后的 System Prompt ====================

TOURIST_SYSTEM_PROMPT = """你是一个专业的景区智能导游，热情友好、知识丰富。

工作原则：
1. 涉及景区信息（景点介绍、门票、交通、活动、规定等）→ 必须用 search_knowledge_base 查询
2. 个性化推荐（"推荐景点""还有什么没去"）→ 必须先 get_my_visits 查记录，再 search_knowledge_base 查详情
3. 路线规划（"怎么走""路线"）→ 直接用 plan_route_on_map 或 plan_multi_route_on_map
4. 简单问候闲聊 → 直接友好回复，不调用工具
5. 知识库无结果 → 诚实告知，绝不编造
6. 【严禁幻觉】表演时间、门票价格、开放时间、联系电话等具体数字绝对不能凭记忆或历史对话编造，
   必须通过 search_knowledge_base 确认。知识库查不到就说"请咨询工作人员"，不要给假数字。
   历史对话中的数字可能不准确，不可直接引用。
7. 【专有名词】雕塑名、建筑名、活动名必须与知识库原文一致。如"天下第一掌"不能改成"拈花微笑"。

标点符号规则：
只能使用口语标点：，。？！；：、""''。
禁止使用：括号【】、书名号《》、破折号——、省略号……、波浪线～、星号*、井号#、斜杠/、反引号`。

动作标记规则：
每次 Final Answer 必须带 [动作:xxx] 标记。
可选动作: nod(点头肯定) / wave(挥手欢迎) / invite(邀请手势) / reject(摇头否定) / think(思考) / explain(解释说明) / celebrate(庆祝) / sad(悲伤)
例：Final Answer: [动作:wave] 大家好！欢迎来到灵山胜境！

视频标记规则（可选）：
涉及具体景点时可带 [视频:景点ID] 播放视频。
景点ID: LS-001~LS-016（灵山胜境）或 NH-001~NH-004（拈花湾）。
例：Final Answer: [动作:invite][视频:LS-006] 九龙灌浴是灵山胜境最精彩的动态景观...

其他：
若用户消息附带经纬度（如"(当前用户经纬度: 纬度..., 经度...)"），且需查天气，必须使用这些经纬度调用 get_weather。"""


# ==================== 标点清理 ====================

def _clean_punctuation(text: str) -> str:
    """
    移除 AI 回复中的非口语标点符号，仅保留常用口语标点。
    同时保护 [动作:xxx] 和 [视频:xxx] 结构标记。
    """
    markers = []

    def _save(m):
        markers.append(m.group(0))
        return f'\x00MK{len(markers)-1}\x00'

    text = re.sub(r'\[动作:\w+\]', _save, text)
    text = re.sub(r'\[视频:[\w-]+\]', _save, text)

    # 保留中文 + 英文字母数字 + 空格换行 + 常用口语标点 + 标记占位符
    text = re.sub(
        r'[^一-鿿'
        r'㐀-䶿'
        r'a-zA-Z0-9'
        r'\s'
        r'。，？！；：""''、'
        r'\.'
        r'\-'
        r':：'       # 保留中英文冒号（时间格式如 10:30 需要）
        r'\x00'
        r']+',
        '',
        text
    )
    text = re.sub(r'\-{2,}', '。', text)

    for i, m in enumerate(markers):
        text = text.replace(f'\x00MK{i}\x00', m)
    return text.strip()


def _ensure_action_marker(text: str) -> str:
    """确保每个回答以 [动作:xxx] 开头"""
    if re.search(r'\[动作:\w+\]', text):
        return text
    # 默认添加 explain 动作
    return f"[动作:explain] {text}"


# ==================== TouristAgent ====================

class TouristAgent(BaseAgent):
    """
    景区智能导游 Agent。

    使用方式:
        agent = TouristAgent(db=db, tourist_id=123)
        result = agent.run("九龙灌浴怎么走？")
        print(result.final_answer)
    """

    def __init__(
        self,
        db=None,
        tourist_id: int = None,
        memory_manager=None,        # 新增：支持外部注入 MemoryManager
        max_iterations: int = None,
        verbose: bool = False,
    ):
        super().__init__(
            name="tourist",
            max_iterations=max_iterations,
            temperature=0.3,
            max_tokens=2048,
            verbose=verbose,
        )
        self.db = db
        self.tourist_id = tourist_id
        self._memory_manager = memory_manager  # 外部注入的 MemoryManager

    # ---- 子类覆盖 ----

    def _get_memory_manager(self):
        """返回 MemoryManager，优先使用外部注入的实例"""
        if self._memory_manager:
            return self._memory_manager
        if self.db and self.tourist_id:
            from app.core.memory import MemoryManager
            self._memory_manager = MemoryManager(self.db, self.tourist_id)
        return self._memory_manager

    # ---- 子类覆盖 ----

    def _get_system_prompt(self) -> str:
        return TOURIST_SYSTEM_PROMPT

    def _build_tools(self, **kwargs) -> List[Dict]:
        """构建游客端工具列表"""
        db = kwargs.get("db", self.db)
        tourist_id = kwargs.get("tourist_id", self.tourist_id)

        tools = AVAILABLE_TOOLS.copy()
        if db is not None and tourist_id is not None:
            tools.extend(make_plan_tools(db, tourist_id))
        return tools

    def _get_rag_retriever(self) -> Optional[Callable]:
        return lambda q: retrieve_context(
            q, top_k=10, return_rich=True, use_cache=True
        )

    def _get_db(self):
        return self.db

    def post_process(self, text: str) -> str:
        """后处理：标点清理 + 动作标记验证"""
        text = _clean_punctuation(text)
        text = _ensure_action_marker(text)
        return text


# ==================== 兼容旧接口 ====================

# 全局 Agent 实例（惰性初始化，兼容旧代码调用方式）
_tourist_agent: Optional[TouristAgent] = None


def _get_agent() -> TouristAgent:
    global _tourist_agent
    if _tourist_agent is None:
        _tourist_agent = TouristAgent()
    return _tourist_agent


def run_agent(question: str, history: list = None, max_iterations: int = None) -> str:
    """兼容旧接口：返回纯文本回答"""
    agent = _get_agent()
    result = agent.run(question, history)
    return result.final_answer


def run_agent_with_thoughts(
    question: str,
    history: list = None,
    max_iterations: int = None,
    optional_tools: list = None,
    verbose: bool = False,
    tourist_id: int = None,  # 用于实时思考流
    mode: str = "normal",    # "normal"=仅RAG | "agent"=完整工具
):
    """
    兼容旧接口：返回 (answer, thoughts, step_logs)。

    注意：BaseAgent 使用 AgentResult，这里做格式转换。
    """
    agent = TouristAgent(verbose=verbose)
    if max_iterations is not None:
        agent.max_iterations = max_iterations

    result = agent.run(
        question=question,
        history=history,
        extra_tools=optional_tools,
        tourist_id=tourist_id,
        mode=mode,
    )
    return result.final_answer, result.thoughts, result.step_logs
