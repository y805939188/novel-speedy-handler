# novel_speedy/llm_client.py
"""
统一封装 LLM API 调用（OpenAI Chat 风格）
"""

import re
import requests
import time
import logging
from typing import List, Optional

from novel_speedy.config import config
from novel_speedy.utils import extract_json_from_text

logger = logging.getLogger(__name__)


def _extract_final_message(content: str) -> str:
    """
    从包含特殊标记的响应中提取最终消息内容。
    
    处理格式如：
    <|channel|>analysis<|message|>...<|end|><|start|>assistant<|channel|>final<|message|>实际内容
    
    Args:
        content: 原始响应内容
    
    Returns:
        str: 提取后的实际内容
    """
    if not content:
        return ""
    
    # 检查是否包含特殊标记格式
    if "<|channel|>final<|message|>" in content:
        # 提取 final message 后的内容
        pattern = r'<\|channel\|>final<\|message\|>(.*?)(?:<\|end\|>|$)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # 如果没有结束标记，直接取 final message 后的所有内容
        idx = content.find("<|channel|>final<|message|>")
        if idx != -1:
            return content[idx + len("<|channel|>final<|message|>"):].strip()
    
    # 如果没有特殊标记，返回原内容
    return content


def call_llm(
    messages: List[dict],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system_message: str = ""
) -> str:
    """
    调用 LLM API，返回 assistant 文本内容。
    
    Args:
        messages: 对话消息列表，格式为 [{"role": "user", "content": "..."}]
        temperature: 生成温度，默认使用配置值
        max_tokens: 最大生成 token 数，默认使用配置值
        system_message: 系统提示词，会插入到消息列表开头
    
    Returns:
        str: 模型返回的文本内容（已清洗）
    
    Raises:
        Exception: 重试耗尽后仍失败时抛出
    """
    cfg = config.llm
    
    # 使用配置默认值
    temperature = temperature if temperature is not None else cfg.default_temperature
    max_tokens = max_tokens if max_tokens is not None else cfg.default_max_tokens
    
    # 构建完整的消息列表
    full_messages = []
    
    if system_message:
        full_messages.append({
            "role": "system",
            "content": system_message
        })
    
    full_messages.extend(messages)
    
    payload = {
        "model": cfg.model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False}
    }
    
    last_error = None
    
    for attempt in range(cfg.max_retries + 1):
        try:
            response = requests.post(
                cfg.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=cfg.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 提取 assistant 的回复内容
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                raise ValueError("模型返回内容为空")
            
            # 处理特殊格式标记（如 <|channel|>final<|message|>）
            content = _extract_final_message(content)
            
            if not content:
                raise ValueError("提取最终消息后内容为空")
            
            # 尝试提取 JSON 部分（处理 markdown 包裹的情况）
            cleaned_content = extract_json_from_text(content)
            
            logger.debug(f"LLM 响应: {cleaned_content[:200]}...")
            
            return cleaned_content
            
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"API 请求失败 (尝试 {attempt + 1}/{cfg.max_retries + 1}): {e}")
            
        except (KeyError, IndexError, ValueError) as e:
            last_error = e
            logger.warning(f"响应解析失败 (尝试 {attempt + 1}/{cfg.max_retries + 1}): {e}")
        
        if attempt < cfg.max_retries:
            time.sleep(cfg.retry_delay)
    
    raise Exception(f"LLM 调用失败，已重试 {cfg.max_retries} 次。最后错误: {last_error}")


def call_llm_raw(
    messages: List[dict],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system_message: str = ""
) -> str:
    """
    调用 LLM API，返回原始文本（不做 JSON 提取）。
    
    适用于非 JSON 输出的场景，如生成速读版文本。
    
    Args:
        messages: 对话消息列表
        temperature: 生成温度
        max_tokens: 最大生成 token 数
        system_message: 系统提示词
    
    Returns:
        str: 模型返回的原始文本
    """
    cfg = config.llm
    
    temperature = temperature if temperature is not None else cfg.default_temperature
    max_tokens = max_tokens if max_tokens is not None else cfg.default_max_tokens
    
    full_messages = []
    if system_message:
        full_messages.append({"role": "system", "content": system_message})
    full_messages.extend(messages)
    
    payload = {
        "model": cfg.model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    last_error = None
    
    for attempt in range(cfg.max_retries + 1):
        try:
            response = requests.post(
                cfg.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=cfg.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                raise ValueError("模型返回内容为空")
            
            # 处理特殊格式标记（如 <|channel|>final<|message|>）
            content = _extract_final_message(content)
            
            if not content:
                raise ValueError("提取最终消息后内容为空")
            
            return content.strip()
            
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"API 请求失败 (尝试 {attempt + 1}/{cfg.max_retries + 1}): {e}")
        except (KeyError, IndexError, ValueError) as e:
            last_error = e
            logger.warning(f"响应解析失败 (尝试 {attempt + 1}/{cfg.max_retries + 1}): {e}")
        
        if attempt < cfg.max_retries:
            time.sleep(cfg.retry_delay)
    
    raise Exception(f"LLM 调用失败，已重试 {cfg.max_retries} 次。最后错误: {last_error}")
