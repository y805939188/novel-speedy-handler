# novel_speedy/speedy/compressor.py
"""
内容压缩器

根据字数预算将章节内容压缩为速读版本。

压缩策略：
1. 保留式（压缩比 > 50%）：保留关键段落，删除冗余
2. 重写式（压缩比 20-50%）：提取核心情节，LLM 重写
3. 摘要式（压缩比 < 20%）：纯 LLM 生成剧情摘要
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from novel_speedy.llm_client import call_llm

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """压缩策略"""
    PRESERVE = "preserve"      # 保留式：压缩比 > 50%
    REWRITE = "rewrite"        # 重写式：压缩比 20-50%
    SUMMARIZE = "summarize"    # 摘要式：压缩比 < 20%


@dataclass
class CompressionConfig:
    """压缩配置"""
    
    # 策略阈值
    preserve_threshold: float = 0.5     # 压缩比 > 50% 使用保留式
    rewrite_threshold: float = 0.2      # 压缩比 > 20% 使用重写式，否则摘要式
    
    # 保留式配置
    preserve_dialogue_priority: float = 1.5   # 对话优先级
    preserve_action_priority: float = 1.3     # 动作场景优先级
    preserve_climax_priority: float = 2.0     # 高潮情节优先级
    
    # 重写式配置
    rewrite_keep_dialogue: bool = True        # 保留关键对话
    rewrite_max_input_chars: int = 6000       # 最大输入字数
    
    # 摘要式配置
    summarize_include_names: bool = True      # 包含人物名字
    summarize_include_events: bool = True     # 包含关键事件
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "preserve_threshold": self.preserve_threshold,
            "rewrite_threshold": self.rewrite_threshold,
        }


@dataclass
class CompressedChapter:
    """压缩后的章节"""
    chapter_index: int
    chapter_title: str
    original_chars: int
    compressed_chars: int
    compression_ratio: float
    strategy_used: str
    content: str
    key_points: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "original_chars": self.original_chars,
            "compressed_chars": self.compressed_chars,
            "compression_ratio": round(self.compression_ratio, 3),
            "strategy_used": self.strategy_used,
            "content": self.content,
            "key_points": self.key_points,
        }


# ==================== 提示词 ====================

REWRITE_SYSTEM_PROMPT = """你是一名专业的小说内容压缩专家。你的任务是将章节内容压缩到指定字数，同时保留核心剧情。

【压缩原则】
1. 保留核心情节和关键转折
2. 保留重要对话（可精简）
3. 保留人物关键动作
4. 删除环境描写细节
5. 删除冗长心理描写
6. 删除过渡性叙述

【输出要求】
1. 直接输出压缩后的内容
2. 不要添加任何说明或标注
3. 保持故事连贯性
4. 确保句子完整"""


SUMMARIZE_SYSTEM_PROMPT = """你是一名专业的小说摘要生成器。你的任务是用极简的文字概括章节的核心剧情。

【摘要原则】
1. 只保留最核心的情节发展
2. 必须包含主要人物名字
3. 必须包含关键事件
4. 语言简洁有力

【输出要求】
1. 直接输出摘要内容
2. 不要添加任何说明或标注
3. 确保句子完整"""


PRESERVE_SYSTEM_PROMPT = """你是一名专业的小说编辑。你的任务是精简章节内容，删除冗余部分，保留精华。

【精简原则】
1. 保留所有对话
2. 保留动作场景
3. 保留情节转折
4. 删除环境描写
5. 删除心理铺垫
6. 简化过渡段落

【输出要求】
1. 直接输出精简后的内容
2. 保持原文风格
3. 确保句子完整"""


class ChapterCompressor:
    """章节压缩器"""
    
    def __init__(
        self, 
        config: Optional[CompressionConfig] = None,
        style: Optional[str] = None,
        continuous_mode: bool = False
    ):
        self.config = config or CompressionConfig()
        self.style = style  # 风格描述
        self.continuous_mode = continuous_mode  # 整体连贯输出模式
    
    def compress(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        target_chars: int,
        climax_score: float = 0.5,
        coolpoint_types: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> CompressedChapter:
        """
        压缩单个章节
        
        Args:
            chapter_text: 章节原文
            chapter_title: 章节标题
            chapter_index: 章节序号
            target_chars: 目标字数
            climax_score: 高潮评分（用于判断重要性）
            coolpoint_types: 爽点类型列表
            context: 上下文信息（如前一章摘要）
        
        Returns:
            CompressedChapter: 压缩后的章节
        """
        original_chars = len(chapter_text)
        
        # 计算压缩比
        if original_chars == 0:
            compression_ratio = 1.0
        else:
            compression_ratio = target_chars / original_chars
        
        # 选择压缩策略
        strategy = self._select_strategy(compression_ratio, climax_score)
        
        logger.info(
            f"[压缩] 章节 {chapter_index}: {original_chars} → {target_chars} 字, "
            f"压缩比 {compression_ratio:.1%}, 策略: {strategy.value}"
        )
        
        # 执行压缩
        if strategy == CompressionStrategy.PRESERVE:
            content = self._compress_preserve(
                chapter_text, chapter_title, target_chars, climax_score, 
                self.style, context, self.continuous_mode
            )
        elif strategy == CompressionStrategy.REWRITE:
            content = self._compress_rewrite(
                chapter_text, chapter_title, target_chars, 
                climax_score, coolpoint_types, context, self.style, self.continuous_mode
            )
        else:
            content = self._compress_summarize(
                chapter_text, chapter_title, target_chars,
                climax_score, coolpoint_types, self.style, context, self.continuous_mode
            )
        
        # 构建结果
        compressed_chars = len(content)
        actual_ratio = compressed_chars / original_chars if original_chars > 0 else 1.0
        
        return CompressedChapter(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            original_chars=original_chars,
            compressed_chars=compressed_chars,
            compression_ratio=actual_ratio,
            strategy_used=strategy.value,
            content=content,
        )
    
    def _select_strategy(
        self,
        compression_ratio: float,
        climax_score: float
    ) -> CompressionStrategy:
        """选择压缩策略"""
        
        # 高潮章节倾向使用保留更多内容的策略
        if climax_score >= 0.7:
            # 高潮章节：提高保留阈值
            if compression_ratio > self.config.preserve_threshold * 0.8:
                return CompressionStrategy.PRESERVE
            elif compression_ratio > self.config.rewrite_threshold * 0.8:
                return CompressionStrategy.REWRITE
            else:
                return CompressionStrategy.SUMMARIZE
        else:
            # 普通章节
            if compression_ratio > self.config.preserve_threshold:
                return CompressionStrategy.PRESERVE
            elif compression_ratio > self.config.rewrite_threshold:
                return CompressionStrategy.REWRITE
            else:
                return CompressionStrategy.SUMMARIZE
    
    def _compress_preserve(
        self,
        chapter_text: str,
        chapter_title: str,
        target_chars: int,
        climax_score: float,
        style: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        continuous_mode: bool = False
    ) -> str:
        """保留式压缩：保留关键段落，删除冗余"""
        
        # 风格要求
        style_instruction = ""
        if style:
            style_instruction = f"\n【风格要求】请使用以下风格进行输出：{style}\n"
        
        # 连贯性过渡提示（整体输出模式）
        continuity_instruction = ""
        if continuous_mode and context and context.get("previous_summary"):
            continuity_instruction = f"""
【连贯性要求】这是整体连贯输出，请注意与前文的自然衔接。
前一章结尾：{context['previous_summary']}
要求：
- 如果前后内容联系紧密，可直接续写，不必加过渡词
- 如果有时间/场景跳转，可用“此时”“与此同时”“另一边”等
- 如果是时间推进，可用“不久后”“第二天”“数日后”等
- 避免每段都以“随后”开头，要多样化
- 根据内容自行判断最自然的衔接方式
"""
        
        prompt = f"""【任务】精简以下章节内容到约 {target_chars} 字

【章节标题】{chapter_title}

【原文】
{chapter_text[:self.config.rewrite_max_input_chars]}
{style_instruction}{continuity_instruction}
【目标字数】约 {target_chars} 字

请直接输出精简后的内容："""
        
        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=target_chars * 2,
                system_message=PRESERVE_SYSTEM_PROMPT
            )
            return self._clean_response(response, target_chars)
        except Exception as e:
            logger.warning(f"保留式压缩失败: {e}")
            return chapter_text[:target_chars]
    
    def _compress_rewrite(
        self,
        chapter_text: str,
        chapter_title: str,
        target_chars: int,
        climax_score: float,
        coolpoint_types: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        style: Optional[str] = None,
        continuous_mode: bool = False
    ) -> str:
        """重写式压缩：提取核心情节，LLM 重写"""
        
        # 构建保留提示
        preserve_hints = []
        if coolpoint_types:
            preserve_hints.append(f"本章爽点类型: {', '.join(coolpoint_types)}")
        if climax_score >= 0.6:
            preserve_hints.append("本章是高潮章节，注意保留精彩情节")
        
        preserve_text = "\n".join(preserve_hints) if preserve_hints else ""
        
        # 上下文信息和连贯性提示
        context_text = ""
        if context and context.get("previous_summary"):
            if continuous_mode:
                context_text = f"""
【前情】{context['previous_summary']}
【连贯性要求】这是整体连贯输出，请自然衔接前文：
- 不必每段都加过渡词，内容连贯时可直接续写
- 根据情节需要自由选择衔接方式（时间跳转、场景切换、因果关系等）
- 避免重复使用“随后”，要多样化
"""
            else:
                context_text = f"\n【前情】{context['previous_summary']}\n"
        
        # 风格要求
        style_instruction = ""
        if style:
            style_instruction = f"\n【风格要求】请使用以下风格进行重写：{style}\n"
        
        prompt = f"""【任务】将以下章节重写压缩到约 {target_chars} 字
{context_text}
【章节标题】{chapter_title}

【原文】
{chapter_text[:self.config.rewrite_max_input_chars]}

【重要提示】
{preserve_text}
{style_instruction}
【目标字数】约 {target_chars} 字

请直接输出重写后的内容："""
        
        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=target_chars * 2,
                system_message=REWRITE_SYSTEM_PROMPT
            )
            return self._clean_response(response, target_chars)
        except Exception as e:
            logger.warning(f"重写式压缩失败: {e}")
            return self._compress_summarize(
                chapter_text, chapter_title, target_chars, climax_score, 
                coolpoint_types, style, context, continuous_mode
            )
    
    def _compress_summarize(
        self,
        chapter_text: str,
        chapter_title: str,
        target_chars: int,
        climax_score: float,
        coolpoint_types: Optional[List[str]] = None,
        style: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        continuous_mode: bool = False
    ) -> str:
        """摘要式压缩：纯 LLM 生成剧情摘要"""
        
        # 爽点提示
        coolpoint_hint = ""
        if coolpoint_types:
            coolpoint_hint = f"\n本章爽点: {', '.join(coolpoint_types)}，请确保在摘要中体现。"
        
        # 风格要求
        style_instruction = ""
        if style:
            style_instruction = f"\n【风格要求】请使用以下风格进行摘要：{style}\n"
        
        # 连贯性过渡提示（整体输出模式）
        continuity_instruction = ""
        if continuous_mode and context and context.get("previous_summary"):
            continuity_instruction = f"""
【连贯性要求】这是整体连贯输出，请自然衔接前文。
前一章结尾：{context['previous_summary']}
要求：
- 不必每段都加过渡词，内容连贯时可直接续写
- 根据上下文自行选择最合适的衔接方式
- 避免重复使用同一个过渡词，要多样化
"""
        
        prompt = f"""【任务】用约 {target_chars} 字概括以下章节的核心剧情

【章节标题】{chapter_title}
【原文】
{chapter_text[:self.config.rewrite_max_input_chars]}
{coolpoint_hint}
{style_instruction}{continuity_instruction}
【目标字数】约 {target_chars} 字

请直接输出摘要："""
        
        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=target_chars * 2,
                system_message=SUMMARIZE_SYSTEM_PROMPT
            )
            return self._clean_response(response, target_chars)
        except Exception as e:
            logger.warning(f"摘要式压缩失败: {e}")
            # 最后的回退：截取开头
            return chapter_text[:target_chars]
    
    def _clean_response(self, response: str, target_chars: int) -> str:
        """清理响应，确保字数合理"""
        content = response.strip()
        
        # 去除可能的前缀
        prefixes = ["【压缩后】", "【摘要】", "【重写】", "压缩后：", "摘要："]
        for prefix in prefixes:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()
        
        # 如果超出目标字数太多，智能截断
        if len(content) > target_chars * 1.5:
            content = self._truncate_to_sentence(content, int(target_chars * 1.2))
        
        return content
    
    def _truncate_to_sentence(self, text: str, max_chars: int) -> str:
        """智能截断到句子边界"""
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        
        # 找最后一个句子结束符
        sentence_endings = ['。', '！', '？', '…', '」', '"']
        last_end = -1
        for i in range(len(truncated) - 1, max(0, len(truncated) - 50), -1):
            if truncated[i] in sentence_endings:
                last_end = i
                break
        
        if last_end > max_chars * 0.6:
            return truncated[:last_end + 1]
        
        return truncated


def compress_chapter(
    chapter_text: str,
    chapter_title: str,
    chapter_index: int,
    target_chars: int,
    climax_score: float = 0.5,
    coolpoint_types: Optional[List[str]] = None
) -> CompressedChapter:
    """
    便捷函数：压缩单个章节
    
    Args:
        chapter_text: 章节原文
        chapter_title: 章节标题
        chapter_index: 章节序号
        target_chars: 目标字数
        climax_score: 高潮评分
        coolpoint_types: 爽点类型列表
    
    Returns:
        CompressedChapter: 压缩后的章节
    """
    compressor = ChapterCompressor()
    return compressor.compress(
        chapter_text=chapter_text,
        chapter_title=chapter_title,
        chapter_index=chapter_index,
        target_chars=target_chars,
        climax_score=climax_score,
        coolpoint_types=coolpoint_types
    )
