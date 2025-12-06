# novel_speedy/pipeline.py
"""
主流程入口

整合章节切分、场景提取、场景分组等功能。
"""

import json
import logging
from typing import List, Optional

from novel_speedy.scene_extractor import extract_scenes_from_chapter, Scene
from novel_speedy.scene_grouping import group_chapters, ChapterWithScenes, ChapterGroup

logger = logging.getLogger(__name__)


def process_chapters(
    chapters: List[dict],
    max_chapters: Optional[int] = None
) -> List[ChapterGroup]:
    """
    主流程：
    1. 对每章抽取 scenes
    2. 使用上一组判断是否连续
    3. 构建 group 列表
    
    Args:
        chapters: 章节列表，格式为：
            [
                {
                    "index": 1,
                    "title": "第1章 陨落的天才",
                    "text": "章节全文"
                },
                ...
            ]
        max_chapters: 最多处理的章节数（用于测试）
    
    Returns:
        List[ChapterGroup]: 章节组列表
    """
    if not chapters:
        logger.warning("输入章节列表为空")
        return []
    
    # 限制章节数量（用于测试）
    if max_chapters:
        chapters = chapters[:max_chapters]
    
    logger.info(f"开始处理 {len(chapters)} 个章节")
    
    # Step 1: 对每章抽取 scenes
    processed_chapters: List[ChapterWithScenes] = []
    
    for i, chapter in enumerate(chapters):
        chapter_index = chapter.get("index", i + 1)
        chapter_title = chapter.get("title", f"第{chapter_index}章")
        chapter_text = chapter.get("text", "")
        
        if not chapter_text:
            logger.warning(f"章节 {chapter_index} 《{chapter_title}》内容为空，跳过")
            continue
        
        logger.info(f"正在处理章节 {chapter_index}/{len(chapters)}: 《{chapter_title}》")
        
        # 提取场景
        scenes = extract_scenes_from_chapter(
            chapter_text=chapter_text,
            chapter_title=chapter_title
        )
        
        processed_chapter: ChapterWithScenes = {
            "index": chapter_index,
            "title": chapter_title,
            "text": chapter_text,
            "scenes": scenes
        }
        processed_chapters.append(processed_chapter)
        
        logger.info(f"章节 {chapter_index} 提取完成，共 {len(scenes)} 个场景")
    
    # Step 2 & 3: 使用上一组判断是否连续，构建 group 列表
    logger.info("开始进行章节分组...")
    groups = group_chapters(processed_chapters)
    
    logger.info(f"章节分组完成，共 {len(groups)} 个组")
    
    # 输出分组摘要
    for group in groups:
        logger.info(
            f"组 {group['group_index']}: "
            f"章节 {group['chapters']}, "
            f"共 {len(group['group_scenes'])} 个场景"
        )
    
    return groups


def save_results(groups: List[ChapterGroup], output_path: str) -> None:
    """
    将分组结果保存到 JSON 文件
    
    Args:
        groups: 章节组列表
        output_path: 输出文件路径
    """
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)
    
    logger.info(f"结果已保存到: {output_path}")


def load_chapters_from_json(input_path: str) -> List[dict]:
    """
    从 JSON 文件加载章节列表
    
    Args:
        input_path: 输入文件路径
    
    Returns:
        List[dict]: 章节列表
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    logger.info(f"从 {input_path} 加载了 {len(chapters)} 个章节")
    return chapters
