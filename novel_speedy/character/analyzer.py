# novel_speedy/character/analyzer.py
"""
人物价值分析器

分析人物在章节/场景中的重要性和价值，用于速读内容生成的人物筛选。
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from novel_speedy.llm_client import call_llm
from novel_speedy.character.base import (
    Character,
    CharacterValue,
    CharacterRole,
    CharacterDatabase,
    ChapterCharacterAnalysis,
    SceneCharacterAnalysis,
    determine_role,
)
from novel_speedy.character.extractor import CharacterExtractor

logger = logging.getLogger(__name__)


ANALYZE_SYSTEM_PROMPT = """你是一个专业的小说人物分析助手。你的任务是分析人物在本章节中的重要性。

【分析维度】
1. importance: 整体重要性(0-1)，考虑人物对剧情的推动作用
2. screen_time: 戏份占比(0-1)，人物在本章出现的篇幅比例
3. dialogue_ratio: 对话占比(0-1)，人物对话在全章对话中的比例
4. action_ratio: 行为占比(0-1)，人物行为描写的比例

【输出要求】
只输出 JSON 对象，不要添加解释文字。"""


def _build_analyze_prompt(
    text: str,
    title: str,
    characters: List[str]
) -> str:
    """构建人物分析提示词"""
    max_len = 3500
    text_preview = text[:max_len] if len(text) > max_len else text
    char_list = ", ".join(characters[:10])  # 限制分析人数
    
    return f"""【任务】分析以下人物在本章中的重要性

【章节标题】{title}

【待分析人物】{char_list}

【章节内容】
{text_preview}

【输出格式】
{{"characters": [
  {{"name": "人物名", "importance": 0.8, "screen_time": 0.6, "dialogue_ratio": 0.5, "action_ratio": 0.4, "reason": "简述原因"}}
]}}

请分析并输出JSON："""


def _parse_analyze_response(raw_response: str) -> List[Dict[str, Any]]:
    """解析分析响应"""
    try:
        result = json.loads(raw_response)
        if isinstance(result, dict):
            return result.get("characters", [])
        elif isinstance(result, list):
            return result
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return result.get("characters", [])
            except:
                pass
    
    logger.warning(f"[人物分析] 解析失败: {raw_response[:200]}")
    return []


@dataclass
class AnalyzerConfig:
    """分析器配置"""
    use_llm: bool = True                    # 是否使用 LLM
    min_importance_threshold: float = 0.1   # 最低重要性阈值
    max_characters_per_chapter: int = 15    # 每章最多分析人数
    protagonist_names: List[str] = field(default_factory=list)  # 已知主角名


class CharacterAnalyzer:
    """人物价值分析器"""
    
    def __init__(
        self,
        config: Optional[AnalyzerConfig] = None,
        character_db: Optional[CharacterDatabase] = None
    ):
        self.config = config or AnalyzerConfig()
        self.extractor = CharacterExtractor(character_db)
        self.character_db = self.extractor.get_database()
    
    def analyze_chapter(
        self,
        chapter_text: str,
        chapter_title: str,
        chapter_index: int,
        scenes: Optional[List[Dict[str, Any]]] = None
    ) -> ChapterCharacterAnalysis:
        """
        分析章节中的人物价值
        
        Args:
            chapter_text: 章节文本
            chapter_title: 章节标题
            chapter_index: 章节索引
            scenes: 可选的场景列表
        
        Returns:
            章节人物分析结果
        """
        logger.info(f"[人物分析] 开始分析章节 {chapter_index}: 《{chapter_title}》")
        
        # 1. 提取人物
        characters, mentions = self.extractor.extract_from_text(
            text=chapter_text,
            title=chapter_title,
            chapter_index=chapter_index,
            use_llm=self.config.use_llm
        )
        
        if not characters:
            logger.warning(f"[人物分析] 章节 {chapter_index} 未识别到人物")
            return ChapterCharacterAnalysis(
                chapter_index=chapter_index,
                chapter_title=chapter_title,
            )
        
        # 2. 分析人物价值
        character_names = [c.name for c in characters[:self.config.max_characters_per_chapter]]
        
        if self.config.use_llm:
            char_values = self._analyze_with_llm(
                chapter_text, chapter_title, character_names
            )
        else:
            char_values = self._analyze_with_rules(
                chapter_text, characters
            )
        
        # 3. 确定主要人物
        main_characters = []
        protagonist_screen_time = 0.0
        
        for cv in char_values:
            cv.role = determine_role(cv.importance_score)
            
            if cv.importance_score >= 0.5:
                main_characters.append(cv.character_id)
            
            if cv.role == CharacterRole.PROTAGONIST:
                protagonist_screen_time = max(protagonist_screen_time, cv.screen_time)
        
        # 4. 按重要性排序
        char_values.sort(key=lambda x: x.importance_score, reverse=True)
        
        # 5. 构建结果
        result = ChapterCharacterAnalysis(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            characters=char_values,
            main_characters=main_characters,
            protagonist_screen_time=protagonist_screen_time,
            total_characters=len(char_values),
        )
        
        logger.info(
            f"[人物分析] 章节 {chapter_index} 完成: "
            f"{len(char_values)} 人物, 主要 {len(main_characters)} 人"
        )
        
        return result
    
    def _analyze_with_llm(
        self,
        text: str,
        title: str,
        character_names: List[str]
    ) -> List[CharacterValue]:
        """使用 LLM 分析人物价值"""
        
        user_prompt = _build_analyze_prompt(text, title, character_names)
        messages = [{"role": "user", "content": user_prompt}]
        
        try:
            raw_response = call_llm(
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
                system_message=ANALYZE_SYSTEM_PROMPT
            )
            
            char_data_list = _parse_analyze_response(raw_response)
            
        except Exception as e:
            logger.error(f"[人物分析] LLM 调用失败: {e}")
            return []
        
        char_values = []
        
        for char_data in char_data_list:
            name = char_data.get("name", "")
            if not name:
                continue
            
            # 查找人物ID
            char = self.character_db.find_similar(name)
            char_id = char.id if char else f"unknown_{name}"
            
            cv = CharacterValue(
                character_id=char_id,
                character_name=name,
                importance_score=float(char_data.get("importance", 0.3)),
                screen_time=float(char_data.get("screen_time", 0.2)),
                dialogue_ratio=float(char_data.get("dialogue_ratio", 0.1)),
                action_ratio=float(char_data.get("action_ratio", 0.1)),
                reason=char_data.get("reason", ""),
            )
            
            char_values.append(cv)
        
        return char_values
    
    def _analyze_with_rules(
        self,
        text: str,
        characters: List[Character]
    ) -> List[CharacterValue]:
        """使用规则分析人物价值"""
        
        total_len = len(text)
        char_values = []
        
        for char in characters:
            # 计算提及密度
            mention_count = text.count(char.name)
            for alias in char.aliases:
                mention_count += text.count(alias)
            
            # 估算戏份
            estimated_screen_time = min(1.0, mention_count * 50 / total_len)
            
            # 估算对话占比
            dialogue_ratio = min(1.0, char.total_dialogues * 0.1)
            
            # 计算重要性
            importance = (
                estimated_screen_time * 0.4 +
                dialogue_ratio * 0.4 +
                (1.0 if char.role == CharacterRole.PROTAGONIST else 0.0) * 0.2
            )
            
            cv = CharacterValue(
                character_id=char.id,
                character_name=char.name,
                importance_score=importance,
                screen_time=estimated_screen_time,
                dialogue_ratio=dialogue_ratio,
                action_ratio=estimated_screen_time * 0.5,
                mention_count=mention_count,
                dialogue_count=char.total_dialogues,
                reason="规则分析",
            )
            
            char_values.append(cv)
        
        return char_values
    
    def analyze_chapters(
        self,
        chapters: List[Dict[str, Any]],
        scenes_by_chapter: Optional[Dict[int, List[Dict]]] = None
    ) -> List[ChapterCharacterAnalysis]:
        """
        批量分析多个章节
        
        Args:
            chapters: 章节列表
            scenes_by_chapter: 可选的场景数据（按章节索引）
        
        Returns:
            章节分析结果列表
        """
        results = []
        
        for chapter in chapters:
            chapter_index = chapter.get("index", 0)
            chapter_title = chapter.get("title", "")
            chapter_text = chapter.get("text", "")
            
            scenes = None
            if scenes_by_chapter:
                scenes = scenes_by_chapter.get(chapter_index)
            
            result = self.analyze_chapter(
                chapter_text=chapter_text,
                chapter_title=chapter_title,
                chapter_index=chapter_index,
                scenes=scenes
            )
            
            results.append(result)
        
        logger.info(f"[人物分析] 批量分析完成: {len(results)} 章")
        return results
    
    def print_analysis_report(
        self,
        results: List[ChapterCharacterAnalysis]
    ) -> None:
        """打印分析报告"""
        print("\n" + "=" * 80)
        print("📊 人物价值分析报告")
        print("=" * 80)
        
        # 汇总全书人物
        all_chars: Dict[str, Dict] = {}
        
        for r in results:
            print(f"\n📖 第{r.chapter_index}章: {r.chapter_title}")
            print(f"   人物数: {r.total_characters}, 主要人物: {len(r.main_characters)}")
            
            for cv in r.characters[:5]:  # 只显示前5个
                role_emoji = {
                    CharacterRole.PROTAGONIST: "⭐",
                    CharacterRole.DEUTERAGONIST: "🌟",
                    CharacterRole.SUPPORTING: "👤",
                    CharacterRole.MINOR: "·",
                    CharacterRole.EXTRA: " ",
                }
                emoji = role_emoji.get(cv.role, "·")
                print(f"   {emoji} {cv.character_name}: "
                      f"重要性={cv.importance_score:.2f}, "
                      f"戏份={cv.screen_time:.2f}")
                
                # 汇总
                if cv.character_id not in all_chars:
                    all_chars[cv.character_id] = {
                        "name": cv.character_name,
                        "chapters": 0,
                        "total_importance": 0,
                    }
                all_chars[cv.character_id]["chapters"] += 1
                all_chars[cv.character_id]["total_importance"] += cv.importance_score
        
        # 全书主要人物
        print("\n" + "-" * 80)
        print("🎭 全书主要人物")
        print("-" * 80)
        
        sorted_chars = sorted(
            all_chars.items(),
            key=lambda x: x[1]["total_importance"],
            reverse=True
        )
        
        for char_id, data in sorted_chars[:10]:
            avg_importance = data["total_importance"] / data["chapters"]
            print(f"   {data['name']}: "
                  f"出现 {data['chapters']} 章, "
                  f"平均重要性 {avg_importance:.2f}")
        
        print("=" * 80)
    
    def get_character_database(self) -> CharacterDatabase:
        """获取人物数据库"""
        return self.character_db
