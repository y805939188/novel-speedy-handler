# novel_speedy/speedy/quality_plugins.py
"""
质量自检插件系统

提供可扩展的质量检查机制，每个插件负责一种检查逻辑。
插件串行执行，每个插件调用 LLM 进行检查。
"""

import re
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

from novel_speedy.llm_client import call_llm

logger = logging.getLogger(__name__)


@dataclass
class QualityCheckResult:
    """质检结果"""
    passed: bool                          # 是否通过
    plugin_name: str                      # 插件名称
    reason: Optional[str] = None          # 不通过的原因
    retry_target: str = "current"         # 重试目标: "current"=当前章, "previous"=上一章
    budget_multiplier: float = 1.1        # 重试时的预算倍数
    extra_prompt: Optional[str] = None    # 重试时的额外提示词


class QualityPlugin(ABC):
    """质检插件基类"""
    
    name: str = "base_plugin"
    
    @abstractmethod
    def check(
        self,
        current_summary: str,
        current_title: str,
        original_text: str,
        previous_summary: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> QualityCheckResult:
        """
        执行质量检查
        
        Args:
            current_summary: 当前章节的摘要
            current_title: 当前章节标题
            original_text: 当前章节原文
            previous_summary: 上一章的摘要（可选）
            previous_title: 上一章标题（可选）
        
        Returns:
            QualityCheckResult: 检查结果
        """
        pass


class CompletenessPlugin(QualityPlugin):
    """完整性检查插件 - 检查摘要是否完整"""
    
    name = "completeness"
    
    SYSTEM_PROMPT = """你是一名专业的小说摘要质量检查员。你的任务是判断给定的章节摘要是否完整。

【检查要点】
1. 句子是否完整（没有截断、没有说到一半）
2. 对话引用是否完整（引号是否成对、台词是否说完）
3. 内容是否有头有尾（不是突然开始或突然结束）
4. 人物名字是否清晰（不会让人混淆）

【不完整的典型例子】
- 句子被截断："萧炎说道："我一定会"（台词没说完）
- 引号不成对："他冷笑道：'你以为你赢了？（缺少结束引号）
- 内容突然结束："众人震惊，这时"（没有下文）
- 人物不明："他说道..."（不知道是谁）

【输出要求】
你必须只回复一个数字：
- 回复 1 表示摘要完整，可以使用
- 回复 0 表示摘要不完整，需要重新生成

不要回复任何其他内容，只回复 0 或 1。"""

    def check(
        self,
        current_summary: str,
        current_title: str,
        original_text: str,
        previous_summary: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> QualityCheckResult:
        """检查摘要是否完整"""
        
        prompt = f"""【章节标题】{current_title}

【原文摘要】（请检查以下摘要是否完整）
{current_summary}

请判断这个摘要是否完整，只回复 0 或 1："""

        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=5,
                system_message=self.SYSTEM_PROMPT
            )
            
            result = response.strip()
            
            if '1' in result:
                return QualityCheckResult(
                    passed=True,
                    plugin_name=self.name
                )
            elif '0' in result:
                return QualityCheckResult(
                    passed=False,
                    plugin_name=self.name,
                    reason="摘要内容不完整",
                    retry_target="current",
                    budget_multiplier=1.1
                )
            else:
                logger.warning(f"      ⚠️ 完整性检查响应无法解析: {result}，默认通过")
                return QualityCheckResult(passed=True, plugin_name=self.name)
                
        except Exception as e:
            logger.warning(f"      ⚠️ 完整性检查调用失败: {e}，默认通过")
            return QualityCheckResult(passed=True, plugin_name=self.name)


class CoherencePlugin(QualityPlugin):
    """连贯性检查插件 - 检查与上一章的连贯性"""
    
    name = "coherence"
    
    SYSTEM_PROMPT = """你是一名专业的小说摘要连贯性检查员。你的任务是判断两个连续章节的摘要是否连贯。

【检查要点】
1. 当前章提到的事件，上一章是否有相关铺垫
2. 当前章提到"得知了xxx"、"发现了xxx"，上一章是否有相关内容
3. 人物状态是否连贯（如上一章受伤，当前章是否有体现）
4. 剧情发展是否有逻辑断层

【不连贯的典型例子】
- 上一章没提到战斗，当前章开头就说"战斗结束后"
- 上一章没提到某个秘密，当前章说"得知了那个秘密"
- 上一章人物在A地，当前章突然在B地且没有过渡
- 上一章没出现某角色，当前章说"他们再次相遇"
- 上一章主角还在昏迷，当前章突然清醒且没有解释
- 上一章没提到任何宝物，当前章说"拿到了那件宝物"
- 上一章没有任何约定，当前章说"按照之前的约定"
- 上一章某角色还活着，当前章说"想起他的死"
- 上一章没有任何交易或谈判，当前章说"交易完成后"
- 上一章主角没有受伤，当前章说"伤势恢复后"
- 上一章没提到任何修炼突破，当前章说"突破之后"
- 上一章没有离别场景，当前章说"离开那里之后"
- 上一章没有获得任何功法/技能，当前章说"掌握了新功法"
- 上一章没有任何敌人出现，当前章说"击败敌人后"
- 当前章节开头是"主角得知了【关键词】"，但是在上一章完全没提到【关键词】
- 当前章说"经过一番苦战"，但上一章完全没提到任何战斗
- 当前章说"师父传授完毕后"，但上一章没有任何传授/教导场景
- 当前章说"服下丹药后"，但上一章没提到获得或服用丹药
- 当前章说"闭关结束"，但上一章没有提到闭关修炼
- 当前章说"比武获胜后"，但上一章没有比武/比赛的情节
- 当前章说"化解了误会"，但上一章没有任何误会产生
- 当前章说"得到长老认可"，但上一章没有长老考验的内容
- 当前章说"渡过危机"，但上一章没有出现任何危机
- 当前章说"解开封印后"，但上一章没有封印相关的剧情
- 当前章说"收服了那只灵兽"，但上一章没有灵兽出现
- 当前章说"主角得知了某件事"，但上一章完全没提这件事

【输出要求】
你必须返回一个 JSON 对象：
- 如果连贯：{"is_consistent": true}
- 如果不连贯：{"is_consistent": false, "reason": "不连贯的具体原因，说明上一章缺少什么内容"}

只返回 JSON，不要有其他内容。"""

    def check(
        self,
        current_summary: str,
        current_title: str,
        original_text: str,
        previous_summary: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> QualityCheckResult:
        """检查与上一章的连贯性"""
        
        # 如果没有上一章，跳过检查
        if not previous_summary:
            return QualityCheckResult(passed=True, plugin_name=self.name)
        
        prompt = f"""【上一章标题】{previous_title or "上一章"}
【上一章摘要】
{previous_summary}

【当前章标题】{current_title}
【当前章摘要】
{current_summary}

请判断这两章的摘要是否连贯，返回 JSON："""

        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
                system_message=self.SYSTEM_PROMPT
            )
            
            result = response.strip()
            
            # 尝试解析 JSON
            try:
                # 处理可能被 markdown 包裹的 JSON
                if '```' in result:
                    result = result.split('```')[1]
                    if result.startswith('json'):
                        result = result[4:]
                
                data = json.loads(result)
                
                if data.get("is_consistent", True):
                    return QualityCheckResult(
                        passed=True,
                        plugin_name=self.name
                    )
                else:
                    reason = data.get("reason", "上下文不连贯")
                    # 构建额外提示词，用于重新生成上一章
                    extra_prompt = f"""【重要补充】
在生成摘要时，请确保包含以下内容的相关铺垫：
{reason}

这是为了保证与下一章内容的连贯性。"""
                    
                    return QualityCheckResult(
                        passed=False,
                        plugin_name=self.name,
                        reason=reason,
                        retry_target="previous",  # 重试上一章
                        budget_multiplier=1.2,    # 增加 20% 预算
                        extra_prompt=extra_prompt
                    )
                    
            except json.JSONDecodeError:
                logger.warning(f"      ⚠️ 连贯性检查 JSON 解析失败: {result}，默认通过")
                return QualityCheckResult(passed=True, plugin_name=self.name)
                
        except Exception as e:
            logger.warning(f"      ⚠️ 连贯性检查调用失败: {e}，默认通过")
            return QualityCheckResult(passed=True, plugin_name=self.name)


class DialogueAttributionPlugin(QualityPlugin):
    """对话归属检查插件 - 检查摘要中的对话是否正确归属于说话者"""
    
    name = "dialogue_attribution"
    
    SYSTEM_PROMPT = """你是一名专业的小说内容校对员。你的任务是检查摘要中的对话是否正确归属于说话者。

【检查任务】
我会给你：
1. 原文内容
2. 摘要中提取的对话列表（包含说话者和台词内容）

请逐一检查每句台词，判断在原文中这句话是否确实是该说话者说的。

【检查要点】
1. 检查原文中这句话或相似的话是否存在
2. 检查原文中说这句话的人是否与摘要标注的说话者一致
3. 如果说话者是代词（如"他"、"她"），根据上下文判断是否指向正确的人物

【输出要求】
返回一个 JSON 对象：
{
    "all_correct": true/false,
    "errors": [
        {
            "dialogue": "台词内容",
            "claimed_speaker": "摘要中标注的说话者",
            "actual_speaker": "原文中实际的说话者（如能确定）",
            "reason": "错误原因说明"
        }
    ]
}

如果所有对话归属都正确，返回：{"all_correct": true, "errors": []}

只返回 JSON，不要有其他内容。"""

    def _extract_dialogues(self, text: str) -> List[Tuple[str, str]]:
        """
        从文本中提取对话和说话者
        
        Returns:
            List of (speaker, dialogue) tuples
        """
        dialogues = []
        
        # 动作词列表（从长到短排序，避免短的先匹配）
        action_words = (
            "冷笑着说道|淡淡地说道|轻声说道|低声说道|大声说道|"
            "冷笑道|笑道|喊道|叫道|问道|答道|说道|"
            "冷笑着说|淡淡地说|轻声说|低声说|大声说|"
            "喃喃道|大叫道|大叫|大声喊"
            "冷冷道|淡淡道|轻轻道|"
            "说|道|喊|叫|问|答"
        )
        
        # 匹配模式：说话者 + 动作词 + 引号内容
        # 支持中文引号 "" 和英文引号 ""
        patterns = [
            # 模式1: xxx说道："yyy"
            rf'([^，。！？\s""\'：:]+?)(?:{action_words})[：:]\s*["""]([^"""]+)["""]',
            # 模式2: "yyy"xxx说/道
            r'["""]([^"""]+)["""]\s*([^，。！？\s""\']{1,8}?)(?:说道|说|道|喊道|叫道|大声|喃喃|低语)',
        ]
        
        # 模式1
        matches = re.findall(patterns[0], text)
        for match in matches:
            speaker, dialogue = match[0].strip(), match[1].strip()
            if speaker and dialogue and len(dialogue) > 2:
                # 清理说话者（移除可能的前缀）
                speaker = re.sub(r'^[，。！？、\s]+', '', speaker)
                # 提取最后一个有效的说话者（如 "他淡淡" -> "他"）
                # 但保留完整人名
                if len(speaker) > 2 and speaker not in ['他', '她', '我', '你']:
                    # 检查是否以副词结尾
                    speaker = re.sub(r'(淡淡|冷冷|轻轻|缓缓|悠悠)$', '', speaker)
                if speaker:
                    dialogues.append((speaker, dialogue))
        
        # 模式2的顺序是反的
        matches = re.findall(patterns[1], text)
        for match in matches:
            dialogue, speaker = match[0].strip(), match[1].strip()
            if speaker and dialogue and len(dialogue) > 2:
                dialogues.append((speaker, dialogue))
        
        # 去重（基于对话内容）
        seen_dialogues = set()
        unique_dialogues = []
        for speaker, dialogue in dialogues:
            if dialogue not in seen_dialogues:
                seen_dialogues.add(dialogue)
                unique_dialogues.append((speaker, dialogue))
        
        return unique_dialogues
    
    def check(
        self,
        current_summary: str,
        current_title: str,
        original_text: str,
        previous_summary: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> QualityCheckResult:
        """检查摘要中的对话归属是否正确"""
        
        # 1. 提取摘要中的对话
        dialogues = self._extract_dialogues(current_summary)
        
        # 如果没有对话，直接通过
        if not dialogues:
            return QualityCheckResult(passed=True, plugin_name=self.name)
        
        logger.info(f"      🔍 对话归属检查: 发现 {len(dialogues)} 句对话")
        
        # 2. 构建检查提示
        dialogue_list = "\n".join([
            f"- 说话者: {speaker}, 台词: \"{dialogue}\""
            for speaker, dialogue in dialogues
        ])
        
        prompt = f"""【原文内容】
{original_text[:8000]}

【摘要中的对话列表】
{dialogue_list}

请检查以上每句台词在原文中是否确实是标注的说话者所说。返回 JSON 格式的检查结果。"""

        try:
            response = call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000,
                system_message=self.SYSTEM_PROMPT
            )
            
            # 解析 JSON 响应
            result = response.strip()
            
            # 尝试提取 JSON
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            try:
                data = json.loads(result)
                
                if data.get("all_correct", True):
                    return QualityCheckResult(passed=True, plugin_name=self.name)
                else:
                    # 有错误的对话归属
                    errors = data.get("errors", [])
                    if not errors:
                        return QualityCheckResult(passed=True, plugin_name=self.name)
                    
                    # 构建错误信息
                    error_details = []
                    for err in errors:
                        dialogue = err.get("dialogue", "")
                        claimed = err.get("claimed_speaker", "")
                        actual = err.get("actual_speaker", "未知")
                        reason = err.get("reason", "")
                        error_details.append(
                            f"台词「{dialogue[:20]}...」被标注为{claimed}所说，"
                            f"但实际是{actual}说的。{reason}"
                        )
                    
                    reason = "对话归属错误: " + "; ".join(error_details)
                    
                    # 构建增强提示词
                    fix_hints = []
                    for err in errors:
                        dialogue = err.get("dialogue", "")
                        actual = err.get("actual_speaker", "")
                        if actual and actual != "未知":
                            fix_hints.append(f"台词「{dialogue[:30]}」应该是{actual}说的，请修正")
                    
                    extra_prompt = f"""【对话归属修正要求】
请注意以下对话的说话者需要修正：
{chr(10).join(fix_hints) if fix_hints else reason}

请确保摘要中每句对话都正确标注说话者。"""
                    
                    return QualityCheckResult(
                        passed=False,
                        plugin_name=self.name,
                        reason=reason,
                        retry_target="current",  # 重试当前章
                        budget_multiplier=1.0,   # 不增加预算，只需修正归属
                        extra_prompt=extra_prompt
                    )
                    
            except json.JSONDecodeError:
                logger.warning(f"      ⚠️ 对话归属检查 JSON 解析失败: {result}，默认通过")
                return QualityCheckResult(passed=True, plugin_name=self.name)
                
        except Exception as e:
            logger.warning(f"      ⚠️ 对话归属检查调用失败: {e}，默认通过")
            return QualityCheckResult(passed=True, plugin_name=self.name)


class QualityChecker:
    """质检管理器 - 串行执行所有插件"""
    
    def __init__(self, plugins: Optional[List[QualityPlugin]] = None):
        """
        初始化质检管理器
        
        Args:
            plugins: 插件列表，按顺序串行执行
        """
        if plugins is None:
            # 默认启用完整性检查和连贯性检查
            plugins = [
                CompletenessPlugin(),
                CoherencePlugin()
            ]
        self.plugins = plugins
    
    def check_all(
        self,
        current_summary: str,
        current_title: str,
        original_text: str,
        previous_summary: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> List[QualityCheckResult]:
        """
        串行执行所有插件检查
        
        Returns:
            所有检查结果的列表
        """
        results = []
        
        for plugin in self.plugins:
            result = plugin.check(
                current_summary=current_summary,
                current_title=current_title,
                original_text=original_text,
                previous_summary=previous_summary,
                previous_title=previous_title
            )
            results.append(result)
            
            # 如果检查不通过，立即返回（串行短路）
            if not result.passed:
                break
        
        return results
    
    def get_first_failure(
        self,
        results: List[QualityCheckResult]
    ) -> Optional[QualityCheckResult]:
        """获取第一个失败的结果"""
        for result in results:
            if not result.passed:
                return result
        return None
