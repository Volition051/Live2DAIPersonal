"""
Skill 数据结构定义
- Skill：可复用的专业能力模块 = 领域 prompt + 工具集 + 执行计划模板
- PlanStep：计划中的单个步骤
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlanStep:
    """执行计划中的单个步骤"""
    step_id: int
    description: str                # 这一步要做什么
    tool_hint: Optional[str] = None  # 建议使用的工具名（None = LLM 自由发挥）
    expected_output: str = ""       # 期望产出描述
    validation: str = ""             # 验证标准
    depends_on: List[int] = field(default_factory=list)
    max_retries: int = 2

    def to_prompt_text(self) -> str:
        """转为注入 LLM 的步骤描述"""
        parts = [f"步骤 {self.step_id}: {self.description}"]
        if self.expected_output:
            parts.append(f"  期望产出: {self.expected_output}")
        if self.validation:
            parts.append(f"  验证标准: {self.validation}")
        return "\n".join(parts)


@dataclass
class Skill:
    """
    技能定义：将"领域知识 + 工具配置 + 执行计划"打包为一个可复用模块。

    触发机制：用户问题命中 triggers 关键词时自动激活。
    计划机制：plan_template 非空时走 Plan-Execute 模式，否则走 ReAct 模式。
    """
    name: str                       # 技能唯一标识，如 "route_planning"
    description: str                # 一句话描述
    triggers: List[str] = field(default_factory=list)  # 触发关键词
    system_fragment: str = ""       # 注入 system prompt 的领域知识片段
    tools: List[str] = field(default_factory=list)     # 需要的工具名称列表
    plan_template: List[PlanStep] = field(default_factory=list)  # 预定义执行计划
    engine: str = "react"           # 执行引擎: "react" | "codeact" | "direct"
    priority: int = 0               # 优先级（多个 Skill 匹配时取最高）
    scope: str = "all"              # 作用域: "tourist" | "admin" | "all"

    def has_plan(self) -> bool:
        return len(self.plan_template) > 0

    def get_plan_summary(self) -> str:
        """生成计划的文本摘要，供 LLM 参考"""
        if not self.plan_template:
            return ""
        lines = [f"执行计划（共 {len(self.plan_template)} 步）:"]
        for step in self.plan_template:
            deps = f" (依赖步骤: {step.depends_on})" if step.depends_on else ""
            lines.append(f"  {step.step_id}. {step.description}{deps}")
        return "\n".join(lines)

    def get_step(self, step_id: int) -> Optional[PlanStep]:
        for s in self.plan_template:
            if s.step_id == step_id:
                return s
        return None

    def get_ready_steps(self, completed_ids: List[int]) -> List[PlanStep]:
        """获取所有依赖已满足的就绪步骤"""
        ready = []
        for step in self.plan_template:
            if step.step_id in completed_ids:
                continue
            if all(d in completed_ids for d in step.depends_on):
                ready.append(step)
        return ready
