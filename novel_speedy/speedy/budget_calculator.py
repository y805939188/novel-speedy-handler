# novel_speedy/speedy/budget_calculator.py
"""
速读字数预算计算器

基于高潮评分，为每一章计算目标字数预算。

核心算法：
1. 根据阅读速度和预期时间计算总字数预算
2. 使用高潮评分计算每章的重要性权重
3. 归一化分配每章预算，高潮章节获得更多预算
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SpeedyBudgetConfig:
    """速读预算配置"""
    
    # ===== 阅读参数 =====
    reading_speed: float = 300.0        # 阅读速度（字/分钟）
    target_time_minutes: float = 60.0   # 目标阅读时间（分钟）
    
    # ===== 或者直接指定总字数 =====
    total_budget_chars: Optional[int] = None  # 直接指定总字数预算
    
    # ===== 高潮权重参数 =====
    # 高潮分数会乘以权重系数，再加上基础系数
    # 最终权重 = base_weight + climax_score * climax_weight_multiplier
    base_weight: float = 0.3             # 基础权重（所有章节至少有这么多）
    climax_weight_multiplier: float = 1.5  # 高潮分数权重乘数
    
    # ===== 约束参数 =====
    min_chapter_chars: int = 100         # 每章最少字数
    max_compression_ratio: float = 0.8   # 最大保留比例（不超过原文的 80%）
    min_compression_ratio: float = 0.02  # 最小保留比例（至少保留 2%）
    
    @property
    def calculated_total_budget(self) -> int:
        """计算总字数预算"""
        if self.total_budget_chars is not None:
            return self.total_budget_chars
        return int(self.target_time_minutes * self.reading_speed)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_speed": self.reading_speed,
            "target_time_minutes": self.target_time_minutes,
            "total_budget_chars": self.calculated_total_budget,
            "base_weight": self.base_weight,
            "climax_weight_multiplier": self.climax_weight_multiplier,
            "min_chapter_chars": self.min_chapter_chars,
            "max_compression_ratio": self.max_compression_ratio,
            "min_compression_ratio": self.min_compression_ratio,
        }


@dataclass
class ChapterBudgetResult:
    """单章预算结果"""
    chapter_index: int
    chapter_title: str
    
    # 原文信息
    original_chars: int
    
    # 高潮评分信息
    climax_score: float = 0.5           # 高潮分数 (0-1)
    is_climax: bool = False             # 是否为高潮章节
    climax_tags: List[str] = field(default_factory=list)
    
    # 计算的权重
    importance_weight: float = 0.5      # 重要性权重（归一化前）
    normalized_weight: float = 0.0      # 归一化后的权重
    
    # 预算结果
    budget_chars: int = 0               # 预算字数
    compression_ratio: float = 0.0      # 压缩比例（预算/原文）
    
    # 预估阅读时间
    estimated_reading_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "original_chars": self.original_chars,
            "climax_score": round(self.climax_score, 3),
            "is_climax": self.is_climax,
            "climax_tags": self.climax_tags,
            "importance_weight": round(self.importance_weight, 4),
            "normalized_weight": round(self.normalized_weight, 4),
            "budget_chars": self.budget_chars,
            "compression_ratio": round(self.compression_ratio, 4),
            "estimated_reading_seconds": round(self.estimated_reading_seconds, 1),
        }


@dataclass
class SpeedyBudgetPlan:
    """速读预算计划"""
    config: SpeedyBudgetConfig
    chapters: List[ChapterBudgetResult] = field(default_factory=list)
    
    @property
    def total_original_chars(self) -> int:
        """原文总字数"""
        return sum(ch.original_chars for ch in self.chapters)
    
    @property
    def total_budget_chars(self) -> int:
        """预算总字数"""
        return sum(ch.budget_chars for ch in self.chapters)
    
    @property
    def overall_compression_ratio(self) -> float:
        """整体压缩比例"""
        if self.total_original_chars == 0:
            return 0.0
        return self.total_budget_chars / self.total_original_chars
    
    @property
    def estimated_total_reading_minutes(self) -> float:
        """预估总阅读时间（分钟）"""
        return self.total_budget_chars / self.config.reading_speed
    
    @property
    def climax_chapter_count(self) -> int:
        """高潮章节数量"""
        return sum(1 for ch in self.chapters if ch.is_climax)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_chapters": len(self.chapters),
                "climax_chapters": self.climax_chapter_count,
                "total_original_chars": self.total_original_chars,
                "total_budget_chars": self.total_budget_chars,
                "overall_compression_ratio": round(self.overall_compression_ratio, 4),
                "target_reading_minutes": self.config.target_time_minutes,
                "estimated_reading_minutes": round(self.estimated_total_reading_minutes, 1),
            },
            "config": self.config.to_dict(),
            "chapters": [ch.to_dict() for ch in self.chapters],
        }
    
    def print_summary(self) -> None:
        """打印预算摘要"""
        print("\n" + "=" * 80)
        print("📊 速读字数预算计划")
        print("=" * 80)
        
        # 配置信息
        print(f"\n📝 配置参数:")
        print(f"   阅读速度: {self.config.reading_speed} 字/分钟")
        print(f"   目标阅读时间: {self.config.target_time_minutes} 分钟")
        print(f"   目标总字数: {self.config.calculated_total_budget:,} 字")
        
        # 统计信息
        print(f"\n📈 统计信息:")
        print(f"   章节总数: {len(self.chapters)}")
        print(f"   高潮章节: {self.climax_chapter_count}")
        print(f"   原文总字数: {self.total_original_chars:,} 字")
        print(f"   预算总字数: {self.total_budget_chars:,} 字")
        print(f"   整体压缩比: {self.overall_compression_ratio:.2%}")
        print(f"   预估阅读时间: {self.estimated_total_reading_minutes:.1f} 分钟")
        
        # 章节详情（前10章）
        print(f"\n📖 章节预算详情（前10章）:")
        print("-" * 80)
        print(f"{'章节':<6} {'标题':<20} {'原文':<10} {'预算':<10} {'压缩比':<10} {'高潮分':<8} {'标记':<10}")
        print("-" * 80)
        
        for ch in self.chapters[:10]:
            title = ch.chapter_title[:18] + ".." if len(ch.chapter_title) > 20 else ch.chapter_title
            climax_mark = "🔥" if ch.is_climax else ""
            print(f"{ch.chapter_index:<6} {title:<20} {ch.original_chars:<10,} {ch.budget_chars:<10,} "
                  f"{ch.compression_ratio:<10.2%} {ch.climax_score:<8.2f} {climax_mark:<10}")
        
        if len(self.chapters) > 10:
            print(f"... 还有 {len(self.chapters) - 10} 章 ...")
        
        print("=" * 80)


class SpeedyBudgetCalculator:
    """速读字数预算计算器"""
    
    def __init__(self, config: Optional[SpeedyBudgetConfig] = None):
        self.config = config or SpeedyBudgetConfig()
    
    def calculate(
        self,
        chapters: List[Dict[str, Any]],
        climax_scores: Optional[List[Dict[str, Any]]] = None
    ) -> SpeedyBudgetPlan:
        """
        计算每章的字数预算
        
        Args:
            chapters: 章节列表，需包含 index, title, text 或 char_count
            climax_scores: 高潮评分列表，需包含 chapter_index, final_score, is_climax, climax_tags
        
        Returns:
            SpeedyBudgetPlan: 预算计划
        """
        logger.info(f"开始计算速读预算: {len(chapters)} 章")
        
        # 1. 构建高潮评分映射
        climax_map = self._build_climax_map(climax_scores)
        
        # 2. 构建章节预算结果列表
        chapter_results = self._build_chapter_results(chapters, climax_map)
        
        if not chapter_results:
            return SpeedyBudgetPlan(config=self.config)
        
        # 3. 计算重要性权重
        self._calculate_importance_weights(chapter_results)
        
        # 4. 归一化权重
        self._normalize_weights(chapter_results)
        
        # 5. 分配预算
        self._allocate_budget(chapter_results)
        
        # 6. 应用约束
        self._apply_constraints(chapter_results)
        
        # 7. 最终归一化（确保总预算接近目标）
        self._final_normalize(chapter_results)
        
        # 8. 计算阅读时间
        self._calculate_reading_time(chapter_results)
        
        plan = SpeedyBudgetPlan(config=self.config, chapters=chapter_results)
        
        logger.info(
            f"预算计算完成: {plan.total_budget_chars:,} 字 / {plan.total_original_chars:,} 字 "
            f"({plan.overall_compression_ratio:.2%})"
        )
        
        return plan
    
    def _build_climax_map(
        self,
        climax_scores: Optional[List[Dict[str, Any]]]
    ) -> Dict[int, Dict[str, Any]]:
        """构建高潮评分映射"""
        if not climax_scores:
            return {}
        
        climax_map = {}
        for score in climax_scores:
            chapter_index = score.get("chapter_index", 0)
            climax_map[chapter_index] = {
                "final_score": score.get("final_score", 0.5),
                "is_climax": score.get("is_climax", False),
                "climax_tags": score.get("climax_tags", []),
            }
        
        return climax_map
    
    def _build_chapter_results(
        self,
        chapters: List[Dict[str, Any]],
        climax_map: Dict[int, Dict[str, Any]]
    ) -> List[ChapterBudgetResult]:
        """构建章节预算结果列表"""
        results = []
        
        for ch in chapters:
            index = ch.get("index", 0)
            title = ch.get("title", f"第{index}章")
            
            # 获取字数
            if "char_count" in ch:
                char_count = ch["char_count"]
            elif "text" in ch:
                char_count = len(ch["text"])
            else:
                char_count = 0
            
            # 获取高潮评分
            climax_info = climax_map.get(index, {})
            climax_score = climax_info.get("final_score", 0.5)
            is_climax = climax_info.get("is_climax", False)
            climax_tags = climax_info.get("climax_tags", [])
            
            result = ChapterBudgetResult(
                chapter_index=index,
                chapter_title=title,
                original_chars=char_count,
                climax_score=climax_score,
                is_climax=is_climax,
                climax_tags=climax_tags,
            )
            
            results.append(result)
        
        return results
    
    def _calculate_importance_weights(
        self,
        chapters: List[ChapterBudgetResult]
    ) -> None:
        """
        计算重要性权重
        
        公式: weight = base_weight + climax_score * multiplier
        
        这样：
        - climax_score = 0 时，weight = base_weight = 0.3
        - climax_score = 1 时，weight = 0.3 + 1.5 = 1.8
        - 高潮章节相对于低谷章节，权重比为 1.8 : 0.3 = 6 : 1
        """
        for ch in chapters:
            ch.importance_weight = (
                self.config.base_weight + 
                ch.climax_score * self.config.climax_weight_multiplier
            )
    
    def _normalize_weights(
        self,
        chapters: List[ChapterBudgetResult]
    ) -> None:
        """归一化权重，使其总和为 1"""
        total_weight = sum(ch.importance_weight for ch in chapters)
        
        if total_weight == 0:
            # 均匀分配
            for ch in chapters:
                ch.normalized_weight = 1.0 / len(chapters)
        else:
            for ch in chapters:
                ch.normalized_weight = ch.importance_weight / total_weight
    
    def _allocate_budget(
        self,
        chapters: List[ChapterBudgetResult]
    ) -> None:
        """根据归一化权重分配预算"""
        total_budget = self.config.calculated_total_budget
        
        for ch in chapters:
            ch.budget_chars = int(total_budget * ch.normalized_weight)
            ch.compression_ratio = (
                ch.budget_chars / ch.original_chars 
                if ch.original_chars > 0 else 0
            )
    
    def _apply_constraints(
        self,
        chapters: List[ChapterBudgetResult]
    ) -> None:
        """应用约束条件"""
        for ch in chapters:
            # 最小字数约束
            if ch.budget_chars < self.config.min_chapter_chars:
                ch.budget_chars = self.config.min_chapter_chars
            
            # 最大压缩比约束（不能保留超过原文的 max_compression_ratio）
            if ch.original_chars > 0:
                max_budget = int(ch.original_chars * self.config.max_compression_ratio)
                if ch.budget_chars > max_budget:
                    ch.budget_chars = max_budget
                
                # 最小压缩比约束（至少保留 min_compression_ratio）
                min_budget = max(
                    self.config.min_chapter_chars,
                    int(ch.original_chars * self.config.min_compression_ratio)
                )
                if ch.budget_chars < min_budget:
                    ch.budget_chars = min_budget
            
            # 更新压缩比
            ch.compression_ratio = (
                ch.budget_chars / ch.original_chars 
                if ch.original_chars > 0 else 0
            )
    
    def _final_normalize(
        self,
        chapters: List[ChapterBudgetResult]
    ) -> None:
        """最终归一化，确保总预算接近目标"""
        current_total = sum(ch.budget_chars for ch in chapters)
        target = self.config.calculated_total_budget
        
        if current_total == 0:
            return
        
        # 计算调整比例
        scale = target / current_total
        
        # 允许 5% 的误差
        if abs(scale - 1.0) > 0.05:
            for ch in chapters:
                new_budget = int(ch.budget_chars * scale)
                # 确保不低于最小值
                ch.budget_chars = max(self.config.min_chapter_chars, new_budget)
                ch.compression_ratio = (
                    ch.budget_chars / ch.original_chars 
                    if ch.original_chars > 0 else 0
                )
    
    def _calculate_reading_time(
        self,
        chapters: List[ChapterBudgetResult]
    ) -> None:
        """计算预估阅读时间"""
        for ch in chapters:
            # 转换为秒
            ch.estimated_reading_seconds = (
                ch.budget_chars / self.config.reading_speed * 60
            )


def calculate_speedy_budget(
    chapters: List[Dict[str, Any]],
    climax_scores: Optional[List[Dict[str, Any]]] = None,
    target_time_minutes: float = 60.0,
    reading_speed: float = 300.0,
    total_budget_chars: Optional[int] = None
) -> SpeedyBudgetPlan:
    """
    便捷函数：计算速读字数预算
    
    Args:
        chapters: 章节列表
        climax_scores: 高潮评分列表
        target_time_minutes: 目标阅读时间（分钟）
        reading_speed: 阅读速度（字/分钟）
        total_budget_chars: 直接指定总字数（优先于时间计算）
    
    Returns:
        SpeedyBudgetPlan: 预算计划
    
    Example:
        >>> chapters = load_chapters("chapters.json")
        >>> climax_scores = load_json("climax_scores.json")
        >>> plan = calculate_speedy_budget(
        ...     chapters, 
        ...     climax_scores,
        ...     target_time_minutes=30
        ... )
        >>> plan.print_summary()
    """
    config = SpeedyBudgetConfig(
        reading_speed=reading_speed,
        target_time_minutes=target_time_minutes,
        total_budget_chars=total_budget_chars,
    )
    calculator = SpeedyBudgetCalculator(config)
    return calculator.calculate(chapters, climax_scores)


def load_and_calculate(
    chapters_path: str,
    climax_scores_path: str,
    target_time_minutes: float = 60.0,
    reading_speed: float = 300.0
) -> SpeedyBudgetPlan:
    """
    从文件加载数据并计算预算
    
    Args:
        chapters_path: 章节文件路径
        climax_scores_path: 高潮评分文件路径
        target_time_minutes: 目标阅读时间
        reading_speed: 阅读速度
    
    Returns:
        SpeedyBudgetPlan: 预算计划
    """
    # 加载章节
    with open(chapters_path, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    # 加载高潮评分
    with open(climax_scores_path, 'r', encoding='utf-8') as f:
        climax_scores = json.load(f)
    
    return calculate_speedy_budget(
        chapters=chapters,
        climax_scores=climax_scores,
        target_time_minutes=target_time_minutes,
        reading_speed=reading_speed
    )
