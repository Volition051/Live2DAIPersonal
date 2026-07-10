"""
Skill 注册中心
负责：技能注册、关键词匹配、语义匹配（降级）、工具筛选
"""
import logging
from typing import List, Optional, Dict

from app.core.skills.definitions import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    技能注册中心（单例模式）

    使用方式：
        registry = SkillRegistry()
        registry.register(my_skill)
        skill = registry.match("帮我规划路线")
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    # ==================== 注册 ====================

    def register(self, skill: Skill) -> None:
        """注册一个技能（同名覆盖）"""
        if skill.name in self._skills:
            logger.warning(f"技能 '{skill.name}' 已存在，将被覆盖")
        self._skills[skill.name] = skill
        logger.info(
            f"注册技能: {skill.name} "
            f"(触发词: {skill.triggers[:3]}{'...' if len(skill.triggers) > 3 else ''}, "
            f"计划步骤: {len(skill.plan_template)})"
        )

    def register_many(self, skills: List[Skill]) -> None:
        """批量注册"""
        for skill in skills:
            self.register(skill)

    def get(self, name: str) -> Optional[Skill]:
        """按名称获取技能"""
        return self._skills.get(name)

    def list_all(self) -> List[Skill]:
        """列出所有已注册技能"""
        return list(self._skills.values())

    def get_tools_for_skills(self, matched_skills: List[Skill]) -> List[str]:
        """汇总多个技能所需的工具名称（去重）"""
        tool_set = set()
        for skill in matched_skills:
            tool_set.update(skill.tools)
        return list(tool_set)

    # ==================== 匹配 ====================

    def match(self, question: str, top_k: int = 3, scope: str = "all") -> List[Skill]:
        """
        根据用户问题匹配最相关的技能。

        匹配策略（两层）：
        1. 关键词匹配 — 零成本，直接命中
        2. 模糊匹配 — 子串部分匹配，作为补充
        （语义匹配由上层用 LLM 做，避免循环依赖）

        scope 参数过滤技能作用域（"tourist" / "admin" / "all"）。
        返回按优先级排序的技能列表。
        """
        if not self._skills:
            return []

        # 按 scope 过滤
        candidates = [
            s for s in self._skills.values()
            if scope == "all" or s.scope == "all" or s.scope == scope
        ]

        question_lower = question.lower()

        # 第一层：精确关键词匹配
        exact_matches = []
        for skill in candidates:
            for trigger in skill.triggers:
                if trigger in question_lower or trigger in question:
                    exact_matches.append(skill)
                    break

        # 第二层：模糊子串匹配（仅在无精确匹配时启用）
        fuzzy_matches = []
        if not exact_matches:
            for skill in candidates:  # 使用 scope 过滤后的候选列表
                for trigger in skill.triggers:
                    if _partial_match(trigger, question):
                        fuzzy_matches.append(skill)
                        break

        # 合并结果，去重，按优先级排序
        # 同优先级时：触发词少的技能更精准，优先匹配
        all_matches = exact_matches + fuzzy_matches
        seen = set()
        ranked = []
        for skill in sorted(all_matches, key=lambda s: (-s.priority, len(s.triggers))):
            if skill.name not in seen:
                seen.add(skill.name)
                ranked.append(skill)

        result = ranked[:top_k]
        if result:
            logger.info(
                f"技能匹配: {[s.name for s in result]} "
                f"(精确: {len(exact_matches)}, 模糊: {len(fuzzy_matches)})"
            )
        return result

    def match_first(self, question: str, scope: str = "all") -> Optional[Skill]:
        """匹配最佳技能，无匹配返回 None"""
        matches = self.match(question, top_k=1, scope=scope)
        return matches[0] if matches else None


# 常见虚词/疑问词，不应作为模糊匹配的触发依据
_STOP_SUBSTRINGS = {
    "什么", "怎么", "哪些", "哪个", "哪里", "为什么", "可以", "这个",
    "一下", "帮我", "一个", "一些", "有什么", "有没有", "是不是",
    "的", "了", "吗", "呢", "吧", "啊", "哦",
    # 景区领域常见通用词（不应作为技能区分的依据）
    "景点", "景区", "游客", "旅游", "游览", "游玩",
}


def _partial_match(trigger: str, question: str) -> bool:
    """
    检查触发词中是否有 ≥2 字的有效子串出现在问题中。
    排除常见虚词/疑问词，避免过于宽泛的匹配。
    """
    trigger_lower = trigger.lower()
    question_lower = question.lower()

    if len(trigger_lower) <= 2:
        if trigger_lower in _STOP_SUBSTRINGS:
            return False
        return trigger_lower in question_lower

    # 滑动窗口检查 3~5 字子串（优先长匹配）
    for window_size in range(min(5, len(trigger_lower)), 1, -1):
        for i in range(len(trigger_lower) - window_size + 1):
            sub = trigger_lower[i:i + window_size]
            if sub in _STOP_SUBSTRINGS:
                continue
            if sub in question_lower:
                return True
    return False


# ==================== 全局单例 ====================
_global_registry: Optional[SkillRegistry] = None
_skills_loaded: bool = False


def _auto_load_skills():
    """首次调用时自动加载技能定义（懒加载，避免循环导入）"""
    global _skills_loaded
    if _skills_loaded:
        return
    _skills_loaded = True
    try:
        from app.core.skills.skill_definitions import (
            register_tourist_skills,
            register_admin_skills,
        )
        register_tourist_skills()
        register_admin_skills()
        logger.info("技能定义自动加载完成")
    except Exception as e:
        logger.warning(f"技能定义加载失败（非致命）: {e}")


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册中心（首次调用自动加载技能定义）"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
        _auto_load_skills()
    return _global_registry
