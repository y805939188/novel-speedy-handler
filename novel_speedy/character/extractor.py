# novel_speedy/character/extractor.py
"""
人物提取器 - 从文本中识别和提取人物信息

使用 LLM 进行人物识别，支持：
1. 识别文本中出现的所有人物
2. 提取人物的别名和称呼
3. 识别对话和行为
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from novel_speedy.llm_client import call_llm
from novel_speedy.character.base import (
    Character,
    CharacterMention,
    CharacterGender,
    CharacterRole,
    CharacterDatabase,
)

logger = logging.getLogger(__name__)


EXTRACT_SYSTEM_PROMPT = """你是一个专业的小说人物分析助手。你的任务是从小说文本中识别所有出现的人物。

【识别要求】
1. 识别所有有名字的人物（包括全名、姓、名、称号）
2. 忽略纯代词指代（他、她、他们）
3. 识别人物的对话（说话次数）
4. 判断人物性别（从称呼、描述推断）

【输出要求】
只输出一个 JSON 对象，不要添加任何解释文字。
直接以 { 开头，以 } 结尾。"""


def _build_extract_prompt(text: str, title: str = "") -> str:
    """构建人物提取提示词"""
    max_len = 4000
    text_preview = text[:max_len] if len(text) > max_len else text
    
    return f"""【任务】从以下小说文本中识别所有人物

【标题】{title}

【文本】
{text_preview}

【输出格式】
{{"characters": [
  {{"name": "人物名", "aliases": ["别名1"], "gender": "male/female/unknown", "mentions": 3, "dialogues": 2, "description": "简短描述"}}
]}}

请分析并输出JSON："""


def _parse_extract_response(raw_response: str) -> List[Dict[str, Any]]:
    """解析人物提取响应"""
    try:
        result = json.loads(raw_response)
        if isinstance(result, dict):
            return result.get("characters", [])
        elif isinstance(result, list):
            return result
    except json.JSONDecodeError:
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return result.get("characters", [])
            except:
                pass
    
    logger.warning(f"[人物提取] 解析失败: {raw_response[:200]}")
    return []


class CharacterExtractor:
    """人物提取器"""
    
    def __init__(self, character_db: Optional[CharacterDatabase] = None):
        """
        初始化提取器
        
        Args:
            character_db: 可选的人物数据库，用于跨章节人物追踪
        """
        self.character_db = character_db or CharacterDatabase()
        self._next_char_id = 1
    
    def _generate_char_id(self, name: str) -> str:
        """生成人物ID"""
        # 使用名字的拼音或简化形式作为ID
        char_id = f"char_{self._next_char_id:04d}_{name[:10]}"
        self._next_char_id += 1
        return char_id
    
    def _normalize_name(self, name: str) -> str:
        """规范化人物名称"""
        # 去除常见称呼前缀
        prefixes = ["小", "老", "阿", "大"]
        name = name.strip()
        
        # 处理 "XXX道" -> "XXX" (去除说话标记)
        if name.endswith("道") and len(name) > 1:
            name = name[:-1]
        
        return name
    
    def extract_from_text(
        self,
        text: str,
        title: str = "",
        chapter_index: int = 0,
        use_llm: bool = True
    ) -> Tuple[List[Character], List[CharacterMention]]:
        """
        从文本中提取人物
        
        Args:
            text: 文本内容
            title: 标题
            chapter_index: 章节索引
            use_llm: 是否使用 LLM
        
        Returns:
            (人物列表, 提及列表)
        """
        if use_llm:
            return self._extract_with_llm(text, title, chapter_index)
        else:
            return self._extract_with_rules(text, chapter_index)
    
    def _extract_with_llm(
        self,
        text: str,
        title: str,
        chapter_index: int
    ) -> Tuple[List[Character], List[CharacterMention]]:
        """使用 LLM 提取人物"""
        
        user_prompt = _build_extract_prompt(text, title)
        messages = [{"role": "user", "content": user_prompt}]
        
        try:
            raw_response = call_llm(
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
                system_message=EXTRACT_SYSTEM_PROMPT
            )
            
            char_data_list = _parse_extract_response(raw_response)
            
        except Exception as e:
            logger.error(f"[人物提取] LLM 调用失败: {e}")
            return self._extract_with_rules(text, chapter_index)
        
        characters = []
        mentions = []
        
        for char_data in char_data_list:
            name = self._normalize_name(char_data.get("name", ""))
            if not name or len(name) < 1:
                continue
            
            # 检查是否已存在
            existing_char = self.character_db.find_similar(name)
            
            if existing_char:
                # 更新已有人物
                char = existing_char
                char.total_mentions += char_data.get("mentions", 1)
                char.total_dialogues += char_data.get("dialogues", 0)
                if chapter_index not in char.chapters_appeared:
                    char.chapters_appeared.append(chapter_index)
                
                # 添加新别名
                for alias in char_data.get("aliases", []):
                    if alias not in char.aliases and alias != char.name:
                        char.aliases.append(alias)
                        self.character_db.name_to_id[alias.lower()] = char.id
            else:
                # 创建新人物
                gender_str = char_data.get("gender", "unknown")
                try:
                    gender = CharacterGender(gender_str)
                except ValueError:
                    gender = CharacterGender.UNKNOWN
                
                char = Character(
                    id=self._generate_char_id(name),
                    name=name,
                    aliases=char_data.get("aliases", []),
                    gender=gender,
                    description=char_data.get("description", ""),
                    first_appearance=chapter_index,
                    total_mentions=char_data.get("mentions", 1),
                    total_dialogues=char_data.get("dialogues", 0),
                    chapters_appeared=[chapter_index],
                )
                
                self.character_db.add_character(char)
            
            characters.append(char)
            
            # 创建提及记录
            mention = CharacterMention(
                character_id=char.id,
                character_name=name,
                mention_type="name",
                is_speaking=char_data.get("dialogues", 0) > 0,
            )
            mentions.append(mention)
        
        logger.info(f"[人物提取] 章节 {chapter_index}: 识别 {len(characters)} 个人物")
        return characters, mentions
    
    def _extract_with_rules(
        self,
        text: str,
        chapter_index: int
    ) -> Tuple[List[Character], List[CharacterMention]]:
        """使用规则提取人物（备用方案）"""
        
        # 简单的对话模式匹配
        dialogue_pattern = r'([^\s"]{2,6})(?:道|说|问|笑道|喊道|叫道|低声道|冷声道)'
        matches = re.findall(dialogue_pattern, text)
        
        # 统计人物出现次数
        name_counts: Dict[str, int] = {}
        for name in matches:
            name = self._normalize_name(name)
            if len(name) >= 2 and len(name) <= 6:
                name_counts[name] = name_counts.get(name, 0) + 1
        
        characters = []
        mentions = []
        
        for name, count in name_counts.items():
            if count < 1:
                continue
            
            existing_char = self.character_db.find_similar(name)
            
            if existing_char:
                char = existing_char
                char.total_mentions += count
                char.total_dialogues += count
                if chapter_index not in char.chapters_appeared:
                    char.chapters_appeared.append(chapter_index)
            else:
                char = Character(
                    id=self._generate_char_id(name),
                    name=name,
                    first_appearance=chapter_index,
                    total_mentions=count,
                    total_dialogues=count,
                    chapters_appeared=[chapter_index],
                )
                self.character_db.add_character(char)
            
            characters.append(char)
            
            mention = CharacterMention(
                character_id=char.id,
                character_name=name,
                mention_type="dialogue",
                is_speaking=True,
            )
            mentions.append(mention)
        
        logger.info(f"[人物提取] 章节 {chapter_index}: 规则匹配 {len(characters)} 个人物")
        return characters, mentions
    
    def get_database(self) -> CharacterDatabase:
        """获取人物数据库"""
        return self.character_db
