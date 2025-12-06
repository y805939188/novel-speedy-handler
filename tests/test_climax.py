# tests/test_climax.py
"""
测试高潮识别插件系统（使用真实数据调用 LLM）

用法:
    python -m tests.test_climax
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters
from novel_speedy.climax import ClimaxAnalyzer, AnalyzerConfig, ChapterClimaxScore
from typing import List


def print_summary_table(results: List[ChapterClimaxScore]):
    """打印测试结果摘要表格"""
    print("\n")
    print("=" * 100)
    print("📊 测试结果摘要")
    print("=" * 100)
    
    # 表头
    print(f"{'章节':<6} {'标题':<25} {'综合分':<8} {'冲突':<8} {'爽点':<8} {'节奏':<8} {'结构':<8} {'标签':<20}")
    print("-" * 100)
    
    # 统计
    total_conflict = 0
    total_coolpoint = 0
    total_rhythm = 0
    total_structure = 0
    success_coolpoint = 0
    
    for r in results:
        # 提取各维度分数
        conflict_score = "-"
        coolpoint_score = "-"
        coolpoint_reason = ""
        rhythm_score = "-"
        structure_score = "-"
        
        for ds in r.dimension_scores:
            if ds.dimension.value == "conflict":
                conflict_score = f"{ds.score:.2f}"
                total_conflict += ds.score
            elif ds.dimension.value == "coolpoint":
                coolpoint_score = f"{ds.score:.2f}"
                coolpoint_reason = ds.reason
                total_coolpoint += ds.score
                if "失败" not in ds.reason:
                    success_coolpoint += 1
            elif ds.dimension.value == "rhythm":
                rhythm_score = f"{ds.score:.2f}"
                total_rhythm += ds.score
            elif ds.dimension.value == "structure":
                structure_score = f"{ds.score:.2f}"
                total_structure += ds.score
        
        # 标签
        tags = ", ".join(r.climax_tags[:2]) if r.climax_tags else "-"
        
        # 高潮标记
        climax_mark = "🔥" if r.is_climax else "  "
        
        # 标题截断
        title = r.chapter_title[:22] + "..." if len(r.chapter_title) > 25 else r.chapter_title
        
        print(f"{climax_mark}{r.chapter_index:<4} {title:<25} {r.final_score:<8.2f} {conflict_score:<8} {coolpoint_score:<8} {rhythm_score:<8} {structure_score:<8} {tags:<20}")
    
    print("-" * 100)
    
    # 统计信息
    n = len(results)
    climax_count = sum(1 for r in results if r.is_climax)
    avg_score = sum(r.final_score for r in results) / n if n else 0
    
    print(f"\n📈 统计信息:")
    print(f"  总章节数: {n}")
    print(f"  高潮章节: {climax_count} ({climax_count/n*100:.1f}%)" if n else "  高潮章节: 0")
    print(f"  平均综合分: {avg_score:.2f}")
    print(f"  平均冲突分: {total_conflict/n:.2f}" if n else "")
    print(f"  平均爽点分: {total_coolpoint/n:.2f}" if n else "")
    print(f"  爽点解析成功率: {success_coolpoint}/{n} ({success_coolpoint/n*100:.1f}%)" if n else "")
    print(f"  平均节奏分: {total_rhythm/n:.2f}" if n else "")
    print(f"  平均结构分: {total_structure/n:.2f}" if n else "")
    
    # Top 3 章节
    sorted_results = sorted(results, key=lambda r: r.final_score, reverse=True)
    print(f"\n🏆 Top 3 高分章节:")
    for i, r in enumerate(sorted_results[:3], 1):
        print(f"  {i}. 第{r.chapter_index}章 《{r.chapter_title}》 - {r.final_score:.2f}")
    
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="测试高潮识别插件系统")
    parser.add_argument("-n", "--num-chapters", type=int, default=10, help="测试章节数量（默认10）")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 插件（快速测试）")
    args = parser.parse_args()
    
    print("\n" + "🚀" * 20)
    print("   高潮识别插件系统测试")
    print("🚀" * 20)
    
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
    print(f"🔧 LLM 插件: {'跳过' if args.skip_llm else '启用'}")
    
    # 创建分析器
    analyzer_config = AnalyzerConfig(skip_llm_plugins=args.skip_llm)
    analyzer = ClimaxAnalyzer(analyzer_config)
    
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
    output_path = os.path.join(config.paths.output_dir, "climax_scores.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存到: {output_path}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
