"""
小说速读系统 - Step 1: 章节切分模块

TODO: 通过 AI 或者纯代码的方式校验章节是否划分准确
    主要需要考虑: 识别错误的、漏掉的
    1. 通过平均字数和每章字数比例做判断
    2. 通过 AI 批量将一部分标题做检测判断相似性
"""

import re
import json
import os
from typing import Optional

# 章节标题匹配正则表达式
CHAPTER_PATTERNS = [
    r'^第[0-9一二三四五六七八九十百千]+[章节回][：:、\s]?(.*)$',
    r'^卷[0-9一二三四五六七八九十百千]+[：:、\s]?(.*)$',
    r'^(序章|楔子|引子|前言)$',
    r'^(尾声|后记|番外)$',
    r'^(Chapter|CHAPTER)\s+[0-9IVXLC]+(\s+.*)?$'
]

# 编译正则表达式以提高性能
COMPILED_PATTERNS = [re.compile(pattern) for pattern in CHAPTER_PATTERNS]

# 兜底切分时每块的字符数
FALLBACK_CHUNK_SIZE = 8000


def is_chapter_title(line: str) -> bool:
    """
    判断一行文本是否是章节标题行
    
    Args:
        line: 输入的文本行
        
    Returns:
        如果匹配任意一个章节模式则返回 True
    """
    stripped = line.strip()
    if not stripped:
        return False
    
    for pattern in COMPILED_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def find_chapter_indices(lines: list[str]) -> list[int]:
    """
    找出所有章节标题行的索引位置
    
    Args:
        lines: 按行分割后的文本列表
        
    Returns:
        所有章节标题行的索引列表
    """
    indices = []
    for i, line in enumerate(lines):
        if is_chapter_title(line):
            indices.append(i)
    return indices


def extract_chapter(lines: list[str], start_idx: int, end_idx: Optional[int]) -> dict:
    """
    从行列表中提取一个章节的内容
    
    Args:
        lines: 按行分割后的文本列表
        start_idx: 章节起始行索引（包含）
        end_idx: 章节结束行索引（不包含），None 表示到文件末尾
        
    Returns:
        包含章节信息的字典
    """
    if end_idx is None:
        chapter_lines = lines[start_idx:]
    else:
        chapter_lines = lines[start_idx:end_idx]
    
    title = lines[start_idx].strip()
    text = "\n".join(chapter_lines)
    
    return {
        "title": title,
        "text": text,
        "char_count": len(text)
    }


def split_by_pattern(lines: list[str], chapter_indices: list[int]) -> list[dict]:
    """
    根据识别到的章节标题位置切分章节
    
    Args:
        lines: 按行分割后的文本列表
        chapter_indices: 章节标题行的索引列表
        
    Returns:
        章节列表
    """
    chapters = []
    
    for i, start_idx in enumerate(chapter_indices):
        # 确定结束位置
        if i + 1 < len(chapter_indices):
            end_idx = chapter_indices[i + 1]
        else:
            end_idx = None
        
        chapter = extract_chapter(lines, start_idx, end_idx)
        chapter["index"] = i + 1
        chapters.append(chapter)
    
    return chapters


def split_by_fallback(text: str, chunk_size: int = FALLBACK_CHUNK_SIZE) -> list[dict]:
    """
    兜底策略：按固定字符数切分文本
    
    Args:
        text: 原始文本
        chunk_size: 每块的字符数
        
    Returns:
        章节列表
    """
    chapters = []
    total_len = len(text)
    index = 1
    start = 0
    
    while start < total_len:
        end = start + chunk_size
        
        # 尽量在换行符处切分，避免切断句子
        if end < total_len:
            # 向前查找最近的换行符
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start:
                end = newline_pos + 1
        
        chunk_text = text[start:end]
        title = f"第{index}章 自动切分"
        
        # 将标题添加到文本开头
        full_text = title + "\n" + chunk_text
        
        chapters.append({
            "index": index,
            "title": title,
            "text": full_text,
            "char_count": len(full_text)
        })
        
        index += 1
        start = end
    
    return chapters


def split_chapters(text: str) -> list[dict]:
    """
    将整本小说的原始文本切分成章节
    
    Args:
        text: 小说原始文本（长字符串）
        
    Returns:
        章节列表，每个元素包含:
        - index: 章节编号（从1开始）
        - title: 章节标题
        - text: 章节完整文本（包含标题行）
        - char_count: 文本长度
    """
    # 按行分割
    lines = text.split("\n")
    
    # 查找所有章节标题行的位置
    chapter_indices = find_chapter_indices(lines)
    
    # 如果没有识别到任何章节标题，使用兜底策略
    if not chapter_indices:
        return split_by_fallback(text)
    
    # 按识别到的章节切分
    chapters = split_by_pattern(lines, chapter_indices)
    
    # 重新整理输出格式，确保字段顺序一致
    result = []
    for chapter in chapters:
        result.append({
            "index": chapter["index"],
            "title": chapter["title"],
            "text": chapter["text"],
            "char_count": chapter["char_count"]
        })
    
    return result


def save_chapters_to_json(chapters: list[dict], output_dir: str = "split_chapter_outputs") -> str:
    """
    将章节列表保存为 JSON 文件
    
    Args:
        chapters: 章节列表
        output_dir: 输出目录
        
    Returns:
        输出文件的完整路径
    """
    # 创建输出目录（如果不存在）
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成输出文件路径
    output_path = os.path.join(output_dir, "chapters.json")
    
    # 写入 JSON 文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    
    return output_path


def process_novel(text: str, output_dir: str = "split_chapter_outputs") -> list[dict]:
    """
    处理小说文本：切分章节并保存结果
    
    Args:
        text: 小说原始文本
        output_dir: 输出目录
        
    Returns:
        章节列表
    """
    # 切分章节
    chapters = split_chapters(text)
    
    # 保存到 JSON
    output_path = save_chapters_to_json(chapters, output_dir)
    print(f"章节切分完成，共 {len(chapters)} 章，已保存到: {output_path}")
    
    return chapters


# 命令行入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python split_chapters.py <小说文件路径>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # 读取小说文件
    with open(input_file, "r", encoding="utf-8") as f:
        novel_text = f.read()
    
    # 处理并输出
    chapters = process_novel(novel_text)
    
    # 打印摘要信息
    print("\n章节摘要:")
    print("-" * 50)
    for chapter in chapters:
        print(f"  {chapter['index']:3d}. {chapter['title'][:40]:<40} ({chapter['char_count']} 字)")
