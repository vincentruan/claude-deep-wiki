"""
统一查询助手

根据配置自动选择 Claude SDK 或 OpenAI SDK，提供统一的查询接口
"""

from typing import Dict, Any, Tuple, Optional, Callable
from .json_extractor import JSONExtractor
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AGENT_SDK


class UnifiedQueryHelper:
    """统一查询助手 - 支持 Claude SDK 和 OpenAI SDK"""

    @staticmethod
    async def query_with_json_retry(
        client,
        prompt: str,
        session_id: Optional[str] = None,
        max_attempts: int = 3,
        validator: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        发送查询并解析JSON，失败时自动重试

        根据 AGENT_SDK 配置自动选择对应的实现

        Args:
            client: Agent 实例（Claude 或 OpenAI）
            prompt: 提示词
            session_id: 会话/线程ID（用于保持上下文）
            max_attempts: 最大尝试次数（默认3次）
            validator: 可选的验证函数，接收解析后的dict，返回bool

        Returns:
            (response_text, parsed_json) 元组

        Raises:
            ValueError: 达到最大重试次数仍失败
        """
        if AGENT_SDK == "claude":
            from .claude_query_helper import ClaudeQueryHelper
            return await ClaudeQueryHelper.query_with_json_retry(
                client, prompt, session_id, max_attempts, validator
            )
        else:  # openai
            from .openai_query_helper import OpenAIQueryHelper
            return await OpenAIQueryHelper.query_with_json_retry(
                client, prompt, session_id, max_attempts, validator
            )

    @staticmethod
    async def query_with_text(
        client,
        prompt: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        发送查询并返回纯文本响应（不解析JSON）

        根据 AGENT_SDK 配置自动选择对应的实现

        Args:
            client: Agent 实例（Claude 或 OpenAI）
            prompt: 提示词
            session_id: 会话/线程ID（用于保持上下文）

        Returns:
            响应文本
        """
        if AGENT_SDK == "claude":
            from .claude_query_helper import ClaudeQueryHelper
            return await ClaudeQueryHelper.query_with_text(
                client, prompt, session_id
            )
        else:  # openai
            from .openai_query_helper import OpenAIQueryHelper
            return await OpenAIQueryHelper.query_with_text(
                client, prompt, session_id
            )
