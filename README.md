# 小说速读系统 (Novel Speedy Reader)

[English](./README_EN.md) | 中文

一个基于 AI 的长篇小说速读版生成工具，可以将数十万字的网文小说压缩成几分钟内可读完的精华版本。

## ✨ 功能特性

### 核心功能

- **🔪 智能章节切分**：自动识别章节标题，将整本小说切分为独立章节
- **📊 高潮识别**：多维度评分（情节张力、情感冲击、爽点密度等）识别高潮章节
- **💰 智能预算分配**：根据章节重要性动态分配字数预算，高潮章节保留更多内容
- **📝 大纲生成**：自动分析小说结构，生成层级大纲
- **🗜️ 多策略压缩**：
  - **保留式**：保留原文精彩段落，删除冗余
  - **重写式**：提取核心情节，重新组织语言
  - **摘要式**：纯 LLM 生成剧情摘要
- **✅ 质量自检（插件系统）**：
  - **完整性检查**：检测句子截断、对话不完整等问题
  - **连贯性检查**：检测上下章节逻辑断层，自动修复

### 输出选项

- **输出模式**：按章节输出 / 整体连贯输出
- **输出格式**：Markdown / TXT / JSON
- **风格定制**：
  - 默认风格（简洁流畅）
  - 评书风格（节奏感强）
  - 古文风格（文言典雅）
  - 幽默风格（诙谐吐槽）
  - 戏剧化风格（情绪饱满）
  - 极简风格（电报式精炼）
  - 讲故事风格（口语化亲切）

### Web 界面

- 🖥️ 现代化 React + TypeScript 前端
- 📁 拖拽上传小说文件
- ⏱️ 自定义阅读时间预算
- 📈 实时处理进度显示
- 📥 一键下载结果

## 📁 目录结构

```
novel-speedy-handler/
├── novel_speedy/              # 后端主包
│   ├── api/                   # FastAPI 接口
│   │   └── app.py
│   ├── speedy/                # 速读核心模块
│   │   ├── generator.py       # 速读生成器（主流程）
│   │   ├── budget_calculator.py # 预算分配
│   │   ├── outline_generator.py # 大纲生成
│   │   ├── compressor.py      # 章节压缩
│   │   └── quality_plugins.py # 质量自检插件
│   ├── climax/                # 高潮识别模块
│   ├── chapter_splitter.py    # 章节切分
│   ├── llm_client.py          # LLM 客户端
│   └── config.py              # 配置管理
├── client/                    # React 前端
│   ├── src/
│   │   └── App.tsx
│   └── package.json
├── run_api.py                 # 启动后端服务
├── requirements.txt
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/y805939188/novel-speedy-handler.git
cd novel-speedy-handler

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd client
pnpm install
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
LLM_API_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4o-mini
```

### 3. 启动服务

```bash
# 终端 1：启动后端
python run_api.py

# 终端 2：启动前端
cd client
pnpm dev
```

访问 http://localhost:5173 使用 Web 界面。

## 📖 使用方法

### Web 界面使用

1. 打开浏览器访问 http://localhost:5173
2. 上传小说 TXT 文件（或粘贴文本）
3. 设置目标阅读时间（如 30 分钟）
4. 选择风格、输出模式等高级选项
5. 点击"开始生成"
6. 等待处理完成后下载结果

### API 调用

```bash
# 启动处理任务
curl -X POST http://localhost:8000/start-task \
  -F "file=@novel.txt" \
  -F "target_reading_time=30" \
  -F "style=default"

# 查询状态
curl http://localhost:8000/status/{task_id}

# 下载结果
curl http://localhost:8000/download/{task_id}
```

### 代码调用

```python
from novel_speedy.speedy import generate_speedy
from novel_speedy.chapter_splitter import ChapterSplitter

# 读取并切分章节
with open("novel.txt", "r", encoding="utf-8") as f:
    text = f.read()

splitter = ChapterSplitter()
chapters = [ch.to_dict() for ch in splitter.split(text)]

# 生成速读版
result = generate_speedy(
    chapters=chapters,
    target_reading_time=30.0,  # 30 分钟
    style="default",
    output_mode="continuous",  # 整体连贯输出
    enable_quality_check=True  # 启用质检
)

print(result["content"])
```

## ⚙️ 配置选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `target_reading_time` | 目标阅读时间（分钟） | 30 |
| `reading_speed` | 阅读速度（字/分钟） | 300 |
| `style` | 输出风格 | "default" |
| `output_mode` | 输出模式 (chapter/continuous) | "chapter" |
| `output_format` | 输出格式 (markdown/txt/json) | "markdown" |
| `enable_quality_check` | 启用质量自检 | true |

## 🔧 质量自检系统

质量自检采用插件架构，串行执行：

```
压缩章节 → 完整性检查 → 连贯性检查 → 完成
              ↓              ↓
         失败: 1.1x 预算重试   失败: 1.2x 预算重新生成上一章
```

- **完整性检查**：检测句子截断、对话引号不匹配、内容突然结束等
- **连贯性检查**：检测上下章节逻辑断层，如"当前章提到战斗结束，但上一章没有战斗"

最多重试 3 次，额外预算不计入总预算。

## 📊 处理流程

```
小说原文
    ↓
┌─────────────────┐
│ 1. 章节切分     │  自动识别章节标题
└─────────────────┘
    ↓
┌─────────────────┐
│ 2. 高潮识别     │  多维度评分
└─────────────────┘
    ↓
┌─────────────────┐
│ 3. 预算分配     │  根据重要性分配字数
└─────────────────┘
    ↓
┌─────────────────┐
│ 4. 大纲生成     │  分析结构，生成大纲
└─────────────────┘
    ↓
┌─────────────────┐
│ 5. 逐章压缩     │  保留/重写/摘要
└─────────────────┘
    ↓
┌─────────────────┐
│ 6. 质量自检     │  完整性 + 连贯性
└─────────────────┘
    ↓
速读版输出
```

## 📝 示例

**输入**：27,739 字小说（10 章）

**输出**：1,687 字速读版，预计阅读 5.6 分钟

**压缩比**：约 6%

## 🛠️ 技术栈

- **后端**：Python, FastAPI, asyncio
- **前端**：React, TypeScript, Vite, TailwindCSS
- **LLM**：OpenAI API 兼容接口

## 📄 License

MIT
