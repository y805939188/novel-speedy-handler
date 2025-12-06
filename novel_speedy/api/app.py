"""FastAPI 速读生成器 API"""

import os
import uuid
import asyncio
import time
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from novel_speedy.chapter_splitter import ChapterSplitter
from novel_speedy.climax import ClimaxAnalyzer
from novel_speedy.speedy import generate_speedy, STYLE_PRESETS

# 配置 rich 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)]
)
logger = logging.getLogger("novel_speedy.api")
console = Console()


# 目录配置
BASE_DIR = Path(__file__).parent.parent.parent
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"

# 确保目录存在
INPUTS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="小说速读生成器 API",
        description="将长篇小说压缩为速读版本的 API 服务",
        version="1.0.0",
    )
    return app


app = create_app()


# ==================== 数据模型 ====================

class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    filename: str
    status: str  # pending, processing, completed, failed
    message: Optional[str] = None
    created_at: str
    download_url: Optional[str] = None


class TaskCreateResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    message: str
    status_url: str


class AvailableStylesResponse(BaseModel):
    """可用风格列表"""
    styles: dict


class AnalyzeResponse(BaseModel):
    """文件分析响应"""
    file_id: str
    filename: str
    total_chapters: int
    total_chars: int
    chapters_preview: list  # 前几章的标题预览
    recommended_reading_time: float  # 推荐最低阅读时间（分钟）
    message: str


class RecommendationRequest(BaseModel):
    """计算推荐值请求"""
    file_id: str
    reading_speed: int = 300
    max_chapters: Optional[int] = None
    min_chars_per_chapter: int = 100


class RecommendationResponse(BaseModel):
    """推荐值响应"""
    recommended_reading_time: float  # 推荐最低阅读时间（分钟）
    total_budget_chars: int  # 对应的总字数
    effective_chapters: int  # 实际处理的章节数
    effective_chars: int  # 实际处理的总字数


# ==================== 辅助函数 ====================

def get_task_status(task_id: str) -> str:
    """获取任务状态"""
    wip_file = OUTPUTS_DIR / f"{task_id}.working_in_progress"
    ok_file = OUTPUTS_DIR / f"{task_id}.ok"
    result_file = OUTPUTS_DIR / f"{task_id}.txt"
    
    if ok_file.exists() and result_file.exists():
        return "completed"
    elif wip_file.exists():
        return "processing"
    elif (INPUTS_DIR / f"{task_id}.txt").exists():
        return "pending"
    else:
        return "not_found"


def mark_processing(task_id: str):
    """标记任务为处理中"""
    wip_file = OUTPUTS_DIR / f"{task_id}.working_in_progress"
    wip_file.touch()


def mark_completed(task_id: str):
    """标记任务为已完成"""
    wip_file = OUTPUTS_DIR / f"{task_id}.working_in_progress"
    ok_file = OUTPUTS_DIR / f"{task_id}.ok"
    
    # 删除 working_in_progress 文件
    if wip_file.exists():
        wip_file.unlink()
    
    # 创建 ok 文件
    ok_file.touch()


def mark_failed(task_id: str, error: str):
    """标记任务为失败"""
    wip_file = OUTPUTS_DIR / f"{task_id}.working_in_progress"
    error_file = OUTPUTS_DIR / f"{task_id}.error"
    
    # 删除 working_in_progress 文件
    if wip_file.exists():
        wip_file.unlink()
    
    # 写入错误信息
    with open(error_file, 'w', encoding='utf-8') as f:
        f.write(error)


async def process_novel(
    task_id: str,
    reading_speed: int,
    target_reading_time: float,
    style: Optional[str],
    output_mode: str,
    max_chapters: Optional[int],
    enable_climax_analysis: bool = True,
    enable_quality_check: bool = True
):
    """后台处理小说"""
    start_time = time.time()
    
    try:
        mark_processing(task_id)
        
        input_file = INPUTS_DIR / f"{task_id}.txt"
        output_file = OUTPUTS_DIR / f"{task_id}.txt"
        
        # ============ Step 1: 读取小说 ============
        console.print()
        console.rule(f"[bold blue]📚 开始处理任务: {task_id[:20]}...[/bold blue]")
        total_steps = 5 if enable_climax_analysis else 4
        logger.info(f"[bold cyan]Step 1/{total_steps}[/bold cyan] 📖 读取小说文件...")
        
        step_start = time.time()
        with open(input_file, 'r', encoding='utf-8') as f:
            novel_text = f.read()
        
        file_size = len(novel_text)
        logger.info(f"   ✅ 文件大小: [green]{file_size:,}[/green] 字符 ({file_size/1024:.1f} KB)")
        logger.info(f"   ⏱️  耗时: {time.time() - step_start:.2f}s")
        
        # ============ Step 2: 分割章节 ============
        logger.info(f"[bold cyan]Step 2/{total_steps}[/bold cyan] ✂️  分割章节...")
        step_start = time.time()
        
        splitter = ChapterSplitter()
        chapter_objs = splitter.split(novel_text)
        
        # 转换为字典格式
        chapters = [
            {
                "index": ch.index,
                "title": ch.title,
                "text": ch.text,
            }
            for ch in chapter_objs
        ]
        
        if not chapters:
            raise ValueError("无法识别章节，请检查小说格式")
        
        total_chapters = len(chapters)
        logger.info(f"   ✅ 识别到 [green]{total_chapters}[/green] 个章节")
        
        # 限制章节数量
        if max_chapters and max_chapters > 0:
            chapters = chapters[:max_chapters]
            logger.info(f"   📋 限制处理前 [yellow]{max_chapters}[/yellow] 章")
        
        total_chars = sum(len(ch.get("text", "")) for ch in chapters)
        logger.info(f"   📊 原文总字数: [green]{total_chars:,}[/green] 字")
        logger.info(f"   ⏱️  耗时: {time.time() - step_start:.2f}s")
        
        # 获取书名
        book_title = "未命名小说"
        if chapters and chapters[0].get("title"):
            first_title = chapters[0]["title"]
            if "序" not in first_title and "楔子" not in first_title:
                book_title = first_title.split()[0] if first_title else "未命名小说"
        
        # ============ Step 3: 高潮评分（可选） ============
        climax_scores = None
        current_step = 3
        
        if enable_climax_analysis:
            logger.info(f"[bold cyan]Step {current_step}/{total_steps}[/bold cyan] 🔥 分析高潮评分...")
            step_start = time.time()
            
            # 预估时间
            estimated_climax_time = len(chapters) * 2.5
            logger.info(f"   ⏳ 预计耗时: [yellow]{estimated_climax_time/60:.1f}[/yellow] 分钟 ({len(chapters)} 章 × ~2.5s)")
            
            try:
                analyzer = ClimaxAnalyzer()
                climax_scores = analyzer.analyze_chapters(chapters)
                
                # 统计高潮章节数量
                high_climax_count = sum(1 for s in climax_scores if s.get("final_score", 0) >= 0.6)
                logger.info(f"   ✅ 高潮评分完成 | 高潮章节: [green]{high_climax_count}[/green] / {len(chapters)}")
                logger.info(f"   ⏱️  耗时: {time.time() - step_start:.1f}s")
            except Exception as e:
                logger.warning(f"   ⚠️ 高潮评分失败: {str(e)}，将使用均匀分配")
                climax_scores = None
            
            current_step += 1
        else:
            logger.info(f"   ⏭️  跳过高潮评分（已禁用）")
        
        # ============ Step 4: 生成速读版 ============
        target_chars = int(target_reading_time * reading_speed)
        logger.info(f"[bold cyan]Step {current_step}/{total_steps}[/bold cyan] ✨ 生成速读版...")
        logger.info(f"   🎯 目标: {target_reading_time:.0f} 分钟 × {reading_speed} 字/分 = [yellow]{target_chars:,}[/yellow] 字")
        logger.info(f"   📉 压缩比: [yellow]{target_chars/total_chars*100:.1f}%[/yellow]")
        if style:
            logger.info(f"   🎭 风格: [magenta]{style}[/magenta]")
        logger.info(f"   📋 模式: [blue]{output_mode}[/blue]")
        if climax_scores:
            logger.info(f"   🔥 高潮评分: [green]已启用[/green]")
        else:
            logger.info(f"   🔥 高潮评分: [yellow]未启用（按章节长度分配预算）[/yellow]")
        
        step_start = time.time()
        
        # 预估处理时间（约 2.5-3 秒/章）
        estimated_time = len(chapters) * 2.8
        logger.info(f"   ⏳ 预计耗时: [yellow]{estimated_time/60:.1f}[/yellow] 分钟 ({len(chapters)} 章 × ~2.8s)")
        console.print()
        
        # 生成速读版
        result = generate_speedy(
            chapters=chapters,
            climax_scores=climax_scores,
            book_title=book_title,
            target_reading_time=target_reading_time,
            reading_speed=reading_speed,
            output_format="txt",
            output_mode=output_mode,
            style=style,
            enable_quality_check=enable_quality_check
        )
        
        step_elapsed = time.time() - step_start
        logger.info(f"   ✅ 生成完成! 实际耗时: [green]{step_elapsed:.1f}s[/green] ({step_elapsed/len(chapters):.2f}s/章)")
        
        current_step += 1
        
        # ============ Step 5: 保存结果 ============
        logger.info(f"[bold cyan]Step {current_step}/{total_steps}[/bold cyan] 💾 保存结果...")
        step_start = time.time()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.to_txt())
        
        output_size = output_file.stat().st_size
        logger.info(f"   ✅ 输出文件: {output_file.name} ({output_size/1024:.1f} KB)")
        logger.info(f"   ⏱️  耗时: {time.time() - step_start:.2f}s")
        
        mark_completed(task_id)
        
        # ============ 完成汇总 ============
        total_elapsed = time.time() - start_time
        console.print()
        console.rule("[bold green]✅ 处理完成[/bold green]")
        console.print(f"   📚 书名: [bold]{book_title}[/bold]")
        console.print(f"   📊 原文: [cyan]{total_chars:,}[/cyan] 字 → 速读版: [green]{result.total_compressed_chars:,}[/green] 字")
        console.print(f"   📖 预计阅读: [yellow]{result.reading_time_minutes:.1f}[/yellow] 分钟")
        console.print(f"   ⏱️  总耗时: [bold green]{total_elapsed:.1f}[/bold green] 秒")
        console.print()
        
    except Exception as e:
        elapsed = time.time() - start_time
        console.print()
        console.rule("[bold red]❌ 处理失败[/bold red]")
        logger.error(f"   错误: {str(e)}")
        logger.error(f"   已耗时: {elapsed:.1f}s")
        console.print()
        mark_failed(task_id, str(e))
        raise


# ==================== API 接口 ====================

@app.get("/", tags=["基础"])
async def root():
    """API 根路径"""
    return {
        "name": "小说速读生成器 API",
        "version": "1.1.0",
        "endpoints": {
            "分析小说": "POST /analyze",
            "计算推荐值": "POST /calculate-recommendation",
            "开始任务": "POST /start-task",
            "上传并处理（旧接口）": "POST /upload",
            "查询状态": "GET /status/{task_id}",
            "下载结果": "GET /download/{task_id}",
            "可用风格": "GET /styles",
        }
    }


@app.get("/styles", response_model=AvailableStylesResponse, tags=["配置"])
async def get_styles():
    """获取可用的风格预设"""
    return AvailableStylesResponse(
        styles={
            "default": "普通白话文，简洁流畅",
            **STYLE_PRESETS
        }
    )


@app.post("/analyze", response_model=AnalyzeResponse, tags=["核心"])
async def analyze_novel(
    file: UploadFile = File(..., description="小说 TXT 文件"),
    reading_speed: int = Form(default=300, ge=100, le=1000, description="阅读速度（字/分钟）"),
    min_chars_per_chapter: int = Form(default=100, ge=50, le=500, description="每章最少字数")
):
    """
    分析小说文件，进行章节切分，返回分析结果和推荐配置
    
    - **file**: 小说 TXT 文件（必传）
    - **reading_speed**: 阅读速度，用于计算推荐阅读时间（默认 300）
    - **min_chars_per_chapter**: 每章最少字数（默认 100）
    """
    # 验证文件类型
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="仅支持 TXT 文件")
    
    # 生成文件 ID
    file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # 读取文件内容
    try:
        content = await file.read()
        # 尝试多种编码
        novel_text = None
        for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                novel_text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if novel_text is None:
            raise HTTPException(status_code=400, detail="无法识别文件编码，请使用 UTF-8 或 GBK 编码")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {str(e)}")
    
    # 保存文件
    input_file = INPUTS_DIR / f"{file_id}.txt"
    with open(input_file, 'w', encoding='utf-8') as f:
        f.write(novel_text)
    
    # 进行章节切分
    try:
        splitter = ChapterSplitter()
        chapter_objs = splitter.split(novel_text)
        
        if not chapter_objs:
            raise HTTPException(
                status_code=400, 
                detail="无法识别章节，请检查小说格式。支持的格式：第X章、第X回、Chapter X 等"
            )
        
        # 计算统计信息
        total_chapters = len(chapter_objs)
        total_chars = sum(len(ch.text) for ch in chapter_objs)
        
        # 章节预览（前5章）
        chapters_preview = [
            {"index": ch.index, "title": ch.title, "chars": len(ch.text)}
            for ch in chapter_objs[:5]
        ]
        
        # 计算推荐最低阅读时间
        # 公式：章节数 × 每章最少字数 / 阅读速度
        min_budget = total_chapters * min_chars_per_chapter
        recommended_time = min_budget / reading_speed
        # 向上取整到 0.5 分钟
        recommended_time = max(1.0, round(recommended_time * 2) / 2)
        
        # 保存分析结果到元数据文件
        meta_file = INPUTS_DIR / f"{file_id}.meta.json"
        import json
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump({
                "filename": file.filename,
                "total_chapters": total_chapters,
                "total_chars": total_chars,
                "chapters": [
                    {"index": ch.index, "title": ch.title, "chars": len(ch.text)}
                    for ch in chapter_objs
                ]
            }, f, ensure_ascii=False, indent=2)
        
        return AnalyzeResponse(
            file_id=file_id,
            filename=file.filename,
            total_chapters=total_chapters,
            total_chars=total_chars,
            chapters_preview=chapters_preview,
            recommended_reading_time=recommended_time,
            message=f"成功识别 {total_chapters} 章，共 {total_chars:,} 字"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"章节切分失败: {str(e)}")
        raise HTTPException(status_code=400, detail=f"章节切分失败: {str(e)}")


@app.post("/calculate-recommendation", response_model=RecommendationResponse, tags=["配置"])
async def calculate_recommendation(request: RecommendationRequest):
    """
    根据配置重新计算推荐阅读时间
    
    当用户修改阅读速度、处理章节数等配置时调用
    """
    # 读取元数据文件
    meta_file = INPUTS_DIR / f"{request.file_id}.meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="文件不存在，请重新上传")
    
    import json
    with open(meta_file, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    chapters = meta.get("chapters", [])
    
    # 限制章节数
    if request.max_chapters and request.max_chapters > 0:
        chapters = chapters[:request.max_chapters]
    
    effective_chapters = len(chapters)
    effective_chars = sum(ch.get("chars", 0) for ch in chapters)
    
    # 计算推荐最低阅读时间
    min_budget = effective_chapters * request.min_chars_per_chapter
    recommended_time = min_budget / request.reading_speed
    # 向上取整到 0.5 分钟
    recommended_time = max(1.0, round(recommended_time * 2) / 2)
    
    return RecommendationResponse(
        recommended_reading_time=recommended_time,
        total_budget_chars=min_budget,
        effective_chapters=effective_chapters,
        effective_chars=effective_chars
    )


@app.post("/start-task", response_model=TaskCreateResponse, tags=["核心"])
async def start_task(
    background_tasks: BackgroundTasks,
    file_id: str = Form(..., description="analyze 接口返回的 file_id"),
    reading_speed: int = Form(..., ge=100, le=1000, description="阅读速度（字/分钟）"),
    target_reading_time: float = Form(..., ge=1, le=600, description="目标阅读时间（分钟）"),
    style: Optional[str] = Form(default=None, description="输出风格"),
    output_mode: str = Form(default="continuous", description="输出模式：chapter/continuous"),
    max_chapters: Optional[int] = Form(default=None, ge=1, description="仅处理前 N 章"),
    enable_climax_analysis: bool = Form(default=True, description="是否启用高潮评分（默认开启，会增加处理时间）"),
    enable_quality_check: bool = Form(default=True, description="是否启用质量自检（默认开启，检测摘要是否完整）")
):
    """
    使用已分析的文件创建速读任务
    
    - **file_id**: analyze 接口返回的文件 ID（必传）
    - **enable_climax_analysis**: 是否启用高潮评分（默认开启）
    - **enable_quality_check**: 是否启用质量自检（默认开启）
    - 其他参数与 upload 接口相同
    """
    # 验证文件存在
    input_file = INPUTS_DIR / f"{file_id}.txt"
    if not input_file.exists():
        raise HTTPException(status_code=404, detail="文件不存在，请重新上传分析")
    
    # 验证输出模式
    if output_mode not in ["chapter", "continuous"]:
        raise HTTPException(status_code=400, detail="output_mode 必须是 chapter 或 continuous")
    
    # 使用 file_id 作为 task_id
    task_id = file_id
    
    # 添加后台任务
    background_tasks.add_task(
        process_novel,
        task_id=task_id,
        reading_speed=reading_speed,
        target_reading_time=target_reading_time,
        style=style,
        output_mode=output_mode,
        max_chapters=max_chapters,
        enable_climax_analysis=enable_climax_analysis,
        enable_quality_check=enable_quality_check
    )
    
    return TaskCreateResponse(
        task_id=task_id,
        message="任务已创建，正在后台处理",
        status_url=f"/status/{task_id}"
    )


@app.post("/upload", response_model=TaskCreateResponse, tags=["核心"])
async def upload_novel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="小说 TXT 文件"),
    reading_speed: int = Form(..., ge=100, le=1000, description="阅读速度（字/分钟），范围 100-1000"),
    target_reading_time: float = Form(..., ge=1, le=600, description="目标阅读时间（分钟），范围 1-600"),
    style: Optional[str] = Form(default=None, description="输出风格：pingshu/ancient/humor/dramatic/minimalist/storytelling 或自定义描述"),
    output_mode: str = Form(default="continuous", description="输出模式：chapter(按章节) / continuous(整体连贯)"),
    max_chapters: Optional[int] = Form(default=None, ge=1, description="仅处理前 N 章，留空表示全部")
):
    """
    上传小说并创建速读任务
    
    - **file**: 小说 TXT 文件（必传）
    - **reading_speed**: 阅读速度，字/分钟（必传，100-1000）
    - **target_reading_time**: 目标阅读时间，分钟（必传，1-600）
    - **style**: 输出风格（可选，默认普通白话文）
    - **output_mode**: 输出模式（可选，默认 continuous）
    - **max_chapters**: 仅处理前 N 章（可选，默认全部）
    """
    # 验证文件类型
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="仅支持 TXT 文件")
    
    # 验证输出模式
    if output_mode not in ["chapter", "continuous"]:
        raise HTTPException(status_code=400, detail="output_mode 必须是 chapter 或 continuous")
    
    # 生成任务 ID
    task_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # 保存上传文件
    input_file = INPUTS_DIR / f"{task_id}.txt"
    content = await file.read()
    
    try:
        # 尝试 UTF-8 解码
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            # 尝试 GBK 解码
            text = content.decode('gbk')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件编码不支持，请使用 UTF-8 或 GBK 编码")
    
    with open(input_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    # 启动后台任务
    background_tasks.add_task(
        process_novel,
        task_id=task_id,
        reading_speed=reading_speed,
        target_reading_time=target_reading_time,
        style=style,
        output_mode=output_mode,
        max_chapters=max_chapters
    )
    
    return TaskCreateResponse(
        task_id=task_id,
        message="任务已创建，正在后台处理",
        status_url=f"/status/{task_id}"
    )


@app.get("/status/{task_id}", response_model=TaskStatus, tags=["核心"])
async def get_task_status_api(task_id: str):
    """
    查询任务状态
    
    - **task_id**: 任务 ID
    """
    status = get_task_status(task_id)
    
    if status == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 获取原始文件名（如果有）
    input_file = INPUTS_DIR / f"{task_id}.txt"
    filename = f"{task_id}.txt"
    
    # 构建响应
    response = TaskStatus(
        task_id=task_id,
        filename=filename,
        status=status,
        created_at=task_id.split('_')[0] if '_' in task_id else "unknown"
    )
    
    if status == "completed":
        response.message = "处理完成，可以下载"
        response.download_url = f"/download/{task_id}"
    elif status == "processing":
        response.message = "正在处理中，请稍候..."
    elif status == "pending":
        response.message = "任务排队中"
    
    # 检查是否有错误
    error_file = OUTPUTS_DIR / f"{task_id}.error"
    if error_file.exists():
        response.status = "failed"
        with open(error_file, 'r', encoding='utf-8') as f:
            response.message = f"处理失败: {f.read()}"
    
    return response


@app.get("/download/{task_id}", tags=["核心"])
async def download_result(task_id: str):
    """
    下载处理结果
    
    - **task_id**: 任务 ID
    
    注意：只有状态为 completed 的任务才能下载
    """
    # 检查 .ok 文件是否存在
    ok_file = OUTPUTS_DIR / f"{task_id}.ok"
    result_file = OUTPUTS_DIR / f"{task_id}.txt"
    
    if not ok_file.exists():
        raise HTTPException(status_code=400, detail="任务尚未完成或不存在")
    
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    
    return FileResponse(
        path=result_file,
        filename=f"{task_id}_speedy.txt",
        media_type="text/plain; charset=utf-8"
    )


@app.get("/tasks", tags=["管理"])
async def list_tasks():
    """列出所有任务"""
    tasks = []
    
    # 遍历 inputs 目录
    for input_file in INPUTS_DIR.glob("*.txt"):
        task_id = input_file.stem
        status = get_task_status(task_id)
        
        tasks.append({
            "task_id": task_id,
            "status": status,
            "download_url": f"/download/{task_id}" if status == "completed" else None
        })
    
    return {"tasks": tasks, "total": len(tasks)}


@app.delete("/tasks/{task_id}", tags=["管理"])
async def delete_task(task_id: str):
    """删除任务及相关文件"""
    files_to_delete = [
        INPUTS_DIR / f"{task_id}.txt",
        OUTPUTS_DIR / f"{task_id}.txt",
        OUTPUTS_DIR / f"{task_id}.ok",
        OUTPUTS_DIR / f"{task_id}.working_in_progress",
        OUTPUTS_DIR / f"{task_id}.error",
    ]
    
    deleted = []
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            deleted.append(f.name)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {"message": "任务已删除", "deleted_files": deleted}


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
