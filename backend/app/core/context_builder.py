"""
上下文构建器 (ContextBuilder)
实现轻量 GSSC 流水线，用于智能地为 Agent 拼装最优上下文
支持自动加载当前任务计划（若提供数据库会话）
"""
from typing import List, Dict, Optional
from datetime import datetime
import re

class ContextPacket:
    """候选信息包"""
    def __init__(self, content: str, timestamp: datetime,
                 token_count: int, relevance_score: float = 0.5,
                 metadata: Optional[Dict] = None):
        self.content = content
        self.timestamp = timestamp
        self.token_count = token_count
        self.relevance_score = max(0.0, min(1.0, relevance_score))
        self.metadata = metadata or {}

class ContextConfig:
    """配置"""
    def __init__(self, max_tokens: int = 3000, reserve_ratio: float = 0.2,
                 min_relevance: float = 0.1, enable_compression: bool = True,
                 recency_weight: float = 0.3, relevance_weight: float = 0.7):
        self.max_tokens = max_tokens
        self.reserve_ratio = reserve_ratio
        self.min_relevance = min_relevance
        self.enable_compression = enable_compression
        self.recency_weight = recency_weight
        self.relevance_weight = relevance_weight

class ContextBuilder:
    """
    上下文构建器
    结合 MemoryManager、RAG 和对话历史，生成优化的上下文
    可选传入 db 会话以自动加载当前任务计划
    """

    def __init__(self, memory_manager=None, rag_retriever=None, config=None, db=None):
        self.memory = memory_manager          # MemoryManager 实例
        self.rag_retriever = rag_retriever    # 可调用对象，如 retrieve_context
        self.config = config or ContextConfig()
        self.db = db                          # SQLAlchemy Session（可选）

    def build(self, user_query: str,
              conversation_history: List[dict] = None,
              system_instructions: str = None,
              custom_packets: List[ContextPacket] = None,
              context_hint: str = "") -> str:
        """
        主入口：返回结构化的上下文字符串。

        Args:
            user_query: 用户问题
            conversation_history: 对话历史
            system_instructions: 系统指令
            custom_packets: 自定义上下文包
            context_hint: 上下文提示（如 Skill 名称），传递给 RAG 检索器优化召回
        """
        packets = self._gather(user_query, conversation_history,
                               system_instructions, custom_packets, context_hint)
        available_tokens = int(self.config.max_tokens * (1 - self.config.reserve_ratio))
        selected = self._select(packets, user_query, available_tokens)
        structured = self._structure(selected, user_query)
        final = self._compress(structured, self.config.max_tokens)
        return final

    def _gather(self, user_query, history, sys_inst, custom, context_hint=""):
        """收集所有候选信息"""
        packets = []
        # 1. 系统指令（最高优先级）
        if sys_inst:
            packets.append(ContextPacket(
                content=sys_inst,
                timestamp=datetime.now(),
                token_count=self._count_tokens(sys_inst),
                relevance_score=1.0,
                metadata={"type": "system_instruction"}
            ))
        # 2. 工作记忆（最近对话，含压缩摘要）
        if self.memory:
            try:
                recent = self.memory.get_working_memory()
                for msg in recent:
                    # 压缩摘要消息单独处理，给更高优先级
                    if msg.get("role") == "summary":
                        packets.append(ContextPacket(
                            content=msg['content'],
                            timestamp=datetime.now(),
                            token_count=self._count_tokens(msg['content']),
                            relevance_score=0.95,
                            metadata={"type": "memory_summary"}
                        ))
                    else:
                        packets.append(ContextPacket(
                            content=f"{msg['role']}: {msg['content']}",
                            timestamp=datetime.now(),
                            token_count=self._count_tokens(msg['content']),
                            relevance_score=0.6,
                            metadata={"type": "working_memory"}
                        ))
            except Exception:
                pass
        # 3. 语义记忆（相关历史）
        if self.memory:
            try:
                sem_chunks = self.memory.get_semantic_memory(user_query)
                for chunk in sem_chunks:
                    packets.append(ContextPacket(
                        content=chunk,
                        timestamp=datetime.now(),
                        token_count=self._count_tokens(chunk),
                        relevance_score=0.8,
                        metadata={"type": "semantic_memory"}
                    ))
            except Exception:
                pass
        # 4. RAG 检索结果
        if self.rag_retriever:
            try:
                rag_results = self.rag_retriever(user_query)
                for chunk in rag_results:
                    packets.append(ContextPacket(
                        content=chunk,
                        timestamp=datetime.now(),
                        token_count=self._count_tokens(chunk),
                        relevance_score=0.9,
                        metadata={"type": "rag"}
                    ))
            except Exception:
                pass
        # 5. 对话历史（仅最近几条）
        if history:
            for msg in history[-6:]:
                packets.append(ContextPacket(
                    content=f"{msg['role']}: {msg['content']}",
                    timestamp=datetime.now(),
                    token_count=self._count_tokens(msg['content']),
                    relevance_score=0.5,
                    metadata={"type": "conversation_history"}
                ))
        # 6. 当前任务计划（自动注入，若 db 可用）
        if self.db:
            try:
                # 延迟导入，避免循环依赖
                from app.core.admin_tools import get_current_plan
                # 默认以 "admin" 为 owner，可根据需求扩展
                plan_str = get_current_plan(self.db, owner="admin")
                if "没有进行中" not in plan_str:
                    packets.append(ContextPacket(
                        content=plan_str,
                        timestamp=datetime.now(),
                        token_count=self._count_tokens(plan_str),
                        relevance_score=1.0,
                        metadata={"type": "task_plan"}
                    ))
            except Exception:
                pass
        # 7. 自定义包
        if custom:
            packets.extend(custom)
        return packets

    def _select(self, packets: List[ContextPacket], query: str, max_tokens: int):
        """根据相关性和新近性选择信息，不超过 token 上限"""
        system_packets = [p for p in packets if p.metadata.get("type") in ("system_instruction", "memory_summary")]
        others = [p for p in packets if p.metadata.get("type") not in ("system_instruction", "memory_summary")]

        # 系统指令始终保留
        selected = system_packets.copy()
        current_tokens = sum(p.token_count for p in selected)

        # 其他包计算综合分数
        scored = []
        for p in others:
            score = self.config.relevance_weight * p.relevance_score + \
                    self.config.recency_weight * self._calc_recency(p.timestamp)
            if p.relevance_score >= self.config.min_relevance:
                scored.append((score, p))
        scored.sort(reverse=True, key=lambda x: x[0])

        # 贪心填充
        for score, p in scored:
            if current_tokens + p.token_count <= max_tokens:
                selected.append(p)
                current_tokens += p.token_count
            else:
                break
        return selected

    def _structure(self, packets: List[ContextPacket], user_query: str) -> str:
        """将选中包组织成结构化文本"""
        sections = []
        # 系统指令
        sys = [p for p in packets if p.metadata.get("type") == "system_instruction"]
        if sys:
            sections.append("[Role & Policies]\n" + "\n".join(p.content for p in sys))

        # 任务
        # 记忆摘要（压缩后的历史对话）
        summaries = [p for p in packets if p.metadata.get("type") == "memory_summary"]
        if summaries:
            sections.append("[Conversation History]\n" + "\n".join(p.content for p in summaries))

        sections.append(f"[Task]\n{user_query}")

        # 任务计划（如果存在）
        plans = [p for p in packets if p.metadata.get("type") == "task_plan"]
        if plans:
            sections.append("[Active Plan]\n" + "\n".join(p.content for p in plans))

        # 证据（RAG + 语义记忆）
        evidence = [p for p in packets if p.metadata.get("type") in ("rag", "semantic_memory")]
        if evidence:
            sections.append("[Evidence]\n" + "\n---\n".join(p.content for p in evidence))

        # 上下文（工作记忆 + 对话历史）
        context_parts = [p for p in packets if p.metadata.get("type") in ("working_memory", "conversation_history")]
        if context_parts:
            sections.append("[Context]\n" + "\n".join(p.content for p in context_parts))

        # 输出指示
        sections.append("[Output]\n请基于以上信息，提供准确、有据的回答。")
        return "\n\n".join(sections)

    def _compress(self, text: str, max_tokens: int) -> str:
        """简单压缩：若超长则截断非关键部分"""
        current = self._count_tokens(text)
        if current <= max_tokens:
            return text
        # 保留前 max_tokens 个 token（粗略按字符比例截断）
        ratio = len(text) / current if current else 1
        allowed_chars = int(max_tokens * ratio)
        return text[:allowed_chars] + "\n[... 内容已压缩]"

    def _count_tokens(self, text: str) -> int:
        """
        改进的 token 估算（中英混合）。
        优先尝试 tiktoken，不可用时回退启发式规则。
        """
        if not text:
            return 0
        # 优先 tiktoken（精确）
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except (ImportError, Exception):
            pass
        # 回退：启发式估算
        cjk_chars = len(re.findall(r'[一-鿿]', text))
        english_words = len(re.findall(r'[a-zA-Z0-9]+', text))
        other_chars = max(0, len(text) - cjk_chars - english_words)
        estimated = int(cjk_chars * 1.5 + english_words * 1.3 + other_chars * 0.3)
        return max(1, estimated)


    def _calc_recency(self, timestamp: datetime) -> float:
        """计算新近性分数（24小时指数衰减）"""
        import math
        hours = (datetime.now() - timestamp).total_seconds() / 3600
        return max(0.1, math.exp(-0.1 * hours / 24))