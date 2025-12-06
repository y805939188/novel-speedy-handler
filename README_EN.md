# Novel Speedy Reader

[中文](./README.md) | English

An AI-powered tool for generating speed-reading versions of long novels, compressing hundreds of thousands of words into a concise version readable in minutes.

## ✨ Features

### Core Features

- **🔪 Smart Chapter Splitting**: Automatically identify chapter titles and split novels into independent chapters
- **📊 Climax Detection**: Multi-dimensional scoring (plot tension, emotional impact, satisfaction points, etc.) to identify climax chapters
- **💰 Smart Budget Allocation**: Dynamically allocate word budgets based on chapter importance, preserving more content for climax chapters
- **📝 Outline Generation**: Automatically analyze novel structure and generate hierarchical outlines
- **🗜️ Multi-Strategy Compression**:
  - **Preserve Mode**: Keep original brilliant paragraphs, remove redundancy
  - **Rewrite Mode**: Extract core plot, reorganize language
  - **Summarize Mode**: Pure LLM-generated plot summary
- **✅ Quality Check (Plugin System)**:
  - **Completeness Check**: Detect truncated sentences, incomplete dialogues, etc.
  - **Coherence Check**: Detect logical gaps between chapters, auto-fix

### Output Options

- **Output Mode**: By chapter / Continuous flow
- **Output Format**: Markdown / TXT / JSON
- **Style Customization**:
  - Default (concise and smooth)
  - Pingshu (Chinese storytelling style, rhythmic)
  - Ancient (classical Chinese style, elegant)
  - Humor (witty and sarcastic)
  - Dramatic (emotionally intense)
  - Minimalist (telegram-style concise)
  - Storytelling (casual, friendly)

### Web Interface

- 🖥️ Modern React + TypeScript frontend
- 📁 Drag-and-drop file upload
- ⏱️ Custom reading time budget
- 📈 Real-time processing progress
- 📥 One-click download results

## 📁 Project Structure

```
novel-speedy-handler/
├── novel_speedy/              # Backend main package
│   ├── api/                   # FastAPI endpoints
│   │   └── app.py
│   ├── speedy/                # Speed-reading core modules
│   │   ├── generator.py       # Speed-reading generator (main flow)
│   │   ├── budget_calculator.py # Budget allocation
│   │   ├── outline_generator.py # Outline generation
│   │   ├── compressor.py      # Chapter compression
│   │   └── quality_plugins.py # Quality check plugins
│   ├── climax/                # Climax detection module
│   ├── chapter_splitter.py    # Chapter splitting
│   ├── llm_client.py          # LLM client
│   └── config.py              # Configuration
├── client/                    # React frontend
│   ├── src/
│   │   └── App.tsx
│   └── package.json
├── run_api.py                 # Start backend service
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Clone the project
git clone https://github.com/y805939188/novel-speedy-handler.git
cd novel-speedy-handler

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd client
pnpm install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit the `.env` file:

```env
LLM_API_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=your-api-key
LLM_MODEL=your-model(I used the Qwen series for my own testing and cannot guarantee compatibility with the output formats of other series models. If necessary, you can modify the code yourself for adaptation)
```

### 3. Start Services

```bash
# Terminal 1: Start backend
python run_api.py

# Terminal 2: Start frontend
cd client
pnpm dev
```

Visit http://localhost:8888 to use the Web interface.

## 📖 Usage

### Web Interface

1. Open browser and visit http://localhost:8888
2. Upload a novel TXT file (or paste text)
3. Set target reading time (e.g., 30 minutes)
4. Choose style, output mode, and other advanced options
5. Click "Start Generation"
6. Download results when processing is complete

### API Calls

```bash
# Start processing task
curl -X POST http://localhost:8000/start-task \
  -F "file=@novel.txt" \
  -F "target_reading_time=30" \
  -F "style=default"

# Check status
curl http://localhost:8000/status/{task_id}

# Download result
curl http://localhost:8000/download/{task_id}
```

### Code Usage

```python
from novel_speedy.speedy import generate_speedy
from novel_speedy.chapter_splitter import ChapterSplitter

# Read and split chapters
with open("novel.txt", "r", encoding="utf-8") as f:
    text = f.read()

splitter = ChapterSplitter()
chapters = [ch.to_dict() for ch in splitter.split(text)]

# Generate speed-reading version
result = generate_speedy(
    chapters=chapters,
    target_reading_time=30.0,  # 30 minutes
    style="default",
    output_mode="continuous",  # Continuous output
    enable_quality_check=True  # Enable quality check
)

print(result["content"])
```

## ⚙️ Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `target_reading_time` | Target reading time (minutes) | 30 |
| `reading_speed` | Reading speed (chars/min) | 300 |
| `style` | Output style | "default" |
| `output_mode` | Output mode (chapter/continuous) | "chapter" |
| `output_format` | Output format (markdown/txt/json) | "markdown" |
| `enable_quality_check` | Enable quality check | true |

## 🔧 Quality Check System

Quality check uses a plugin architecture, executed serially:

```
Compress Chapter → Completeness Check → Coherence Check → Done
                         ↓                    ↓
                   Fail: 1.1x budget retry    Fail: 1.2x budget regenerate previous chapter
```

- **Completeness Check**: Detect truncated sentences, mismatched quotation marks, abrupt endings, etc.
- **Coherence Check**: Detect logical gaps between chapters, e.g., "current chapter mentions battle ended, but previous chapter had no battle"

Maximum 3 retries, extra budget is not counted towards total budget.

## 📊 Processing Flow

```
Novel Text
    ↓
┌─────────────────┐
│ 1. Chapter Split│  Auto-detect chapter titles
└─────────────────┘
    ↓
┌─────────────────┐
│ 2. Climax Detect│  Multi-dimensional scoring
└─────────────────┘
    ↓
┌─────────────────┐
│ 3. Budget Alloc │  Allocate by importance
└─────────────────┘
    ↓
┌─────────────────┐
│ 4. Outline Gen  │  Analyze structure
└─────────────────┘
    ↓
┌─────────────────┐
│ 5. Compression  │  Preserve/Rewrite/Summarize
└─────────────────┘
    ↓
┌─────────────────┐
│ 6. Quality Check│  Completeness + Coherence
└─────────────────┘
    ↓
Speed-Reading Output
```

## 📝 Example

**Input**: 27,739 characters novel (10 chapters)

**Output**: 1,687 characters speed-reading version, ~5.6 minutes read time

**Compression Ratio**: ~6%

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, asyncio
- **Frontend**: React, TypeScript, Vite, TailwindCSS
- **LLM**: OpenAI API compatible interface

## 📄 License

MIT
