"""
记忆管理模块（增强版）
提供游客对话记忆的存储、检索与上下文构建能力
"""
from typing import List, Optional
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from app.models import InteractionLog
from app.services.indexer import get_collection  # ← 改为惰性导入

logger = logging.getLogger(__name__)


# ==================== 压缩提示模板 ====================

COMPRESS_PROMPT = """请将以下对话历史压缩成一段简洁的摘要,保留所有关键事实和重要信息。

{existing_summary}

新对话:
{history}

请输出更新后的累积摘要（直接输出摘要内容,不要加前缀）:"""


# ==================== 记忆配置 ====================

class MemoryConfig:
    """记忆系统配置"""
    WORKING_WINDOW: int = 10          # 工作记忆:最近对话轮数
    EPISODIC_LIMIT: int = 20          # 情景记忆:单次检索最大记录数
    SEMANTIC_TOP_K: int = 5           # 语义记忆:向量检索返回数
    MEMORY_STALE_DAYS: int = 30       # 超过此天数的记忆视为"陈旧"
    # ---- 压缩配置 ----
    COMPRESS_THRESHOLD: int = 10       # 超过此轮数触发压缩
    KEEP_RECENT_ROUNDS: int = 4        # 压缩后保留最近 N 轮完整消息


class MemoryItem:
    """标准化记忆条目（如有需要可扩展使用）"""
    def __init__(self, role: str, content: str, timestamp: datetime = None, importance: float = 0.5):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.importance = importance

    def to_message(self) -> dict:
        return {"role": self.role, "content": self.content}


class MemoryManager:
    """
    记忆管理器（统一管理游客的工作记忆、情景记忆和语义记忆）
    """

    def __init__(self, db: Session, tourist_id: int, config: MemoryConfig = None):
        self.db = db
        self.tourist_id = tourist_id          # 仍然是内部整数 ID
        self.config = config or MemoryConfig()
        # ---- 压缩状态 ----
        self._summary: str = ""                # 最新压缩摘要
        self._compressed_rounds: int = 0       # 已被压缩的轮次总数

    # ==================== 记忆添加 ====================

    def add_interaction(self, question: str, answer: str) -> int:
        """将一轮问答持久化到数据库,并尝试向量化问题（失败不影响主流程）"""
        # 1. 写入关系数据库,字段名改为 tourist_pk
        log = InteractionLog(
            tourist_pk=self.tourist_id,   # ★ 改为 tourist_pk
            question=question,
            answer=answer
        )
        self.db.add(log)
        self.db.commit()
        logger.info(f"已保存互动记录 (tourist_id={self.tourist_id}, log_id={log.id})")

        # 2. 可选:向量索引（用于语义记忆）
        try:
            col = get_collection()  # 惰性获取
            col.add(
                documents=[question],
                metadatas=[{"tourist_id": self.tourist_id, "log_id": log.id, "type": "question"}],
                ids=[f"mem_{self.tourist_id}_{log.id}"]
            )
            logger.debug(f"向量索引添加成功: mem_{self.tourist_id}_{log.id}")
        except Exception as e:
            logger.warning(f"向量索引添加失败（非致命）: {e}")

        return log.id

    # ==================== 记忆检索 ====================

    def get_working_memory(self) -> List[dict]:
        """
        工作记忆:压缩摘要 + 最近 N 轮对话（时间正序）。

        如果存在压缩摘要,则以 summary 消息开头；
        随后是压缩后新增的完整对话（最多 WORKING_WINDOW 轮）。
        """
        logs = (
            self.db.query(InteractionLog)
            .filter(InteractionLog.tourist_pk == self.tourist_id)
            .order_by(InteractionLog.created_at.desc())
            .limit(self.config.WORKING_WINDOW)
            .all()
        )
        logs = list(reversed(logs))
        messages = []

        # 注入压缩摘要（如果有）
        if self._summary:
            messages.append({
                "role": "summary",
                "content": f"[对话历史摘要]\n{self._summary}",
            })

        for log in logs:
            messages.append({"role": "user", "content": log.question})
            messages.append({"role": "assistant", "content": log.answer})
        return messages

    # ==================== 记忆压缩 ====================

    def need_compress(self) -> bool:
        """
        检查是否需要压缩。
        条件:总对话轮数 > 压缩阈值 + 已压缩轮数。
        """
        total = self._count_total_rounds()
        effective = total - self._compressed_rounds
        return effective > self.config.COMPRESS_THRESHOLD

    def compress(self) -> bool:
        """
        压缩旧对话为摘要。

        流程:
        1. 计算应保留的起始索引（保留最近 KEEP_RECENT_ROUNDS 轮）
        2. 将更早的消息送给 LLM 生成摘要
        3. 合并旧摘要（如果有）形成累积摘要
        4. 记录被压缩的轮次数

        Returns: 是否成功压缩
        """
        total = self._count_total_rounds()
        keep = self.config.KEEP_RECENT_ROUNDS
        if total <= keep:
            return False

        # 需要压缩的轮数 = 总轮数 - 保留轮数
        rounds_to_compress = total - keep
        if rounds_to_compress <= 0:
            return False

        # 获取所有日志,分割为"待压缩"和"保留"
        all_logs = (
            self.db.query(InteractionLog)
            .filter(InteractionLog.tourist_pk == self.tourist_id)
            .order_by(InteractionLog.created_at.asc())
            .all()
        )
        old_logs = all_logs[:rounds_to_compress]
        recent_logs = all_logs[rounds_to_compress:]

        if not old_logs:
            return False

        # 构建压缩提示
        history_text = self._logs_to_text(old_logs)
        existing = f"已有摘要:{self._summary}" if self._summary else "（首次压缩,无已有摘要）"
        prompt = COMPRESS_PROMPT.format(
            existing_summary=existing,
            history=history_text,
        )

        try:
            from app.core.client import client, model_name
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=512,
            )
            new_summary = response.choices[0].message.content.strip()
            self._summary = new_summary
            self._compressed_rounds = rounds_to_compress
            logger.info(
                f"记忆压缩完成,压缩 {rounds_to_compress} 轮 -> "
                f"{len(new_summary)} 字符摘要"
            )
            return True
        except Exception as e:
            logger.error(f"记忆压缩失败: {e}")
            return False

    def get_summary(self) -> str:
        """获取当前压缩摘要"""
        return self._summary

    def get_compressed_context(self) -> List[dict]:
        """
        获取完整的压缩上下文:摘要 + 最近消息。
        已覆盖 get_working_memory(),保留此方法作为显式调用入口。
        """
        return self.get_working_memory()

    # ==================== 内部辅助 ====================

    def _count_total_rounds(self) -> int:
        """统计该用户总对话轮数（以 user question 计数）"""
        return (
            self.db.query(InteractionLog)
            .filter(InteractionLog.tourist_pk == self.tourist_id)
            .count()
        )

    @staticmethod
    def _logs_to_text(logs: List[InteractionLog]) -> str:
        """将日志列表转为纯文本,供 LLM 压缩"""
        lines = []
        for log in logs:
            lines.append(f"User: {log.question}")
            lines.append(f"Assistant: {log.answer}")
        return "\n".join(lines)

    def get_episodic_memory(self, query: str = None, days: int = None) -> List[dict]:
        """情景记忆:根据关键词搜索近期历史事件"""
        days = days or self.config.MEMORY_STALE_DAYS
        cutoff = datetime.now() - timedelta(days=days)

        base_query = self.db.query(InteractionLog).filter(
            InteractionLog.tourist_pk == self.tourist_id,           # ★ 改为 tourist_pk
            InteractionLog.created_at >= cutoff
        )

        if query:
            base_query = base_query.filter(
                InteractionLog.question.ilike(f"%{query}%") |
                InteractionLog.answer.ilike(f"%{query}%")
            )

        logs = base_query.order_by(InteractionLog.created_at.desc()).limit(self.config.EPISODIC_LIMIT).all()
        logs = list(reversed(logs))

        messages = []
        for log in logs:
            messages.append({"role": "user", "content": f"[记忆片段] 你曾问过: {log.question}"})
            messages.append({"role": "assistant", "content": f"我当时回答: {log.answer}"})
        return messages

    def get_semantic_memory(self, query: str, top_k: int = None) -> List[str]:
        """语义记忆:从向量库中检索最相关的历史对话"""
        top_k = top_k or self.config.SEMANTIC_TOP_K
        try:
            col = get_collection()  # 惰性获取
            results = col.query(
                query_texts=[query],
                n_results=top_k,
                where={"tourist_id": self.tourist_id}
            )
            retrieved = []
            if results.get('metadatas') and results['metadatas'][0]:
                for meta in results['metadatas'][0]:
                    log_id = meta.get('log_id')
                    if log_id:
                        log = self.db.query(InteractionLog).get(log_id)
                        if log:
                            retrieved.append(f"Q: {log.question}\nA: {log.answer}")
            return retrieved
        except Exception as e:
            logger.warning(f"语义记忆检索失败: {e}")
            return []

    # ==================== 上下文构建 ====================

    def build_context(self, current_question: str) -> tuple[List[dict], str]:
        """
        构建完整的对话上下文:压缩摘要 + 工作记忆 + 语义记忆。

        Returns:
            (messages_for_agent, additional_context_text)
        """
        # 自动压缩检查
        if self.need_compress():
            logger.info(f"用户 {self.tourist_id} 触发记忆压缩...")
            self.compress()

        working = self.get_working_memory()
        semantic_chunks = self.get_semantic_memory(current_question)

        context_parts = []
        if self._summary:
            context_parts.append(f"【对话历史摘要】\n{self._summary}")
        if semantic_chunks:
            context_parts.append("【相关的历史对话】")
            context_parts.extend(semantic_chunks)

        context_text = "\n".join(context_parts) if context_parts else ""
        return working, context_text

    # ==================== 记忆管理 ====================

    def clear_memory(self):
        """清除该游客的所有对话记忆（数据库 + 向量库）"""
        try:
            self.db.query(InteractionLog).filter(
                InteractionLog.tourist_pk == self.tourist_id   # ★ 改为 tourist_pk
            ).delete()
            self.db.commit()
            logger.info(f"已清除游客 {self.tourist_id} 的全部对话记录")
        except Exception as e:
            self.db.rollback()
            logger.error(f"清除数据库记录失败: {e}")
            raise

        try:
            col = get_collection()  # 惰性获取
            col.delete(where={"tourist_id": self.tourist_id})
            logger.info(f"已清除游客 {self.tourist_id} 的语义记忆向量")
        except Exception as e:
            logger.warning(f"清除向量库失败（非致命）: {e}")

    def get_memory_stats(self) -> dict:
        """获取记忆统计信息"""
        total = self.db.query(InteractionLog).filter(
            InteractionLog.tourist_pk == self.tourist_id   # ★ 改为 tourist_pk
        ).count()
        recent_week = self.db.query(InteractionLog).filter(
            InteractionLog.tourist_pk == self.tourist_id,  # ★ 改为 tourist_pk
            InteractionLog.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        return {
            "total_interactions": total,
            "recent_week": recent_week,
        }

    def clean_stale_memories(self, days: int = None) -> int:
        """清理超过指定天数的旧记忆（返回删除条数）"""
        days = days or self.config.MEMORY_STALE_DAYS
        cutoff = datetime.now() - timedelta(days=days)
        try:
            deleted = self.db.query(InteractionLog).filter(
                InteractionLog.tourist_pk == self.tourist_id,   # ★ 改为 tourist_pk
                InteractionLog.created_at < cutoff
            ).delete()
            self.db.commit()
            if deleted:
                logger.info(f"清理了游客 {self.tourist_id} 的 {deleted} 条陈旧记忆")
            return deleted
        except Exception as e:
            self.db.rollback()
            logger.error(f"清理陈旧记忆失败: {e}")
            return 0