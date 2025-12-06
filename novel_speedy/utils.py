# novel_speedy/utils.py
"""
工具函数模块
"""

import re
import json
import logging
from typing import Any, Optional, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def clean_json_output(raw_text: str) -> str:
    """
    清洗 LLM 输出，移除多余的空白字符和格式问题。
    
    Args:
        raw_text: 原始文本
    
    Returns:
        str: 清洗后的文本
    """
    if not raw_text:
        return ""
    
    # 移除首尾空白
    cleaned = raw_text.strip()
    
    # 移除 BOM 字符
    cleaned = cleaned.lstrip('\ufeff')
    
    return cleaned


def extract_json_from_text(raw_text: str) -> str:
    """
    从可能包含 markdown 代码块或其他文本的内容中提取 JSON 部分。
    
    处理以下情况：
    1. ```json ... ``` 包裹
    2. ``` ... ``` 包裹
    3. 纯 JSON 文本
    4. JSON 前后有其他解释文字
    
    Args:
        raw_text: 原始文本
    
    Returns:
        str: 提取出的 JSON 字符串
    """
    if not raw_text:
        return ""
    
    text = raw_text.strip()
    
    # 情况1: 处理 ```json ... ``` 或 ``` ... ``` 包裹
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(code_block_pattern, text)
    if matches:
        # 返回第一个匹配的代码块内容
        return matches[0].strip()
    
    # 情况2: 尝试提取 JSON 数组 [...]
    array_pattern = r'(\[[\s\S]*\])'
    array_matches = re.findall(array_pattern, text)
    if array_matches:
        # 找最长的匹配（最完整的 JSON）
        longest_match = max(array_matches, key=len)
        # 验证是否是有效 JSON
        try:
            json.loads(longest_match)
            return longest_match
        except json.JSONDecodeError:
            pass
    
    # 情况3: 尝试提取 JSON 对象 {...}
    object_pattern = r'(\{[\s\S]*\})'
    object_matches = re.findall(object_pattern, text)
    if object_matches:
        longest_match = max(object_matches, key=len)
        try:
            json.loads(longest_match)
            return longest_match
        except json.JSONDecodeError:
            pass
    
    # 情况4: 原样返回，让调用方处理
    return text


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    安全的 JSON 解析，失败时返回默认值。
    
    Args:
        json_str: JSON 字符串
        default: 解析失败时的默认值
    
    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON 解析失败: {e}")
        return default


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    截断文本到指定长度。
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后的后缀
    
    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def scenes_to_json_str(scenes: List[dict]) -> str:
    """
    将场景列表转换为格式化的 JSON 字符串。
    
    Args:
        scenes: 场景列表
    
    Returns:
        str: 格式化的 JSON 字符串
    """
    return json.dumps(scenes, ensure_ascii=False, indent=2)


def count_chinese_chars(text: str) -> int:
    """
    统计文本中的中文字符数。
    
    Args:
        text: 输入文本
    
    Returns:
        int: 中文字符数量
    """
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return len(chinese_pattern.findall(text))


def estimate_reading_time(char_count: int, chars_per_second: float = 5.0) -> float:
    """
    估算阅读时间。
    
    Args:
        char_count: 字符数
        chars_per_second: 阅读速度（字/秒）
    
    Returns:
        float: 阅读时间（秒）
    """
    return char_count / chars_per_second


def format_duration(seconds: float) -> str:
    """
    格式化时间长度为可读字符串。
    
    Args:
        seconds: 秒数
    
    Returns:
        str: 格式化后的字符串，如 "2小时30分钟"
    """
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}分钟{secs}秒" if secs else f"{minutes}分钟"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}小时{minutes}分钟" if minutes else f"{hours}小时"
