# novel_speedy/climax/base.py
"""
高潮识别插件系统 - 基础接口定义

定义评分插件的抽象基类和通用数据结构。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ScoreDimension(Enum):
    """评分维度枚举"""
    CONFLICT = "conflict"           # 情节冲突强度
    COOLPOINT = "coolpoint"         # 爽点检测
    RHYTHM = "rhythm"               # 语言节奏
    STRUCTURE = "structure"         # 结构位置
    EMOTION = "emotion"             # 情感强度
    SUSPENSE = "suspense"           # 悬念紧张度
    CUSTOM = "custom"               # 自定义维度


@dataclass
class DimensionScore:
    """单维度评分结果"""
    dimension: ScoreDimension
    score: float                    # 0.0 ~ 1.0
    confidence: float = 1.0         # 置信度 0.0 ~ 1.0
    reason: str = ""                # 评分理由
    details: Dict[str, Any] = field(default_factory=dict)  # 额外细节
    
    def weighted_score(self, weight: float = 1.0) -> float:
        """计算加权分数"""
        return self.score * self.confidence * weight


@dataclass
class ChapterClimaxScore:
    """章节高潮综合评分"""
    chapter_index: int
    chapter_title: str
    
    # 各维度评分
    dimension_scores: List[DimensionScore] = field(default_factory=list)
    
    # 综合分数（0.0 ~ 1.0）
    final_score: float = 0.0
    
    # 是否为高潮章节
    is_climax: bool = False
    
    # 高潮类型标签
    climax_tags: List[str] = field(default_factory=list)
    
    # 摘要说明
    summary: str = ""
    
    def get_dimension_score(self, dimension: ScoreDimension) -> Optional[DimensionScore]:
        """获取指定维度的评分"""
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds
        return None
    
    def to_dict(self) -> dict:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "final_score": round(self.final_score, 4),
            "is_climax": self.is_climax,
            "climax_tags": self.climax_tags,
            "summary": self.summary,
            "dimension_scores": [
                {
                    "dimension": ds.dimension.value,
                    "score": round(ds.score, 4),
                    "confidence": round(ds.confidence, 4),
                    "reason": ds.reason
                }
                for ds in self.dimension_scores
            ]
        }


@dataclass
class SceneClimaxScore:
    """场景高潮评分（更细粒度）"""
    scene_index: int
    scene_summary: str
    
    dimension_scores: List[DimensionScore] = field(default_factory=list)
    final_score: float = 0.0
    is_climax: bool = False
    climax_tags: List[str] = field(default_factory=list)


class ClimaxPlugin(ABC):
    """
    高潮识别插件抽象基类
    
    所有评分插件都需要继承此类并实现 score_chapter 方法。
    """
    
    # 插件名称
    name: str = "base_plugin"
    
    # 评分维度
    dimension: ScoreDimension = ScoreDimension.CUSTOM
    
    # 默认权重
    default_weight: float = 1.0
    
    # 是否需要调用 LLM
    requires_llm: bool = False
    
    def __init__(self, weight: Optional[float] = None):
        """
        初始化插件
        
        Args:
            weight: 自定义权重，默认使用 default_weight
        """
        self.weight = weight if weight is not None else self.default_weight
    
    @abstractmethod
    def score_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """
        对章节进行评分
        
        Args:
            chapter_text: 章节全文
            chapter_title: 章节标题
            chapter_index: 章节序号
            context: 上下文信息（可选），可包含：
                - scenes: 该章节的场景列表
                - total_chapters: 总章节数
                - prev_chapters: 前几章的信息
                - novel_info: 小说元信息
        
        Returns:
            DimensionScore: 该维度的评分结果
        """
        pass
    
    def score_scene(
        self,
        scene_text: str,
        scene_summary: str,
        scene_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """
        对场景进行评分（可选实现）
        
        默认实现：复用 score_chapter 逻辑
        """
        return self.score_chapter(
            chapter_text=scene_text,
            chapter_title=scene_summary,
            chapter_index=scene_index,
            context=context
        )
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, dimension={self.dimension.value}, weight={self.weight})"


class PluginRegistry:
    """
    插件注册表
    
    管理所有已注册的评分插件。
    """
    
    _plugins: Dict[str, type] = {}
    
    @classmethod
    def register(cls, plugin_class: type) -> type:
        """
        注册插件（装饰器）
        
        Usage:
            @PluginRegistry.register
            class MyPlugin(ClimaxPlugin):
                ...
        """
        if not issubclass(plugin_class, ClimaxPlugin):
            raise TypeError(f"{plugin_class} 必须继承 ClimaxPlugin")
        
        cls._plugins[plugin_class.name] = plugin_class
        return plugin_class
    
    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """获取插件类"""
        return cls._plugins.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, type]:
        """获取所有已注册插件"""
        return cls._plugins.copy()
    
    @classmethod
    def list_plugins(cls) -> List[str]:
        """列出所有插件名称"""
        return list(cls._plugins.keys())
    
    @classmethod
    def create(cls, name: str, **kwargs) -> ClimaxPlugin:
        """创建插件实例"""
        plugin_class = cls.get(name)
        if plugin_class is None:
            raise ValueError(f"未找到插件: {name}")
        return plugin_class(**kwargs)
