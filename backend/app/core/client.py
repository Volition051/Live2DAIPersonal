"""
LLM 客户端模块
根据 LLM_PROVIDER 配置自动选择 DashScope 或 DeepSeek 客户端。
导出:
  - client:   OpenAI 兼容客户端实例
  - model_name: 当前激活的模型名称
"""
from openai import OpenAI
from app.config import settings


def _get_llm_config():
    """根据 LLM_PROVIDER 返回 (OpenAI客户端, 模型名称)"""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "deepseek":
        return (
            OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            ),
            settings.DEEPSEEK_MODEL,
        )
    else:
        # 默认: dashscope（阿里百炼）
        return (
            OpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL,
            ),
            settings.DASHSCOPE_MODEL,
        )


client, model_name = _get_llm_config()
