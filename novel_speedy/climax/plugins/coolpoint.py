# novel_speedy/climax/plugins/coolpoint.py
"""
爽点检测评分插件

识别网文中的"爽点"元素：
- 逆袭翻盘
- 实力突破/升级
- 打脸装逼
- 获得奇遇/宝物
- 复仇成功
- 英雄救美
"""

import json
import logging
from typing import Dict, Any, Optional, List

from novel_speedy.climax.base import (
    ClimaxPlugin,
    DimensionScore,
    ScoreDimension,
    PluginRegistry
)
from novel_speedy.llm_client import call_llm

logger = logging.getLogger(__name__)

# 爽点类型定义
COOLPOINT_TYPES = {
    "reversal": "逆袭翻盘",
    "level_up": "实力突破/升级",
    "face_slap": "打脸装逼",
    "treasure": "获得奇遇/宝物",
    "revenge": "复仇成功",
    "rescue": "英雄救美",
    "recognition": "身份揭露/认可",
    "breakthrough": "突破困境",
}

COOLPOINT_SYSTEM_PROMPT = """你是一名网络小说爽点分析专家。你的任务是分析章节内容，识别能让读者感到"爽"的情节元素。

爽点类型（英文代码）：
- reversal: 逆袭翻盘
- level_up: 实力突破/升级
- face_slap: 打脸装逼
- treasure: 获得奇遇/宝物
- revenge: 复仇成功
- rescue: 英雄救美
- recognition: 身份揭露/认可
- breakthrough: 突破困境

【输出要求】
1. 只输出一个 JSON 对象，不要输出任何其他内容
2. 不要使用 markdown 代码块
3. 不要添加解释文字
4. 直接以 { 开头，以 } 结尾"""


def _build_coolpoint_prompt(chapter_text: str, chapter_title: str) -> str:
    """构建爽点检测提示词"""
    max_len = 6000
    text_preview = chapter_text[:max_len] if len(chapter_text) > max_len else chapter_text
    if len(chapter_text) > max_len:
        text_preview += f"\n\n[...章节共 {len(chapter_text)} 字，已截取前 {max_len} 字...]"
    
    return f"""【任务】分析章节是否包含"爽点"情节

【标题】{chapter_title}

【内容摘要】
{text_preview[:3000]}

【输出要求】
严格按照下面的JSON格式输出，必须包含所有字段：
- score: 爽点强度(0.0-1.0)，无爽点填0.2
- confidence: 置信度(0.0-1.0)
- coolpoint_types: 爽点类型数组，可选值[reversal,level_up,face_slap,treasure,revenge,rescue,recognition,breakthrough]，无则填[]
- reason: 简短理由(20字内)

【示例输出】
{{"score":0.2,"confidence":0.8,"coolpoint_types":[],"reason":"本章无明显爽点"}}

现在请分析并输出JSON："""


@PluginRegistry.register
class CoolpointPlugin(ClimaxPlugin):
    """爽点检测评分插件"""
    
    name = "coolpoint"
    dimension = ScoreDimension.COOLPOINT
    default_weight = 1.2  # 爽点权重略高
    requires_llm = True
    
    def score_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """检测章节的爽点元素"""
        
        if not chapter_text:
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                confidence=0.0,
                reason="章节内容为空"
            )
        
        try:
            user_prompt = _build_coolpoint_prompt(chapter_text, chapter_title)
            messages = [{"role": "user", "content": user_prompt}]
            
            raw_response = call_llm(
                messages=messages,
                temperature=0.2,
                max_tokens=512,
                system_message=COOLPOINT_SYSTEM_PROMPT
            )
            
            logger.debug(f"[爽点评分] 原始响应: {raw_response[:300]}")
            
            # 尝试解析 JSON
            try:
                result = json.loads(raw_response)
            except json.JSONDecodeError as e:
                # 尝试手动提取 JSON 对象
                import re
                json_match = re.search(r'\{[^{}]*\}', raw_response)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        logger.info(f"[爽点评分] 手动提取 JSON 成功")
                    except json.JSONDecodeError:
                        logger.warning(f"[爽点评分] 解析失败，原始响应: {raw_response[:200]}")
                        result = {"score": 0.3, "confidence": 0.5, "reason": "解析失败"}
                else:
                    logger.warning(f"[爽点评分] 未找到 JSON，原始响应: {raw_response[:200]}")
                    result = {"score": 0.3, "confidence": 0.5, "reason": "解析失败"}
            
            # 处理返回结果可能是列表的情况
            if isinstance(result, list):
                result = result[0] if result else {}
            
            # 如果还是字符串，尝试再次解析
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {"score": 0.3, "confidence": 0.5, "reason": "二次解析失败"}
            
            if not isinstance(result, dict):
                logger.warning(f"[爽点评分] 返回格式异常: {type(result)}, 使用默认值")
                result = {"score": 0.3, "confidence": 0.5, "reason": "格式异常"}
            
            score = float(result.get("score", 0.3))
            confidence = float(result.get("confidence", 0.8))
            reason = result.get("reason", "")
            coolpoint_types = result.get("coolpoint_types", [])
            
            # 确保 coolpoint_types 是列表
            if isinstance(coolpoint_types, str):
                coolpoint_types = [coolpoint_types] if coolpoint_types else []
            elif not isinstance(coolpoint_types, list):
                coolpoint_types = []
            
            details = {
                "coolpoint_types": coolpoint_types,
                "intensity": float(result.get("intensity", 0.0)),
                "satisfaction": float(result.get("satisfaction", 0.0)),
                "type_labels": [COOLPOINT_TYPES.get(t, t) for t in coolpoint_types]
            }
            
            logger.info(f"[爽点评分] 章节 {chapter_index}: {score:.2f}, 类型: {coolpoint_types}")
            
            return DimensionScore(
                dimension=self.dimension,
                score=score,
                confidence=confidence,
                reason=reason,
                details=details
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"[爽点评分] JSON 解析失败: {e}")
            return DimensionScore(
                dimension=self.dimension,
                score=0.3,
                confidence=0.3,
                reason="评分解析失败，使用默认值"
            )
        except Exception as e:
            logger.error(f"[爽点评分] 评分失败: {e}")
            return DimensionScore(
                dimension=self.dimension,
                score=0.3,
                confidence=0.1,
                reason=f"评分失败: {str(e)}"
            )
