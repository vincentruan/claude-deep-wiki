"""
OpenAI 查询助手

提供带重试和JSON解析的统一查询接口
"""

from typing import Dict, Any, Tuple, Optional, Callable
from .json_extractor import JSONExtractor
import logging

logger = logging.getLogger(__name__)


class OpenAIQueryHelper:
    """OpenAI查询助手 - 带重试和JSON解析"""

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

        Args:
            client: OpenAI Agent实例
            prompt: 提示词
            session_id: 会话ID（可选，用于保持上下文，内部映射为 conversation_id）
            max_attempts: 最大尝试次数（默认3次）
            validator: 可选的验证函数，接收解析后的dict，返回bool

        Returns:
            (response_text, parsed_json) 元组

        Raises:
            ValueError: 达到最大重试次数仍失败
        """
        from agents import Runner

        # session_id 映射为 conversation_id，保持接口统一
        conversation_id = session_id
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                # 调试日志：记录请求信息
                logger.info(f"[OpenAI Query] Attempt {attempt}/{max_attempts}")
                logger.info(f"[OpenAI Query] Agent: {client.name}")
                # 提取模型名称
                model_name = client.model.model if hasattr(client.model, 'model') else str(client.model)
                logger.info(f"[OpenAI Query] Model: {model_name}")
                logger.info(f"[OpenAI Query] Conversation ID: {conversation_id}")
                logger.info(f"[OpenAI Query] Prompt length: {len(prompt)} chars")

                # 检查全局客户端配置
                from agents import _config
                default_client = getattr(_config, '_default_openai_client', None)
                if default_client:
                    logger.info(f"[OpenAI Query] Using default client with base_url: {default_client.base_url}")
                    logger.info(f"[OpenAI Query] API key (masked): {str(default_client.api_key)[:10]}...{str(default_client.api_key)[-4:]}")
                else:
                    logger.info(f"[OpenAI Query] No default OpenAI client set!")

                # 使用 Runner 执行 Agent
                result = await Runner.run(
                    starting_agent=client,
                    input=prompt,
                    conversation_id=conversation_id
                )

                logger.info(f"[OpenAI Query] Request completed successfully")

                # 提取响应文本
                # RunResult.final_output 包含最终输出
                response_text = ""
                if hasattr(result, 'final_output') and result.final_output:
                    if isinstance(result.final_output, str):
                        response_text = result.final_output
                    else:
                        response_text = str(result.final_output)

                # 如果 final_output 为空，尝试从 new_items 提取
                if not response_text and hasattr(result, 'new_items'):
                    for item in result.new_items:
                        content = getattr(item, 'content', None)
                        if content:
                            if isinstance(content, str):
                                response_text += content
                            elif isinstance(content, list):
                                for block in content:
                                    text = getattr(block, 'text', None)
                                    if text:
                                        response_text += text

                # 提取JSON
                parsed_json = JSONExtractor.extract(response_text)

                # 检查是否提取到有效JSON
                if not parsed_json:
                    last_error = "JSON提取失败：返回空字典"
                    if attempt < max_attempts:
                        print(f"          ⚠️  JSON提取失败，重试 {attempt}/{max_attempts-1}...")
                        continue
                    else:
                        print(f"          ❌ JSON提取失败，已达最大重试次数")
                        raise ValueError(f"JSON提取失败（尝试{max_attempts}次）")

                # 如果提供了验证器，执行验证
                if validator and not validator(parsed_json):
                    last_error = "JSON验证失败：不符合预期格式"
                    if attempt < max_attempts:
                        print(f"          ⚠️  JSON验证失败，重试 {attempt}/{max_attempts-1}...")
                        continue
                    else:
                        print(f"          ❌ JSON验证失败，已达最大重试次数")
                        raise ValueError(f"JSON验证失败（尝试{max_attempts}次）")

                # 成功
                return response_text, parsed_json

            except Exception as e:
                last_error = str(e)
                if attempt < max_attempts:
                    print(f"          ⚠️  查询异常：{e}，重试 {attempt}/{max_attempts-1}...")
                    continue
                else:
                    print(f"          ❌ 查询异常：{e}，已达最大重试次数")
                    raise

        # 不应该到达这里，但为了类型检查
        raise ValueError(f"查询失败（尝试{max_attempts}次）：{last_error}")

    @staticmethod
    async def query_with_text(
        client,
        prompt: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        发送查询并返回纯文本响应（不解析JSON）

        Args:
            client: OpenAI Agent实例
            prompt: 提示词
            session_id: 会话ID（可选，用于保持上下文，内部映射为 conversation_id）

        Returns:
            响应文本
        """
        from agents import Runner

        # session_id 映射为 conversation_id，保持接口统一
        conversation_id = session_id

        # 使用 Runner 执行 Agent
        result = await Runner.run(
            starting_agent=client,
            input=prompt,
            conversation_id=conversation_id
        )

        # 提取响应文本
        # RunResult.final_output 包含最终输出
        response_text = ""
        if hasattr(result, 'final_output') and result.final_output:
            if isinstance(result.final_output, str):
                response_text = result.final_output
            else:
                response_text = str(result.final_output)

        # 如果 final_output 为空，尝试从 new_items 提取
        if not response_text and hasattr(result, 'new_items'):
            for item in result.new_items:
                content = getattr(item, 'content', None)
                if content:
                    if isinstance(content, str):
                        response_text += content
                    elif isinstance(content, list):
                        for block in content:
                            text = getattr(block, 'text', None)
                            if text:
                                response_text += text

        return response_text
