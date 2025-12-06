# 小说速读系统 (Novel Speedy Reader)

一个基于 AI 的长篇小说速读生成工具。

## 功能特性

- **章节切分**：自动识别章节标题，将整本小说切分为独立章节
- **场景提取**：使用 LLM 从每章提取关键场景
- **场景分组**：自动识别连续剧情，将相关章节分组
- **（开发中）高潮识别**：多维度评分识别小说高潮段落
- **（开发中）人物评分**：自动评估角色重要性
- **（开发中）速读生成**：根据时间预算生成小说速读版本

## 目录结构

```
novel-speedy-handler/
├── novel_speedy/           # 主包
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── chapter_splitter.py # 章节切分
│   ├── scene_extractor.py  # 场景提取
│   ├── scene_grouping.py   # 场景分组
│   ├── llm_client.py       # LLM 客户端
│   ├── utils.py            # 工具函数
│   └── pipeline.py         # 主流程
├── tests/                  # 测试目录
│   └── test_pipeline.py
├── data/                   # 数据目录
│   ├── input/              # 输入文件（小说原文）
│   └── output/             # 输出文件（处理结果）
├── requirements.txt
├── README.md
└── .gitignore
```

## 安装

```bash
# 克隆项目
git clone <repo_url>
cd novel-speedy-handler

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 1. 准备小说文件

将小说 txt 文件放到 `data/input/` 目录下，例如：
```
data/input/novel_dpcq.txt
```

### 2. 运行测试

```bash
# 运行完整测试（章节切分 + 场景提取）
python -m tests.test_pipeline
```

### 3. 单独使用章节切分

```bash
# 命令行方式
python -m novel_speedy.chapter_splitter data/input/novel_dpcq.txt data/output/chapters.json
```

### 4. 代码中使用

```python
from novel_speedy import (
    ChapterSplitter, 
    load_chapters, 
    process_chapters,
    config
)

# 读取小说
with open("data/input/novel.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 切分章节
splitter = ChapterSplitter()
chapters = splitter.split(text)

# 获取前 10 章进行处理
chapter_dicts = [ch.to_dict() for ch in chapters[:10]]

# 提取场景并分组
groups = process_chapters(chapter_dicts)

print(f"共 {len(groups)} 个场景组")
```

## 配置

可以在代码中修改配置：

```python
from novel_speedy.config import config, update_llm_config

# 修改 LLM API 地址
update_llm_config(api_url="https://your-api.com/v1/chat/completions")

# 修改模型
update_llm_config(model="gpt-4")

# 查看当前配置
print(config.llm.api_url)
print(config.paths.output_dir)
```

## 开发进度

- [x] 项目结构重构
- [x] 章节切分模块
- [x] 场景提取模块
- [x] 场景分组模块
- [ ] 篇幅预算模块
- [ ] 高潮识别插件系统
- [ ] 人物 CVS 评分系统
- [ ] 速读版生成模块
- [ ] 全书整合与润色

## License

MIT
