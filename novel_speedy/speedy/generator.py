# novel_speedy/speedy/generator.py
"""
速读生成器

将所有模块串联起来，一键生成速读版小说。

流程：
1. 加载章节数据
2. 计算字数预算
3. 生成大纲
4. 逐章压缩内容
5. 输出格式化结果
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from novel_speedy.speedy.budget_calculator import (
    SpeedyBudgetConfig,
    SpeedyBudgetCalculator,
    SpeedyBudgetPlan,
)
from novel_speedy.speedy.outline_generator import (
    OutlineConfig,
    OutlineGenerator,
    BookOutline,
)
from novel_speedy.speedy.compressor import (
    CompressionConfig,
    ChapterCompressor,
    CompressedChapter,
)
from novel_speedy.speedy.quality_plugins import (
    QualityChecker,
    QualityCheckResult,
    CompletenessPlugin,
    CoherencePlugin,
)

logger = logging.getLogger(__name__)


# 预定义风格
STYLE_PRESETS = {
    "default": "保持原文风格，简洁流畅",
    "pingshu": "评书风格：使用评书的口吻，适当加入\"话说\"、\"且说\"、\"看官\"等词汇，节奏感强，抑扬顿挫",
    "ancient": "古文风格：使用文言文或半文言的表达方式，简练典雅，有古典韵味",
    "humor": "幽默风趣：语言诙谐幽默，可加入调侃和吐槽，让读者会心一笑",
    "dramatic": "戏剧化风格：强调冲突和张力，语言富有感染力，情绪饱满",
    "minimalist": "极简风格：极度精炼，只保留最核心的信息，像电报一样简洁",
    "storytelling": "讲故事风格：像在给朋友讲故事一样，口语化，亲切自然",
}


@dataclass
class SpeedyConfig:
    """速读生成配置"""
    
    # 阅读配置
    target_reading_time: float = 30.0      # 目标阅读时间（分钟）
    reading_speed: int = 300               # 阅读速度（字/分钟）
    
    # 大纲配置
    outline_budget_ratio: float = 0.05     # 大纲占总预算的比例
    include_outline: bool = True           # 是否包含大纲
    
    # 压缩配置
    compression_config: Optional[CompressionConfig] = None
    
    # 风格配置
    style: Optional[str] = None            # 风格：可以是预设名称或自定义描述
    
    # 输出配置
    output_format: str = "markdown"        # 输出格式: markdown, json, txt
    output_mode: str = "chapter"           # 输出模式: chapter(按章节) / continuous(整体连贯)
    include_chapter_title: bool = True     # 是否包含章节标题（仅 chapter 模式有效）
    include_stats: bool = True             # 是否包含统计信息
    
    # 章节范围
    start_chapter: int = 1                 # 起始章节
    end_chapter: Optional[int] = None      # 结束章节（None 表示全部）
    
    # 质量自检
    enable_quality_check: bool = True      # 是否启用质量自检（默认开启）
    
    @property
    def style_description(self) -> Optional[str]:
        """获取风格描述"""
        if not self.style:
            return None
        # 如果是预设风格名称，返回预设描述
        if self.style in STYLE_PRESETS:
            return STYLE_PRESETS[self.style]
        # 否则当作自定义风格描述
        return self.style
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_reading_time": self.target_reading_time,
            "reading_speed": self.reading_speed,
            "outline_budget_ratio": self.outline_budget_ratio,
            "include_outline": self.include_outline,
            "output_format": self.output_format,
            "output_mode": self.output_mode,
            "style": self.style,
        }


@dataclass
class SpeedyResult:
    """速读生成结果"""
    
    # 基本信息
    book_title: str = ""
    generated_at: str = ""
    
    # 配置
    config: Optional[SpeedyConfig] = None
    
    # 大纲
    outline: Optional[BookOutline] = None
    
    # 压缩后的章节
    chapters: List[CompressedChapter] = field(default_factory=list)
    
    # 统计
    total_original_chars: int = 0
    total_compressed_chars: int = 0
    total_chapters: int = 0
    reading_time_minutes: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_title": self.book_title,
            "generated_at": self.generated_at,
            "config": self.config.to_dict() if self.config else {},
            "outline": self.outline.to_dict() if self.outline else None,
            "chapters": [ch.to_dict() for ch in self.chapters],
            "stats": {
                "total_original_chars": self.total_original_chars,
                "total_compressed_chars": self.total_compressed_chars,
                "total_chapters": self.total_chapters,
                "reading_time_minutes": round(self.reading_time_minutes, 1),
                "compression_ratio": round(
                    self.total_compressed_chars / self.total_original_chars, 3
                ) if self.total_original_chars > 0 else 0,
            }
        }
    
    def to_markdown(self) -> str:
        """输出为 Markdown 格式"""
        lines = []
        
        # 标题
        lines.append(f"# {self.book_title} - 速读版\n")
        
        # 统计信息
        if self.config and self.config.include_stats:
            lines.append("---\n")
            lines.append(f"**生成时间**: {self.generated_at}\n")
            lines.append(f"**原文字数**: {self.total_original_chars:,} 字\n")
            lines.append(f"**速读字数**: {self.total_compressed_chars:,} 字\n")
            lines.append(f"**预计阅读**: {self.reading_time_minutes:.0f} 分钟\n")
            lines.append("---\n\n")
        
        # 大纲
        if self.outline and self.config and self.config.include_outline:
            lines.append("## 📖 故事概述\n\n")
            lines.append(f"{self.outline.overview}\n\n")
            
            # 故事弧
            if self.outline.story_arcs:
                lines.append("### 故事脉络\n\n")
                for arc in self.outline.story_arcs:
                    lines.append(f"**{arc.arc_name}** (第{arc.start_chapter}-{arc.end_chapter}章)\n")
                    lines.append(f"{arc.summary}\n\n")
        
        # 章节内容
        is_continuous = self.config and self.config.output_mode == "continuous"
        
        if is_continuous:
            # 整体连贯模式：不显示章节标题，内容连续输出
            lines.append("---\n\n")
            lines.append("## 📚 故事正文\n\n")
            for ch in self.chapters:
                lines.append(f"{ch.content}\n\n")
        else:
            # 按章节模式
            lines.append("---\n\n")
            lines.append("## 📚 章节速读\n\n")
            for ch in self.chapters:
                if self.config and self.config.include_chapter_title:
                    lines.append(f"### {ch.chapter_title}\n\n")
                lines.append(f"{ch.content}\n\n")
        
        return "".join(lines)
    
    def to_txt(self) -> str:
        """输出为纯文本格式"""
        lines = []
        
        # 标题
        lines.append(f"{self.book_title} - 速读版")
        lines.append("=" * 40)
        lines.append("")
        
        # 大纲
        if self.outline and self.config and self.config.include_outline:
            lines.append("【故事概述】")
            lines.append(self.outline.overview)
            lines.append("")
            lines.append("-" * 40)
            lines.append("")
        
        # 章节内容
        is_continuous = self.config and self.config.output_mode == "continuous"
        
        if is_continuous:
            # 整体连贯模式：不显示章节标题，用换行分隔
            for ch in self.chapters:
                lines.append(ch.content)
                lines.append("")  # 章节间只用一个空行分隔
        else:
            # 按章节模式
            for ch in self.chapters:
                if self.config and self.config.include_chapter_title:
                    lines.append(f"【{ch.chapter_title}】")
                lines.append(ch.content)
                lines.append("")
        
        return "\n".join(lines)


class SpeedyGenerator:
    """速读生成器"""
    
    def __init__(self, config: Optional[SpeedyConfig] = None):
        self.config = config or SpeedyConfig()
        
        # 初始化子模块
        self.budget_calculator = SpeedyBudgetCalculator(SpeedyBudgetConfig(
            target_time_minutes=self.config.target_reading_time,
            reading_speed=self.config.reading_speed,
        ))
        
        self.outline_generator = OutlineGenerator(OutlineConfig(
            outline_budget_ratio=self.config.outline_budget_ratio,
        ))
        
        # 构建压缩配置，注入 enable_quality_check
        compression_config = self.config.compression_config or CompressionConfig()
        compression_config.enable_quality_check = self.config.enable_quality_check
        
        self.compressor = ChapterCompressor(
            config=compression_config,
            style=self.config.style_description,  # 传递风格描述
            continuous_mode=(self.config.output_mode == "continuous")  # 整体连贯模式
        )
    
    def generate(
        self,
        chapters: List[Dict[str, Any]],
        climax_scores: Optional[List[Dict[str, Any]]] = None,
        book_title: str = "未命名小说"
    ) -> SpeedyResult:
        """
        生成速读版
        
        Args:
            chapters: 章节列表
            climax_scores: 高潮评分列表
            book_title: 书名
        
        Returns:
            SpeedyResult: 速读生成结果
        """
        logger.info(f"开始生成速读版: {book_title}, {len(chapters)} 章")
        
        # 筛选章节范围
        chapters = self._filter_chapters(chapters)
        logger.info(f"筛选后章节数: {len(chapters)}")
        
        # Step 1: 计算字数预算
        logger.info("Step 1: 计算字数预算...")
        budget_plan = self.budget_calculator.calculate(chapters, climax_scores)
        total_budget = budget_plan.total_budget_chars
        
        # Step 2: 生成大纲
        outline = None
        outline_chars = 0
        if self.config.include_outline:
            logger.info("Step 2: 生成大纲...")
            outline = self.outline_generator.generate(
                chapters=chapters,
                climax_scores=climax_scores,
                speedy_total_budget=total_budget,
                book_title=book_title
            )
            outline_chars = outline.outline_chars
        
        # Step 3: 逐章压缩
        logger.info("Step 3: 逐章压缩内容...")
        compressed_chapters = self._compress_chapters(
            chapters=chapters,
            budget_plan=budget_plan,
            climax_scores=climax_scores
        )
        
        # 计算统计
        total_original = sum(ch.original_chars for ch in compressed_chapters)
        total_compressed = sum(ch.compressed_chars for ch in compressed_chapters) + outline_chars
        reading_time = total_compressed / self.config.reading_speed
        
        # 构建结果
        result = SpeedyResult(
            book_title=book_title,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            config=self.config,
            outline=outline,
            chapters=compressed_chapters,
            total_original_chars=total_original,
            total_compressed_chars=total_compressed,
            total_chapters=len(compressed_chapters),
            reading_time_minutes=reading_time,
        )
        
        logger.info(
            f"速读版生成完成: {total_original:,} → {total_compressed:,} 字, "
            f"预计阅读 {reading_time:.1f} 分钟"
        )
        
        return result
    
    def _filter_chapters(
        self,
        chapters: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """筛选章节范围"""
        start = self.config.start_chapter
        end = self.config.end_chapter
        
        filtered = []
        for ch in chapters:
            index = ch.get("index", 0)
            if index >= start and (end is None or index <= end):
                filtered.append(ch)
        
        return filtered
    
    def _compress_chapters(
        self,
        chapters: List[Dict[str, Any]],
        budget_plan: SpeedyBudgetPlan,
        climax_scores: Optional[List[Dict[str, Any]]] = None
    ) -> List[CompressedChapter]:
        """逐章压缩（带插件质检）"""
        
        # 构建映射
        budget_map = {cb.chapter_index: cb for cb in budget_plan.chapters}
        climax_map = {}
        coolpoint_map = {}
        
        if climax_scores:
            for cs in climax_scores:
                idx = cs.get("chapter_index", 0)
                climax_map[idx] = cs.get("final_score", 0.5)
                # 提取爽点类型
                for ds in cs.get("dimension_scores", []):
                    if ds.get("dimension") == "coolpoint":
                        details = ds.get("details", {})
                        coolpoint_map[idx] = details.get("coolpoint_types", [])
        
        # 初始化质检器（如果启用质检）
        quality_checker = None
        if self.config.enable_quality_check:
            quality_checker = QualityChecker([
                CompletenessPlugin(),
                CoherencePlugin()
            ])
        
        # 逐章压缩
        results = []
        previous_summary = None
        previous_title = None
        
        # 保存章节原始数据，用于可能的重新生成
        chapter_data_map = {}
        
        # 进度追踪
        import time
        total_chapters = len(chapters)
        processing_times = []
        max_retry = 3  # 质检最大重试次数
        
        for i, ch in enumerate(chapters):
            start_time = time.time()
            
            index = ch.get("index", 0)
            title = ch.get("title", f"第{index}章")
            text = ch.get("text", "")
            
            # 保存章节数据
            chapter_data_map[index] = {
                "text": text,
                "title": title,
                "climax_score": climax_map.get(index, 0.5),
                "coolpoint_types": coolpoint_map.get(index, [])
            }
            
            # 获取预算
            budget_result = budget_map.get(index)
            target_chars = budget_result.budget_chars if budget_result else int(len(text) * 0.1)
            original_target_chars = target_chars  # 保存原始预算
            
            # 获取高潮信息
            climax_score = climax_map.get(index, 0.5)
            coolpoint_types = coolpoint_map.get(index, [])
            
            # 构建上下文
            context = {}
            if previous_summary:
                context["previous_summary"] = previous_summary
            
            # 进度信息
            progress_pct = (i / total_chapters) * 100
            eta_str = ""
            eta_detail = ""
            if processing_times:
                avg_time = sum(processing_times) / len(processing_times)
                remaining = total_chapters - i
                eta_seconds = avg_time * remaining
                if eta_seconds >= 60:
                    eta_str = f"⏳ 预计剩余 {eta_seconds/60:.1f} 分钟"
                else:
                    eta_str = f"⏳ 预计剩余 {eta_seconds:.0f} 秒"
                eta_detail = f" | 平均 {avg_time:.1f}s/章"
            
            # 构建进度条
            bar_width = 20
            filled = int(bar_width * progress_pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            # 压缩比预览
            compress_ratio = target_chars / len(text) * 100 if len(text) > 0 else 100
            
            logger.info(
                f"   [{bar}] {progress_pct:5.1f}% | "
                f"[{i+1}/{total_chapters}] {title[:15]:<15} | "
                f"{len(text):,}→{target_chars:,}字 ({compress_ratio:.0f}%)"
                f"{eta_detail}"
            )
            if eta_str:
                logger.info(f"   {eta_str}")
            
            # 压缩当前章节（带完整性检查重试）
            compressed = None
            for attempt in range(max_retry + 1):
                compressed = self.compressor.compress(
                    chapter_text=text,
                    chapter_title=title,
                    chapter_index=index,
                    target_chars=target_chars,
                    climax_score=climax_score,
                    coolpoint_types=coolpoint_types,
                    context=context
                )
                
                # 如果不启用质检，直接跳出
                if not quality_checker:
                    break
                
                # 完整性检查
                completeness_result = CompletenessPlugin().check(
                    current_summary=compressed.content,
                    current_title=title,
                    original_text=text
                )
                
                if completeness_result.passed:
                    if attempt > 0:
                        extra_budget = target_chars - original_target_chars
                        logger.info(f"      ✅ 完整性检查通过（重试 {attempt} 次，额外预算 +{extra_budget} 字）")
                    else:
                        logger.info(f"      ✅ 完整性检查通过")
                    break
                else:
                    if attempt < max_retry:
                        old_target = target_chars
                        target_chars = int(target_chars * 1.1)  # 增加 10% 预算
                        logger.warning(
                            f"      ⚠️ 完整性检查不通过，增加预算重试... "
                            f"({attempt + 1}/{max_retry}) [{old_target}→{target_chars} 字]"
                        )
                    else:
                        logger.warning(f"      ⚠️ 完整性检查不通过，已达最大重试次数，使用当前结果")
            
            # 连贯性检查（需要有上一章）
            if quality_checker and results and previous_summary:
                prev_compressed = results[-1]
                prev_index = prev_compressed.chapter_index
                prev_data = chapter_data_map.get(prev_index, {})
                prev_target_chars = prev_compressed.compressed_chars
                
                for coherence_attempt in range(max_retry + 1):
                    coherence_result = CoherencePlugin().check(
                        current_summary=compressed.content,
                        current_title=title,
                        original_text=text,
                        previous_summary=prev_compressed.content,
                        previous_title=prev_compressed.chapter_title
                    )
                    
                    if coherence_result.passed:
                        if coherence_attempt > 0:
                            logger.info(f"      ✅ 连贯性检查通过（重新生成上一章 {coherence_attempt} 次）")
                        else:
                            logger.info(f"      ✅ 连贯性检查通过")
                        break
                    else:
                        if coherence_attempt < max_retry:
                            # 增加上一章预算 20%
                            old_prev_target = prev_target_chars
                            prev_target_chars = int(prev_target_chars * 1.2)
                            
                            logger.warning(
                                f"      ⚠️ 连贯性检查不通过: {coherence_result.reason}"
                            )
                            logger.warning(
                                f"      🔄 重新生成上一章 ({coherence_attempt + 1}/{max_retry}) "
                                f"[{old_prev_target}→{prev_target_chars} 字]"
                            )
                            
                            # 构建上一章的上下文（带额外提示词）
                            prev_context = {}
                            if len(results) > 1:
                                prev_prev = results[-2]
                                sentences = prev_prev.content.replace('。', '。|').split('|')
                                prev_context["previous_summary"] = sentences[-2] if len(sentences) > 1 else prev_prev.content[:50]
                            
                            # 添加连贯性修复的额外提示词
                            prev_context["extra_prompt"] = coherence_result.extra_prompt
                            
                            # 重新压缩上一章
                            new_prev_compressed = self.compressor.compress(
                                chapter_text=prev_data.get("text", ""),
                                chapter_title=prev_data.get("title", ""),
                                chapter_index=prev_index,
                                target_chars=prev_target_chars,
                                climax_score=prev_data.get("climax_score", 0.5),
                                coolpoint_types=prev_data.get("coolpoint_types", []),
                                context=prev_context
                            )
                            
                            # 更新 results 中的上一章
                            results[-1] = new_prev_compressed
                            prev_compressed = new_prev_compressed
                            
                            # 更新 previous_summary 供下一轮检查
                            sentences = new_prev_compressed.content.replace('。', '。|').split('|')
                            previous_summary = sentences[-2] if len(sentences) > 1 else new_prev_compressed.content[:50]
                        else:
                            logger.warning(f"      ⚠️ 连贯性检查不通过，已达最大重试次数，保持当前结果")
            
            results.append(compressed)
            
            # 记录处理时间
            elapsed = time.time() - start_time
            processing_times.append(elapsed)
            
            # 更新上下文
            if compressed.content:
                sentences = compressed.content.replace('。', '。|').split('|')
                previous_summary = sentences[-2] if len(sentences) > 1 else compressed.content[:50]
            previous_title = title
        
        # 输出总耗时
        total_time = sum(processing_times)
        avg_time = total_time / len(processing_times) if processing_times else 0
        logger.info(f"   [{'█' * 20}] 100.0% | ✅ 全部完成!")
        logger.info(
            f"   📊 压缩汇总: {total_chapters} 章 | "
            f"总耗时 {total_time:.1f}s | 平均 {avg_time:.2f}s/章"
        )
        
        return results


def generate_speedy(
    chapters: List[Dict[str, Any]],
    climax_scores: Optional[List[Dict[str, Any]]] = None,
    book_title: str = "未命名小说",
    target_reading_time: float = 30.0,
    reading_speed: int = 300,
    output_format: str = "markdown",
    output_mode: str = "chapter",
    style: Optional[str] = None,
    enable_quality_check: bool = True
) -> SpeedyResult:
    """
    便捷函数：生成速读版
    
    Args:
        chapters: 章节列表
        climax_scores: 高潮评分列表
        book_title: 书名
        target_reading_time: 目标阅读时间（分钟）
        reading_speed: 阅读速度（字/分钟）
        output_format: 输出格式
        output_mode: 输出模式
                     chapter - 按章节输出，显示章节标题
                     continuous - 整体连贯输出，不显示章节标题，注重衔接过渡
        style: 输出风格（预设名称或自定义描述）
               预设: pingshu(评书), ancient(古文), humor(幽默), 
                     dramatic(戏剧化), minimalist(极简), storytelling(讲故事)
        enable_quality_check: 是否启用质量自检（默认开启）
    
    Returns:
        SpeedyResult: 速读生成结果
    """
    config = SpeedyConfig(
        target_reading_time=target_reading_time,
        reading_speed=reading_speed,
        output_format=output_format,
        output_mode=output_mode,
        style=style,
        enable_quality_check=enable_quality_check,
    )
    
    generator = SpeedyGenerator(config)
    return generator.generate(chapters, climax_scores, book_title)
