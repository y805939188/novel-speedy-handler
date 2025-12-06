# novel_speedy/budget.py
"""
篇幅预算模块

根据阅读时间目标，计算总字数预算，并按章节/场景组分配。
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """预算配置"""
    # 目标阅读时间（分钟）
    target_time_minutes: float = 30.0
    
    # 阅读速度（字/分钟），默认 300 字/分钟
    reading_speed: float = 300.0
    
    # 允许的误差范围（±10%）
    tolerance: float = 0.1
    
    # 最小章节预算（字），避免某些章节被压缩得太小
    min_chapter_budget: int = 200
    
    # 最大压缩比例（原文的百分比），避免某些章节被过度压缩
    max_compression_ratio: float = 0.5
    
    @property
    def total_budget(self) -> int:
        """计算总字数预算"""
        return int(self.target_time_minutes * self.reading_speed)
    
    @property
    def budget_range(self) -> tuple:
        """计算允许的预算范围"""
        total = self.total_budget
        return (
            int(total * (1 - self.tolerance)),
            int(total * (1 + self.tolerance))
        )


@dataclass
class ChapterBudget:
    """章节预算"""
    chapter_index: int
    chapter_title: str
    original_chars: int
    
    # 预算字数
    budget_chars: int = 0
    
    # 压缩比例（预算 / 原文）
    compression_ratio: float = 0.0
    
    # 重要性分数（0-1），用于加权分配
    importance_score: float = 0.5
    
    def to_dict(self) -> dict:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "original_chars": self.original_chars,
            "budget_chars": self.budget_chars,
            "compression_ratio": round(self.compression_ratio, 4),
            "importance_score": round(self.importance_score, 2)
        }


@dataclass
class BudgetPlan:
    """预算计划"""
    config: BudgetConfig
    chapters: List[ChapterBudget] = field(default_factory=list)
    
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
    
    def is_within_tolerance(self) -> bool:
        """检查是否在允许范围内"""
        min_budget, max_budget = self.config.budget_range
        return min_budget <= self.total_budget_chars <= max_budget
    
    def summary(self) -> dict:
        """生成摘要"""
        return {
            "target_time_minutes": self.config.target_time_minutes,
            "reading_speed": self.config.reading_speed,
            "target_budget": self.config.total_budget,
            "budget_range": self.config.budget_range,
            "total_original_chars": self.total_original_chars,
            "total_budget_chars": self.total_budget_chars,
            "overall_compression_ratio": round(self.overall_compression_ratio, 4),
            "chapter_count": len(self.chapters),
            "is_within_tolerance": self.is_within_tolerance()
        }
    
    def print_summary(self) -> None:
        """打印预算摘要"""
        s = self.summary()
        print("=" * 60)
        print("📊 篇幅预算计划")
        print("=" * 60)
        print(f"目标阅读时间: {s['target_time_minutes']} 分钟")
        print(f"阅读速度: {s['reading_speed']} 字/分钟")
        print(f"目标字数: {s['target_budget']:,} 字")
        print(f"允许范围: {s['budget_range'][0]:,} ~ {s['budget_range'][1]:,} 字")
        print("-" * 60)
        print(f"原文总字数: {s['total_original_chars']:,} 字")
        print(f"预算总字数: {s['total_budget_chars']:,} 字")
        print(f"整体压缩比: {s['overall_compression_ratio']:.2%}")
        print(f"章节数量: {s['chapter_count']}")
        print(f"是否在范围内: {'✅ 是' if s['is_within_tolerance'] else '❌ 否'}")
        print("=" * 60)


class BudgetAllocator:
    """
    预算分配器
    
    支持多种分配策略：
    - uniform: 均匀分配
    - proportional: 按原文长度比例分配
    - weighted: 按重要性加权分配（需要提供 importance_scores）
    """
    
    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
    
    def allocate(
        self,
        chapters: List[dict],
        strategy: str = "proportional",
        importance_scores: Optional[Dict[int, float]] = None
    ) -> BudgetPlan:
        """
        分配预算
        
        Args:
            chapters: 章节列表，每个章节需包含 index, title, text 或 char_count
            strategy: 分配策略 ("uniform", "proportional", "weighted")
            importance_scores: 重要性分数字典 {chapter_index: score}
        
        Returns:
            BudgetPlan: 预算计划
        """
        if not chapters:
            return BudgetPlan(config=self.config)
        
        # 构建章节预算列表
        chapter_budgets = []
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
            
            # 获取重要性分数
            if importance_scores and index in importance_scores:
                importance = importance_scores[index]
            else:
                importance = 0.5  # 默认中等重要性
            
            chapter_budgets.append(ChapterBudget(
                chapter_index=index,
                chapter_title=title,
                original_chars=char_count,
                importance_score=importance
            ))
        
        # 根据策略分配预算
        if strategy == "uniform":
            self._allocate_uniform(chapter_budgets)
        elif strategy == "weighted":
            self._allocate_weighted(chapter_budgets)
        else:  # proportional
            self._allocate_proportional(chapter_budgets)
        
        # 应用约束（最小预算、最大压缩比）
        self._apply_constraints(chapter_budgets)
        
        # 归一化，确保总预算在范围内
        self._normalize(chapter_budgets)
        
        plan = BudgetPlan(config=self.config, chapters=chapter_budgets)
        
        logger.info(f"预算分配完成: {plan.total_budget_chars:,} 字 / {plan.total_original_chars:,} 字")
        
        return plan
    
    def _allocate_uniform(self, chapters: List[ChapterBudget]) -> None:
        """均匀分配"""
        if not chapters:
            return
        
        budget_per_chapter = self.config.total_budget // len(chapters)
        
        for ch in chapters:
            ch.budget_chars = budget_per_chapter
            ch.compression_ratio = ch.budget_chars / ch.original_chars if ch.original_chars > 0 else 0
    
    def _allocate_proportional(self, chapters: List[ChapterBudget]) -> None:
        """按原文长度比例分配"""
        total_original = sum(ch.original_chars for ch in chapters)
        
        if total_original == 0:
            return self._allocate_uniform(chapters)
        
        for ch in chapters:
            ratio = ch.original_chars / total_original
            ch.budget_chars = int(self.config.total_budget * ratio)
            ch.compression_ratio = ch.budget_chars / ch.original_chars if ch.original_chars > 0 else 0
    
    def _allocate_weighted(self, chapters: List[ChapterBudget]) -> None:
        """
        按重要性加权分配
        
        公式: budget_i = total_budget * (weight_i / sum(weights))
        weight_i = original_chars_i * importance_score_i
        """
        weights = []
        for ch in chapters:
            # 权重 = 原文长度 × 重要性分数
            weight = ch.original_chars * ch.importance_score
            weights.append(weight)
        
        total_weight = sum(weights)
        
        if total_weight == 0:
            return self._allocate_uniform(chapters)
        
        for i, ch in enumerate(chapters):
            ratio = weights[i] / total_weight
            ch.budget_chars = int(self.config.total_budget * ratio)
            ch.compression_ratio = ch.budget_chars / ch.original_chars if ch.original_chars > 0 else 0
    
    def _apply_constraints(self, chapters: List[ChapterBudget]) -> None:
        """应用约束条件"""
        for ch in chapters:
            # 最小预算约束
            if ch.budget_chars < self.config.min_chapter_budget:
                ch.budget_chars = self.config.min_chapter_budget
            
            # 最大压缩比约束（不能超过原文的 max_compression_ratio）
            max_budget = int(ch.original_chars * self.config.max_compression_ratio)
            if ch.budget_chars > max_budget and max_budget > self.config.min_chapter_budget:
                ch.budget_chars = max_budget
            
            # 更新压缩比
            ch.compression_ratio = ch.budget_chars / ch.original_chars if ch.original_chars > 0 else 0
    
    def _normalize(self, chapters: List[ChapterBudget]) -> None:
        """
        归一化，确保总预算接近目标
        
        如果超出范围，按比例调整
        """
        current_total = sum(ch.budget_chars for ch in chapters)
        target = self.config.total_budget
        
        if current_total == 0:
            return
        
        # 计算调整比例
        scale = target / current_total
        
        # 只有当超出容忍范围时才调整
        min_budget, max_budget = self.config.budget_range
        if current_total < min_budget or current_total > max_budget:
            for ch in chapters:
                ch.budget_chars = max(
                    self.config.min_chapter_budget,
                    int(ch.budget_chars * scale)
                )
                ch.compression_ratio = ch.budget_chars / ch.original_chars if ch.original_chars > 0 else 0


# ============ 便捷函数 ============

def calculate_budget(
    chapters: List[dict],
    target_time_minutes: float = 30.0,
    reading_speed: float = 300.0,
    strategy: str = "proportional",
    importance_scores: Optional[Dict[int, float]] = None
) -> BudgetPlan:
    """
    便捷函数：计算预算分配
    
    Args:
        chapters: 章节列表
        target_time_minutes: 目标阅读时间（分钟）
        reading_speed: 阅读速度（字/分钟）
        strategy: 分配策略
        importance_scores: 重要性分数
    
    Returns:
        BudgetPlan: 预算计划
    
    Example:
        >>> chapters = [{"index": 1, "title": "第1章", "char_count": 3000}, ...]
        >>> plan = calculate_budget(chapters, target_time_minutes=30)
        >>> plan.print_summary()
    """
    config = BudgetConfig(
        target_time_minutes=target_time_minutes,
        reading_speed=reading_speed
    )
    allocator = BudgetAllocator(config)
    return allocator.allocate(chapters, strategy, importance_scores)


def estimate_reading_time(char_count: int, reading_speed: float = 300.0) -> float:
    """
    估算阅读时间
    
    Args:
        char_count: 字数
        reading_speed: 阅读速度（字/分钟）
    
    Returns:
        float: 阅读时间（分钟）
    """
    return char_count / reading_speed


def format_time(minutes: float) -> str:
    """
    格式化时间
    
    Args:
        minutes: 分钟数
    
    Returns:
        str: 格式化后的时间字符串
    """
    if minutes < 1:
        return f"{int(minutes * 60)} 秒"
    elif minutes < 60:
        return f"{int(minutes)} 分钟"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours} 小时 {mins} 分钟" if mins else f"{hours} 小时"
