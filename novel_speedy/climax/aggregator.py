# novel_speedy/climax/aggregator.py
"""
评分聚合器

将多个维度的评分聚合为最终的高潮分数。
支持多种聚合策略。
"""

import logging
from typing import List, Dict, Optional
from enum import Enum

from novel_speedy.climax.base import DimensionScore, ChapterClimaxScore, ScoreDimension

logger = logging.getLogger(__name__)


class AggregationStrategy(Enum):
    """聚合策略"""
    WEIGHTED_AVERAGE = "weighted_average"   # 加权平均
    MAX = "max"                             # 取最大值
    HARMONIC_MEAN = "harmonic_mean"         # 调和平均
    GEOMETRIC_MEAN = "geometric_mean"       # 几何平均
    RANK_FUSION = "rank_fusion"             # 排名融合


class ScoreAggregator:
    """
    评分聚合器
    
    将多个维度的评分聚合为单一的最终分数。
    """
    
    # 默认维度权重
    DEFAULT_WEIGHTS = {
        ScoreDimension.CONFLICT: 1.0,
        ScoreDimension.COOLPOINT: 1.2,
        ScoreDimension.RHYTHM: 0.8,
        ScoreDimension.STRUCTURE: 0.6,
        ScoreDimension.EMOTION: 0.9,
        ScoreDimension.SUSPENSE: 0.9,
        ScoreDimension.CUSTOM: 1.0,
    }
    
    # 高潮阈值
    DEFAULT_CLIMAX_THRESHOLD = 0.6
    
    def __init__(
        self,
        strategy: AggregationStrategy = AggregationStrategy.WEIGHTED_AVERAGE,
        weights: Optional[Dict[ScoreDimension, float]] = None,
        climax_threshold: float = DEFAULT_CLIMAX_THRESHOLD
    ):
        """
        初始化聚合器
        
        Args:
            strategy: 聚合策略
            weights: 自定义维度权重
            climax_threshold: 高潮判定阈值
        """
        self.strategy = strategy
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.climax_threshold = climax_threshold
    
    def aggregate(
        self,
        dimension_scores: List[DimensionScore],
        chapter_index: int,
        chapter_title: str
    ) -> ChapterClimaxScore:
        """
        聚合多维度评分
        
        Args:
            dimension_scores: 各维度评分列表
            chapter_index: 章节序号
            chapter_title: 章节标题
        
        Returns:
            ChapterClimaxScore: 综合评分结果
        """
        if not dimension_scores:
            return ChapterClimaxScore(
                chapter_index=chapter_index,
                chapter_title=chapter_title,
                dimension_scores=[],
                final_score=0.0,
                is_climax=False,
                summary="无评分数据"
            )
        
        # 根据策略计算最终分数
        if self.strategy == AggregationStrategy.WEIGHTED_AVERAGE:
            final_score = self._weighted_average(dimension_scores)
        elif self.strategy == AggregationStrategy.MAX:
            final_score = self._max_score(dimension_scores)
        elif self.strategy == AggregationStrategy.HARMONIC_MEAN:
            final_score = self._harmonic_mean(dimension_scores)
        elif self.strategy == AggregationStrategy.GEOMETRIC_MEAN:
            final_score = self._geometric_mean(dimension_scores)
        else:
            final_score = self._weighted_average(dimension_scores)
        
        # 判断是否为高潮
        is_climax = final_score >= self.climax_threshold
        
        # 生成高潮标签
        climax_tags = self._generate_tags(dimension_scores, final_score)
        
        # 生成摘要
        summary = self._generate_summary(dimension_scores, final_score, is_climax)
        
        return ChapterClimaxScore(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            dimension_scores=dimension_scores,
            final_score=final_score,
            is_climax=is_climax,
            climax_tags=climax_tags,
            summary=summary
        )
    
    def _weighted_average(self, scores: List[DimensionScore]) -> float:
        """加权平均"""
        total_weight = 0.0
        weighted_sum = 0.0
        
        for ds in scores:
            weight = self.weights.get(ds.dimension, 1.0)
            # 考虑置信度
            effective_weight = weight * ds.confidence
            weighted_sum += ds.score * effective_weight
            total_weight += effective_weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    def _max_score(self, scores: List[DimensionScore]) -> float:
        """取最大值"""
        if not scores:
            return 0.0
        return max(ds.score * ds.confidence for ds in scores)
    
    def _harmonic_mean(self, scores: List[DimensionScore]) -> float:
        """调和平均（对低分更敏感）"""
        valid_scores = [ds.score * ds.confidence for ds in scores if ds.score > 0]
        if not valid_scores:
            return 0.0
        
        harmonic = len(valid_scores) / sum(1.0 / s for s in valid_scores)
        return harmonic
    
    def _geometric_mean(self, scores: List[DimensionScore]) -> float:
        """几何平均"""
        valid_scores = [ds.score * ds.confidence for ds in scores if ds.score > 0]
        if not valid_scores:
            return 0.0
        
        product = 1.0
        for s in valid_scores:
            product *= s
        
        return product ** (1.0 / len(valid_scores))
    
    def _generate_tags(
        self,
        scores: List[DimensionScore],
        final_score: float
    ) -> List[str]:
        """生成高潮标签"""
        tags = []
        
        for ds in scores:
            if ds.score >= 0.7:
                if ds.dimension == ScoreDimension.CONFLICT:
                    tags.append("激烈冲突")
                elif ds.dimension == ScoreDimension.COOLPOINT:
                    # 添加具体爽点类型
                    coolpoint_types = ds.details.get("type_labels", [])
                    tags.extend(coolpoint_types[:2])  # 最多2个
                elif ds.dimension == ScoreDimension.RHYTHM:
                    tags.append("节奏紧张")
                elif ds.dimension == ScoreDimension.STRUCTURE:
                    structure_type = ds.details.get("structure_type", "")
                    if structure_type == "major_climax":
                        tags.append("关键转折")
                    elif structure_type == "ending":
                        tags.append("高潮结局")
        
        return list(set(tags))[:4]  # 去重，最多4个标签
    
    def _generate_summary(
        self,
        scores: List[DimensionScore],
        final_score: float,
        is_climax: bool
    ) -> str:
        """生成摘要"""
        if not scores:
            return "无评分数据"
        
        # 找出最高分维度
        top_score = max(scores, key=lambda ds: ds.score)
        
        level = "高潮" if is_climax else ("中等" if final_score >= 0.4 else "平缓")
        
        summary_parts = [f"{level}章节"]
        
        if top_score.reason:
            summary_parts.append(top_score.reason)
        
        return "，".join(summary_parts)


def aggregate_scores(
    dimension_scores: List[DimensionScore],
    chapter_index: int,
    chapter_title: str,
    strategy: str = "weighted_average",
    climax_threshold: float = 0.6
) -> ChapterClimaxScore:
    """
    便捷函数：聚合评分
    
    Args:
        dimension_scores: 各维度评分列表
        chapter_index: 章节序号
        chapter_title: 章节标题
        strategy: 聚合策略名称
        climax_threshold: 高潮阈值
    
    Returns:
        ChapterClimaxScore: 综合评分结果
    """
    strategy_enum = AggregationStrategy(strategy)
    aggregator = ScoreAggregator(
        strategy=strategy_enum,
        climax_threshold=climax_threshold
    )
    return aggregator.aggregate(dimension_scores, chapter_index, chapter_title)
