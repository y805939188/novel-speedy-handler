# tests/test_speedy_generator.py
"""
测试速读生成器（完整流程）

用法:
    python -m tests.test_speedy_generator
    python -m tests.test_speedy_generator -n 10 -t 5
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters
from novel_speedy.speedy import (
    SpeedyConfig,
    SpeedyGenerator,
    generate_speedy,
)

console = Console()


def main():
    parser = argparse.ArgumentParser(description="测试速读生成器")
    parser.add_argument("-n", "--num-chapters", type=int, default=5, help="测试章节数量（默认5）")
    parser.add_argument("-t", "--time", type=float, default=3.0, help="目标阅读时间（分钟，默认3）")
    parser.add_argument("-s", "--speed", type=int, default=300, help="阅读速度（字/分钟，默认300）")
    parser.add_argument("-o", "--output", type=str, default="markdown", help="输出格式（markdown/json/txt）")
    parser.add_argument("--style", type=str, default=None, 
                        help="输出风格: pingshu(评书), ancient(古文), humor(幽默), dramatic(戏剧化), minimalist(极简), storytelling(讲故事), 或自定义描述")
    args = parser.parse_args()
    
    console.print("\n" + "🚀" * 20)
    console.print("   速读生成器测试")
    console.print("🚀" * 20)
    
    # 加载数据
    chapters_path = os.path.join(config.paths.output_dir, "chapters.json")
    climax_path = os.path.join(config.paths.output_dir, "climax_scores.json")
    
    if not os.path.exists(chapters_path):
        console.print(f"\n[red]❌ 章节文件不存在: {chapters_path}[/]")
        return
    
    chapters = load_chapters(chapters_path)[:args.num_chapters]
    
    # 加载高潮评分
    climax_scores = None
    if os.path.exists(climax_path):
        with open(climax_path, 'r', encoding='utf-8') as f:
            all_scores = json.load(f)
            chapter_indices = {ch["index"] for ch in chapters}
            climax_scores = [cs for cs in all_scores if cs["chapter_index"] in chapter_indices]
        console.print(f"\n📁 高潮评分: {len(climax_scores)} 章")
    
    console.print(f"\n📚 章节数量: {len(chapters)}")
    console.print(f"⏱️  目标阅读时间: {args.time} 分钟")
    console.print(f"📖 阅读速度: {args.speed} 字/分钟")
    console.print(f"📝 输出格式: {args.output}")
    if args.style:
        console.print(f"🎭 输出风格: {args.style}")
    
    total_chars = sum(len(ch.get("text", "")) for ch in chapters)
    console.print(f"📊 原文总字数: {total_chars:,} 字")
    console.print(f"🎯 目标字数: {int(args.time * args.speed):,} 字")
    
    console.print(f"\n{'='*60}")
    console.print("开始生成速读版...")
    console.print("⚠️  调用 LLM API 中，请稍候...")
    console.print("=" * 60)
    
    # 生成速读版
    result = generate_speedy(
        chapters=chapters,
        climax_scores=climax_scores,
        book_title="斗破苍穹",
        target_reading_time=args.time,
        reading_speed=args.speed,
        output_format=args.output,
        style=args.style
    )
    
    # 显示统计
    console.print("\n")
    stats_table = Table(title="📊 生成统计", show_header=False, box=None)
    stats_table.add_column("指标", style="cyan", width=20)
    stats_table.add_column("值", style="bold")
    
    stats_table.add_row("原文总字数", f"{result.total_original_chars:,} 字")
    stats_table.add_row("速读版字数", f"{result.total_compressed_chars:,} 字")
    stats_table.add_row("压缩比", f"{result.total_compressed_chars / result.total_original_chars:.1%}" if result.total_original_chars > 0 else "N/A")
    stats_table.add_row("预计阅读时间", f"{result.reading_time_minutes:.1f} 分钟")
    stats_table.add_row("章节数", str(result.total_chapters))
    
    console.print(stats_table)
    
    # 显示大纲
    if result.outline:
        console.print("\n")
        console.print(Panel(
            result.outline.overview,
            title="📖 故事概述",
            border_style="cyan"
        ))
    
    # 显示压缩结果表
    chapter_table = Table(title="📚 章节压缩结果", show_header=True, header_style="bold cyan")
    chapter_table.add_column("章节", width=6)
    chapter_table.add_column("标题", width=18)
    chapter_table.add_column("原文", justify="right", width=8)
    chapter_table.add_column("压缩后", justify="right", width=8)
    chapter_table.add_column("策略", width=10)
    
    for ch in result.chapters:
        title = ch.chapter_title[:16] + ".." if len(ch.chapter_title) > 18 else ch.chapter_title
        chapter_table.add_row(
            str(ch.chapter_index),
            title,
            f"{ch.original_chars:,}",
            f"{ch.compressed_chars:,}",
            ch.strategy_used
        )
    
    console.print("\n")
    console.print(chapter_table)
    
    # 输出内容预览
    console.print("\n")
    console.print(Panel(
        result.chapters[0].content if result.chapters else "无内容",
        title=f"📝 第1章速读预览: {result.chapters[0].chapter_title if result.chapters else ''}",
        border_style="green"
    ))
    
    # 保存结果
    output_dir = config.paths.output_dir
    
    # JSON 格式
    json_path = os.path.join(output_dir, "speedy_result.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    console.print(f"\n[green]✅ JSON 结果: {json_path}[/]")
    
    # Markdown 格式
    md_path = os.path.join(output_dir, "speedy_result.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(result.to_markdown())
    console.print(f"[green]✅ Markdown 结果: {md_path}[/]")
    
    # TXT 格式
    txt_path = os.path.join(output_dir, "speedy_result.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(result.to_txt())
    console.print(f"[green]✅ TXT 结果: {txt_path}[/]")
    
    console.print("\n" + "=" * 60)
    console.print("[green]✅ 速读版生成完成！[/]")
    console.print("=" * 60)


if __name__ == "__main__":
    main()
