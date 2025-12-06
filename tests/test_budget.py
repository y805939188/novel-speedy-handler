# tests/test_budget.py
"""
测试篇幅预算模块

用法:
    python -m tests.test_budget
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters
from novel_speedy.budget import (
    BudgetConfig,
    BudgetAllocator,
    calculate_budget,
    estimate_reading_time,
    format_time
)


def test_basic_budget():
    """测试基本预算计算"""
    print("\n" + "=" * 60)
    print("测试 1: 基本预算计算")
    print("=" * 60)
    
    # 创建测试数据
    chapters = [
        {"index": 1, "title": "第1章", "char_count": 3000},
        {"index": 2, "title": "第2章", "char_count": 4000},
        {"index": 3, "title": "第3章", "char_count": 2500},
        {"index": 4, "title": "第4章", "char_count": 3500},
    ]
    
    total_chars = sum(ch["char_count"] for ch in chapters)
    print(f"原文总字数: {total_chars:,} 字")
    print(f"原文阅读时间: {format_time(estimate_reading_time(total_chars))}")
    
    # 计算预算（目标 5 分钟阅读）
    plan = calculate_budget(
        chapters,
        target_time_minutes=5,
        reading_speed=300,
        strategy="proportional"
    )
    
    plan.print_summary()
    
    print("\n📖 各章节预算:")
    print("-" * 60)
    for ch in plan.chapters:
        print(f"  {ch.chapter_index}. {ch.chapter_title}: "
              f"{ch.original_chars:,} → {ch.budget_chars:,} 字 "
              f"(压缩比 {ch.compression_ratio:.1%})")


def test_strategies():
    """测试不同分配策略"""
    print("\n" + "=" * 60)
    print("测试 2: 不同分配策略对比")
    print("=" * 60)
    
    chapters = [
        {"index": 1, "title": "序章", "char_count": 500},
        {"index": 2, "title": "第1章", "char_count": 3000},
        {"index": 3, "title": "第2章", "char_count": 5000},
        {"index": 4, "title": "第3章", "char_count": 2000},
    ]
    
    strategies = ["uniform", "proportional", "weighted"]
    
    # 设置重要性分数（第2章最重要）
    importance_scores = {1: 0.3, 2: 1.0, 3: 0.6, 4: 0.4}
    
    for strategy in strategies:
        print(f"\n📊 策略: {strategy}")
        print("-" * 40)
        
        plan = calculate_budget(
            chapters,
            target_time_minutes=3,
            reading_speed=300,
            strategy=strategy,
            importance_scores=importance_scores if strategy == "weighted" else None
        )
        
        for ch in plan.chapters:
            bar = "█" * int(ch.budget_chars / 50)
            print(f"  第{ch.chapter_index}章: {ch.budget_chars:4d} 字 {bar}")
        
        print(f"  总计: {plan.total_budget_chars:,} 字")


def test_real_chapters():
    """使用真实章节数据测试"""
    print("\n" + "=" * 60)
    print("测试 3: 真实章节数据（前 20 章）")
    print("=" * 60)
    
    chapters_path = os.path.join(config.paths.output_dir, "chapters.json")
    
    if not os.path.exists(chapters_path):
        print(f"❌ 章节文件不存在: {chapters_path}")
        print("   请先运行 python -m tests.test_pipeline 生成章节数据")
        return
    
    chapters = load_chapters(chapters_path)
    
    # 只取前 20 章
    chapters = chapters[:20]
    
    total_chars = sum(ch.get("char_count", len(ch.get("text", ""))) for ch in chapters)
    print(f"前 20 章总字数: {total_chars:,} 字")
    print(f"原文阅读时间: {format_time(estimate_reading_time(total_chars))}")
    
    # 测试不同目标时间
    target_times = [5, 10, 15]
    
    for target in target_times:
        print(f"\n🎯 目标阅读时间: {target} 分钟")
        print("-" * 40)
        
        plan = calculate_budget(
            chapters,
            target_time_minutes=target,
            reading_speed=300,
            strategy="proportional"
        )
        
        # 只显示前 5 章
        for ch in plan.chapters[:5]:
            print(f"  {ch.chapter_index:2d}. {ch.chapter_title[:15]:<15}: "
                  f"{ch.original_chars:,} → {ch.budget_chars:,} 字")
        
        if len(plan.chapters) > 5:
            print(f"  ... 共 {len(plan.chapters)} 章")
        
        print(f"  整体压缩比: {plan.overall_compression_ratio:.1%}")
        print(f"  预算阅读时间: {format_time(estimate_reading_time(plan.total_budget_chars))}")


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("测试 4: 边界情况")
    print("=" * 60)
    
    # 空章节列表
    print("\n📋 空章节列表:")
    plan = calculate_budget([], target_time_minutes=10)
    print(f"  总预算: {plan.total_budget_chars} 字")
    
    # 单章节
    print("\n📋 单章节:")
    plan = calculate_budget(
        [{"index": 1, "title": "唯一章节", "char_count": 10000}],
        target_time_minutes=5
    )
    plan.print_summary()
    
    # 极短章节
    print("\n📋 极短章节（测试最小预算约束）:")
    plan = calculate_budget(
        [
            {"index": 1, "title": "短章1", "char_count": 100},
            {"index": 2, "title": "短章2", "char_count": 150},
        ],
        target_time_minutes=1
    )
    for ch in plan.chapters:
        print(f"  {ch.chapter_title}: {ch.budget_chars} 字 (原 {ch.original_chars} 字)")


def main():
    print("\n" + "🚀" * 20)
    print("   篇幅预算模块测试")
    print("🚀" * 20)
    
    test_basic_budget()
    test_strategies()
    test_real_chapters()
    test_edge_cases()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
