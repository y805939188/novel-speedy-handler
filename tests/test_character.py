# tests/test_character.py
"""
测试人物价值评分模块（使用真实数据调用 LLM）

用法:
    python -m tests.test_character
    python -m tests.test_character -n 5
    python -m tests.test_character --skip-llm
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
from novel_speedy.character import (
    CharacterAnalyzer,
    AnalyzerConfig,
    ChapterCharacterAnalysis,
    CharacterRole,
)
from typing import List

console = Console()


def print_summary_table(results: List[ChapterCharacterAnalysis]):
    """打印测试结果摘要表格"""
    
    # 章节人物表格
    table = Table(title="📊 人物分析结果", show_header=True, header_style="bold cyan")
    table.add_column("章节", style="dim", width=6)
    table.add_column("标题", width=20)
    table.add_column("人物数", justify="right")
    table.add_column("主要人物", width=45)
    
    # 汇总全书人物
    all_chars = {}
    
    for r in results:
        # 主要人物名字
        main_char_names = []
        for cv in r.characters:
            if cv.importance_score >= 0.5:
                main_char_names.append(f"[bold]{cv.character_name}[/]({cv.importance_score:.2f})")
            
            # 汇总
            if cv.character_name not in all_chars:
                all_chars[cv.character_name] = {
                    "chapters": 0,
                    "total_importance": 0,
                    "total_screen_time": 0,
                }
            all_chars[cv.character_name]["chapters"] += 1
            all_chars[cv.character_name]["total_importance"] += cv.importance_score
            all_chars[cv.character_name]["total_screen_time"] += cv.screen_time
        
        main_str = ", ".join(main_char_names[:3]) if main_char_names else "[dim]-[/]"
        
        # 标题截断
        title = r.chapter_title[:18] + ".." if len(r.chapter_title) > 20 else r.chapter_title
        
        table.add_row(
            str(r.chapter_index),
            title,
            str(r.total_characters),
            main_str
        )
    
    console.print()
    console.print(table)
    
    # 全书人物统计
    stats_table = Table(title="📈 全书人物统计", show_header=False, box=None)
    stats_table.add_column("指标", style="cyan")
    stats_table.add_column("值", style="bold")
    stats_table.add_row("识别人物总数", str(len(all_chars)))
    
    console.print()
    console.print(stats_table)
    
    # Top 10 人物
    sorted_chars = sorted(
        all_chars.items(),
        key=lambda x: x[1]["total_importance"],
        reverse=True
    )
    
    top_table = Table(title="🎭 Top 10 重要人物", show_header=True, header_style="bold magenta")
    top_table.add_column("排名", style="bold yellow", width=6)
    top_table.add_column("人物", width=15)
    top_table.add_column("出现章数", justify="right")
    top_table.add_column("平均重要性", justify="right", style="green")
    top_table.add_column("平均戏份", justify="right")
    
    for i, (name, data) in enumerate(sorted_chars[:10], 1):
        avg_importance = data["total_importance"] / data["chapters"]
        avg_screen_time = data["total_screen_time"] / data["chapters"]
        top_table.add_row(
            str(i),
            name,
            str(data['chapters']),
            f"{avg_importance:.2f}",
            f"{avg_screen_time:.2f}"
        )
    
    console.print()
    console.print(top_table)


def main():
    parser = argparse.ArgumentParser(description="测试人物价值评分模块")
    parser.add_argument("-n", "--num-chapters", type=int, default=5, help="测试章节数量（默认5）")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM（使用规则分析）")
    args = parser.parse_args()
    
    print("\n" + "🎭" * 20)
    print("   人物价值评分模块测试")
    print("🎭" * 20)
    
    # 加载章节数据
    chapters_path = os.path.join(config.paths.output_dir, "chapters.json")
    
    if not os.path.exists(chapters_path):
        print(f"\n❌ 章节文件不存在: {chapters_path}")
        print("   请先运行 python -m tests.test_pipeline 生成章节数据")
        return
    
    chapters = load_chapters(chapters_path)
    chapters = chapters[:args.num_chapters]
    
    print(f"\n📁 数据文件: {chapters_path}")
    print(f"📚 测试章节: 前 {len(chapters)} 章")
    print(f"🔧 LLM 分析: {'跳过' if args.skip_llm else '启用'}")
    
    # 创建分析器
    analyzer_config = AnalyzerConfig(use_llm=not args.skip_llm)
    analyzer = CharacterAnalyzer(analyzer_config)
    
    print(f"\n{'='*60}")
    print("开始分析...")
    if not args.skip_llm:
        print("⚠️  调用 LLM API 中，请稍候...")
    print("=" * 60)
    
    # 运行分析
    results = analyzer.analyze_chapters(chapters)
    
    # 打印结果摘要表格
    print_summary_table(results)
    
    # 保存结果
    output_path = os.path.join(config.paths.output_dir, "character_analysis.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        output_data = {
            "chapters": [r.to_dict() for r in results],
            "character_database": analyzer.get_character_database().to_dict(),
        }
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存到: {output_path}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
