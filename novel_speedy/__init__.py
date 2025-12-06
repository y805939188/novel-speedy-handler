# novel_speedy/__init__.py
"""
小说速读系统 (Novel Speedy Reader)

一个基于 AI 的长篇小说速读生成工具。
"""

__version__ = "0.1.0"

from novel_speedy.config import config, Config, LLMConfig, PathConfig
from novel_speedy.chapter_splitter import (
    Chapter,
    ChapterSplitter, 
    split_chapters, 
    load_chapters, 
    save_chapters
)
from novel_speedy.scene_extractor import Scene, extract_scenes_from_chapter
from novel_speedy.scene_grouping import ChapterGroup, group_chapters
from novel_speedy.pipeline import process_chapters, save_results

__all__ = [
    # 版本
    "__version__",
    # 配置
    "config",
    "Config",
    "LLMConfig", 
    "PathConfig",
    # 章节切分
    "Chapter",
    "ChapterSplitter",
    "split_chapters",
    "load_chapters",
    "save_chapters",
    # 场景提取
    "Scene",
    "extract_scenes_from_chapter",
    # 场景分组
    "ChapterGroup",
    "group_chapters",
    # 流程
    "process_chapters",
    "save_results",
]
