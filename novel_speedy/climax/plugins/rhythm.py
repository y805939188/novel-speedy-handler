# novel_speedy/climax/plugins/rhythm.py
"""
语言节奏评分插件

分析章节的语言节奏特征：
- 句子长度变化
- 对话密度
- 动作描写密度
- 节奏紧张度
"""

import re
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
class RhythmPlugin(ClimaxPlugin):
    """
    语言节奏评分插件
    
    使用规则分析（不依赖 LLM），分析文本的节奏特征。
    """
    
    name = "rhythm"
    dimension = ScoreDimension.RHYTHM
    default_weight = 0.8
    requires_llm = False  # 不需要 LLM，纯规则分析
    
    # 动作词汇（高节奏指示）
    ACTION_WORDS = [
        "冲", "砍", "劈", "刺", "打", "踢", "挥", "闪", "躲", "避",
        "爆", "炸", "撞", "击", "斩", "杀", "逃", "追", "跳", "飞",
        "吼", "喝", "怒", "冲锋", "攻击", "防御", "闪避", "爆发",
    ]
    
    # 紧张词汇
    TENSION_WORDS = [
        "危险", "紧张", "恐惧", "害怕", "惊恐", "慌", "急",
        "死", "亡", "灭", "血", "伤", "痛", "绝望", "崩溃",
        "来不及", "必须", "赶紧", "快", "速度", "瞬间",
    ]
    
    def score_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """分析章节的语言节奏"""
        
        if not chapter_text:
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                confidence=0.0,
                reason="章节内容为空"
            )
        
        # 分析各项指标
        metrics = self._analyze_rhythm(chapter_text)
        
        # 计算综合分数
        score = self._calculate_score(metrics)
        
        reason = self._generate_reason(metrics, score)
        
        logger.info(f"[节奏评分] 章节 {chapter_index}: {score:.2f}")
        
        return DimensionScore(
            dimension=self.dimension,
            score=score,
            confidence=0.9,  # 规则分析置信度较高
            reason=reason,
            details=metrics
        )
    
    def _analyze_rhythm(self, text: str) -> Dict[str, float]:
        """分析文本节奏特征"""
        
        # 分句
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return {
                "avg_sentence_length": 0,
                "short_sentence_ratio": 0,
                "dialogue_density": 0,
                "action_density": 0,
                "tension_density": 0,
            }
        
        # 1. 平均句子长度
        sentence_lengths = [len(s) for s in sentences]
        avg_length = sum(sentence_lengths) / len(sentence_lengths)
        
        # 2. 短句比例（<15字为短句，紧张节奏）
        short_sentences = sum(1 for l in sentence_lengths if l < 15)
        short_ratio = short_sentences / len(sentences)
        
        # 3. 对话密度（引号内容）
        dialogue_matches = re.findall(r'["""](.*?)["""]', text)
        dialogue_chars = sum(len(d) for d in dialogue_matches)
        dialogue_density = dialogue_chars / len(text) if text else 0
        
        # 4. 动作词密度
        action_count = sum(text.count(word) for word in self.ACTION_WORDS)
        action_density = action_count / (len(text) / 100)  # 每百字动作词数
        
        # 5. 紧张词密度
        tension_count = sum(text.count(word) for word in self.TENSION_WORDS)
        tension_density = tension_count / (len(text) / 100)
        
        return {
            "avg_sentence_length": avg_length,
            "short_sentence_ratio": short_ratio,
            "dialogue_density": dialogue_density,
            "action_density": min(action_density / 5, 1.0),  # 归一化
            "tension_density": min(tension_density / 3, 1.0),
            "sentence_count": len(sentences),
        }
    
    def _calculate_score(self, metrics: Dict[str, float]) -> float:
        """根据指标计算节奏分数"""
        
        # 短句比例：越高节奏越快
        short_score = min(metrics["short_sentence_ratio"] * 1.5, 1.0)
        
        # 对话密度：适中最好（0.2-0.4）
        dialogue = metrics["dialogue_density"]
        if 0.2 <= dialogue <= 0.4:
            dialogue_score = 0.8
        elif dialogue > 0.4:
            dialogue_score = 0.6
        else:
            dialogue_score = dialogue * 2
        
        # 动作词密度：越高节奏越紧张
        action_score = metrics["action_density"]
        
        # 紧张词密度
        tension_score = metrics["tension_density"]
        
        # 综合评分（加权平均）
        score = (
            short_score * 0.25 +
            dialogue_score * 0.15 +
            action_score * 0.35 +
            tension_score * 0.25
        )
        
        return min(max(score, 0.0), 1.0)
    
    def _generate_reason(self, metrics: Dict[str, float], score: float) -> str:
        """生成评分理由"""
        reasons = []
        
        if metrics["short_sentence_ratio"] > 0.4:
            reasons.append("短句密集")
        if metrics["action_density"] > 0.5:
            reasons.append("动作描写多")
        if metrics["tension_density"] > 0.4:
            reasons.append("紧张氛围浓")
        if metrics["dialogue_density"] > 0.3:
            reasons.append("对话丰富")
        
        if not reasons:
            if score > 0.6:
                reasons.append("节奏较快")
            elif score > 0.3:
                reasons.append("节奏适中")
            else:
                reasons.append("节奏平缓")
        
        return "，".join(reasons)
