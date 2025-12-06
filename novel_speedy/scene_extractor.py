# novel_speedy/scene_extractor.py
"""
场景提取模块

负责从章节中提取"场景数组"，每个场景代表一个独立的叙事片段。
"""

import json
import logging
from typing import List, TypedDict, Optional

from novel_speedy.llm_client import call_llm
from novel_speedy.utils import clean_json_output

logger = logging.getLogger(__name__)


class Scene(TypedDict, total=False):
    """场景结构"""
    scene_index: int       # 场景序号
    summary: str           # 场景摘要
    characters: List[str]  # 出场人物
    location: str          # 地点
    topic: str             # 主题（如：战斗/对话/修炼/转场）


# 系统提示词
SCENE_EXTRACTION_SYSTEM_PROMPT = """你是一名小说"场景提取助手"。
请从给定章节中提取 1～4 个主要场景。
每个场景代表：在同一时间、地点、人物组合下围绕一个事件展开的叙事片段。

场景必须包含：
- scene_index: 场景序号（从1开始）
- summary: 场景摘要（必须，不超过40字）
- characters: 出场人物列表（可选）
- location: 地点（可选）
- topic: 主题类型（如：战斗/对话/修炼/追逐/转场）

【重要】你必须直接输出纯 JSON 数组，不要使用 markdown 代码块包裹，不要输出任何解释文字。"""


def _build_user_prompt(chapter_title: str, chapter_text: str) -> str:
    """
    构建用户提示词
    
    Args:
        chapter_title: 章节标题
        chapter_text: 章节全文
    
    Returns:
        str: 格式化后的用户提示词
    """
    return f"""【章节标题】
{chapter_title}

【章节全文】
{chapter_text}

请从中提取 1～4 个场景（summary 不超过 40 字）。
输出严格 JSON：

[
  {{
    "scene_index": 1,
    "summary": "...",
    "characters": ["角色1", "角色2"],
    "location": "地点",
    "topic": "战斗"
  }}
]"""


def extract_scenes_from_chapter(
    chapter_text: str,
    chapter_title: str,
    max_retries: int = 2
) -> List[Scene]:
    """
    调用 LLM 提取本章的场景数组
    
    Args:
        chapter_text: 章节全文
        chapter_title: 章节标题
        max_retries: 最大重试次数
    
    Returns:
        List[Scene]: 场景列表
    """
    user_prompt = _build_user_prompt(chapter_title, chapter_text)
    messages = [{"role": "user", "content": user_prompt}]
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            raw_response = call_llm(
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
                system_message=SCENE_EXTRACTION_SYSTEM_PROMPT
            )
            
            # 清洗并解析 JSON
            cleaned_json = clean_json_output(raw_response)
            scenes = json.loads(cleaned_json)
            
            # 验证返回格式
            if not isinstance(scenes, list):
                raise ValueError("返回格式不是数组")
            
            if len(scenes) == 0:
                raise ValueError("未提取到任何场景")
            
            # 验证每个场景的必要字段
            validated_scenes: List[Scene] = []
            for i, scene in enumerate(scenes):
                if not isinstance(scene, dict):
                    continue
                    
                # summary 是必须的
                if "summary" not in scene or not scene["summary"]:
                    logger.warning(f"场景 {i} 缺少 summary，跳过")
                    continue
                
                validated_scene: Scene = {
                    "scene_index": scene.get("scene_index", i + 1),
                    "summary": scene["summary"],
                    "characters": scene.get("characters", []),
                    "location": scene.get("location", ""),
                    "topic": scene.get("topic", "")
                }
                validated_scenes.append(validated_scene)
            
            if len(validated_scenes) == 0:
                raise ValueError("验证后无有效场景")
            
            logger.info(f"章节《{chapter_title}》提取到 {len(validated_scenes)} 个场景")
            return validated_scenes
            
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(f"JSON 解析失败 (尝试 {attempt + 1}): {e}")
            
        except ValueError as e:
            last_error = e
            logger.warning(f"场景验证失败 (尝试 {attempt + 1}): {e}")
            
        except Exception as e:
            last_error = e
            logger.warning(f"场景提取失败 (尝试 {attempt + 1}): {e}")
    
    # 所有重试都失败，返回一个默认场景
    logger.error(f"章节《{chapter_title}》场景提取失败，使用默认场景。错误: {last_error}")
    return [{
        "scene_index": 1,
        "summary": f"（提取失败）{chapter_title}",
        "characters": [],
        "location": "",
        "topic": "未知"
    }]


def extract_scenes_batch(
    chapters: List[dict],
    max_chapters: Optional[int] = None
) -> List[dict]:
    """
    批量提取多个章节的场景
    
    Args:
        chapters: 章节列表
        max_chapters: 最多处理的章节数（用于测试）
    
    Returns:
        List[dict]: 带场景信息的章节列表
    """
    if max_chapters:
        chapters = chapters[:max_chapters]
    
    results = []
    
    for i, chapter in enumerate(chapters):
        chapter_index = chapter.get("index", i + 1)
        chapter_title = chapter.get("title", f"第{chapter_index}章")
        chapter_text = chapter.get("text", "")
        
        if not chapter_text:
            logger.warning(f"章节 {chapter_index} 内容为空，跳过")
            continue
        
        logger.info(f"处理章节 {chapter_index}/{len(chapters)}: 《{chapter_title}》")
        
        scenes = extract_scenes_from_chapter(chapter_text, chapter_title)
        
        results.append({
            "index": chapter_index,
            "title": chapter_title,
            "text": chapter_text,
            "scenes": scenes
        })
    
    return results
