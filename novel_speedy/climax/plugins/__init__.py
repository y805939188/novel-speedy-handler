# novel_speedy/climax/plugins/__init__.py
"""
高潮识别评分插件集合

可用插件：
- ConflictPlugin: 情节冲突强度评分
- CoolpointPlugin: 爽点检测评分
- RhythmPlugin: 语言节奏评分
- StructurePlugin: 结构位置评分
"""

from novel_speedy.climax.plugins.conflict import ConflictPlugin
from novel_speedy.climax.plugins.coolpoint import CoolpointPlugin
from novel_speedy.climax.plugins.rhythm import RhythmPlugin
from novel_speedy.climax.plugins.structure import StructurePlugin

__all__ = [
    "ConflictPlugin",
    "CoolpointPlugin",
    "RhythmPlugin",
    "StructurePlugin",
]
