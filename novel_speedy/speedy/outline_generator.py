# novel_speedy/speedy/outline_generator.py
"""
大纲生成器

基于章节内容和高潮评分，生成全书大纲。

大纲结构：
1. 全书概述（整体故事线）
2. 分卷/故事弧概述
3. 重要章节摘要（根据高潮评分筛选）
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from novel_speedy.llm_client import call_llm

logger = logging.getLogger(__name__)


@dataclass
class OutlineConfig:
    """大纲配置"""
    
    # 大纲预算比例（相对于速读总预算）
    outline_budget_ratio: float = 0.05  # 默认 5%
    
    # 或直接指定大纲字数
    outline_budget_chars: Optional[int] = None
    
    # 大纲内部分配
    overview_ratio: float = 0.25        # 全书概述占比
    arc_ratio: float = 0.25             # 分卷概述占比
    chapter_ratio: float = 0.50         # 章节摘要占比
    
    # 章节筛选阈值
    climax_threshold_must: float = 0.6  # 必须包含的高潮章节
    climax_threshold_maybe: float = 0.4 # 可能包含的重要章节
    
    # 每章摘要的字数范围
    min_chapter_summary_chars: int = 15
    max_chapter_summary_chars: int = 80
    
    # 故事弧划分
    chapters_per_arc: int = 50          # 每多少章划分一个故事弧
    
    def calculate_budget(self, speedy_total_budget: int) -> int:
        """计算大纲预算"""
        if self.outline_budget_chars is not None:
            return self.outline_budget_chars
        return int(speedy_total_budget * self.outline_budget_ratio)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "outline_budget_ratio": self.outline_budget_ratio,
            "outline_budget_chars": self.outline_budget_chars,
            "overview_ratio": self.overview_ratio,
            "arc_ratio": self.arc_ratio,
            "chapter_ratio": self.chapter_ratio,
            "climax_threshold_must": self.climax_threshold_must,
            "climax_threshold_maybe": self.climax_threshold_maybe,
        }


@dataclass
class ChapterSummary:
    """章节摘要"""
    chapter_index: int
    chapter_title: str
    summary: str
    climax_score: float = 0.0
    is_key_chapter: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "summary": self.summary,
            "climax_score": round(self.climax_score, 3),
            "is_key_chapter": self.is_key_chapter,
        }


@dataclass
class StoryArc:
    """故事弧/卷"""
    arc_index: int
    arc_name: str
    start_chapter: int
    end_chapter: int
    summary: str
    key_events: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "arc_index": self.arc_index,
            "arc_name": self.arc_name,
            "start_chapter": self.start_chapter,
            "end_chapter": self.end_chapter,
            "summary": self.summary,
            "key_events": self.key_events,
        }


@dataclass
class BookOutline:
    """全书大纲"""
    title: str = ""
    total_chapters: int = 0
    total_chars: int = 0
    
    # 全书概述
    overview: str = ""
    
    # 故事弧
    story_arcs: List[StoryArc] = field(default_factory=list)
    
    # 章节摘要（只包含重要章节）
    chapter_summaries: List[ChapterSummary] = field(default_factory=list)
    
    # 统计
    outline_chars: int = 0
    key_chapters_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "total_chapters": self.total_chapters,
            "total_chars": self.total_chars,
            "overview": self.overview,
            "story_arcs": [arc.to_dict() for arc in self.story_arcs],
            "chapter_summaries": [cs.to_dict() for cs in self.chapter_summaries],
            "outline_chars": self.outline_chars,
            "key_chapters_count": self.key_chapters_count,
        }


# LLM 提示词
OVERVIEW_SYSTEM_PROMPT = """你是一个专业的小说分析师。你的任务是为小说生成简洁的故事概述。

【必须包含的要素】
1. 人物：主角姓名、身份、关键配角
2. 时间：故事发生的时代背景或时间跨度
3. 地点：主要场景和世界观设定
4. 冲突：核心矛盾和主角目标

【要求】
1. 概述整体故事线和主要冲突
2. 不要剧透结局细节
3. 语言精炼，引人入胜
4. 确保句子完整，不要在句中截断"""


CHAPTER_SUMMARY_SYSTEM_PROMPT = """你是一个专业的小说摘要生成器。你的任务是用一句话概括章节内容。

【必须包含的要素】
1. 人物：谁在做什么
2. 时间：如果有明确时间点或时间跨度，需要提及
3. 地点：如果有场景转换，需要说明
4. 事件：核心情节发展

【要求】
1. 只输出核心情节，不要废话
2. 字数控制在指定范围内
3. 直接输出摘要内容，不要任何前缀
4. 确保句子完整"""


ARC_SUMMARY_SYSTEM_PROMPT = """你是一个专业的小说分析师。你的任务是为一组章节生成故事弧概述。

【必须包含的要素】
1. 人物：这一阶段的主要人物及其行动
2. 时间：这一阶段的时间跨度
3. 地点：主要场景
4. 发展：关键转折和冲突

【要求】
1. 总结这一阶段的主要剧情发展
2. 语言简洁
3. 直接输出内容，不要JSON格式
4. 确保句子完整"""


class OutlineGenerator:
    """大纲生成器"""
    
    def __init__(self, config: Optional[OutlineConfig] = None):
        self.config = config or OutlineConfig()
    
    def _truncate_to_sentence(self, text: str, max_chars: int) -> str:
        """
        智能截断文本，确保在句子边界截断
        
        Args:
            text: 原始文本
            max_chars: 最大字符数
        
        Returns:
            截断后的文本，确保句子完整
        """
        if len(text) <= max_chars:
            return text
        
        # 在最大字符数范围内找到最后一个句子结束符
        sentence_endings = ['。', '！', '？', '…', '」', '"', '\n']
        
        # 先截取到 max_chars
        truncated = text[:max_chars]
        
        # 从后向前找句子结束符
        last_end_pos = -1
        for i in range(len(truncated) - 1, max(0, len(truncated) - 50), -1):
            if truncated[i] in sentence_endings:
                last_end_pos = i
                break
        
        if last_end_pos > max_chars * 0.6:  # 至少保留 60% 的内容
            return truncated[:last_end_pos + 1]
        
        # 如果找不到合适的句子边界，尝试找逗号
        for i in range(len(truncated) - 1, max(0, len(truncated) - 30), -1):
            if truncated[i] in ['，', '、', '；']:
                return truncated[:i + 1]
        
        # 实在找不到，直接截断
        return truncated
    
    def generate(
        self,
        chapters: List[Dict[str, Any]],
        climax_scores: Optional[List[Dict[str, Any]]] = None,
        speedy_total_budget: int = 18000,
        book_title: str = ""
    ) -> BookOutline:
        """
        生成全书大纲
        
        Args:
            chapters: 章节列表
            climax_scores: 高潮评分列表
            speedy_total_budget: 速读总预算（用于计算大纲预算）
            book_title: 书名
        
        Returns:
            BookOutline: 全书大纲
        """
        logger.info(f"开始生成大纲: {len(chapters)} 章")
        
        # 计算预算
        outline_budget = self.config.calculate_budget(speedy_total_budget)
        overview_budget = int(outline_budget * self.config.overview_ratio)
        arc_budget = int(outline_budget * self.config.arc_ratio)
        chapter_budget = int(outline_budget * self.config.chapter_ratio)
        
        logger.info(f"大纲预算: {outline_budget} 字 (概述:{overview_budget}, 弧:{arc_budget}, 章:{chapter_budget})")
        
        # 构建高潮评分映射
        climax_map = self._build_climax_map(climax_scores)
        
        # 1. 筛选重要章节
        key_chapters = self._select_key_chapters(chapters, climax_map, chapter_budget)
        logger.info(f"筛选出 {len(key_chapters)} 个重要章节")
        
        # 2. 生成章节摘要
        chapter_summaries = self._generate_chapter_summaries(key_chapters, climax_map, chapter_budget)
        
        # 3. 划分故事弧
        story_arcs = self._generate_story_arcs(chapters, chapter_summaries, arc_budget)
        
        # 4. 生成全书概述
        overview = self._generate_overview(chapters, story_arcs, chapter_summaries, overview_budget)
        
        # 5. 构建结果
        total_chars = sum(len(ch.get("text", "")) for ch in chapters)
        outline_chars = len(overview) + sum(len(arc.summary) for arc in story_arcs) + sum(len(cs.summary) for cs in chapter_summaries)
        
        outline = BookOutline(
            title=book_title,
            total_chapters=len(chapters),
            total_chars=total_chars,
            overview=overview,
            story_arcs=story_arcs,
            chapter_summaries=chapter_summaries,
            outline_chars=outline_chars,
            key_chapters_count=len(key_chapters),
        )
        
        logger.info(f"大纲生成完成: {outline_chars} 字")
        return outline
    
    def _build_climax_map(
        self,
        climax_scores: Optional[List[Dict[str, Any]]]
    ) -> Dict[int, float]:
        """构建高潮评分映射"""
        if not climax_scores:
            return {}
        
        return {
            score.get("chapter_index", 0): score.get("final_score", 0.5)
            for score in climax_scores
        }
    
    def _select_key_chapters(
        self,
        chapters: List[Dict[str, Any]],
        climax_map: Dict[int, float],
        budget: int
    ) -> List[Dict[str, Any]]:
        """筛选重要章节"""
        
        # 计算可以包含多少章
        avg_summary_chars = (self.config.min_chapter_summary_chars + self.config.max_chapter_summary_chars) // 2
        max_chapters = budget // avg_summary_chars
        
        # 按高潮分数排序
        chapters_with_score = []
        for ch in chapters:
            index = ch.get("index", 0)
            score = climax_map.get(index, 0.5)
            chapters_with_score.append((ch, score))
        
        # 筛选策略：
        # 1. 必须包含高潮章节
        # 2. 按分数排序选择剩余名额
        must_include = [(ch, s) for ch, s in chapters_with_score if s >= self.config.climax_threshold_must]
        maybe_include = [(ch, s) for ch, s in chapters_with_score if s < self.config.climax_threshold_must]
        
        # 按分数排序 maybe 章节
        maybe_include.sort(key=lambda x: x[1], reverse=True)
        
        # 选择
        selected = must_include[:max_chapters]
        remaining_slots = max_chapters - len(selected)
        
        if remaining_slots > 0:
            selected.extend(maybe_include[:remaining_slots])
        
        # 按章节顺序排序
        selected.sort(key=lambda x: x[0].get("index", 0))
        
        return [ch for ch, _ in selected]
    
    def _generate_chapter_summaries(
        self,
        chapters: List[Dict[str, Any]],
        climax_map: Dict[int, float],
        budget: int
    ) -> List[ChapterSummary]:
        """生成章节摘要"""
        
        if not chapters:
            return []
        
        # 计算每章预算
        chars_per_chapter = max(
            self.config.min_chapter_summary_chars,
            min(self.config.max_chapter_summary_chars, budget // len(chapters))
        )
        
        summaries = []
        total = len(chapters)
        
        import time
        processing_times = []
        
        for i, ch in enumerate(chapters):
            start_time = time.time()
            
            index = ch.get("index", 0)
            title = ch.get("title", f"第{index}章")
            text = ch.get("text", "")[:3000]  # 限制输入长度
            climax_score = climax_map.get(index, 0.5)
            
            # 进度信息
            progress_pct = (i / total) * 100
            eta_str = ""
            if processing_times:
                avg_time = sum(processing_times) / len(processing_times)
                remaining = total - i
                eta_seconds = avg_time * remaining
                eta_str = f" | ⏳ 剩余 {eta_seconds:.0f}s" if eta_seconds < 60 else f" | ⏳ 剩余 {eta_seconds/60:.1f}min"
            
            # 进度条
            bar_width = 15
            filled = int(bar_width * progress_pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            logger.info(f"   [{bar}] {progress_pct:5.1f}% | 摘要 [{i+1}/{total}] {title[:12]:<12}{eta_str}")
            
            # 生成摘要
            summary = self._generate_single_summary(title, text, chars_per_chapter)
            
            elapsed = time.time() - start_time
            processing_times.append(elapsed)
            
            summaries.append(ChapterSummary(
                chapter_index=index,
                chapter_title=title,
                summary=summary,
                climax_score=climax_score,
                is_key_chapter=climax_score >= self.config.climax_threshold_must,
            ))
        
        if processing_times:
            logger.info(f"   [{'█' * 15}] 100.0% | ✅ 摘要完成 | 共 {len(chapters)} 章 | 耗时 {sum(processing_times):.1f}s")
        
        return summaries
    
    def _generate_single_summary(
        self,
        title: str,
        text: str,
        target_chars: int
    ) -> str:
        """生成单章摘要"""
        
        logger.info(f"      📝 调用 LLM API [摘要] | 输入 {len(text):,} 字 → 目标 {target_chars} 字")
        
        prompt = f"""用一句话（{target_chars}字以内）概括以下章节的核心情节：

【章节标题】{title}

【章节内容】
{text}

【摘要】"""
        
        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
                system_message=CHAPTER_SUMMARY_SYSTEM_PROMPT
            )
            
            # 清理响应
            summary = response.strip()
            # 去除可能的前缀
            for prefix in ["摘要：", "摘要:", "【摘要】"]:
                if summary.startswith(prefix):
                    summary = summary[len(prefix):].strip()
            
            # 截断到目标长度
            if len(summary) > target_chars * 1.5:
                summary = self._truncate_to_sentence(summary, int(target_chars * 1.2))
            
            logger.info(f"      ✅ LLM 响应完成 | 实际输出 {len(summary)} 字")
            return summary
            
        except Exception as e:
            logger.warning(f"      ❌ 生成摘要失败: {e}")
            return f"{title}内容概述"
    
    def _generate_story_arcs(
        self,
        chapters: List[Dict[str, Any]],
        chapter_summaries: List[ChapterSummary],
        budget: int
    ) -> List[StoryArc]:
        """生成故事弧"""
        
        if not chapters:
            return []
        
        # 划分弧
        num_arcs = max(1, len(chapters) // self.config.chapters_per_arc)
        chapters_per_arc = len(chapters) // num_arcs
        
        # 每个弧的预算
        chars_per_arc = budget // num_arcs if num_arcs > 0 else budget
        
        logger.info(f"   📖 生成故事弧: {num_arcs} 卷 | 每卷预算 {chars_per_arc} 字")
        
        arcs = []
        
        import time
        
        for i in range(num_arcs):
            start_time = time.time()
            start_idx = i * chapters_per_arc
            end_idx = start_idx + chapters_per_arc if i < num_arcs - 1 else len(chapters)
            
            arc_chapters = chapters[start_idx:end_idx]
            if not arc_chapters:
                continue
            
            start_chapter = arc_chapters[0].get("index", start_idx + 1)
            end_chapter = arc_chapters[-1].get("index", end_idx)
            
            # 收集该弧的章节摘要
            arc_summaries = [
                cs for cs in chapter_summaries
                if start_chapter <= cs.chapter_index <= end_chapter
            ]
            
            # 进度日志
            progress_pct = ((i + 1) / num_arcs) * 100
            logger.info(f"      [{i+1}/{num_arcs}] 第{i+1}卷 (第{start_chapter}-{end_chapter}章)")
            
            # 生成弧概述
            arc_summary = self._generate_arc_summary(
                arc_chapters, arc_summaries, chars_per_arc, i + 1
            )
            
            elapsed = time.time() - start_time
            logger.info(f"      ✅ 第{i+1}卷完成 | {len(arc_summary)} 字 | 耗时 {elapsed:.1f}s")
            
            arcs.append(StoryArc(
                arc_index=i + 1,
                arc_name=f"第{i + 1}卷",
                start_chapter=start_chapter,
                end_chapter=end_chapter,
                summary=arc_summary,
            ))
        
        return arcs
    
    def _generate_arc_summary(
        self,
        chapters: List[Dict[str, Any]],
        summaries: List[ChapterSummary],
        target_chars: int,
        arc_index: int
    ) -> str:
        """生成单个故事弧概述"""
        
        # 收集章节摘要作为上下文
        summary_text = "\n".join([
            f"第{cs.chapter_index}章: {cs.summary}"
            for cs in summaries[:10]  # 限制数量
        ])
        
        if not summary_text:
            # 直接从章节内容生成
            sample_text = ""
            for ch in chapters[:3]:
                sample_text += ch.get("text", "")[:500] + "\n"
        else:
            sample_text = summary_text
        
        prompt = f"""根据以下章节信息，生成第{arc_index}卷的故事概述（{target_chars}字以内）：

{sample_text}

【第{arc_index}卷概述】"""
        
        logger.info(f"         📝 调用 LLM API [弧概述] | 目标 {target_chars} 字")
        
        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
                system_message=ARC_SUMMARY_SYSTEM_PROMPT
            )
            
            result = self._truncate_to_sentence(response.strip(), target_chars)
            logger.info(f"         ✅ LLM 响应完成 | 实际输出 {len(result)} 字")
            return result
            
        except Exception as e:
            logger.warning(f"         ❌ 生成弧概述失败: {e}")
            return f"第{arc_index}卷：第{chapters[0].get('index', 1)}章至第{chapters[-1].get('index', len(chapters))}章"
    
    def _generate_overview(
        self,
        chapters: List[Dict[str, Any]],
        arcs: List[StoryArc],
        summaries: List[ChapterSummary],
        budget: int
    ) -> str:
        """生成全书概述"""
        
        # 收集故事弧概述
        arc_text = "\n".join([
            f"第{arc.arc_index}卷: {arc.summary}"
            for arc in arcs[:5]
        ])
        
        # 收集关键章节
        key_summaries = [cs for cs in summaries if cs.is_key_chapter][:10]
        key_text = "\n".join([
            f"第{cs.chapter_index}章: {cs.summary}"
            for cs in key_summaries
        ])
        
        # 获取开头内容
        opening = chapters[0].get("text", "")[:1000] if chapters else ""
        
        prompt = f"""根据以下信息，生成全书故事概述（{budget}字以内）：

【开篇】
{opening}

【故事发展】
{arc_text}

【关键情节】
{key_text}

请生成一段引人入胜的故事概述："""
        
        logger.info(f"   📝 生成全书概述...")
        logger.info(f"      📝 调用 LLM API [全书概述] | 目标 {budget} 字")
        
        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500,
                system_message=OVERVIEW_SYSTEM_PROMPT
            )
            
            result = self._truncate_to_sentence(response.strip(), budget)
            logger.info(f"      ✅ LLM 响应完成 | 实际输出 {len(result)} 字")
            return result
            
        except Exception as e:
            logger.warning(f"      ❌ 生成概述失败: {e}")
            return f"本书共{len(chapters)}章，讲述了一个精彩的故事。"


def generate_outline(
    chapters: List[Dict[str, Any]],
    climax_scores: Optional[List[Dict[str, Any]]] = None,
    speedy_total_budget: int = 18000,
    outline_budget_ratio: float = 0.05,
    book_title: str = ""
) -> BookOutline:
    """
    便捷函数：生成全书大纲
    
    Args:
        chapters: 章节列表
        climax_scores: 高潮评分列表
        speedy_total_budget: 速读总预算
        outline_budget_ratio: 大纲预算比例（默认5%）
        book_title: 书名
    
    Returns:
        BookOutline: 全书大纲
    """
    config = OutlineConfig(outline_budget_ratio=outline_budget_ratio)
    generator = OutlineGenerator(config)
    return generator.generate(chapters, climax_scores, speedy_total_budget, book_title)
