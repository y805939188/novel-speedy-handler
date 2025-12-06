# tests/test_outline.py
"""
测试大纲生成器

用法:
    python -m tests.test_outline
    python -m tests.test_outline -n 10
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
    OutlineConfig,
    OutlineGenerator,
    BookOutline,
    generate_outline,
)

console = Console()


def print_outline(outline: BookOutline):
    """打印大纲"""
    
    # 全书概述
    console.print()
    console.print(Panel(
        outline.overview,
        title="📖 全书概述",
        border_style="cyan"
    ))
    
    # 故事弧
    if outline.story_arcs:
        arc_table = Table(title="📚 故事弧", show_header=True, header_style="bold magenta")
        arc_table.add_column("卷", style="bold", width=8)
        arc_table.add_column("章节范围", width=12)
        arc_table.add_column("概述", width=60)
        
        for arc in outline.story_arcs:
            arc_table.add_row(
                arc.arc_name,
                f"{arc.start_chapter}-{arc.end_chapter}",
                arc.summary[:55] + "..." if len(arc.summary) > 55 else arc.summary
            )
        
        console.print()
        console.print(arc_table)
    
    # 章节摘要
    if outline.chapter_summaries:
        chapter_table = Table(title="📝 重要章节摘要", show_header=True, header_style="bold cyan")
        chapter_table.add_column("章节", style="dim", width=6)
        chapter_table.add_column("标题", width=18)
        chapter_table.add_column("高潮分", justify="right", width=8)
        chapter_table.add_column("摘要", width=50)
        
        for cs in outline.chapter_summaries:
            score_style = "bold red" if cs.is_key_chapter else "yellow" if cs.climax_score >= 0.4 else "dim"
            mark = "🔥" if cs.is_key_chapter else ""
            
            title = cs.chapter_title[:16] + ".." if len(cs.chapter_title) > 18 else cs.chapter_title
            summary = cs.summary[:48] + ".." if len(cs.summary) > 50 else cs.summary
            
            chapter_table.add_row(
                f"{mark}{cs.chapter_index}",
                title,
                f"[{score_style}]{cs.climax_score:.2f}[/]",
                summary
            )
        
        console.print()
        console.print(chapter_table)
    
    # 统计
    stats_table = Table(title="📈 统计信息", show_header=False, box=None)
    stats_table.add_column("指标", style="cyan", width=20)
    stats_table.add_column("值", style="bold")
    
    stats_table.add_row("总章节数", str(outline.total_chapters))
    stats_table.add_row("原文总字数", f"{outline.total_chars:,} 字")
    stats_table.add_row("大纲字数", f"{outline.outline_chars:,} 字")
    stats_table.add_row("重要章节数", str(outline.key_chapters_count))
    stats_table.add_row("故事弧数", str(len(outline.story_arcs)))
    
    console.print()
    console.print(stats_table)


def main():
    parser = argparse.ArgumentParser(description="测试大纲生成器")
    parser.add_argument("-n", "--num-chapters", type=int, default=10, help="测试章节数量（默认10）")
    parser.add_argument("-b", "--budget", type=int, default=3000, help="速读总预算（字，默认3000）")
    parser.add_argument("-r", "--ratio", type=float, default=0.05, help="大纲预算比例（默认0.05）")
    args = parser.parse_args()
    
    console.print("\n" + "📖" * 20)
    console.print("   大纲生成器测试")
    console.print("📖" * 20)
    
    # 加载章节数据
    chapters_path = os.path.join(config.paths.output_dir, "chapters.json")
    climax_path = os.path.join(config.paths.output_dir, "climax_scores.json")
    
    if not os.path.exists(chapters_path):
        console.print(f"\n[red]❌ 章节文件不存在: {chapters_path}[/]")
        console.print("   请先运行 python -m tests.test_pipeline 生成章节数据")
        return
    
    # 加载数据
    chapters = load_chapters(chapters_path)[:args.num_chapters]
    
    # 加载高潮评分
    climax_scores = None
    if os.path.exists(climax_path):
        with open(climax_path, 'r', encoding='utf-8') as f:
            all_climax_scores = json.load(f)
            chapter_indices = {ch["index"] for ch in chapters}
            climax_scores = [cs for cs in all_climax_scores if cs["chapter_index"] in chapter_indices]
        console.print(f"\n📁 高潮评分文件: {climax_path}")
        console.print(f"   加载了 {len(climax_scores)} 章的高潮评分")
    else:
        console.print(f"\n[yellow]⚠️  高潮评分文件不存在，使用默认评分[/]")
    
    # 计算大纲预算
    outline_budget = int(args.budget * args.ratio)
    
    console.print(f"\n📚 测试章节: {len(chapters)} 章")
    console.print(f"💰 速读总预算: {args.budget:,} 字")
    console.print(f"📝 大纲预算比例: {args.ratio:.0%}")
    console.print(f"📝 大纲预算: {outline_budget:,} 字")
    
    console.print(f"\n{'='*60}")
    console.print("开始生成大纲...")
    console.print("⚠️  调用 LLM API 中，请稍候...")
    console.print("=" * 60)
    
    # 生成大纲
    outline = generate_outline(
        chapters=chapters,
        climax_scores=climax_scores,
        speedy_total_budget=args.budget,
        outline_budget_ratio=args.ratio,
        book_title="斗破苍穹"
    )
    
    # 打印结果
    print_outline(outline)
    
    # 保存结果
    output_path = os.path.join(config.paths.output_dir, "outline.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
    console.print(f"\n[green]✅ 结果已保存到: {output_path}[/]")
    
    console.print("\n" + "=" * 60)
    console.print("[green]✅ 测试完成[/]")
    console.print("=" * 60)


if __name__ == "__main__":
    main()
