# tests/test_speedy_budget.py
"""
测试速读字数预算计算器

用法:
    python -m tests.test_speedy_budget
    python -m tests.test_speedy_budget -n 20 -t 30
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters
from novel_speedy.speedy import (
    SpeedyBudgetConfig,
    SpeedyBudgetCalculator,
    calculate_speedy_budget,
)

console = Console()


def print_detailed_table(plan):
    """打印详细的预算表格"""
    
    # 章节预算表格
    table = Table(title="📊 速读字数预算详情", show_header=True, header_style="bold cyan")
    table.add_column("章节", style="dim", width=6)
    table.add_column("标题", width=20)
    table.add_column("原文", justify="right")
    table.add_column("预算", justify="right", style="bold green")
    table.add_column("压缩比", justify="right")
    table.add_column("高潮分", justify="right")
    table.add_column("权重", justify="right")
    table.add_column("标记", width=4)
    
    for ch in plan.chapters:
        title = ch.chapter_title[:18] + ".." if len(ch.chapter_title) > 20 else ch.chapter_title
        
        # 标记和样式
        if ch.is_climax:
            mark = "🔥"
            ratio_style = "bold red"
        elif ch.climax_score > 0.5:
            mark = "⬆️"
            ratio_style = "yellow"
        else:
            mark = ""
            ratio_style = "dim"
        
        table.add_row(
            str(ch.chapter_index),
            title,
            f"{ch.original_chars:,}",
            f"{ch.budget_chars:,}",
            f"[{ratio_style}]{ch.compression_ratio:.1%}[/]",
            f"{ch.climax_score:.2f}",
            f"{ch.normalized_weight:.4f}",
            mark
        )
    
    console.print()
    console.print(table)
    
    # 汇总统计
    stats_table = Table(title="📈 汇总统计", show_header=False, box=None)
    stats_table.add_column("指标", style="cyan", width=20)
    stats_table.add_column("值", style="bold")
    
    stats_table.add_row("章节总数", str(len(plan.chapters)))
    stats_table.add_row("高潮章节数", str(plan.climax_chapter_count))
    stats_table.add_row("原文总字数", f"{plan.total_original_chars:,} 字")
    stats_table.add_row("预算总字数", f"[bold green]{plan.total_budget_chars:,} 字[/]")
    stats_table.add_row("整体压缩比", f"{plan.overall_compression_ratio:.2%}")
    stats_table.add_row("目标阅读时间", f"{plan.config.target_time_minutes} 分钟")
    stats_table.add_row("预估阅读时间", f"[bold]{plan.estimated_total_reading_minutes:.1f} 分钟[/]")
    
    console.print()
    console.print(stats_table)
    
    # 高潮分布
    high_climax = [ch for ch in plan.chapters if ch.climax_score >= 0.6]
    mid_climax = [ch for ch in plan.chapters if 0.4 <= ch.climax_score < 0.6]
    low_climax = [ch for ch in plan.chapters if ch.climax_score < 0.4]
    
    dist_table = Table(title="📊 高潮分布", show_header=True, header_style="bold magenta")
    dist_table.add_column("类型", width=20)
    dist_table.add_column("章数", justify="right")
    dist_table.add_column("平均压缩比", justify="right")
    
    if high_climax:
        avg_ratio = sum(ch.compression_ratio for ch in high_climax) / len(high_climax)
        dist_table.add_row("🔥 高潮章节 (≥0.6)", str(len(high_climax)), f"{avg_ratio:.1%}")
    else:
        dist_table.add_row("🔥 高潮章节 (≥0.6)", "0", "-")
    
    if mid_climax:
        avg_ratio = sum(ch.compression_ratio for ch in mid_climax) / len(mid_climax)
        dist_table.add_row("⬆️ 中等章节 (0.4-0.6)", str(len(mid_climax)), f"{avg_ratio:.1%}")
    else:
        dist_table.add_row("⬆️ 中等章节 (0.4-0.6)", "0", "-")
    
    if low_climax:
        avg_ratio = sum(ch.compression_ratio for ch in low_climax) / len(low_climax)
        dist_table.add_row("   低潮章节 (<0.4)", str(len(low_climax)), f"{avg_ratio:.1%}")
    else:
        dist_table.add_row("   低潮章节 (<0.4)", "0", "-")
    
    console.print()
    console.print(dist_table)


def main():
    parser = argparse.ArgumentParser(description="测试速读字数预算计算器")
    parser.add_argument("-n", "--num-chapters", type=int, default=10, help="测试章节数量（默认10）")
    parser.add_argument("-t", "--target-time", type=float, default=10.0, help="目标阅读时间（分钟，默认60）")
    parser.add_argument("-s", "--reading-speed", type=float, default=300.0, help="阅读速度（字/分钟，默认300）")
    args = parser.parse_args()
    
    print("\n" + "📖" * 20)
    print("   速读字数预算计算器测试")
    print("📖" * 20)
    
    # 加载章节数据
    chapters_path = os.path.join(config.paths.output_dir, "chapters.json")
    climax_path = os.path.join(config.paths.output_dir, "climax_scores.json")
    
    if not os.path.exists(chapters_path):
        print(f"\n❌ 章节文件不存在: {chapters_path}")
        print("   请先运行 python -m tests.test_pipeline 生成章节数据")
        return
    
    # 加载数据
    chapters = load_chapters(chapters_path)[:args.num_chapters]
    
    # 加载高潮评分（如果存在）
    climax_scores = None
    if os.path.exists(climax_path):
        with open(climax_path, 'r', encoding='utf-8') as f:
            all_climax_scores = json.load(f)
            # 只取对应章节的评分
            chapter_indices = {ch["index"] for ch in chapters}
            climax_scores = [cs for cs in all_climax_scores if cs["chapter_index"] in chapter_indices]
        print(f"\n📁 高潮评分文件: {climax_path}")
        print(f"   加载了 {len(climax_scores)} 章的高潮评分")
    else:
        print(f"\n⚠️  高潮评分文件不存在: {climax_path}")
        print("   将使用默认评分 0.5")
    
    print(f"\n📚 测试章节: {len(chapters)} 章")
    print(f"🎯 目标阅读时间: {args.target_time} 分钟")
    print(f"📖 阅读速度: {args.reading_speed} 字/分钟")
    print(f"📝 目标总字数: {int(args.target_time * args.reading_speed):,} 字")
    
    # 计算预算
    print(f"\n{'='*60}")
    print("开始计算预算...")
    print("=" * 60)
    
    plan = calculate_speedy_budget(
        chapters=chapters,
        climax_scores=climax_scores,
        target_time_minutes=args.target_time,
        reading_speed=args.reading_speed
    )
    
    # 打印结果
    print_detailed_table(plan)
    
    # 保存结果
    output_path = os.path.join(config.paths.output_dir, "speedy_budget.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存到: {output_path}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
