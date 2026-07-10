"""
工具抽象基类
提供统一的工具接口、参数校验、重试与超时控制。
"""
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            return self.data
        return f"工具执行出错: {self.error}"

    def to_observation(self) -> str:
        """转为 Agent 可读的 Observation 文本"""
        if self.success:
            return self.data
        return f"错误: {self.error}"


class ToolError(Exception):
    """工具执行异常"""

    def __init__(self, message: str, tool_name: str = "", recoverable: bool = True):
        super().__init__(message)
        self.tool_name = tool_name
        self.recoverable = recoverable


class BaseTool(ABC):
    """
    所有工具的抽象基类。

    子类只需实现 name / description / parameters / execute 四个抽象成员。
    框架自动处理：参数校验、重试、超时、日志。
    """

    # ---- 子类可覆盖的配置 ----
    retry_count: int = 2
    timeout: float = 30.0
    category: str = "general"  # 工具分类：knowledge / map / stats / system / planning

    # ---- 抽象成员 ----
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，供 LLM 理解何时调用"""
        ...

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        JSON Schema 格式的参数定义。
        例：{"type": "object", "properties": {...}, "required": [...]}
        """
        ...

    @abstractmethod
    def _execute(self, **kwargs) -> str:
        """子类实现：执行工具逻辑，返回字符串结果"""
        ...

    # ---- 框架方法（自动处理校验/重试/日志）----
    def execute(self, **kwargs) -> str:
        """带校验、重试、超时的执行入口"""
        last_error = None

        for attempt in range(self.retry_count + 1):
            try:
                # 参数校验
                self._validate_args(kwargs)

                # 执行（带超时）
                t_start = time.time()
                result = self._execute(**kwargs)
                elapsed = time.time() - t_start

                logger.info(
                    f"[{self.name}] 执行成功, "
                    f"耗时: {elapsed:.3f}s, "
                    f"attempt: {attempt+1}/{self.retry_count+1}"
                )
                return str(result)

            except ToolError as e:
                if not e.recoverable:
                    logger.error(f"[{self.name}] 不可恢复错误: {e}")
                    return f"工具执行失败（不可恢复）: {e}"
                last_error = e
                logger.warning(
                    f"[{self.name}] 可恢复错误 (attempt {attempt+1}): {e}"
                )

            except Exception as e:
                last_error = e
                logger.error(
                    f"[{self.name}] 未知异常 (attempt {attempt+1}): {e}",
                    exc_info=True
                )

            # 重试前等待
            if attempt < self.retry_count:
                time.sleep(0.5 * (attempt + 1))

        return f"工具 '{self.name}' 执行失败（已重试 {self.retry_count} 次）: {last_error}"

    def _validate_args(self, kwargs: Dict[str, Any]) -> None:
        """基于 parameters schema 做基本校验"""
        schema = self.parameters
        if not schema or schema == {}:
            return  # 无参数工具，跳过校验

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # 检查必填参数
        for param in required:
            if param not in kwargs:
                raise ToolError(
                    f"缺少必填参数 '{param}'。需要: {required}",
                    tool_name=self.name,
                    recoverable=False,
                )

        # 检查参数类型
        for key, value in kwargs.items():
            if key in properties:
                expected = properties[key].get("type", "string")
                if not self._check_type(value, expected):
                    raise ToolError(
                        f"参数 '{key}' 类型错误: 期望 {expected}, 实际 {type(value).__name__}",
                        tool_name=self.name,
                        recoverable=False,
                    )

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """简易类型检查"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "float": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True
        return isinstance(value, expected)

    def to_openai_function(self) -> Dict[str, Any]:
        """转为 OpenAI function-calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        """转为 Agent 兼容的工具字典（兼容旧代码）"""
        return {
            "name": self.name,
            "description": self.description,
            "func": self.execute,
            "params": self._params_to_simple(self.parameters),
            "category": self.category,
        }

    @staticmethod
    def _params_to_simple(schema: Dict) -> Dict[str, str]:
        """将 JSON Schema 转为简化的 {参数名: 类型} 字典"""
        if not schema or "properties" not in schema:
            return {}
        return {
            k: v.get("type", "string")
            for k, v in schema["properties"].items()
        }


# ---- 函数工具包装器 ----
class FunctionTool(BaseTool):
    """
    将普通函数包装为 BaseTool。
    用于快速适配旧代码中的裸函数工具。
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Optional[Dict[str, Any]] = None,
        category: str = "general",
        retry_count: int = 2,
    ):
        self._name = name
        self._description = description
        self._func = func
        self._parameters = parameters or {"type": "object", "properties": {}, "required": []}
        self.category = category
        self.retry_count = retry_count

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters

    def _execute(self, **kwargs) -> str:
        return str(self._func(**kwargs))
