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

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters
from novel_speedy.character import (
    CharacterAnalyzer,
    AnalyzerConfig,
    ChapterCharacterAnalysis,
    CharacterRole,
)
from typing import List


def print_summary_table(results: List[ChapterCharacterAnalysis]):
    """打印测试结果摘要表格"""
    print("\n")
    print("=" * 100)
    print("📊 人物分析结果摘要")
    print("=" * 100)
    
    # 表头
    print(f"{'章节':<6} {'标题':<20} {'人物数':<8} {'主要人物':<40}")
    print("-" * 100)
    
    # 汇总全书人物
    all_chars = {}
    
    for r in results:
        # 主要人物名字
        main_char_names = []
        for cv in r.characters:
            if cv.importance_score >= 0.5:
                main_char_names.append(f"{cv.character_name}({cv.importance_score:.2f})")
            
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
        
        main_str = ", ".join(main_char_names[:4]) if main_char_names else "-"
        
        # 标题截断
        title = r.chapter_title[:18] + ".." if len(r.chapter_title) > 20 else r.chapter_title
        
        print(f"{r.chapter_index:<6} {title:<20} {r.total_characters:<8} {main_str:<40}")
    
    print("-" * 100)
    
    # 全书人物统计
    print(f"\n📈 全书人物统计:")
    print(f"  识别人物总数: {len(all_chars)}")
    
    # Top 10 人物
    sorted_chars = sorted(
        all_chars.items(),
        key=lambda x: x[1]["total_importance"],
        reverse=True
    )
    
    print(f"\n🎭 Top 10 重要人物:")
    print(f"{'排名':<6} {'人物':<15} {'出现章数':<10} {'平均重要性':<12} {'平均戏份':<12}")
    print("-" * 60)
    
    for i, (name, data) in enumerate(sorted_chars[:10], 1):
        avg_importance = data["total_importance"] / data["chapters"]
        avg_screen_time = data["total_screen_time"] / data["chapters"]
        print(f"{i:<6} {name:<15} {data['chapters']:<10} {avg_importance:<12.2f} {avg_screen_time:<12.2f}")
    
    print("=" * 100)


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
