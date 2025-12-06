# novel_speedy/character/base.py
"""
人物价值评分模块 - 基础数据类和接口

功能：
1. 识别章节/场景中出现的人物
2. 评估每个人物的戏份占比和重要性
3. 标记主角、配角、龙套
4. 为速读生成提供人物重要性依据
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class CharacterRole(Enum):
    """人物角色类型"""
    PROTAGONIST = "protagonist"      # 主角
    DEUTERAGONIST = "deuteragonist"  # 第二主角/重要配角
    SUPPORTING = "supporting"        # 配角
    MINOR = "minor"                  # 次要人物
    EXTRA = "extra"                  # 龙套


class CharacterGender(Enum):
    """人物性别"""
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


@dataclass
class Character:
    """人物基本信息"""
    id: str                          # 唯一标识符（通常是规范化的名字）
    name: str                        # 主要名称
    aliases: List[str] = field(default_factory=list)  # 别名列表
    role: CharacterRole = CharacterRole.MINOR
    gender: CharacterGender = CharacterGender.UNKNOWN
    description: str = ""            # 人物简介
    first_appearance: int = 0        # 首次出现的章节
    
    # 累计统计
    total_mentions: int = 0          # 总提及次数
    total_dialogues: int = 0         # 总对话次数
    chapters_appeared: List[int] = field(default_factory=list)  # 出现的章节列表
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Character):
            return self.id == other.id
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            "role": self.role.value,
            "gender": self.gender.value,
            "description": self.description,
            "first_appearance": self.first_appearance,
            "total_mentions": self.total_mentions,
            "total_dialogues": self.total_dialogues,
            "chapters_appeared": self.chapters_appeared,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        return cls(
            id=data["id"],
            name=data["name"],
            aliases=data.get("aliases", []),
            role=CharacterRole(data.get("role", "minor")),
            gender=CharacterGender(data.get("gender", "unknown")),
            description=data.get("description", ""),
            first_appearance=data.get("first_appearance", 0),
            total_mentions=data.get("total_mentions", 0),
            total_dialogues=data.get("total_dialogues", 0),
            chapters_appeared=data.get("chapters_appeared", []),
        )


@dataclass
class CharacterMention:
    """人物在文本中的一次出现/提及"""
    character_id: str               # 人物ID
    character_name: str             # 使用的名称（可能是别名）
    mention_type: str               # 提及类型: "name", "pronoun", "title", "dialogue"
    context: str = ""               # 上下文片段
    position: int = 0               # 在文本中的大致位置（字符偏移）
    is_speaking: bool = False       # 是否在说话
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "mention_type": self.mention_type,
            "context": self.context,
            "position": self.position,
            "is_speaking": self.is_speaking,
        }


@dataclass
class CharacterValue:
    """人物价值评分"""
    character_id: str
    character_name: str
    
    # 核心评分 (0.0 - 1.0)
    importance_score: float = 0.0   # 重要性分数
    screen_time: float = 0.0        # 戏份占比
    dialogue_ratio: float = 0.0     # 对话占比
    action_ratio: float = 0.0       # 动作/行为占比
    
    # 角色判定
    role: CharacterRole = CharacterRole.MINOR
    
    # 统计数据
    mention_count: int = 0          # 提及次数
    dialogue_count: int = 0         # 对话次数
    
    # 分析说明
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "importance_score": round(self.importance_score, 3),
            "screen_time": round(self.screen_time, 3),
            "dialogue_ratio": round(self.dialogue_ratio, 3),
            "action_ratio": round(self.action_ratio, 3),
            "role": self.role.value,
            "mention_count": self.mention_count,
            "dialogue_count": self.dialogue_count,
            "reason": self.reason,
        }


@dataclass
class SceneCharacterAnalysis:
    """场景级人物分析结果"""
    scene_index: int
    scene_title: str = ""
    characters: List[CharacterValue] = field(default_factory=list)
    main_characters: List[str] = field(default_factory=list)  # 主要人物ID列表
    total_characters: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_index": self.scene_index,
            "scene_title": self.scene_title,
            "characters": [c.to_dict() for c in self.characters],
            "main_characters": self.main_characters,
            "total_characters": self.total_characters,
        }


@dataclass
class ChapterCharacterAnalysis:
    """章节级人物分析结果"""
    chapter_index: int
    chapter_title: str = ""
    characters: List[CharacterValue] = field(default_factory=list)
    main_characters: List[str] = field(default_factory=list)
    protagonist_screen_time: float = 0.0   # 主角戏份
    total_characters: int = 0
    scene_analyses: List[SceneCharacterAnalysis] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "characters": [c.to_dict() for c in self.characters],
            "main_characters": self.main_characters,
            "protagonist_screen_time": round(self.protagonist_screen_time, 3),
            "total_characters": self.total_characters,
            "scene_analyses": [s.to_dict() for s in self.scene_analyses],
        }


@dataclass 
class CharacterDatabase:
    """人物数据库 - 存储全书人物信息"""
    characters: Dict[str, Character] = field(default_factory=dict)
    name_to_id: Dict[str, str] = field(default_factory=dict)  # 名称/别名 -> ID 映射
    
    def add_character(self, character: Character) -> None:
        """添加人物"""
        self.characters[character.id] = character
        # 建立名称映射
        self.name_to_id[character.name.lower()] = character.id
        for alias in character.aliases:
            self.name_to_id[alias.lower()] = character.id
    
    def get_by_name(self, name: str) -> Optional[Character]:
        """根据名称获取人物"""
        char_id = self.name_to_id.get(name.lower())
        if char_id:
            return self.characters.get(char_id)
        return None
    
    def get_by_id(self, char_id: str) -> Optional[Character]:
        """根据ID获取人物"""
        return self.characters.get(char_id)
    
    def find_similar(self, name: str) -> Optional[Character]:
        """模糊查找人物（处理称呼变化）"""
        # 精确匹配
        char = self.get_by_name(name)
        if char:
            return char
        
        # 包含匹配
        name_lower = name.lower()
        for stored_name, char_id in self.name_to_id.items():
            if name_lower in stored_name or stored_name in name_lower:
                return self.characters[char_id]
        
        return None
    
    def merge_characters(self, char_id1: str, char_id2: str) -> None:
        """合并两个人物（处理同一人物识别为不同人的情况）"""
        if char_id1 not in self.characters or char_id2 not in self.characters:
            return
        
        char1 = self.characters[char_id1]
        char2 = self.characters[char_id2]
        
        # 合并别名
        char1.aliases.extend([char2.name] + char2.aliases)
        char1.aliases = list(set(char1.aliases))
        
        # 合并统计
        char1.total_mentions += char2.total_mentions
        char1.total_dialogues += char2.total_dialogues
        char1.chapters_appeared = list(set(char1.chapters_appeared + char2.chapters_appeared))
        
        # 更新映射
        for alias in char2.aliases + [char2.name]:
            self.name_to_id[alias.lower()] = char_id1
        
        # 删除旧人物
        del self.characters[char_id2]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterDatabase":
        db = cls()
        for char_id, char_data in data.get("characters", {}).items():
            char = Character.from_dict(char_data)
            db.add_character(char)
        return db


# 角色重要性阈值
ROLE_THRESHOLDS = {
    CharacterRole.PROTAGONIST: 0.8,      # 主角阈值
    CharacterRole.DEUTERAGONIST: 0.5,    # 重要配角阈值
    CharacterRole.SUPPORTING: 0.3,       # 配角阈值
    CharacterRole.MINOR: 0.1,            # 次要人物阈值
    CharacterRole.EXTRA: 0.0,            # 龙套
}


def determine_role(importance_score: float) -> CharacterRole:
    """根据重要性分数判定角色类型"""
    if importance_score >= ROLE_THRESHOLDS[CharacterRole.PROTAGONIST]:
        return CharacterRole.PROTAGONIST
    elif importance_score >= ROLE_THRESHOLDS[CharacterRole.DEUTERAGONIST]:
        return CharacterRole.DEUTERAGONIST
    elif importance_score >= ROLE_THRESHOLDS[CharacterRole.SUPPORTING]:
        return CharacterRole.SUPPORTING
    elif importance_score >= ROLE_THRESHOLDS[CharacterRole.MINOR]:
        return CharacterRole.MINOR
    else:
        return CharacterRole.EXTRA
