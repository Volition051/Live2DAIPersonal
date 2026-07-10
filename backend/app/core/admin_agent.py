"""
AdminAgent — 景区系统管理员助手
继承 BaseAgent，只定义角色 prompt 和管理工具。
"""
import re
import logging
from typing import List, Dict

from app.core.base_agent import BaseAgent, AgentResult

logger = logging.getLogger(__name__)


# ==================== 精简后的 System Prompt ====================

ADMIN_SYSTEM_PROMPT = """你是一个景区系统管理员助手，帮助管理员查询游客统计数据、知识库状态、系统健康等信息。

工作原则：
1. 日常问候或与系统数据无关的问题 → 直接回复，不调用工具
2. 涉及景区运营数据、知识库、系统状态 → 必须调用相应工具获取真实数据
3. 复杂需求（"生成运营周报""统计报告"等）→ 按技能计划逐步执行

标点符号规则：
只能使用常用口语标点：，。？！；：、""''。
禁止使用：括号【】、书名号《》、破折号——、省略号……、波浪线～、星号*、井号#等特殊符号。

输出要求：
简洁中文，不使用表情符号，数据准确有据。"""


# ==================== 标点清理 ====================

def _clean_punctuation(text: str) -> str:
    """Remove non-verbal punctuation marks from AI responses"""
    # Keep: Chinese chars, ASCII letters/digits, whitespace, common punctuation
    allowed = (
        r'一-鿿㐀-䶿'
        r'a-zA-Z0-9'
        r'\s'
        r'。，！？；：“”‘’、'
        r'.\-'
        r':：'  # 保留冒号（时间格式 10:30）
    )
    text = re.sub(f'[^{allowed}]+', '', text)
    text = re.sub(r'-{2,}', '。', text)  # Replace long dashes with period
    return text.strip()


# ==================== AdminAgent ====================

class AdminAgent(BaseAgent):
    """
    管理员助手 Agent。

    使用方式:
        agent = AdminAgent(db=db)
        result = agent.run("今天客流怎么样？")
        print(result.final_answer)
    """

    def __init__(
        self,
        db=None,
        max_iterations: int = None,
        verbose: bool = False,
    ):
        super().__init__(
            name="admin",
            max_iterations=max_iterations,
            temperature=0.3,
            max_tokens=1024,
            verbose=verbose,
        )
        self.db = db

    # ---- 子类覆盖 ----

    def _get_system_prompt(self) -> str:
        return ADMIN_SYSTEM_PROMPT

    def _build_tools(self, **kwargs) -> List[Dict]:
        """构建管理端工具列表"""
        db = kwargs.get("db", self.db)
        return _build_admin_tools(db)

    def _get_rag_retriever(self):
        return None  # 管理端不用 RAG

    def _get_db(self):
        return self.db

    def post_process(self, text: str) -> str:
        """后处理：标点清理"""
        return _clean_punctuation(text)


# ==================== 工具构建 ====================

def _build_admin_tools(db):
    """构建管理端工具列表（懒加载避免循环导入）"""
    from app.core.admin_tools import (
        query_visitor_gender_stats,
        query_visitor_age_stats,
        query_top_attractions,
        query_monthly_visitors,
        query_spending_avg,
        query_satisfaction_stats,
        query_knowledge_doc_list,
        query_knowledge_stats,
        get_system_health,
        list_project_structure,
        read_file_content,
        get_annotated_project_structure,
        update_file_description,
        create_plan,
        get_current_plan,
        update_step_status,
    )

    if db is None:
        return []

    return [
        {
            "name": "visitor_gender_stats",
            "description": "查询游客性别分布",
            "func": lambda **kw: query_visitor_gender_stats(db),
            "params": {},
        },
        {
            "name": "visitor_age_stats",
            "description": "查询游客年龄分布",
            "func": lambda **kw: query_visitor_age_stats(db),
            "params": {},
        },
        {
            "name": "top_attractions",
            "description": "热门景点排行，limit默认10",
            "func": lambda **kw: query_top_attractions(db, limit=kw.get("limit", 10)),
            "params": {"limit": "int"},
        },
        {
            "name": "monthly_visitors",
            "description": "月度客流量",
            "func": lambda **kw: query_monthly_visitors(db),
            "params": {},
        },
        {
            "name": "spending_avg",
            "description": "平均消费组成",
            "func": lambda **kw: query_spending_avg(db),
            "params": {},
        },
        {
            "name": "satisfaction_stats",
            "description": "满意度分布",
            "func": lambda **kw: query_satisfaction_stats(db),
            "params": {},
        },
        {
            "name": "knowledge_doc_list",
            "description": "知识库文档列表",
            "func": lambda **kw: query_knowledge_doc_list(db),
            "params": {},
        },
        {
            "name": "knowledge_stats",
            "description": "知识库整体统计",
            "func": lambda **kw: query_knowledge_stats(db),
            "params": {},
        },
        {
            "name": "system_health",
            "description": "系统健康检查",
            "func": lambda **kw: get_system_health(db),
            "params": {},
        },
        {
            "name": "list_project_structure",
            "description": "查看项目文件目录结构。参数 root_path（可选），max_depth（可选）",
            "func": lambda **kw: list_project_structure(
                root_path=kw.get("root_path"),
                max_depth=kw.get("max_depth"),
            ),
            "params": {"root_path": "string (可选)", "max_depth": "int (可选)"},
        },
        {
            "name": "read_file_content",
            "description": "读取项目文件内容。参数 file_path（必填），max_lines（可选，默认100）",
            "func": lambda **kw: read_file_content(
                file_path=kw.get("file_path"),
                max_lines=kw.get("max_lines", 100),
            ),
            "params": {"file_path": "string (必填)", "max_lines": "int (可选)"},
        },
        {
            "name": "project_structure",
            "description": "查看带描述的项目文件结构（从数据库读取）。参数 root_path（可选），max_depth（可选）",
            "func": lambda **kw: get_annotated_project_structure(
                db,
                root_path=kw.get("root_path", "/backend"),
                max_depth=kw.get("max_depth"),
            ),
            "params": {"root_path": "string (可选)", "max_depth": "int (可选)"},
        },
        {
            "name": "update_project_description",
            "description": "修改项目文件或文件夹的描述。参数 file_path（必填），description（必填）",
            "func": lambda **kw: update_file_description(
                db, kw['file_path'], kw['description']
            ),
            "params": {"file_path": "string", "description": "string"},
        },
        {
            "name": "create_plan",
            "description": "创建任务计划。参数 title (字符串)，steps (字符串列表)",
            "func": lambda **kw: create_plan(
                db, kw['title'], kw['steps'], owner="admin"
            ),
            "params": {"title": "string", "steps": "list of strings"},
        },
        {
            "name": "get_current_plan",
            "description": "查看当前进行中的任务计划",
            "func": lambda **kw: get_current_plan(db, owner="admin"),
            "params": {},
        },
        {
            "name": "update_step_status",
            "description": "更新计划步骤状态。参数 plan_id, step_order, status, result(可选)",
            "func": lambda **kw: update_step_status(
                db, kw['plan_id'], kw['step_order'],
                kw['status'], kw.get('result', '')
            ),
            "params": {
                "plan_id": "int", "step_order": "int",
                "status": "string", "result": "string (可选)"
            },
        },
    ]


# ==================== 兼容旧接口 ====================

def run_admin_agent(
    question: str,
    history: list,
    db,
    max_iterations: int = None,
):
    """兼容旧接口：返回 (answer, thoughts)"""
    agent = AdminAgent(db=db, max_iterations=max_iterations)
    result = agent.run(question=question, history=history)
    return result.final_answer, result.thoughts
