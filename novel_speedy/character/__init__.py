# novel_speedy/character/__init__.py
"""
人物价值评分模块

功能：
1. 识别章节/场景中出现的人物
2. 评估每个人物的戏份占比和重要性
3. 标记主角、配角、龙套
4. 为速读生成提供人物重要性依据
"""

from novel_speedy.character.base import (
    Character,
    CharacterRole,
    CharacterGender,
    CharacterMention,
    CharacterValue,
    CharacterDatabase,
    ChapterCharacterAnalysis,
    SceneCharacterAnalysis,
    determine_role,
    ROLE_THRESHOLDS,
)

from novel_speedy.character.extractor import CharacterExtractor
from novel_speedy.character.analyzer import CharacterAnalyzer, AnalyzerConfig


def analyze_chapters(
    chapters: list,
    use_llm: bool = True,
    protagonist_names: list = None
) -> list:
    """
    便捷函数：分析章节中的人物
    
    Args:
        chapters: 章节列表
        use_llm: 是否使用 LLM
        protagonist_names: 已知主角名列表
    
    Returns:
        分析结果列表
    """
    config = AnalyzerConfig(
        use_llm=use_llm,
        protagonist_names=protagonist_names or []
    )
    analyzer = CharacterAnalyzer(config)
    return analyzer.analyze_chapters(chapters)


__all__ = [
    # 数据类
    "Character",
    "CharacterRole",
    "CharacterGender",
    "CharacterMention",
    "CharacterValue",
    "CharacterDatabase",
    "ChapterCharacterAnalysis",
    "SceneCharacterAnalysis",
    # 工具函数
    "determine_role",
    "ROLE_THRESHOLDS",
    # 核心类
    "CharacterExtractor",
    "CharacterAnalyzer",
    "AnalyzerConfig",
    # 便捷函数
    "analyze_chapters",
]
