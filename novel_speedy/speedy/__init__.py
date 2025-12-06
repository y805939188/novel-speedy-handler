# novel_speedy/speedy/__init__.py
"""
速读生成模块
"""

from novel_speedy.speedy.budget_calculator import (
    SpeedyBudgetConfig,
    ChapterBudgetResult,
    SpeedyBudgetPlan,
    SpeedyBudgetCalculator,
    calculate_speedy_budget,
)

from novel_speedy.speedy.outline_generator import (
    OutlineConfig,
    ChapterSummary,
    StoryArc,
    BookOutline,
    OutlineGenerator,
    generate_outline,
)

from novel_speedy.speedy.compressor import (
    CompressionStrategy,
    CompressionConfig,
    CompressedChapter,
    ChapterCompressor,
    compress_chapter,
)

from novel_speedy.speedy.generator import (
    STYLE_PRESETS,
    SpeedyConfig,
    SpeedyResult,
    SpeedyGenerator,
    generate_speedy,
)

__all__ = [
    # 预算计算
    "SpeedyBudgetConfig",
    "ChapterBudgetResult",
    "SpeedyBudgetPlan",
    "SpeedyBudgetCalculator",
    "calculate_speedy_budget",
    # 大纲生成
    "OutlineConfig",
    "ChapterSummary",
    "StoryArc",
    "BookOutline",
    "OutlineGenerator",
    "generate_outline",
    # 内容压缩
    "CompressionStrategy",
    "CompressionConfig",
    "CompressedChapter",
    "ChapterCompressor",
    "compress_chapter",
    # 速读生成
    "STYLE_PRESETS",
    "SpeedyConfig",
    "SpeedyResult",
    "SpeedyGenerator",
    "generate_speedy",
]
