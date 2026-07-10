"""
BaseAgent — 统一执行引擎
支持 Plan-Execute 优先、ReAct 降级的混合执行模式。
消除 agent.py 和 admin_agent.py 之间 ~80% 的重复代码。
"""
import re
import json
import logging
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field

from app.config import settings
from app.core.client import client, model_name
from app.core.context_builder import ContextBuilder
from app.core.skills.registry import get_skill_registry
from app.core.skills.definitions import Skill, PlanStep

logger = logging.getLogger(__name__)

# ==================== 实时思考流存储 ====================
# 全局字典：user_id → [{type, content, duration_ms}, ...]
# 前端轮询此数据，实现 DeepSeek 式渐进思考显示
_live_thoughts: Dict[str, List[Dict]] = {}
_live_thoughts_lock = None  # 惰性导入 threading


def _get_live_lock():
    global _live_thoughts_lock
    if _live_thoughts_lock is None:
        import threading
        _live_thoughts_lock = threading.Lock()
    return _live_thoughts_lock


def clear_live_thoughts(user_id: str):
    """清除指定用户的实时思考"""
    with _get_live_lock():
        _live_thoughts.pop(user_id, None)


def get_live_thoughts(user_id: str) -> List[Dict]:
    """获取指定用户的实时思考（非阻塞）"""
    with _get_live_lock():
        return _live_thoughts.get(user_id, []).copy()


# ==================== 数据结构 ====================

@dataclass
class AgentResult:
    """Agent 执行结果"""
    final_answer: str
    thoughts: List[Dict] = field(default_factory=list)
    step_logs: List[Dict] = field(default_factory=list)
    skill_used: Optional[str] = None
    plan_executed: bool = False
    total_steps: int = 0
    tool_calls: int = 0


# ==================== ReAct 输出格式 ====================

DEFAULT_REACT_FORMAT = """输出格式：
Question: 用户的问题
Thought: 你的思考过程
Action: 工具名称（需要调用工具时）
Action Input: JSON 格式的参数（需要调用工具时）
Observation: 工具返回结果（系统填充）
... (上述 Thought/Action/Action Input/Observation 可循环多次)
Thought: 我现在知道最终答案了
Final Answer: 最终回复"""


# ==================== BaseAgent ====================

class BaseAgent:
    """
    统一 Agent 引擎。

    执行流程:
        1. Skill 匹配 → 加载领域 prompt + 工具筛选 + 计划模板
        2. 上下文构建 → ContextBuilder 统一管理
        3. 执行:
           - 有 Skill + Plan → Plan-Execute 模式（逐步执行，每步验证）
           - 无 Plan → ReAct 模式（传统 Thought/Action/Observation 循环）
        4. 后处理 → 标点清理、动作标记注入等

    子类只需覆盖:
        - name: str
        - _build_tools() → List[Dict]
        - _get_rag_retriever() → Optional[Callable]
        - pre_process(text) → str  (可选)
        - post_process(text) → str (可选)
    """

    def __init__(
        self,
        name: str = "base",
        max_iterations: int = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        verbose: bool = False,
    ):
        self.name = name
        self.max_iterations = max_iterations or settings.AGENT_MAX_ITERATIONS
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.agent_scope = name  # "tourist" 或 "admin"，用于技能过滤

        # 技能注册中心（全局单例）
        self.skill_registry = get_skill_registry()

        # 上下文构建器（子类通过 _get_rag_retriever 注入）
        self._context_builder: Optional[ContextBuilder] = None

    # ==================== 子类覆盖点 ====================

    def _get_system_prompt(self) -> str:
        """子类覆盖：返回基础 system prompt"""
        return "你是一个智能助手。"

    def _build_tools(self, **kwargs) -> List[Dict]:
        """子类覆盖：返回工具列表（dict 格式，兼容旧代码）"""
        return []

    def _get_rag_retriever(self) -> Optional[Callable]:
        """子类覆盖：返回 RAG 检索函数"""
        return None

    def _get_db(self):
        """子类覆盖：返回数据库会话（用于 ContextBuilder 注入计划）"""
        return None

    def _get_memory_manager(self):
        """子类覆盖：返回 MemoryManager 实例（用于上下文构建）"""
        return None

    def pre_process(self, text: str) -> str:
        """子类覆盖：执行前预处理（如清理特殊标记）"""
        return re.sub(r'<\|.*?\|>', '', text).strip()

    def post_process(self, text: str) -> str:
        """子类覆盖：执行后处理（如标点清理、动作标记验证）"""
        return text

    @staticmethod
    def _clean_answer(text: str) -> str:
        """从回复文本中剥离 ReAct 工具调用语法标记（Action/Action Input 等）。

        用于强制生成结果或非标准输出格式的最终回答，
        确保泄露的工具调用格式不会出现在用户看到的内容中。
        """
        if not text:
            return text
        # 按行处理：移除以 ReAct 标记开头的整行（Action:/Action Input:/Thought: 等）
        cleaned_lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            # 跳过 ReAct 格式行和非功能性残留
            if re.match(
                r'^(Action\s*(Input)?|Thought|Question|Observation)\s*[:：]',
                stripped
            ):
                continue
            cleaned_lines.append(line)
        result = '\n'.join(cleaned_lines).strip()
        # 收尾：清理可能残留的多余空行
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result

    # ==================== 计时辅助 ====================

    def _now_ms(self) -> int:
        """获取高精度时间戳（毫秒），使用 perf_counter 避免同一秒内重复"""
        import time
        return int(time.perf_counter() * 1000)

    def _record_thought(
        self,
        thoughts: List[Dict],
        step: int,
        thought_type: str,
        content: str,
        start_time_ms: int,
    ) -> None:
        """记录一条思考步骤，自动附加耗时，并推送到实时流"""
        duration = self._now_ms() - start_time_ms
        raw = content
        # 清理后端技术信息（仅对 thought 和 final_answer 类型）
        if thought_type in ('thought', 'final_answer'):
            content = str(content)
            # ReAct 格式前缀
            for prefix in ['Thought:', 'Action Input:', 'Action:', 'Observation:', 'Final Answer:', 'Question:']:
                content = content.replace(prefix, '')
            # 动作标记
            content = re.sub(r'\[动作:\w+\]', '', content)
            # 内嵌 JSON
            content = re.sub(r'\{[^{}]*"[^"]+"\s*:\s*"[^"]*"[^{}]*\}', '', content)
            # 原始工具名（snake_case 函数名）
            content = re.sub(r'`?\b[a-z]+_[a-z]+(?:_[a-z]+)*\b`?', '', content)
            # 清理残留虚词（如"必须用 查询"→"必须查询"）
            content = re.sub(r'(用|调用|通过|使用)\s{1,2}(?=[，。！？\s]|$)', '', content)
            content = re.sub(r'\s{2,}', ' ', content)
            content = re.sub(r'，\s*，', '，', content)
            content = re.sub(r'`{2,}', '', content)
            content = content.strip()
        # observation 类型自动格式化为可读文本
        if thought_type == "observation":
            content = self._format_observation(content)
        item = {
            "step": step,
            "type": thought_type,
            "content": content,
            "duration_ms": duration,
        }
        # observation 附带完整原文供前端展开（保留足够内容显示多条结果）
        if thought_type == "observation" and raw != content:
            item["raw_content"] = raw[:2000]
        thoughts.append(item)
        # 推送到实时思考流（供前端轮询）
        uid = getattr(self, '_live_user_id', None)
        if uid:
            with _get_live_lock():
                if uid not in _live_thoughts:
                    _live_thoughts[uid] = []
                _live_thoughts[uid].append(item)

    # ==================== 主入口 ====================

    def run(
        self,
        question: str,
        history: List[Dict] = None,
        extra_tools: List[Dict] = None,
        **tool_kwargs,
    ) -> AgentResult:
        """
        执行用户问题。

        Args:
            question: 用户问题
            history: 对话历史
            extra_tools: 额外工具（运行时动态注入）
            **tool_kwargs: 传递给 _build_tools 的参数（如 db, tourist_id）

        Returns:
            AgentResult: 包含 final_answer, thoughts, step_logs 的结果对象
        """
        history = history or []
        agent_mode = tool_kwargs.get('mode', 'normal') if tool_kwargs else 'normal'

        # ---- normal 模式：仅 RAG，跳过技能与计划，快速问答 ----
        if agent_mode == 'normal':
            return self._execute_normal_mode(
                question=question, history=history, **tool_kwargs
            )

        # ---- 阶段 1: Skill 匹配 ----
        matched_skill = self._match_skill(question)

        # ---- 阶段 2: 构建工具列表 ----
        tools = self._build_tools(**tool_kwargs)
        if extra_tools:
            tools = tools + extra_tools

        # 如果有 Skill 匹配且限制了工具，则筛选
        if matched_skill and matched_skill.tools:
            active_tools = self._filter_tools_by_skill(tools, matched_skill)
        else:
            active_tools = tools

        # ---- 阶段 3: 构建上下文 ----
        system_content = self._build_system_content(matched_skill, active_tools)
        rag = self._get_rag_retriever()
        db = self._get_db()
        memory_mgr = self._get_memory_manager()

        context_builder = ContextBuilder(
            memory_manager=memory_mgr,
            rag_retriever=rag,
            db=db,
        )
        context = context_builder.build(
            user_query=question,
            conversation_history=history,
            system_instructions=system_content,
            context_hint=matched_skill.name if matched_skill else "",
        )

        # 设置实时思考流用户 ID（从 tool_kwargs 中提取）
        self._live_user_id = tool_kwargs.get('tourist_id') if tool_kwargs else None
        if self._live_user_id:
            self._live_user_id = f"tourist_{self._live_user_id}"
            clear_live_thoughts(self._live_user_id)

        # 验证技能所需的工具是否可用（避免游客匹配到管理端技能）
        if matched_skill and matched_skill.tools:
            available_names = {t["name"] for t in active_tools}
            required = set(matched_skill.tools)
            if not required.intersection(available_names):
                logger.warning(
                    f"技能 '{matched_skill.name}' 需要的工具 {required} "
                    f"均不可用（可用: {available_names}），降级为 ReAct 模式"
                )
                matched_skill = None  # 丢弃不匹配的技能

        # ---- 阶段 4: 执行 ----
        if matched_skill and matched_skill.has_plan():
            logger.info(f"[{self.name}] 技能 '{matched_skill.name}' 激活，Plan-Execute 模式")
            result = self._execute_plan(
                skill=matched_skill,
                question=question,
                context=context,
                tools=active_tools,
                history=history,
            )
        else:
            logger.info(
                f"[{self.name}] "
                f"{'技能 ' + matched_skill.name + ' 无计划模板' if matched_skill else '无匹配技能'}，"
                f"ReAct 模式"
            )
            result = self._execute_react(
                question=question,
                context=context,
                tools=active_tools,
                history=history,
            )

        # ---- 阶段 5: 后处理 ----
        result.final_answer = self.post_process(result.final_answer)
        result.skill_used = matched_skill.name if matched_skill else None

        logger.info(
            f"[{self.name}] 完成。技能: {result.skill_used or '无'}, "
            f"计划执行: {result.plan_executed}, "
            f"总步数: {result.total_steps}, 工具调用: {result.tool_calls}"
        )
        return result

    # ==================== Normal 模式（仅 RAG 快速问答）====================

    def _execute_normal_mode(
        self, question: str, history: List[Dict] = None, **tool_kwargs
    ) -> AgentResult:
        """
        轻量模式：服务端先查知识库，LLM 只负责基于结果回答。
        零幻觉 — LLM 只能看到检索结果，看不到自己的训练数据。
        速度目标：< 2 秒（1 次 RAG + 1 次 LLM）。
        """
        history = history or []
        start_time = self._now_ms()
        thoughts: List[Dict] = []

        # ① 服务端直接查知识库（不经过 LLM，确保真实检索）
        # 清理前端和路由追加的噪声文本
        query_text = question
        query_text = re.sub(r'【[^】]*】', '', query_text)
        query_text = re.sub(r'\(当前用户经纬度[^)]*\)', '', query_text)
        query_text = re.sub(r'\n[\s\S]*', '', query_text)
        query_text = query_text.strip()
        # 规则查询扩展：疑问词 → 实体词（零延迟，修"哪年→2003年"检索鸿沟）
        QUERY_EXPAND = {
            '哪年': '年份 历史 建立 建成 开放 时间',
            '几点': '时间 开放 营业',
            '多少钱': '价格 费用 元',
            '多久': '时长 时间 分钟',
            '多高': '高度 米',
        }
        for qword, expand in QUERY_EXPAND.items():
            if qword in query_text:
                query_text = f"{query_text} {expand}"
                break
        # 短查询自动补景区上下文
        greetings = {'你好','在吗','谢谢','再见','hi','hello','好的','早','晚上好','嗯','哦'}
        skip_search = query_text.strip().lower() in greetings
        self._record_thought(thoughts, 1, "thought", f"搜索知识库: {query_text[:50]}" if not skip_search else "直接回答（闲聊）", start_time)
        tools = self._build_tools(**tool_kwargs)
        kb_tool = next((t for t in tools if t["name"] == "search_knowledge_base"), None)
        kb_results = ""
        if kb_tool and not skip_search:
            try:
                kb_results = kb_tool["func"](query_text)
                chunk_count = kb_results.count("[来源:") if kb_results else 0
                self._record_thought(thoughts, 1, "action", f"查询知识库 · {chunk_count} 条结果", start_time)
                self._record_thought(thoughts, 1, "observation", kb_results, start_time)
            except Exception as e:
                kb_results = f"知识库查询失败: {e}"
        elif not skip_search:
            # 降级：用 RAG 检索函数
            rag = self._get_rag_retriever()
            if rag:
                try:
                    chunks = rag(query_text)
                    kb_results = "\n---\n".join(chunks) if chunks else ""
                    self._record_thought(thoughts, 1, "action", f"检索知识库 · {len(chunks)} 条结果", start_time)
                    self._record_thought(thoughts, 1, "observation", kb_results, start_time)
                except Exception:
                    pass

        # ② LLM 回答（闲聊走简单 prompt，知识查询走严格 prompt）
        if skip_search:
            chat_prompt = "你是景区智能导游，友好热情。简单问候直接回复，2-3句话即可。"
            messages = [
                {"role": "system", "content": chat_prompt},
                {"role": "user", "content": question},
            ]
        else:
            strict_prompt = (
                "你是景区知识助手。下面是从知识库检索到的内容，这是你唯一的信息来源。\n"
                "【严格规则 — 违反一条即视为错误】\n"
                "1. 只能基于下方知识库内容回答，禁止使用你自己的知识补充任何数字、时间、价格、日期、年份\n"
                "2. 知识库写\"4-5场\"就答\"4到5场\"，不要改成\"4场\"或添加具体时间\n"
                "3. 专有名词（雕塑名、建筑名、活动名）必须与知识库原文一字不差，禁止自行命名\n"
                "   例：知识库写\"天下第一掌\"，你就答\"天下第一掌\"，不能改成\"拈花微笑\"\n"
                "4. 时间格式必须用冒号（如 10:30），禁止写成 1030\n"
                "5. 知识库没直接答案但有相关信息时，引用相关信息（如\"建议9点前入园\"）\n"
                "6. 完全查不到时，说\"知识库暂未收录，请咨询工作人员\"，禁止凭记忆猜测\n"
                "7. 回答简洁口语化，2-3句话，不用 Markdown"
            )
            knowledge = f"\n\n=== 知识库检索结果 ===\n{kb_results}" if kb_results else "\n\n（知识库未返回相关内容）"
            messages = [
                {"role": "system", "content": strict_prompt + knowledge},
                {"role": "user", "content": question + "\n\n请严格基于以上知识库内容回答。"},
            ]

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,  # 低温度减少编造
                max_tokens=min(self.max_tokens, 1024),
            )
            final = self.pre_process(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"[{self.name}] Normal LLM失败: {e}")
            return AgentResult(final_answer="抱歉，服务暂时不可用。")

        if "Final Answer:" in final:
            final = final.split("Final Answer:")[-1].strip()
        final = self.post_process(final)

        self._record_thought(thoughts, 1, "final_answer", final[:200], start_time)
        return AgentResult(
            final_answer=final,
            thoughts=thoughts,
            total_steps=1,
            tool_calls=1 if kb_results else 0,
        )

    # ==================== Skill 匹配 ====================

    def _match_skill(self, question: str) -> Optional[Skill]:
        """匹配最合适的技能（只用原始问题，排除上下文噪声）"""
        # 只取第一行，去掉前端前缀
        clean_q = question.split('\n')[0].strip()
        clean_q = re.sub(r'【[^】]*】', '', clean_q).strip()
        return self.skill_registry.match_first(clean_q, scope=self.agent_scope)

    # ==================== 上下文构建 ====================

    def _build_system_content(
        self, skill: Optional[Skill], tools: List[Dict]
    ) -> str:
        """
        构建最终的 system prompt。
        基础 prompt + Skill 领域知识 + 工具描述 + 输出格式。
        """
        base = self._get_system_prompt()
        parts = [base]

        # 注入 Skill 的领域知识
        if skill and skill.system_fragment:
            parts.append(f"\n[当前技能: {skill.name} — {skill.description}]")
            parts.append(skill.system_fragment)

            # 注入执行计划摘要
            if skill.has_plan():
                parts.append(f"\n{skill.get_plan_summary()}")

        # 工具描述
        tools_desc = self._format_tools_description(tools)
        tool_names = ", ".join([t["name"] for t in tools])
        parts.append(f"\n可用工具 ({len(tools)} 个):\n{tools_desc}")

        # 输出格式说明
        parts.append(f"\n{DEFAULT_REACT_FORMAT}")

        return "\n".join(parts)

    @staticmethod
    def _format_tools_description(tools: List[Dict]) -> str:
        """格式化工具列表为 LLM 可读文本"""
        lines = []
        for t in tools:
            params_str = ""
            if t.get("params"):
                params_str = ", ".join(
                    f"{k}:{v}" for k, v in t["params"].items()
                )
                params_str = f"  (参数: {params_str})"
            lines.append(f"- {t['name']}: {t['description']}{params_str}")
        return "\n".join(lines)

    @staticmethod
    def _filter_tools_by_skill(
        tools: List[Dict], skill: Skill
    ) -> List[Dict]:
        """根据技能声明的工具列表筛选"""
        if not skill.tools:
            return tools
        return [t for t in tools if t["name"] in skill.tools]

    # ==================== Plan-Execute 模式 ====================

    def _execute_plan(
        self,
        skill: Skill,
        question: str,
        context: str,
        tools: List[Dict],
        history: List[Dict],
    ) -> AgentResult:
        """
        按技能的计划模板逐步执行。
        每步：构建步骤专用 prompt → 执行（可能是单轮 ReAct 子循环）→ 验证 → 记录
        """
        plan = skill.plan_template
        step_results: Dict[int, str] = {}
        thoughts: List[Dict] = []
        step_logs: List[Dict] = []
        tool_calls_total = 0
        plan_start = self._now_ms()  # 计划执行计时起点

        logger.info(f"[{self.name}] Plan-Execute 开始，共 {len(plan)} 步")

        for step_idx, step in enumerate(plan):
            logger.info(
                f"[{self.name}] 执行步骤 {step.step_id}/{len(plan)}: {step.description}"
            )

            # 检查依赖
            for dep_id in step.depends_on:
                if dep_id not in step_results:
                    logger.warning(
                        f"[{self.name}] 步骤 {step.step_id} 依赖步骤 {dep_id} 未完成，跳过"
                    )
                    continue

            # 构建步骤上下文
            step_context = self._build_step_context(
                skill=skill,
                step=step,
                question=question,
                base_context=context,
                previous_results=step_results,
            )

            # 筛选当前步骤的工具（只保留 hint 指定的 + 基础工具）
            step_tools = self._get_step_tools(step, tools)

            # 执行单步（小 ReAct 循环，最多 max_sub_steps 轮）
            step_answer = None
            max_retries = getattr(step, 'max_retries', 1)
            for retry in range(max_retries + 1):
                step_result = self._execute_single_step(
                    step_context=step_context,
                    step_tools=step_tools,
                    step=step,
                    max_sub_steps=6,  # 增加子步数，避免大模型多次工具调用后仍被强制截断
                    start_time_ms=plan_start,
                )
                step_answer = step_result.final_answer
                tool_calls_total += step_result.tool_calls

                # 验证步骤产物
                if self._validate_step_output(step, step_answer):
                    break
                logger.warning(
                    f"[{self.name}] 步骤 {step.step_id} 验证未通过, "
                    f"重试 {retry+1}/{max_retries}"
                )
                # 重试时补充反馈
                step_context += (
                    f"\n[上轮输出验证未通过，请确保: {step.validation}]"
                )

            step_results[step.step_id] = step_answer or ""
            # 收集子步骤的思考过程（duration_ms 已相对于 plan_start）
            if step_result.thoughts:
                thoughts.extend(step_result.thoughts)
            else:
                # 降级：至少生成一条带计时的 thought 记录
                self._record_thought(thoughts, step.step_id, "thought",
                    f"[步骤{step.step_id}] {step.description}", plan_start)
                if step_answer:
                    self._record_thought(thoughts, step.step_id, "final_answer",
                        str(step_answer)[:200], plan_start)
            step_logs.append({
                "round": step.step_id,
                "thought": step.description,
                "action": step.tool_hint or "",
                "obs": str(step_answer)[:200] if step_answer else "",
                "final_answer": str(step_answer)[:200] if step_answer else "",
                "is_repeat": False,
            })

        # ---- 最终汇总（只有多步骤时才额外合成，单步骤直接返回）----
        if len(plan) > 1:
            final_answer = self._synthesize_results(
                skill=skill,
                question=question,
                step_results=step_results,
            )
        elif plan:
            final_answer = step_results.get(plan[0].step_id, "")
        else:
            final_answer = "抱歉，无法完成该任务。"

        return AgentResult(
            final_answer=final_answer,
            thoughts=thoughts,
            step_logs=step_logs,
            plan_executed=True,
            total_steps=len(plan),
            tool_calls=tool_calls_total,
        )

    def _build_step_context(
        self,
        skill: Skill,
        step: PlanStep,
        question: str,
        base_context: str,
        previous_results: Dict[int, str],
    ) -> str:
        """为单个步骤构建上下文"""
        parts = [base_context]

        # 当前步骤目标
        parts.append(f"\n--- 当前步骤 ---")
        parts.append(step.to_prompt_text())

        # 前面步骤的结果
        if previous_results:
            parts.append(f"\n--- 前面步骤结果 ---")
            for sid, sresult in previous_results.items():
                prev_step = skill.get_step(sid)
                label = prev_step.description if prev_step else f"步骤{sid}"
                parts.append(f"[{label}]\n{str(sresult)[:500]}")

        # 原始用户问题
        parts.append(f"\n--- 原始问题 ---\n{question}")

        parts.append(
            f"\n请完成当前步骤并给出结果。"
            f"如果需要调用工具，使用 Thought/Action/Action Input 格式。"
        )
        return "\n".join(parts)

    @staticmethod
    def _get_step_tools(step: PlanStep, all_tools: List[Dict]) -> List[Dict]:
        """
        获取当前步骤适用的工具。
        tool_hint 仅作为建议，始终保留所有工具供 LLM 灵活选择。
        hint 指定的工具会排在前面（便于 LLM 优先关注）。
        """
        if not step.tool_hint:
            return all_tools
        # 将 hint 工具排到最前面，但保留所有工具
        hinted = [t for t in all_tools if t["name"] == step.tool_hint]
        others = [t for t in all_tools if t["name"] != step.tool_hint]
        return hinted + others

    def _execute_single_step(
        self,
        step_context: str,
        step_tools: List[Dict],
        step: PlanStep,
        max_sub_steps: int = 3,
        start_time_ms: int = 0,  # 新增：计时起点
    ) -> AgentResult:
        """单步执行（微缩版 ReAct 循环）"""
        if start_time_ms == 0:
            start_time_ms = self._now_ms()
        messages = [
            {"role": "system", "content": step_context},
            {"role": "user", "content": f"请完成: {step.description}"},
        ]
        tool_calls = 0
        sub_thoughts: List[Dict] = []  # 收集子步骤的思考过程

        for sub_step in range(max_sub_steps):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stop=["Observation:"],
                )
                answer = self.pre_process(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"[{self.name}] 步骤{step.step_id} LLM调用失败: {e}")
                continue

            messages.append({"role": "assistant", "content": answer})

            # 提取 Thought
            thought_match = re.search(r"Thought:\s*(.*)", answer)
            if thought_match:
                self._record_thought(sub_thoughts, step.step_id, "thought", thought_match.group(1).strip(), start_time_ms)

            # 检查是否直接给出答案
            if "Final Answer:" in answer:
                final = answer.split("Final Answer:")[-1].strip()
                # 安全剥离：大模型有时会在 Final Answer 后仍带 Action 标记
                final = self._clean_answer(final)
                self._record_thought(sub_thoughts, step.step_id, "final_answer", final[:200], start_time_ms)
                return AgentResult(
                    final_answer=final,
                    tool_calls=tool_calls,
                    thoughts=sub_thoughts,
                )

            # 检查是否有最终答案标志
            if not self._has_tool_call(answer):
                # 没有工具调用也没有 Final Answer，可能是直接输出
                # 用 _clean_answer 按行剥离 ReAct 标记，只保留正文
                clean = self._clean_answer(answer)
                if clean:
                    self._record_thought(sub_thoughts, step.step_id, "final_answer", clean[:200], start_time_ms)
                    return AgentResult(
                        final_answer=clean,
                        tool_calls=tool_calls,
                        thoughts=sub_thoughts,
                    )

            # 解析并执行工具
            action_match = re.search(r"Action:\s*(.*)", answer)
            input_match = re.search(r"Action Input:\s*(.*)", answer)

            if not action_match or not input_match:
                continue

            action = action_match.group(1).strip()
            input_str = input_match.group(1).strip()

            # 记录工具调用
            self._record_thought(sub_thoughts, step.step_id, "action", f"调用工具: {action}", start_time_ms)
            self._record_thought(sub_thoughts, step.step_id, "action_input", input_str, start_time_ms)

            # 执行工具
            observation = self._call_tool(action, input_str, step_tools)
            tool_calls += 1
            self._record_thought(sub_thoughts, step.step_id, "observation", observation, start_time_ms)
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}",
            })

        # 超出子步数，强制生成答案
        messages.append({
            "role": "user",
            "content": "请基于以上信息，直接用自然语言给出当前步骤的最终结果。不要输出 Action、Action Input 等工具调用格式。",
        })
        try:
            final_resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            final = self.pre_process(final_resp.choices[0].message.content)
            if "Final Answer:" in final:
                final = final.split("Final Answer:")[-1].strip()
            # 强制剥离可能泄露的工具调用格式
            final = self._clean_answer(final)
        except Exception as e:
            logger.error(f"[{self.name}] 步骤{step.step_id} 强制生成失败: {e}")
            final = f"步骤 {step.step_id} 执行超时。"
        self._record_thought(sub_thoughts, step.step_id, "final_answer", final[:200], start_time_ms)
        return AgentResult(final_answer=final, tool_calls=tool_calls, thoughts=sub_thoughts)

    def _validate_step_output(self, step: PlanStep, output: str) -> bool:
        """验证步骤输出是否满足要求"""
        if not step.validation or not output:
            return True  # 无验证标准 = 默认通过
        # 简单的关键词检查（后续可升级为 LLM 验证）
        validation_keywords = step.validation.replace(" ", "")
        output_clean = output.replace(" ", "")
        # 至少有一半的关键词出现在输出中
        match_count = sum(
            1 for kw in validation_keywords
            if kw in output_clean
        )
        return match_count >= max(1, len(validation_keywords) // 3)

    def _synthesize_results(
        self,
        skill: Skill,
        question: str,
        step_results: Dict[int, str],
    ) -> str:
        """汇总所有步骤结果为最终回答"""
        results_text = "\n\n".join(
            f"[步骤 {sid}]\n{result}"
            for sid, result in step_results.items()
        )
        prompt = (
            f"你是一个汇总专家。请根据以下各步骤的执行结果，"
            f"整合成一篇完整的最终回答。\n\n"
            f"原始问题: {question}\n\n"
            f"各步骤结果:\n{results_text}\n\n"
            f"请直接输出面向用户的最终回答（不要使用 Final Answer: 格式，直接写内容）:"
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            result = self.pre_process(response.choices[0].message.content)
            return self._clean_answer(result)
        except Exception as e:
            logger.error(f"[{self.name}] 汇总失败: {e}")
            # 降级：拼接所有步骤结果
            return "\n".join(
                str(r) for r in step_results.values() if r
            )

    # ==================== ReAct 模式（降级） ====================

    def _execute_react(
        self,
        question: str,
        context: str,
        tools: List[Dict],
        history: List[Dict],
    ) -> AgentResult:
        """
        传统 ReAct 循环。
        当没有匹配的 Skill 计划模板时使用。
        """
        thoughts: List[Dict] = []
        step_logs: List[Dict] = []
        previous_calls: set = set()
        tool_calls_total = 0
        start_time = self._now_ms()  # 思考计时起点

        messages = [{"role": "system", "content": context}]

        # 注意：对话历史已由 ContextBuilder 整合到 context 中，此处不再重复注入
        messages.append({"role": "user", "content": f"Question: {question}\n"})

        # ReAct 循环
        for iteration in range(self.max_iterations):
            # 发起模型调用
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stop=["Observation:"],
                )
                answer = self.pre_process(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"[{self.name}] LLM调用失败: {e}")
                self._record_thought(thoughts, iteration + 1, "thought", "模型调用失败", start_time)
                return AgentResult(
                    final_answer="抱歉，服务暂时不可用，请稍后再试。",
                    thoughts=thoughts,
                    step_logs=step_logs,
                    total_steps=iteration + 1,
                    tool_calls=tool_calls_total,
                )

            messages.append({"role": "assistant", "content": answer})

            # 提取 Thought
            thought_match = re.search(r"Thought:\s*(.*)", answer)
            thought_content = thought_match.group(1).strip() if thought_match else ""
            if thought_match:
                self._record_thought(thoughts, iteration, "thought", thought_content, start_time)

            # 检查 Final Answer
            if "Final Answer:" in answer:
                final = answer.split("Final Answer:")[-1].strip()
                final = self._clean_answer(final)
                final = self.pre_process(final)
                if not final:
                    final = "抱歉，我暂时无法回答您的问题。"
                self._record_thought(thoughts, iteration, "final_answer", final, start_time)
                if self.verbose:
                    step_logs.append({
                        "round": iteration + 1,
                        "thought": thought_content,
                        "action": "",
                        "obs": "",
                        "final_answer": final[:200],
                        "is_repeat": False,
                    })
                return AgentResult(
                    final_answer=final,
                    thoughts=thoughts,
                    step_logs=step_logs,
                    total_steps=iteration + 1,
                    tool_calls=tool_calls_total,
                )

            # 解析 Action
            action_match = re.search(r"Action:\s*(.*)", answer)
            input_match = re.search(r"Action Input:\s*(.*)", answer)

            if not action_match or not input_match:
                # 无有效 Action，尝试提取直接回答
                final_candidate = re.sub(
                    r'(Question|Thought|Action|Action Input|Observation):.*',
                    '', answer
                ).strip()
                final_candidate = self.pre_process(final_candidate)
                if final_candidate:
                    self._record_thought(thoughts, iteration, "thought", "直接回答", start_time)
                    if self.verbose:
                        step_logs.append({
                            "round": iteration + 1,
                            "thought": "直接回答",
                            "action": "",
                            "obs": "",
                            "final_answer": final_candidate[:200],
                            "is_repeat": False,
                        })
                    return AgentResult(
                        final_answer=final_candidate,
                        thoughts=thoughts,
                        step_logs=step_logs,
                        total_steps=iteration + 1,
                        tool_calls=tool_calls_total,
                    )
                else:
                    if self.verbose:
                        step_logs.append({
                            "round": iteration + 1,
                            "thought": thought_content,
                            "action": "解析失败",
                            "obs": "",
                            "final_answer": "",
                            "is_repeat": False,
                        })
                    continue

            action = action_match.group(1).strip()
            action_input_str = input_match.group(1).strip()
            self._record_thought(thoughts, iteration, "action", f"调用工具: {action}", start_time)
            self._record_thought(thoughts, iteration, "action_input", action_input_str, start_time)

            # 执行工具
            observation = self._call_tool(action, action_input_str, tools)
            tool_calls_total += 1
            self._record_thought(thoughts, iteration, "observation", observation, start_time)
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}",
            })

            # 记录步骤日志
            if self.verbose:
                call_signature = (action, action_input_str)
                is_repeat = call_signature in previous_calls
                previous_calls.add(call_signature)
                step_logs.append({
                    "round": iteration + 1,
                    "thought": thought_content,
                    "action": f"{action}({action_input_str})",
                    "obs": observation[:200],
                    "final_answer": "",
                    "is_repeat": is_repeat,
                })

        # 超步数强制回答
        final_text = "抱歉，我暂时无法回答您的问题，请稍后再试。"
        self._record_thought(thoughts, self.max_iterations, "thought", "已达到最大步数，强制生成答案。", start_time)
        try:
            final_response = client.chat.completions.create(
                model=model_name,
                messages=messages + [{
                    "role": "user",
                    "content": "请直接给出最终回答（必须包含 Final Answer:）。",
                }],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            final_text = self.pre_process(
                final_response.choices[0].message.content
            )
            if "Final Answer:" in final_text:
                final_text = final_text.split("Final Answer:")[-1].strip()
            if not final_text:
                final_text = "抱歉，我暂时无法回答您的问题，请稍后再试。"
        except Exception as e:
            logger.error(f"[{self.name}] 最终回答失败: {e}")

        if self.verbose:
            step_logs.append({
                "round": self.max_iterations + 1,
                "thought": "已达到最大步数",
                "action": "",
                "obs": "",
                "final_answer": final_text[:200],
                "is_repeat": False,
            })
        return AgentResult(
            final_answer=final_text,
            thoughts=thoughts,
            step_logs=step_logs,
            total_steps=self.max_iterations + 1,
            tool_calls=tool_calls_total,
        )

    # ==================== 观察结果格式化 ====================

    @staticmethod
    def _format_observation(raw: str, max_len: int = 500) -> str:
        """
        将工具返回的原始结果转为可读的 Observation 文本。
        如果是 JSON 且包含 message/status 字段，提取 message；
        否则智能截断：优先保留完整段落。
        """
        if not raw:
            return "(无结果)"
        # 尝试解析 JSON，提取可读消息
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                if "message" in obj:
                    msg = obj["message"]
                    return msg[:max_len] + ("..." if len(msg) > max_len else "")
                if "error" in obj:
                    return f"错误: {obj['error']}"[:max_len]
        except (json.JSONDecodeError, TypeError):
            pass
        # 纯文本：尽量保留完整内容
        if len(raw) <= max_len:
            return raw
        # 在最后一个完整段落处截断
        cut = raw.rfind('\n', 0, max_len)
        if cut > max_len // 2:
            return raw[:cut] + "..."
        return raw[:max_len] + "..."

    # ==================== 工具调用 ====================

    @staticmethod
    def _call_tool(
        action: str,
        action_input_str: str,
        tools: List[Dict],
    ) -> str:
        """调用工具并返回 Observation 文本"""
        # 解析参数
        try:
            args = json.loads(action_input_str)
        except json.JSONDecodeError:
            return f"Action Input 格式错误，必须为 JSON: {action_input_str[:100]}"

        # 查找工具
        tool = next((t for t in tools if t["name"] == action), None)
        if not tool:
            available = ", ".join(t["name"] for t in tools)
            return f"未知工具: {action}。可用工具: {available}"

        # 执行
        try:
            logger.info(f">>> 调用工具: {action}, 参数: {json.dumps(args, ensure_ascii=False)}")
            result = tool["func"](**args)
            obs_preview = str(result)[:300]
            logger.info(f"<<< 工具返回 ({action}): {obs_preview}")
            return str(result)
        except Exception as e:
            logger.error(f"工具 {action} 执行出错: {e}", exc_info=True)
            return f"工具执行出错: {str(e)}"

    @staticmethod
    def _has_tool_call(text: str) -> bool:
        """检查文本中是否包含工具调用"""
        return bool(re.search(r"Action:\s*\w+", text))
