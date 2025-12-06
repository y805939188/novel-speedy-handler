# novel_speedy/climax/__init__.py
"""
高潮识别插件系统

提供多维度的章节高潮评分能力：
- 情节冲突强度 (ConflictPlugin)
- 爽点检测 (CoolpointPlugin)
- 语言节奏 (RhythmPlugin)
- 结构位置 (StructurePlugin)

使用方式：
```python
from novel_speedy.climax import ClimaxAnalyzer, analyze_chapters

# 方式1：使用分析器
analyzer = ClimaxAnalyzer()
results = analyzer.analyze_chapters(chapters)
analyzer.print_analysis_report(results)

# 方式2：使用便捷函数
results = analyze_chapters(chapters, max_chapters=10)
```
"""

from novel_speedy.climax.base import (
    ScoreDimension,
    DimensionScore,
    ChapterClimaxScore,
    SceneClimaxScore,
    ClimaxPlugin,
    PluginRegistry
)

from novel_speedy.climax.aggregator import (
    AggregationStrategy,
    ScoreAggregator,
    aggregate_scores
)

from novel_speedy.climax.analyzer import (
    AnalyzerConfig,
    ClimaxAnalyzer,
    analyze_chapter,
    analyze_chapters
)

# 导入插件以触发注册
from novel_speedy.climax import plugins

__all__ = [
    # 基础类型
    "ScoreDimension",
    "DimensionScore",
    "ChapterClimaxScore",
    "SceneClimaxScore",
    "ClimaxPlugin",
    "PluginRegistry",
    # 聚合
    "AggregationStrategy",
    "ScoreAggregator",
    "aggregate_scores",
    # 分析器
    "AnalyzerConfig",
    "ClimaxAnalyzer",
    "analyze_chapter",
    "analyze_chapters",
    # 插件
    "plugins",
]
