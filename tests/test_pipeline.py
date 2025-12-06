# tests/test_pipeline.py
"""
测试脚本：使用前 10 章进行测试

用法:
    python -m tests.test_pipeline
"""

import os
import sys
import json
import logging

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novel_speedy.config import config
from novel_speedy.chapter_splitter import load_chapters, save_chapters, ChapterSplitter
from novel_speedy.pipeline import process_chapters, save_results

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_chapter_splitter():
    """测试章节切分"""
    print("\n" + "=" * 60)
    print("测试 1: 章节切分")
    print("=" * 60)
    
    # 读取原始小说
    novel_path = os.path.join(config.paths.input_dir, "novel_dpcq.txt")
    
    if not os.path.exists(novel_path):
        print(f"❌ 小说文件不存在: {novel_path}")
        print(f"   请将小说文件放到 {config.paths.input_dir} 目录下")
        return None
    
    with open(novel_path, "r", encoding="utf-8") as f:
        novel_text = f.read()
    
    print(f"📖 小说总字数: {len(novel_text):,}")
    
    # 切分章节
    splitter = ChapterSplitter()
    chapters = splitter.split(novel_text)
    
    # 获取统计信息
    stats = splitter.get_stats(chapters)
    
    print(f"\n📊 章节统计:")
    print(f"   总章节数: {stats['total_chapters']}")
    print(f"   总字数: {stats['total_chars']:,}")
    print(f"   平均每章: {stats['avg_chars']:,} 字")
    print(f"   最短章节: {stats['min_chars']:,} 字")
    print(f"   最长章节: {stats['max_chars']:,} 字")
    
    # 显示前 10 章摘要
    print(f"\n📖 前 10 章摘要:")
    print("-" * 60)
    for ch in chapters[:10]:
        print(f"   {ch.index:4d}. {ch.title[:35]:<35} ({ch.char_count:,} 字)")
    
    # 保存切分结果
    output_path = os.path.join(config.paths.output_dir, "chapters.json")
    save_chapters(chapters, output_path)
    print(f"\n✅ 章节已保存到: {output_path}")
    
    return chapters[:10]  # 返回前 10 章用于后续测试


def test_scene_extraction(chapters: list):
    """测试场景提取（使用前 10 章）"""
    print("\n" + "=" * 60)
    print("测试 2: 场景提取 + 分组（前 10 章）")
    print("=" * 60)
    
    if not chapters:
        print("❌ 无章节数据")
        return
    
    # 转换为 dict 格式
    chapter_dicts = [ch.to_dict() if hasattr(ch, 'to_dict') else ch for ch in chapters]
    
    print(f"📚 即将处理 {len(chapter_dicts)} 个章节...")
    print("⚠️  这将调用 LLM API，可能需要几分钟时间")
    
    # 运行 pipeline
    groups = process_chapters(chapter_dicts)
    
    print(f"\n✅ 处理完成，共 {len(groups)} 个场景组")
    
    # 显示分组结果
    for group in groups:
        print(f"\n📁 组 {group['group_index']}:")
        print(f"   章节: {group['chapters']}")
        print(f"   场景数: {len(group['group_scenes'])}")
        print("   场景摘要:")
        for scene in group['group_scenes'][:5]:  # 只显示前 5 个场景
            summary = scene.get('summary', '无摘要')[:50]
            print(f"      - {summary}")
        if len(group['group_scenes']) > 5:
            print(f"      ... 共 {len(group['group_scenes'])} 个场景")
    
    # 保存结果
    output_path = os.path.join(config.paths.output_dir, "scenes.json")
    save_results(groups, output_path)
    print(f"\n✅ 场景已保存到: {output_path}")


def main():
    """主测试入口"""
    print("\n" + "🚀" * 20)
    print("   小说速读系统 - 功能测试")
    print("🚀" * 20)
    
    print(f"\n📁 项目目录: {config.paths.base_dir}")
    print(f"📁 输入目录: {config.paths.input_dir}")
    print(f"📁 输出目录: {config.paths.output_dir}")
    
    # 测试 1: 章节切分（不需要 LLM）
    chapters = test_chapter_splitter()
    
    if not chapters:
        print("\n❌ 章节切分失败，无法继续测试")
        return
    
    # 询问是否继续测试场景提取
    print("\n" + "-" * 60)
    user_input = input("是否测试场景提取？需要调用 LLM API (y/n): ").strip().lower()
    
    if user_input == 'y':
        test_scene_extraction(chapters)
    else:
        print("⏭️  跳过场景提取测试")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
