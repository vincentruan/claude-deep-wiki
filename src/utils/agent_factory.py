"""
Agent 工厂

根据配置创建 Claude 或 OpenAI Agent
"""

import sys
from pathlib import Path
from typing import Any, Optional, List
import logging

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    AGENT_SDK,
    ANTHROPIC_AUTH_TOKEN,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    DEFAULT_MODEL,
    MODEL_TEMPERATURE,
    MODEL_TOP_P,
    MODEL_MAX_TOKENS,
    MAX_TURNS,
    ENABLE_STREAMING
)

logger = logging.getLogger(__name__)


class AgentFactory:
    """Agent 工厂类 - 根据配置创建相应的 Agent"""

    @staticmethod
    def create_client(
        name: str,
        instructions: str,
        mcp_server: Optional[Any] = None,
        tools: Optional[List] = None
    ):
        """
        创建 Agent 客户端

        Args:
            name: Agent 名称
            instructions: Agent 指令
            mcp_server: MCP 服务器（可选）
            tools: 工具列表（可选）

        Returns:
            根据 AGENT_SDK 配置返回相应的 client 实例和相关对象
            返回: (client, openai_client/None, threads_dict)
        """
        if AGENT_SDK == "claude":
            return AgentFactory._create_claude_client(name, instructions, mcp_server)
        else:  # openai
            return AgentFactory._create_openai_client(name, instructions, mcp_server, tools)

    @staticmethod
    def _create_claude_client(
        name: str,
        instructions: str,
        mcp_server: Optional[Any] = None
    ):
        """
        创建 Claude Agent 客户端

        Returns:
            (claude_client, None, None) - Claude 不需要额外的 openai_client 和 threads
        """
        try:
            from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        except ImportError:
            raise ImportError(
                "Claude Agent SDK 未安装。请运行: "
                "pip install git+https://github.com/anthropics/anthropic-sdk-python.git"
            )

        if not ANTHROPIC_AUTH_TOKEN:
            raise ValueError("使用 Claude SDK 需要设置 ANTHROPIC_AUTH_TOKEN 环境变量")

        # 准备选项
        options_kwargs = {
            "env": {"ANTHROPIC_AUTH_TOKEN": ANTHROPIC_AUTH_TOKEN},
            "system_prompt": instructions,
            "max_turns": MAX_TURNS,
            "permission_mode": "bypassPermissions"
        }

        # 添加 MCP 服务器（如果提供）
        if mcp_server:
            options_kwargs["mcp_servers"] = {"code-analysis": mcp_server}
            options_kwargs["allowed_tools"] = ["code-analysis/*"]
        else:
            options_kwargs["mcp_servers"] = {}
            options_kwargs["allowed_tools"] = []

        # 添加模型配置（如果指定）
        if DEFAULT_MODEL:
            options_kwargs["model"] = DEFAULT_MODEL

        client = ClaudeSDKClient(options=ClaudeAgentOptions(**options_kwargs))

        # Claude SDK 不需要额外的 client 和 threads 字典
        return client, None, None

    @staticmethod
    def _create_openai_client(
        name: str,
        instructions: str,
        mcp_server: Optional[Any] = None,
        tools: Optional[List] = None
    ):
        """
        创建 OpenAI Agent 客户端

        Returns:
            (agent, openai_client, threads_dict) - OpenAI 需要这三个对象
        """
        try:
            from openai import AsyncOpenAI
            from agents import Agent, set_default_openai_client  # OpenAI Agents SDK (独立包)
        except ImportError:
            raise ImportError(
                "OpenAI Agents SDK 未安装。请运行: pip install openai-agents openai"
            )

        if not OPENAI_API_KEY:
            raise ValueError("使用 OpenAI SDK 需要设置 OPENAI_API_KEY 环境变量")

        # 调试日志：记录配置信息
        logger.info(f"[AgentFactory] Creating OpenAI Agent: {name}")
        logger.info(f"[AgentFactory] Model: {DEFAULT_MODEL}")
        logger.info(f"[AgentFactory] Base URL: {OPENAI_BASE_URL or 'default (https://api.openai.com/v1)'}")
        logger.info(f"[AgentFactory] API Key (masked): {OPENAI_API_KEY[:10]}...{OPENAI_API_KEY[-4:]}")
        logger.info(f"[AgentFactory] Temperature: {MODEL_TEMPERATURE}, Top-P: {MODEL_TOP_P}, Max Tokens: {MODEL_MAX_TOKENS}")

        # 创建 OpenAI Client
        client_kwargs = {"api_key": OPENAI_API_KEY}
        if OPENAI_BASE_URL:
            client_kwargs["base_url"] = OPENAI_BASE_URL
        openai_client = AsyncOpenAI(**client_kwargs)

        logger.info(f"[AgentFactory] Created AsyncOpenAI client with base_url: {openai_client.base_url}")

        # 设置全局默认客户端（OpenAI Agents SDK 要求）
        # use_for_tracing=False 避免 tracing 客户端尝试连接到错误的端点
        set_default_openai_client(openai_client, use_for_tracing=False)
        logger.info(f"[AgentFactory] Set default OpenAI client (use_for_tracing=False)")

        # 禁用 tracing 以避免额外的 API 调用
        from agents import set_tracing_disabled
        set_tracing_disabled(True)
        logger.info(f"[AgentFactory] Disabled tracing")

        # 准备工具列表
        agent_tools = []
        if mcp_server:
            # mcp_server 是工具列表
            if isinstance(mcp_server, list):
                agent_tools.extend(mcp_server)
            else:
                agent_tools.append(mcp_server)
        if tools:
            agent_tools.extend(tools)

        # 准备模型设置
        from agents import ModelSettings
        model_settings = ModelSettings(
            temperature=MODEL_TEMPERATURE,
            top_p=MODEL_TOP_P,
            max_tokens=MODEL_MAX_TOKENS
        )

        # 创建Model对象，使用chat completions API（兼容DeepSeek等OpenAI兼容API）
        # 注意：直接传字符串会使用Responses API，不兼容第三方API
        from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

        model = OpenAIChatCompletionsModel(
            model=DEFAULT_MODEL,
            openai_client=openai_client,
            stream=ENABLE_STREAMING  # 支持流式响应
        )
        logger.info(f"[AgentFactory] Created OpenAIChatCompletionsModel for {DEFAULT_MODEL}")
        logger.info(f"[AgentFactory] Streaming mode: {'enabled' if ENABLE_STREAMING else 'disabled'}")

        # 创建 Agent（使用显式的Model对象而不是字符串）
        agent = Agent(
            name=name,
            model=model,
            instructions=instructions,
            tools=agent_tools,
            model_settings=model_settings
        )

        # OpenAI 需要管理 threads
        threads = {}

        return agent, openai_client, threads

    @staticmethod
    async def connect_client(client):
        """
        连接客户端（仅 Claude 需要）

        Args:
            client: Agent 客户端
        """
        if AGENT_SDK == "claude":
            await client.connect()

    @staticmethod
    async def disconnect_client(client, openai_client=None):
        """
        断开客户端连接

        Args:
            client: Agent 客户端
            openai_client: OpenAI 客户端（仅 OpenAI 需要）
        """
        if AGENT_SDK == "claude":
            await client.disconnect()
        else:  # openai
            if openai_client:
                await openai_client.close()

    @staticmethod
    def get_session_id(session_key: str, threads: Optional[dict] = None) -> Optional[str]:
        """
        获取会话ID/线程ID

        Args:
            session_key: 会话标识符
            threads: 线程字典（OpenAI 使用，Claude 忽略）

        Returns:
            Claude: 返回 session_key
            OpenAI: 返回 threads.get(session_key) 或 None
        """
        if AGENT_SDK == "claude":
            return session_key
        else:  # openai
            if threads is not None:
                return threads.get(session_key)
            return None
