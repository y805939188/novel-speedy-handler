# novel_speedy/climax/plugins/structure.py
"""
结构位置评分插件

基于章节在全书中的位置给予结构性加成：
- 开篇（吸引读者）
- 关键转折点
- 小高潮位置（约每 30-50 章）
- 大高潮位置（约 1/4, 1/2, 3/4 处）
- 结尾（大结局）
"""

import logging
from typing import Dict, Any, Optional

from novel_speedy.climax.base import (
    ClimaxPlugin,
    DimensionScore,
    ScoreDimension,
    PluginRegistry
)

logger = logging.getLogger(__name__)


@PluginRegistry.register
class StructurePlugin(ClimaxPlugin):
    """
    结构位置评分插件
    
    根据章节位置给予结构性加成，不需要 LLM。
    """
    
    name = "structure"
    dimension = ScoreDimension.STRUCTURE
    default_weight = 0.6  # 结构位置权重较低
    requires_llm = False
    
    # 小高潮间隔（每隔多少章有一个小高潮）
    MINOR_CLIMAX_INTERVAL = 40
    
    # 大高潮位置（占全书比例）
    MAJOR_CLIMAX_POSITIONS = [0.25, 0.5, 0.75, 1.0]  # 1/4, 1/2, 3/4, 结尾
    
    # 位置容忍度
    POSITION_TOLERANCE = 0.03  # 3%
    
    def score_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """根据结构位置评分"""
        
        # 获取总章节数
        total_chapters = 100  # 默认值
        if context and "total_chapters" in context:
            total_chapters = context["total_chapters"]
        
        # 计算章节位置比例
        position_ratio = chapter_index / total_chapters if total_chapters > 0 else 0
        
        # 计算各项结构分数
        opening_score = self._opening_score(chapter_index)
        minor_climax_score = self._minor_climax_score(chapter_index)
        major_climax_score = self._major_climax_score(position_ratio)
        ending_score = self._ending_score(position_ratio)
        
        # 取最高分
        scores = {
            "opening": opening_score,
            "minor_climax": minor_climax_score,
            "major_climax": major_climax_score,
            "ending": ending_score,
        }
        
        max_type = max(scores, key=scores.get)
        score = scores[max_type]
        
        # 生成理由
        reason = self._generate_reason(max_type, position_ratio, chapter_index, total_chapters)
        
        logger.info(f"[结构评分] 章节 {chapter_index}: {score:.2f} ({max_type})")
        
        return DimensionScore(
            dimension=self.dimension,
            score=score,
            confidence=0.95,  # 规则计算，置信度高
            reason=reason,
            details={
                "position_ratio": round(position_ratio, 4),
                "total_chapters": total_chapters,
                "structure_type": max_type,
                **scores
            }
        )
    
    def _opening_score(self, chapter_index: int) -> float:
        """开篇分数（前几章）"""
        if chapter_index <= 3:
            return 0.7 - (chapter_index - 1) * 0.1
        elif chapter_index <= 10:
            return 0.4 - (chapter_index - 3) * 0.03
        return 0.0
    
    def _minor_climax_score(self, chapter_index: int) -> float:
        """小高潮分数"""
        # 每隔 MINOR_CLIMAX_INTERVAL 章有一个小高潮位置
        interval = self.MINOR_CLIMAX_INTERVAL
        remainder = chapter_index % interval
        
        # 距离小高潮位置越近分数越高
        if remainder == 0 and chapter_index > 0:
            return 0.6
        elif remainder <= 2 or remainder >= interval - 2:
            return 0.4
        elif remainder <= 5 or remainder >= interval - 5:
            return 0.2
        return 0.0
    
    def _major_climax_score(self, position_ratio: float) -> float:
        """大高潮分数"""
        for major_pos in self.MAJOR_CLIMAX_POSITIONS:
            distance = abs(position_ratio - major_pos)
            if distance <= self.POSITION_TOLERANCE:
                return 0.9 - distance * 10
            elif distance <= self.POSITION_TOLERANCE * 2:
                return 0.6 - distance * 5
            elif distance <= self.POSITION_TOLERANCE * 3:
                return 0.3
        return 0.0
    
    def _ending_score(self, position_ratio: float) -> float:
        """结尾分数"""
        if position_ratio >= 0.97:
            return 0.9
        elif position_ratio >= 0.95:
            return 0.7
        elif position_ratio >= 0.90:
            return 0.4
        return 0.0
    
    def _generate_reason(
        self,
        structure_type: str,
        position_ratio: float,
        chapter_index: int,
        total_chapters: int
    ) -> str:
        """生成评分理由"""
        position_pct = f"{position_ratio * 100:.1f}%"
        
        if structure_type == "opening":
            return f"开篇章节（第{chapter_index}章）"
        elif structure_type == "minor_climax":
            return f"小高潮位置（第{chapter_index}章）"
        elif structure_type == "major_climax":
            if position_ratio < 0.3:
                return f"第一幕高潮位置（{position_pct}）"
            elif position_ratio < 0.6:
                return f"中间转折位置（{position_pct}）"
            else:
                return f"高潮位置（{position_pct}）"
        elif structure_type == "ending":
            return f"结局章节（{position_pct}）"
        else:
            return f"普通位置（{position_pct}）"
