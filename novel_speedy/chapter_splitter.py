# novel_speedy/chapter_splitter.py
"""
章节切分模块

将整本小说按章节标题切分为独立章节。
"""

import re
import json
import os
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 章节标题匹配正则表达式
CHAPTER_PATTERNS = [
    r'^第[0-9一二三四五六七八九十百千万]+[章节回][：:、\s]?(.*)$',
    r'^卷[0-9一二三四五六七八九十百千]+[：:、\s]?(.*)$',
    r'^(序章|楔子|引子|前言|序|引言)$',
    r'^(尾声|后记|番外|终章|大结局)$',
    r'^(Chapter|CHAPTER)\s+[0-9IVXLC]+(\s+.*)?$',
    r'^\d+[、.．]\s*.+$',  # 如 "1、开始" 或 "1. 开始"
]

COMPILED_PATTERNS = [re.compile(p) for p in CHAPTER_PATTERNS]

# 兜底切分时每块的字符数
FALLBACK_CHUNK_SIZE = 8000


@dataclass
class Chapter:
    """章节数据结构"""
    index: int
    title: str
    text: str
    char_count: int
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "index": self.index,
            "title": self.title,
            "text": self.text,
            "char_count": self.char_count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Chapter":
        """从字典创建实例"""
        return cls(
            index=data["index"],
            title=data["title"],
            text=data["text"],
            char_count=data.get("char_count", len(data["text"]))
        )


class ChapterSplitter:
    """
    章节切分器
    
    支持多种章节标题格式的识别和切分。
    """
    
    def __init__(self, fallback_chunk_size: int = FALLBACK_CHUNK_SIZE):
        """
        初始化切分器
        
        Args:
            fallback_chunk_size: 兜底切分时每块的字符数
        """
        self.fallback_chunk_size = fallback_chunk_size
    
    def is_chapter_title(self, line: str) -> bool:
        """
        判断一行文本是否是章节标题行
        
        Args:
            line: 输入的文本行
            
        Returns:
            bool: 如果匹配任意一个章节模式则返回 True
        """
        stripped = line.strip()
        if not stripped:
            return False
        
        # 标题行通常不会太长
        if len(stripped) > 50:
            return False
        
        return any(p.match(stripped) for p in COMPILED_PATTERNS)
    
    def find_chapter_indices(self, lines: List[str]) -> List[int]:
        """
        找出所有章节标题行的索引位置
        
        Args:
            lines: 按行分割后的文本列表
            
        Returns:
            List[int]: 所有章节标题行的索引列表
        """
        indices = []
        for i, line in enumerate(lines):
            if self.is_chapter_title(line):
                indices.append(i)
        return indices
    
    def split(self, text: str) -> List[Chapter]:
        """
        将整本小说的原始文本切分成章节
        
        Args:
            text: 小说原始文本（长字符串）
            
        Returns:
            List[Chapter]: 章节列表
        """
        lines = text.split("\n")
        chapter_indices = self.find_chapter_indices(lines)
        
        # 如果没有识别到任何章节标题，使用兜底策略
        if not chapter_indices:
            logger.warning("未识别到章节标题，使用兜底切分策略")
            return self._fallback_split(text)
        
        chapters = []
        
        for i, start_idx in enumerate(chapter_indices):
            # 确定结束位置
            end_idx = chapter_indices[i + 1] if i + 1 < len(chapter_indices) else None
            
            # 提取章节内容
            chapter_lines = lines[start_idx:end_idx] if end_idx else lines[start_idx:]
            title = lines[start_idx].strip()
            chapter_text = "\n".join(chapter_lines)
            
            chapters.append(Chapter(
                index=i + 1,
                title=title,
                text=chapter_text,
                char_count=len(chapter_text)
            ))
        
        logger.info(f"章节切分完成，共 {len(chapters)} 章")
        return chapters
    
    def _fallback_split(self, text: str) -> List[Chapter]:
        """
        兜底策略：按固定字符数切分文本
        
        Args:
            text: 原始文本
            
        Returns:
            List[Chapter]: 章节列表
        """
        chapters = []
        total_len = len(text)
        start = 0
        index = 1
        
        while start < total_len:
            end = min(start + self.fallback_chunk_size, total_len)
            
            # 尽量在换行符处切分，避免切断句子
            if end < total_len:
                newline_pos = text.rfind("\n", start, end)
                if newline_pos > start:
                    end = newline_pos + 1
            
            chunk_text = text[start:end]
            title = f"第{index}章 (自动切分)"
            
            chapters.append(Chapter(
                index=index,
                title=title,
                text=chunk_text,
                char_count=len(chunk_text)
            ))
            
            index += 1
            start = end
        
        logger.info(f"兜底切分完成，共 {len(chapters)} 块")
        return chapters
    
    def get_stats(self, chapters: List[Chapter]) -> dict:
        """
        获取章节统计信息
        
        Args:
            chapters: 章节列表
            
        Returns:
            dict: 统计信息
        """
        if not chapters:
            return {"total_chapters": 0}
        
        char_counts = [ch.char_count for ch in chapters]
        
        return {
            "total_chapters": len(chapters),
            "total_chars": sum(char_counts),
            "avg_chars": sum(char_counts) // len(chapters),
            "min_chars": min(char_counts),
            "max_chars": max(char_counts),
        }


# ============ 便捷函数 ============

def split_chapters(text: str) -> List[dict]:
    """
    便捷函数：切分章节并返回字典列表
    
    Args:
        text: 小说原始文本
        
    Returns:
        List[dict]: 章节字典列表
    """
    splitter = ChapterSplitter()
    chapters = splitter.split(text)
    return [ch.to_dict() for ch in chapters]


def save_chapters(chapters: List[Chapter], output_path: str) -> None:
    """
    保存章节到 JSON 文件
    
    Args:
        chapters: 章节列表（Chapter 对象或字典）
        output_path: 输出文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 统一转换为字典
    data = []
    for ch in chapters:
        if isinstance(ch, Chapter):
            data.append(ch.to_dict())
        else:
            data.append(ch)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"章节已保存到: {output_path}")


def load_chapters(input_path: str) -> List[dict]:
    """
    从 JSON 文件加载章节
    
    Args:
        input_path: 输入文件路径
        
    Returns:
        List[dict]: 章节字典列表
    """
    with open(input_path, "r", encoding="utf-8") as f:
        chapters = json.load(f)
    
    logger.info(f"从 {input_path} 加载了 {len(chapters)} 个章节")
    return chapters


# ============ 命令行入口 ============

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python -m novel_speedy.chapter_splitter <小说文件路径> [输出路径]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "chapters.json"
    
    # 读取小说文件
    with open(input_file, "r", encoding="utf-8") as f:
        novel_text = f.read()
    
    # 切分章节
    splitter = ChapterSplitter()
    chapters = splitter.split(novel_text)
    
    # 打印统计信息
    stats = splitter.get_stats(chapters)
    print(f"\n📊 章节统计:")
    print(f"  总章节数: {stats['total_chapters']}")
    print(f"  总字数: {stats['total_chars']}")
    print(f"  平均每章: {stats['avg_chars']} 字")
    print(f"  最短章节: {stats['min_chars']} 字")
    print(f"  最长章节: {stats['max_chars']} 字")
    
    # 保存结果
    save_chapters(chapters, output_file)
    
    # 打印前 10 章摘要
    print(f"\n📖 章节摘要 (前 10 章):")
    print("-" * 60)
    for ch in chapters[:10]:
        print(f"  {ch.index:4d}. {ch.title[:40]:<40} ({ch.char_count} 字)")
