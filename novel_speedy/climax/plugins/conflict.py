# novel_speedy/climax/plugins/conflict.py
"""
情节冲突强度评分插件

评估章节中的情节冲突程度：
- 角色间的对抗
- 内心挣扎
- 危机/紧张局面
- 转折点
"""

import json
import logging
from typing import Dict, Any, Optional

from novel_speedy.climax.base import (
    ClimaxPlugin,
    DimensionScore,
    ScoreDimension,
    PluginRegistry
)
from novel_speedy.llm_client import call_llm

logger = logging.getLogger(__name__)

# 系统提示词
CONFLICT_SYSTEM_PROMPT = """你是一名专业的小说情节分析师，专注于识别和评估章节中的冲突强度。

请从以下维度分析章节的冲突程度：
1. **外部冲突**：角色间的对抗、战斗、争执
2. **内部冲突**：角色内心的挣扎、抉择、矛盾
3. **环境冲突**：角色与环境/命运的对抗
4. **危机程度**：紧张局面、危险程度
5. **转折强度**：剧情转折、反转的冲击力

【重要】你必须直接输出纯 JSON 对象，不要使用 markdown 代码块包裹。"""


def _build_conflict_prompt(chapter_text: str, chapter_title: str) -> str:
    """构建评分提示词"""
    # 截取章节文本（避免超长）
    max_len = 6000
    text_preview = chapter_text[:max_len] if len(chapter_text) > max_len else chapter_text
    if len(chapter_text) > max_len:
        text_preview += f"\n\n[...章节全文共 {len(chapter_text)} 字，已截取前 {max_len} 字...]"
    
    return f"""请分析以下章节的情节冲突强度：

【章节标题】
{chapter_title}

【章节内容】
{text_preview}

请输出 JSON 格式的评分结果：
{{
    "score": 0.0~1.0,           // 冲突强度总分
    "confidence": 0.0~1.0,      // 评分置信度
    "external_conflict": 0.0~1.0,  // 外部冲突
    "internal_conflict": 0.0~1.0,  // 内部冲突
    "crisis_level": 0.0~1.0,       // 危机程度
    "turning_point": 0.0~1.0,      // 转折强度
    "reason": "简要说明评分理由（不超过50字）"
}}"""


@PluginRegistry.register
class ConflictPlugin(ClimaxPlugin):
    """情节冲突强度评分插件"""
    
    name = "conflict"
    dimension = ScoreDimension.CONFLICT
    default_weight = 1.0
    requires_llm = True
    
    def score_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """评估章节的情节冲突强度"""
        
        if not chapter_text:
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                confidence=0.0,
                reason="章节内容为空"
            )
        
        try:
            user_prompt = _build_conflict_prompt(chapter_text, chapter_title)
            messages = [{"role": "user", "content": user_prompt}]
            
            raw_response = call_llm(
                messages=messages,
                temperature=0.2,
                max_tokens=512,
                system_message=CONFLICT_SYSTEM_PROMPT
            )
            
            # 尝试解析 JSON
            try:
                result = json.loads(raw_response)
            except json.JSONDecodeError:
                logger.warning(f"[冲突评分] 原始响应解析失败: {raw_response[:200]}")
                result = {"score": 0.5, "confidence": 0.5, "reason": "解析失败"}
            
            # 处理返回结果可能是列表的情况
            if isinstance(result, list):
                result = result[0] if result else {}
            
            # 如果还是字符串，尝试再次解析
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {"score": 0.5, "confidence": 0.5, "reason": "二次解析失败"}
            
            if not isinstance(result, dict):
                logger.warning(f"[冲突评分] 返回格式异常: {type(result)}, 使用默认值")
                result = {"score": 0.5, "confidence": 0.5, "reason": "格式异常"}
            
            # 提取分数
            score = float(result.get("score", 0.5))
            confidence = float(result.get("confidence", 0.8))
            reason = result.get("reason", "")
            
            # 收集详细分数
            details = {
                "external_conflict": float(result.get("external_conflict", 0.0)),
                "internal_conflict": float(result.get("internal_conflict", 0.0)),
                "crisis_level": float(result.get("crisis_level", 0.0)),
                "turning_point": float(result.get("turning_point", 0.0)),
            }
            
            logger.info(f"[冲突评分] 章节 {chapter_index}: {score:.2f} ({reason})")
            
            return DimensionScore(
                dimension=self.dimension,
                score=score,
                confidence=confidence,
                reason=reason,
                details=details
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"[冲突评分] JSON 解析失败: {e}")
            return DimensionScore(
                dimension=self.dimension,
                score=0.5,
                confidence=0.3,
                reason="评分解析失败，使用默认值"
            )
        except Exception as e:
            logger.error(f"[冲突评分] 评分失败: {e}")
            return DimensionScore(
                dimension=self.dimension,
                score=0.5,
                confidence=0.1,
                reason=f"评分失败: {str(e)}"
            )
