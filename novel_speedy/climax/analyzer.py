# novel_speedy/climax/analyzer.py
"""
高潮分析器

整合多个评分插件，对章节进行综合高潮分析。
"""

import logging
from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass, field

from novel_speedy.climax.base import (
    ClimaxPlugin,
    DimensionScore,
    ChapterClimaxScore,
    PluginRegistry
)
from novel_speedy.climax.aggregator import ScoreAggregator, AggregationStrategy

logger = logging.getLogger(__name__)


@dataclass
class AnalyzerConfig:
    """分析器配置"""
    # 启用的插件列表（为空则使用所有已注册插件）
    enabled_plugins: List[str] = field(default_factory=list)
    
    # 聚合策略
    aggregation_strategy: AggregationStrategy = AggregationStrategy.WEIGHTED_AVERAGE
    
    # 高潮阈值
    climax_threshold: float = 0.6
    
    # 是否跳过 LLM 插件（用于快速测试）
    skip_llm_plugins: bool = False


class ClimaxAnalyzer:
    """
    高潮分析器
    
    整合多个评分插件，对章节进行综合高潮分析。
    
    使用方式：
    ```python
    analyzer = ClimaxAnalyzer()
    
    # 分析单个章节
    result = analyzer.analyze_chapter(chapter_text, chapter_title, chapter_index)
    
    # 批量分析
    results = analyzer.analyze_chapters(chapters)
    ```
    """
    
    def __init__(self, config: Optional[AnalyzerConfig] = None):
        """
        初始化分析器
        
        Args:
            config: 分析器配置
        """
        self.config = config or AnalyzerConfig()
        self.plugins: List[ClimaxPlugin] = []
        self.aggregator = ScoreAggregator(
            strategy=self.config.aggregation_strategy,
            climax_threshold=self.config.climax_threshold
        )
        
        self._load_plugins()
    
    def _load_plugins(self) -> None:
        """加载评分插件"""
        # 导入插件模块以触发注册
        from novel_speedy.climax import plugins  # noqa
        
        available_plugins = PluginRegistry.get_all()
        
        if self.config.enabled_plugins:
            # 只加载指定的插件
            plugin_names = self.config.enabled_plugins
        else:
            # 加载所有已注册插件
            plugin_names = list(available_plugins.keys())
        
        for name in plugin_names:
            plugin_class = available_plugins.get(name)
            if plugin_class is None:
                logger.warning(f"插件未找到: {name}")
                continue
            
            # 检查是否跳过 LLM 插件
            if self.config.skip_llm_plugins and plugin_class.requires_llm:
                logger.info(f"跳过 LLM 插件: {name}")
                continue
            
            plugin = plugin_class()
            self.plugins.append(plugin)
            logger.info(f"已加载插件: {plugin}")
        
        logger.info(f"共加载 {len(self.plugins)} 个插件")
    
    def analyze_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> ChapterClimaxScore:
        """
        分析单个章节的高潮程度
        
        Args:
            chapter_text: 章节全文
            chapter_title: 章节标题
            chapter_index: 章节序号
            context: 上下文信息
        
        Returns:
            ChapterClimaxScore: 综合评分结果
        """
        logger.info(f"开始分析章节 {chapter_index}: 《{chapter_title}》")
        
        dimension_scores: List[DimensionScore] = []
        
        # 调用每个插件进行评分
        for plugin in self.plugins:
            try:
                score = plugin.score_chapter(
                    chapter_text=chapter_text,
                    chapter_title=chapter_title,
                    chapter_index=chapter_index,
                    context=context
                )
                dimension_scores.append(score)
                
            except Exception as e:
                logger.error(f"插件 {plugin.name} 评分失败: {e}")
                # 继续其他插件
        
        # 聚合评分
        result = self.aggregator.aggregate(
            dimension_scores=dimension_scores,
            chapter_index=chapter_index,
            chapter_title=chapter_title
        )
        
        logger.info(
            f"章节 {chapter_index} 分析完成: "
            f"score={result.final_score:.2f}, "
            f"is_climax={result.is_climax}, "
            f"tags={result.climax_tags}"
        )
        
        return result
    
    def analyze_chapters(
        self,
        chapters: List[dict],
        max_chapters: Optional[int] = None
    ) -> List[ChapterClimaxScore]:
        """
        批量分析多个章节
        
        Args:
            chapters: 章节列表，每个章节需包含 index, title, text
            max_chapters: 最多分析的章节数（用于测试）
        
        Returns:
            List[ChapterClimaxScore]: 各章节的评分结果
        """
        if max_chapters:
            chapters = chapters[:max_chapters]
        
        total_chapters = len(chapters)
        logger.info(f"开始批量分析 {total_chapters} 个章节")
        
        results: List[ChapterClimaxScore] = []
        
        for i, chapter in enumerate(chapters):
            chapter_index = chapter.get("index", i + 1)
            chapter_title = chapter.get("title", f"第{chapter_index}章")
            chapter_text = chapter.get("text", "")
            
            if not chapter_text:
                logger.warning(f"章节 {chapter_index} 内容为空，跳过")
                continue
            
            # 构建上下文
            context = {
                "total_chapters": total_chapters,
                "scenes": chapter.get("scenes", []),
            }
            
            result = self.analyze_chapter(
                chapter_text=chapter_text,
                chapter_title=chapter_title,
                chapter_index=chapter_index,
                context=context
            )
            
            results.append(result)
        
        # 统计高潮章节
        climax_count = sum(1 for r in results if r.is_climax)
        avg_score = sum(r.final_score for r in results) / len(results) if results else 0
        
        logger.info(
            f"批量分析完成: {len(results)} 章, "
            f"高潮章节 {climax_count} 个, "
            f"平均分 {avg_score:.2f}"
        )
        
        return results
    
    def get_climax_chapters(
        self,
        results: List[ChapterClimaxScore],
        top_n: Optional[int] = None
    ) -> List[ChapterClimaxScore]:
        """
        获取高潮章节
        
        Args:
            results: 分析结果列表
            top_n: 返回前 N 个高分章节（如果指定）
        
        Returns:
            List[ChapterClimaxScore]: 高潮章节列表（按分数降序）
        """
        # 按分数降序排序
        sorted_results = sorted(results, key=lambda r: r.final_score, reverse=True)
        
        if top_n:
            return sorted_results[:top_n]
        
        # 返回所有标记为高潮的章节
        return [r for r in sorted_results if r.is_climax]
    
    def print_analysis_report(self, results: List[ChapterClimaxScore]) -> None:
        """打印分析报告"""
        if not results:
            print("无分析结果")
            return
        
        print("\n" + "=" * 70)
        print("📊 高潮分析报告")
        print("=" * 70)
        
        # 统计信息
        climax_chapters = [r for r in results if r.is_climax]
        avg_score = sum(r.final_score for r in results) / len(results)
        
        print(f"\n📈 总体统计:")
        print(f"  分析章节数: {len(results)}")
        print(f"  高潮章节数: {len(climax_chapters)}")
        print(f"  高潮比例: {len(climax_chapters) / len(results):.1%}")
        print(f"  平均得分: {avg_score:.2f}")
        
        # Top 10 高分章节
        print(f"\n🏆 Top 10 高分章节:")
        print("-" * 70)
        
        sorted_results = sorted(results, key=lambda r: r.final_score, reverse=True)
        for r in sorted_results[:10]:
            tags_str = ", ".join(r.climax_tags) if r.climax_tags else "无标签"
            climax_mark = "🔥" if r.is_climax else "  "
            print(
                f"  {climax_mark} 第{r.chapter_index:4d}章 "
                f"[{r.final_score:.2f}] "
                f"{r.chapter_title[:20]:<20} "
                f"| {tags_str}"
            )
        
        # 高潮分布
        print(f"\n📍 高潮分布:")
        print("-" * 70)
        
        # 将章节分为 10 等份，统计每份的高潮数
        bins = 10
        bin_size = len(results) // bins if len(results) >= bins else 1
        
        for i in range(bins):
            start = i * bin_size
            end = start + bin_size if i < bins - 1 else len(results)
            bin_results = results[start:end]
            
            bin_climax = sum(1 for r in bin_results if r.is_climax)
            bin_avg = sum(r.final_score for r in bin_results) / len(bin_results) if bin_results else 0
            
            bar = "█" * int(bin_avg * 20)
            print(f"  {start+1:4d}-{end:4d}: {bar:<20} ({bin_climax} 个高潮, 均分 {bin_avg:.2f})")
        
        print("=" * 70)


# ============ 便捷函数 ============

def analyze_chapter(
    chapter_text: str,
    chapter_title: str,
    chapter_index: int,
    skip_llm: bool = False
) -> ChapterClimaxScore:
    """
    便捷函数：分析单个章节
    
    Args:
        chapter_text: 章节全文
        chapter_title: 章节标题
        chapter_index: 章节序号
        skip_llm: 是否跳过 LLM 插件
    
    Returns:
        ChapterClimaxScore: 评分结果
    """
    config = AnalyzerConfig(skip_llm_plugins=skip_llm)
    analyzer = ClimaxAnalyzer(config)
    return analyzer.analyze_chapter(chapter_text, chapter_title, chapter_index)


def analyze_chapters(
    chapters: List[dict],
    max_chapters: Optional[int] = None,
    skip_llm: bool = False
) -> List[ChapterClimaxScore]:
    """
    便捷函数：批量分析章节
    
    Args:
        chapters: 章节列表
        max_chapters: 最多分析的章节数
        skip_llm: 是否跳过 LLM 插件
    
    Returns:
        List[ChapterClimaxScore]: 评分结果列表
    """
    config = AnalyzerConfig(skip_llm_plugins=skip_llm)
    analyzer = ClimaxAnalyzer(config)
    return analyzer.analyze_chapters(chapters, max_chapters)
