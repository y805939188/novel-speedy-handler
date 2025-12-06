# tests/test_compressor.py
"""
测试内容压缩器

用法:
    python -m tests.test_compressor
    python -m tests.test_compressor -n 5
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters
from novel_speedy.speedy import (
    ChapterCompressor,
    CompressionConfig,
    compress_chapter,
)

console = Console()


def print_compressed_result(result, original_text: str):
    """打印压缩结果"""
    
    # 显示压缩统计
    stats = Table(title="📊 压缩统计", show_header=False, box=None)
    stats.add_column("指标", style="cyan", width=15)
    stats.add_column("值", style="bold")
    
    stats.add_row("原文字数", f"{result.original_chars:,} 字")
    stats.add_row("压缩后字数", f"{result.compressed_chars:,} 字")
    stats.add_row("压缩比", f"{result.compression_ratio:.1%}")
    stats.add_row("使用策略", result.strategy_used)
    
    console.print(stats)
    
    # 显示原文片段
    console.print()
    console.print(Panel(
        original_text[:300] + "..." if len(original_text) > 300 else original_text,
        title="📖 原文片段",
        border_style="dim"
    ))
    
    # 显示压缩后内容
    console.print()
    console.print(Panel(
        result.content,
        title="✨ 压缩后内容",
        border_style="green"
    ))


def main():
    parser = argparse.ArgumentParser(description="测试内容压缩器")
    parser.add_argument("-n", "--num-chapters", type=int, default=3, help="测试章节数量（默认3）")
    parser.add_argument("-r", "--ratio", type=float, default=0.15, help="目标压缩比（默认0.15）")
    args = parser.parse_args()
    
    console.print("\n" + "🗜️" * 20)
    console.print("   内容压缩器测试")
    console.print("🗜️" * 20)
    
    # 加载数据
    chapters_path = os.path.join(config.paths.output_dir, "chapters.json")
    climax_path = os.path.join(config.paths.output_dir, "climax_scores.json")
    budget_path = os.path.join(config.paths.output_dir, "speedy_budget.json")
    
    if not os.path.exists(chapters_path):
        console.print(f"\n[red]❌ 章节文件不存在: {chapters_path}[/]")
        return
    
    chapters = load_chapters(chapters_path)[:args.num_chapters]
    
    # 加载高潮评分
    climax_map = {}
    coolpoint_map = {}
    if os.path.exists(climax_path):
        with open(climax_path, 'r', encoding='utf-8') as f:
            climax_scores = json.load(f)
            for cs in climax_scores:
                idx = cs.get("chapter_index", 0)
                climax_map[idx] = cs.get("final_score", 0.5)
                # 提取爽点类型
                for ds in cs.get("dimension_scores", []):
                    if ds.get("dimension") == "coolpoint":
                        details = ds.get("details", {})
                        coolpoint_map[idx] = details.get("coolpoint_types", [])
    
    # 加载预算（如果有）
    budget_map = {}
    if os.path.exists(budget_path):
        with open(budget_path, 'r', encoding='utf-8') as f:
            budget_data = json.load(f)
            for cb in budget_data.get("chapter_budgets", []):
                budget_map[cb["chapter_index"]] = cb["budget_chars"]
    
    console.print(f"\n📚 测试章节: {len(chapters)} 章")
    console.print(f"📉 目标压缩比: {args.ratio:.0%}")
    
    # 创建压缩器
    compressor = ChapterCompressor()
    
    # 结果汇总表
    summary_table = Table(title="📋 压缩结果汇总", show_header=True, header_style="bold cyan")
    summary_table.add_column("章节", width=6)
    summary_table.add_column("标题", width=18)
    summary_table.add_column("原文", justify="right", width=8)
    summary_table.add_column("目标", justify="right", width=8)
    summary_table.add_column("实际", justify="right", width=8)
    summary_table.add_column("策略", width=10)
    summary_table.add_column("高潮分", justify="right", width=8)
    
    results = []
    
    for ch in chapters:
        index = ch.get("index", 0)
        title = ch.get("title", f"第{index}章")
        text = ch.get("text", "")
        
        # 获取高潮评分和爽点类型
        climax_score = climax_map.get(index, 0.5)
        coolpoint_types = coolpoint_map.get(index, [])
        
        # 计算目标字数
        if index in budget_map:
            target_chars = budget_map[index]
        else:
            target_chars = int(len(text) * args.ratio)
        
        console.print(f"\n{'='*60}")
        console.print(f"[bold]章节 {index}: {title}[/]")
        console.print(f"高潮分: {climax_score:.2f}, 爽点: {coolpoint_types}")
        console.print("=" * 60)
        console.print("⏳ 正在压缩...")
        
        # 执行压缩
        result = compressor.compress(
            chapter_text=text,
            chapter_title=title,
            chapter_index=index,
            target_chars=target_chars,
            climax_score=climax_score,
            coolpoint_types=coolpoint_types
        )
        
        results.append(result)
        
        # 打印详细结果
        print_compressed_result(result, text)
        
        # 添加到汇总表
        strategy_style = {
            "preserve": "green",
            "rewrite": "yellow", 
            "summarize": "cyan"
        }.get(result.strategy_used, "white")
        
        title_short = title[:16] + ".." if len(title) > 18 else title
        
        summary_table.add_row(
            str(index),
            title_short,
            f"{result.original_chars:,}",
            f"{target_chars:,}",
            f"{result.compressed_chars:,}",
            f"[{strategy_style}]{result.strategy_used}[/]",
            f"{climax_score:.2f}"
        )
    
    # 打印汇总
    console.print("\n")
    console.print(summary_table)
    
    # 保存结果
    output_data = {
        "chapters": [r.to_dict() for r in results],
        "total_original_chars": sum(r.original_chars for r in results),
        "total_compressed_chars": sum(r.compressed_chars for r in results),
    }
    
    output_path = os.path.join(config.paths.output_dir, "compressed_chapters.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    console.print(f"\n[green]✅ 结果已保存到: {output_path}[/]")
    
    # 统计
    total_original = sum(r.original_chars for r in results)
    total_compressed = sum(r.compressed_chars for r in results)
    overall_ratio = total_compressed / total_original if total_original > 0 else 0
    
    console.print(f"\n📈 总体统计:")
    console.print(f"   原文总字数: {total_original:,} 字")
    console.print(f"   压缩后总字数: {total_compressed:,} 字")
    console.print(f"   总体压缩比: {overall_ratio:.1%}")
    
    console.print("\n" + "=" * 60)
    console.print("[green]✅ 测试完成[/]")
    console.print("=" * 60)


if __name__ == "__main__":
    main()
