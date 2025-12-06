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
    # === 打脸类 ===
    "face_slap": "打脸装逼",           # 让小看主角的人后悔
    "counter_slap": "反打脸/主动反击",   # 你退我婚？不，我休你！
    "dignity": "尊严维护",             # 被羞辱后强势回应
    
    # === 逆袭类 ===
    "reversal": "逆袭翻盘",             # 形势逆转
    "underdog_win": "以弱胜强",         # 低等级击败高等级
    "hidden_strength": "隐藏实力",       # 被低估后展现真实实力
    
    # === 进步类 ===
    "level_up": "实力突破/升级",       # 修炼等级提升
    "treasure": "获得奇遇/宝物",       # 得到宝物、传承、奇遇
    "breakthrough": "突破困境",           # 化解危机
    
    # === 复仇类 ===
    "revenge": "复仇成功",             # 复仇行动
    "promise": "立下誓言/约定",       # 三年之约、复仇宣言
    "endure": "隐忍蓄势",             # 暂时示弱但有后手
    
    # === 社交类 ===
    "recognition": "身份揭露/认可",     # 身份被揭露或获得认可
    "rescue": "英雄救美",             # 救人于危难
    "ally": "获得强援",               # 得到强者支持/收为徒弟
    
    # === 智斗类 ===
    "outsmart": "计谋得逘",             # 设计成功，智取对手
    "expose": "识破阴谋",             # 拆穿对手的计策
    "bluff": "虚张声势",             # 装逼吓住对方
    
    # === 战斗类 ===
    "dominate": "碾压秒杀",           # 压倒性胜利
    "clutch": "绝地反杀",             # 危机时刻翻盘
    "combo": "连胜/连杀",             # 连续击败多个对手
    
    # === 财富类 ===
    "wealth": "一夜暴富",             # 突然获得大量财富
    "auction": "拍卖打脸",             # 拍卖会上的竞价胜利
    
    # === 情感类 ===
    "confession": "告白成功",           # 感情线突破
    "loyalty": "兄弟情深",             # 患难与共的场面
}

COOLPOINT_SYSTEM_PROMPT = """你是一名网络小说爽点分析专家。你的任务是分析章节内容，识别能让读者感到“爽”的情节元素。

【爽点类型详解】

1. 打脸类：
   - face_slap: 打脸装逼，让小看主角的人后悔
   - counter_slap: 反打脸/主动反击
   - dignity: 尊严维护，被羞辱后强势回应

2. 逆袭类：
   - reversal: 逆袭翻盘，形势逆转
   - underdog_win: 以弱胜强，低等级击败高等级
   - hidden_strength: 隐藏实力，扮猪吃老虎，被低估后展现真实实力

3. 进步类：
   - level_up: 实力突破、升级
   - treasure: 获得奇遇、宝物、传承
   - breakthrough: 突破困境、化解危机

4. 复仇蓄势类：
   - revenge: 复仇成功
   - promise: 立下誓言/约定，如"n 年之约"、"复仇宣言"等
   - endure: 隐忍蓄势，暂时示弱但有后手

5. 社交类：
   - recognition: 身份揭露或获得认可
   - rescue: 英雄救美，卡点救人，路见不平等
   - ally: 获得强援、被强者收为徒弟

6. 智斗类：
   - outsmart: 计谋得逘，设计成功
   - expose: 识破阴谋，拆穿对手计策
   - bluff: 虚张声势，装逼吓住对方

7. 战斗类：
   - dominate: 碾压秒杀，压倒性胜利
   - clutch: 绝地反杀，危机时刻翻盘
   - combo: 连胜连杀，连续击败多个对手

8. 财富类：
   - wealth: 一夜暴富，突然获得大量财富
   - auction: 拍卖打脸，拍卖会竞价胜利

9. 情感类：
   - confession: 告白成功，感情线突破
   - loyalty: 兄弟情深，患难与共

【重要提示】
- "被退婚后主动休妻"是 counter_slap
- "立下三年之约"是 promise
- "被羞辱后说狠话"是 dignity
- 这些都是重要的爽点！

【输出要求】
1. 只输出一个 JSON 对象
2. 不要使用 markdown 代码块
3. 直接以 { 开头，以 } 结尾"""


def _build_coolpoint_prompt(chapter_text: str, chapter_title: str) -> str:
    """构建爽点检测提示词"""
    max_len = 6000
    text_preview = chapter_text[:max_len] if len(chapter_text) > max_len else chapter_text
    if len(chapter_text) > max_len:
        text_preview += f"\n\n[...章节共 {len(chapter_text)} 字，已截取前 {max_len} 字...]"
    
    return f"""【任务】分析章节是否包含“爽点”情节

【标题】{chapter_title}

【内容】
{text_preview[:4000]}

【重点关注】
1. 打脸类：主动反击、装逼打脸、尊严维护
2. 逆袭类：翻盘、以弱胜强、隐藏实力
3. 进步类：升级突破、获得奇遇/宝物
4. 蓄势类：立誓言约定、隐忍蓄势
5. 智斗类：计谋得逞、识破阴谋
6. 战斗类：碾压秒杀、绝地反杀
7. 其他：一夜暴富、告白成功、兄弟情深

【输出要求】
严格按照JSON格式输出：
- score: 爽点强度(0.0-1.0)，无爽点填0.2，有明显爽点填0.6+
- confidence: 置信度(0.0-1.0)
- coolpoint_types: 爽点类型数组，可选值[face_slap,counter_slap,dignity,reversal,underdog_win,hidden_strength,level_up,treasure,breakthrough,revenge,promise,endure,recognition,rescue,ally,outsmart,expose,bluff,dominate,clutch,combo,wealth,auction,confession,loyalty]
- reason: 简短理由(30字内)

【示例】
被退婚后主动休对方：{{"score":0.7,"confidence":0.9,"coolpoint_types":["counter_slap","dignity"],"reason":"主动反击，不是被退而是我休你"}}
立下三年之约：{{"score":0.65,"confidence":0.85,"coolpoint_types":["promise","endure"],"reason":"复仇宣言，蓄势待发"}}
无爽点：{{"score":0.2,"confidence":0.8,"coolpoint_types":[],"reason":"本章无明显爽点"}}

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
                # 检查是否是爽点类型数组（如 ["counter_slap", "dignity"]）
                if result and all(isinstance(item, str) for item in result):
                    # LLM 只返回了类型列表，需要构造完整结果
                    types_count = len(result)
                    inferred_score = min(0.9, 0.5 + types_count * 0.15)  # 每个类型+0.15分
                    result = {
                        "score": inferred_score,
                        "confidence": 0.7,
                        "coolpoint_types": result,
                        "reason": f"识别到{types_count}种爽点类型"
                    }
                    logger.info(f"[爽点评分] 从类型列表推断分数: {inferred_score:.2f}, 类型: {result['coolpoint_types']}")
                elif result and isinstance(result[0], dict):
                    result = result[0]
                else:
                    result = {}
            
            # 如果还是字符串，尝试再次解析
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # 可能是单个类型字符串
                    if result in COOLPOINT_TYPES:
                        result = {
                            "score": 0.6,
                            "confidence": 0.7,
                            "coolpoint_types": [result],
                            "reason": f"识别到爽点: {COOLPOINT_TYPES.get(result, result)}"
                        }
                    else:
                        result = {"score": 0.3, "confidence": 0.5, "reason": "解析失败"}
            
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
