# novel_speedy/scene_grouping.py
"""
场景分组模块

负责跨章节自动分组，将连续剧情的章节组织在一起。
"""

import json
import logging
from typing import List, TypedDict

from novel_speedy.llm_client import call_llm
from novel_speedy.scene_extractor import Scene
from novel_speedy.utils import clean_json_output, scenes_to_json_str

logger = logging.getLogger(__name__)


class ChapterWithScenes(TypedDict):
    """带场景的章节结构"""
    index: int
    title: str
    text: str
    scenes: List[Scene]


class ChapterGroup(TypedDict):
    """章节组结构（super chapter group）"""
    group_index: int           # 组序号
    chapters: List[int]        # 章节索引列表
    group_scenes: List[Scene]  # 本组所有章节的场景集合


# 系统提示词
CONTINUATION_CHECK_SYSTEM_PROMPT = """你是一名"小说连续剧情判断助手"。
你的任务：判断两个章节的场景是否属于同一持续剧情。
不要分析整本书，只比较两个场景列表。

【重要】你必须直接输出纯 JSON 对象，不要使用 markdown 代码块包裹，不要输出任何解释文字。"""


def _build_continuation_prompt(previous_scenes: List[Scene], current_scenes: List[Scene]) -> str:
    """
    构建连续性判断的用户提示词
    
    Args:
        previous_scenes: 上一组的场景列表
        current_scenes: 当前章节的场景列表
    
    Returns:
        str: 格式化后的用户提示词
    """
    prev_json = scenes_to_json_str(previous_scenes)
    curr_json = scenes_to_json_str(current_scenes)
    
    return f"""【上一组场景】
{prev_json}

【当前章节场景】
{curr_json}

请判断当前章节是否延续上一组的主要场景。

判断标准：
- 主要人物是否连续
- 地点是否相同或强相关
- 事件是否未结束或正在持续推进
- 是否属于同一主线

输出 JSON：
{{
  "is_continuation": true/false,
  "confidence": 0.0～1.0,
  "reason": "...简述理由..."
}}"""


def is_continuation(
    previous_scenes: List[Scene],
    current_scenes: List[Scene],
    confidence_threshold: float = 0.6,
    max_retries: int = 2
) -> bool:
    """
    调用 LLM 判断当前章节是否属于上一 group 的延续
    
    Args:
        previous_scenes: 上一组的场景列表
        current_scenes: 当前章节的场景列表
        confidence_threshold: 置信度阈值
        max_retries: 最大重试次数
    
    Returns:
        bool: 是否为延续（is_continuation == true and confidence > threshold）
    """
    if not previous_scenes:
        return False
    
    user_prompt = _build_continuation_prompt(previous_scenes, current_scenes)
    messages = [{"role": "user", "content": user_prompt}]
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            raw_response = call_llm(
                messages=messages,
                temperature=0.2,
                max_tokens=512,
                system_message=CONTINUATION_CHECK_SYSTEM_PROMPT
            )
            
            # 清洗并解析 JSON
            cleaned_json = clean_json_output(raw_response)
            result = json.loads(cleaned_json)
            
            # 验证返回格式
            if not isinstance(result, dict):
                raise ValueError("返回格式不是对象")
            
            is_cont = result.get("is_continuation", False)
            confidence = result.get("confidence", 0.0)
            reason = result.get("reason", "")
            
            # 判断标准：is_continuation == true and confidence > threshold
            final_result = bool(is_cont) and float(confidence) > confidence_threshold
            
            logger.info(f"连续性判断: is_continuation={is_cont}, confidence={confidence}, result={final_result}")
            logger.debug(f"判断理由: {reason}")
            
            return final_result
            
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(f"JSON 解析失败 (尝试 {attempt + 1}): {e}")
            
        except (ValueError, TypeError) as e:
            last_error = e
            logger.warning(f"结果验证失败 (尝试 {attempt + 1}): {e}")
            
        except Exception as e:
            last_error = e
            logger.warning(f"连续性判断失败 (尝试 {attempt + 1}): {e}")
    
    # 所有重试都失败，默认不延续（创建新组更安全）
    logger.error(f"连续性判断失败，默认返回 False。错误: {last_error}")
    return False


def group_chapters(chapters: List[ChapterWithScenes]) -> List[ChapterGroup]:
    """
    依次处理章节，构建连续剧情组
    
    规则：
    - 每个章节需已包含 scenes 字段
    - 使用上一章节组的场景作为上下文，判断当前章节是否延续同一"剧情场景链"
    - 若延续：加入当前 group
    - 若不延续：创建一个新 group
    
    Args:
        chapters: 章节列表，每个章节需包含 scenes 字段
    
    Returns:
        List[ChapterGroup]: 章节组列表
    """
    if not chapters:
        return []
    
    groups: List[ChapterGroup] = []
    current_group: ChapterGroup = {
        "group_index": 1,
        "chapters": [],
        "group_scenes": []
    }
    
    for chapter in chapters:
        chapter_index = chapter["index"]
        chapter_scenes = chapter.get("scenes", [])
        
        if not chapter_scenes:
            logger.warning(f"章节 {chapter_index} 无场景数据，跳过")
            continue
        
        # 第一个章节，直接加入
        if not current_group["chapters"]:
            current_group["chapters"].append(chapter_index)
            current_group["group_scenes"].extend(chapter_scenes)
            logger.info(f"章节 {chapter_index} 作为第一章加入组 {current_group['group_index']}")
            continue
        
        # 判断是否延续上一组
        if is_continuation(current_group["group_scenes"], chapter_scenes):
            # 延续：加入当前组
            current_group["chapters"].append(chapter_index)
            current_group["group_scenes"].extend(chapter_scenes)
            logger.info(f"章节 {chapter_index} 延续加入组 {current_group['group_index']}")
        else:
            # 不延续：保存当前组，创建新组
            groups.append(current_group)
            logger.info(f"组 {current_group['group_index']} 完成，包含章节: {current_group['chapters']}")
            
            current_group = {
                "group_index": len(groups) + 1,
                "chapters": [chapter_index],
                "group_scenes": list(chapter_scenes)
            }
            logger.info(f"章节 {chapter_index} 创建新组 {current_group['group_index']}")
    
    # 保存最后一个组
    if current_group["chapters"]:
        groups.append(current_group)
        logger.info(f"组 {current_group['group_index']} 完成，包含章节: {current_group['chapters']}")
    
    return groups
