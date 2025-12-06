import { useState, useEffect, useCallback } from 'react'
import { 
  Upload, 
  BookOpen, 
  Clock, 
  Zap, 
  Download, 
  CheckCircle, 
  Loader2, 
  AlertCircle,
  FileText,
  Settings,
  Sparkles,
  Info,
  Hash,
  Type
} from 'lucide-react'
import './App.css'

// API 基础路径
const API_BASE = '/api'

// 风格选项
const STYLE_OPTIONS = [
  { value: '', label: '普通白话文（默认）' },
  { value: 'pingshu', label: '评书风格' },
  { value: 'ancient', label: '古文风格' },
  { value: 'humor', label: '幽默风趣' },
  { value: 'dramatic', label: '戏剧化' },
  { value: 'minimalist', label: '极简风格' },
  { value: 'storytelling', label: '讲故事风格' },
]

// 任务状态类型
interface TaskStatus {
  task_id: string
  filename: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message?: string
  created_at: string
  download_url?: string
}

// 分析结果类型
interface AnalyzeResult {
  file_id: string
  filename: string
  total_chapters: number
  total_chars: number
  chapters_preview: Array<{ index: number; title: string; chars: number }>
  recommended_reading_time: number
  message: string
}

// 推荐值类型
interface Recommendation {
  recommended_reading_time: number
  total_budget_chars: number
  effective_chapters: number
  effective_chars: number
}

function App() {
  // 表单状态
  const [file, setFile] = useState<File | null>(null)
  const [readingSpeed, setReadingSpeed] = useState(300)
  const [targetTime, setTargetTime] = useState(30)
  const [style, setStyle] = useState('')
  const [outputMode, setOutputMode] = useState('continuous')
  const [maxChapters, setMaxChapters] = useState<number | ''>('')
  const [enableClimaxAnalysis, setEnableClimaxAnalysis] = useState(true)
  const [enableQualityCheck, setEnableQualityCheck] = useState(true)
  
  // 分析状态
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null)
  
  // UI 状态
  const [uploading, setUploading] = useState(false)
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(true)

  // 轮询任务状态
  useEffect(() => {
    if (!currentTask || currentTask.status === 'completed' || currentTask.status === 'failed') {
      return
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${currentTask.task_id}`)
        if (res.ok) {
          const data = await res.json()
          setCurrentTask(data)
        }
      } catch (e) {
        console.error('轮询状态失败', e)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [currentTask])

  // 处理文件选择并分析
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return
    
    if (!selectedFile.name.endsWith('.txt')) {
      setError('请选择 TXT 格式的文件')
      return
    }
    
    setFile(selectedFile)
    setError(null)
    setAnalyzing(true)
    setAnalyzeResult(null)
    
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('reading_speed', readingSpeed.toString())
      
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData,
      })
      
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || '分析失败')
      }
      
      const data: AnalyzeResult = await res.json()
      setAnalyzeResult(data)
      
      // 设置推荐的阅读时间为默认值
      setTargetTime(data.recommended_reading_time)
      
      // 设置初始推荐值
      setRecommendation({
        recommended_reading_time: data.recommended_reading_time,
        total_budget_chars: Math.round(data.recommended_reading_time * readingSpeed),
        effective_chapters: data.total_chapters,
        effective_chars: data.total_chars,
      })
      
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析失败')
      setFile(null)
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      if (fileInput) fileInput.value = ''
    } finally {
      setAnalyzing(false)
    }
  }
  
  // 重新计算推荐值
  const updateRecommendation = useCallback(async () => {
    if (!analyzeResult) return
    
    try {
      const res = await fetch(`${API_BASE}/calculate-recommendation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: analyzeResult.file_id,
          reading_speed: readingSpeed,
          max_chapters: maxChapters || null,
          min_chars_per_chapter: 100,
        }),
      })
      
      if (res.ok) {
        const data: Recommendation = await res.json()
        setRecommendation(data)
        // 自动更新目标时间为推荐值
        setTargetTime(data.recommended_reading_time)
      }
    } catch (e) {
      console.error('计算推荐值失败', e)
    }
  }, [analyzeResult, readingSpeed, maxChapters])
  
  // 当配置改变时重新计算推荐值
  useEffect(() => {
    if (analyzeResult) {
      updateRecommendation()
    }
  }, [readingSpeed, maxChapters, analyzeResult, updateRecommendation])

  // 提交任务
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!analyzeResult) {
      setError('请先上传并分析小说文件')
      return
    }

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file_id', analyzeResult.file_id)
      formData.append('reading_speed', readingSpeed.toString())
      formData.append('target_reading_time', targetTime.toString())
      formData.append('output_mode', outputMode)
      formData.append('enable_climax_analysis', enableClimaxAnalysis.toString())
      formData.append('enable_quality_check', enableQualityCheck.toString())
      if (style) formData.append('style', style)
      if (maxChapters) formData.append('max_chapters', maxChapters.toString())

      const res = await fetch(`${API_BASE}/start-task`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || '创建任务失败')
      }

      const data = await res.json()
      
      // 开始轮询状态
      setCurrentTask({
        task_id: data.task_id,
        filename: analyzeResult.filename,
        status: 'processing',
        message: '正在处理中...',
        created_at: new Date().toISOString(),
      })
      
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建任务失败')
    } finally {
      setUploading(false)
    }
  }

  // 下载结果
  const handleDownload = () => {
    if (currentTask?.download_url) {
      window.open(`${API_BASE}${currentTask.download_url}`, '_blank')
    }
  }

  // 重置任务
  const handleReset = () => {
    setCurrentTask(null)
    setError(null)
    setFile(null)
    setAnalyzeResult(null)
    setRecommendation(null)
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    if (fileInput) fileInput.value = ''
  }

  return (
    <div className="app">
      {/* 头部 */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <BookOpen size={32} />
            <h1>小说速读生成器</h1>
          </div>
          <p className="subtitle">将长篇小说压缩为速读版本，节省您的阅读时间</p>
        </div>
      </header>

      {/* 主要内容 */}
      <main className="main">
        <div className="container">
          {/* 上传表单 */}
          {!currentTask && (
            <form className="upload-form" onSubmit={handleSubmit}>
              {/* 文件上传区域 */}
              <div className="upload-area">
                <input
                  type="file"
                  accept=".txt"
                  onChange={handleFileChange}
                  id="file-input"
                  className="file-input"
                  disabled={analyzing}
                />
                <label htmlFor="file-input" className={`file-label ${analyzing ? 'analyzing' : ''}`}>
                  {analyzing ? (
                    <>
                      <Loader2 size={48} className="spin" />
                      <span>正在分析章节结构...</span>
                    </>
                  ) : file ? (
                    <>
                      <FileText size={48} />
                      <span className="file-name">{file.name}</span>
                      <span className="file-size">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                    </>
                  ) : (
                    <>
                      <Upload size={48} />
                      <span>点击或拖拽上传小说 TXT 文件</span>
                      <span className="hint">支持 UTF-8 和 GBK 编码</span>
                    </>
                  )}
                </label>
              </div>

              {/* 分析结果展示 */}
              {analyzeResult && (
                <div className="analyze-result">
                  <div className="result-header">
                    <Info size={20} />
                    <h3>文件分析结果</h3>
                  </div>
                  <div className="result-stats">
                    <div className="stat-item">
                      <Hash size={16} />
                      <span className="stat-label">章节数量</span>
                      <span className="stat-value">{analyzeResult.total_chapters} 章</span>
                    </div>
                    <div className="stat-item">
                      <Type size={16} />
                      <span className="stat-label">总字数</span>
                      <span className="stat-value">{analyzeResult.total_chars.toLocaleString()} 字</span>
                    </div>
                    <div className="stat-item recommended">
                      <Clock size={16} />
                      <span className="stat-label">推荐最低阅读时间</span>
                      <span className="stat-value highlight">
                        {recommendation?.recommended_reading_time || analyzeResult.recommended_reading_time} 分钟
                      </span>
                    </div>
                  </div>
                  {analyzeResult.chapters_preview.length > 0 && (
                    <div className="chapters-preview">
                      <span className="preview-label">章节预览：</span>
                      {analyzeResult.chapters_preview.slice(0, 3).map((ch, i) => (
                        <span key={i} className="preview-chapter">{ch.title}</span>
                      ))}
                      {analyzeResult.total_chapters > 3 && (
                        <span className="preview-more">...共 {analyzeResult.total_chapters} 章</span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* 基本参数 */}
              <div className="form-grid">
                <div className="form-group">
                  <label>
                    <Zap size={16} />
                    阅读速度（字/分钟）
                  </label>
                  <input
                    type="number"
                    value={readingSpeed}
                    onChange={(e) => setReadingSpeed(Number(e.target.value))}
                    min={100}
                    max={1000}
                    required
                  />
                  <span className="hint">普通人阅读速度约 200-400 字/分钟</span>
                </div>

                <div className="form-group">
                  <label>
                    <Clock size={16} />
                    目标阅读时间（分钟）
                  </label>
                  <input
                    type="number"
                    value={targetTime}
                    onChange={(e) => setTargetTime(Number(e.target.value))}
                    min={1}
                    max={600}
                    required
                  />
                  <span className="hint">
                    预计生成 {(targetTime * readingSpeed).toLocaleString()} 字
                  </span>
                </div>
              </div>

              {/* 高级选项 */}
              <div className="advanced-toggle">
                <button
                  type="button"
                  className="toggle-btn"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  <Settings size={16} />
                  {showAdvanced ? '收起高级选项' : '展开高级选项'}
                </button>
              </div>

              {showAdvanced && (
                <div className="advanced-options">
                  <div className="form-grid">
                    <div className="form-group">
                      <label>
                        <Sparkles size={16} />
                        输出风格
                      </label>
                      <select
                        value={style}
                        onChange={(e) => setStyle(e.target.value)}
                      >
                        {STYLE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group">
                      <label>输出模式</label>
                      <select
                        value={outputMode}
                        onChange={(e) => setOutputMode(e.target.value)}
                      >
                        <option value="continuous">整体连贯（推荐）</option>
                        <option value="chapter">按章节</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>仅处理前 N 章（可选）</label>
                      <input
                        type="number"
                        value={maxChapters}
                        onChange={(e) => setMaxChapters(e.target.value ? Number(e.target.value) : '')}
                        min={1}
                        placeholder="留空表示全部"
                      />
                    </div>
                  </div>
                  
                  {/* 高潮评分开关 */}
                  <div className="climax-toggle">
                    <label className="toggle-label">
                      <input
                        type="checkbox"
                        checked={enableClimaxAnalysis}
                        onChange={(e) => setEnableClimaxAnalysis(e.target.checked)}
                      />
                      <span className="toggle-switch"></span>
                      <span className="toggle-text">
                        🔥 启用高潮评分系统
                        <span className="toggle-hint">
                          {enableClimaxAnalysis 
                            ? '重要章节将获得更多字数预算（处理时间增加）' 
                            : '按章节长度分配预算（处理更快）'}
                        </span>
                      </span>
                    </label>
                  </div>
                  
                  {/* 质量自检开关 */}
                  <div className="climax-toggle">
                    <label className="toggle-label">
                      <input
                        type="checkbox"
                        checked={enableQualityCheck}
                        onChange={(e) => setEnableQualityCheck(e.target.checked)}
                      />
                      <span className="toggle-switch"></span>
                      <span className="toggle-text">
                        ✅ 启用质量自检
                        <span className="toggle-hint">
                          {enableQualityCheck 
                            ? '自动检测摘要是否完整，不完整则重新生成（最多重试3次）' 
                            : '不检测摘要完整性，直接使用生成结果'}
                        </span>
                      </span>
                    </label>
                  </div>
                </div>
              )}

              {/* 错误提示 */}
              {error && (
                <div className="error-message">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}

              {/* 提交按钮 */}
              <button
                type="submit"
                className="submit-btn"
                disabled={!analyzeResult || uploading || analyzing}
              >
                {uploading ? (
                  <>
                    <Loader2 size={20} className="spin" />
                    创建任务中...
                  </>
                ) : analyzing ? (
                  <>
                    <Loader2 size={20} className="spin" />
                    分析中...
                  </>
                ) : !analyzeResult ? (
                  <>
                    <Upload size={20} />
                    请先上传小说文件
                  </>
                ) : (
                  <>
                    <Sparkles size={20} />
                    开始生成速读版
                  </>
                )}
              </button>
            </form>
          )}

          {/* 任务状态 */}
          {currentTask && (
            <div className="task-status">
              <div className={`status-card ${currentTask.status}`}>
                {currentTask.status === 'processing' && (
                  <>
                    <Loader2 size={64} className="spin" />
                    <h2>正在生成速读版...</h2>
                    <p>这可能需要几分钟，请耐心等待</p>
                    <div className="progress-bar">
                      <div className="progress-fill"></div>
                    </div>
                  </>
                )}

                {currentTask.status === 'completed' && (
                  <>
                    <CheckCircle size={64} />
                    <h2>生成完成！</h2>
                    <p>{currentTask.message}</p>
                    <div className="action-buttons">
                      <button className="download-btn" onClick={handleDownload}>
                        <Download size={20} />
                        下载速读版
                      </button>
                      <button className="reset-btn" onClick={handleReset}>
                        继续处理其他小说
                      </button>
                    </div>
                  </>
                )}

                {currentTask.status === 'failed' && (
                  <>
                    <AlertCircle size={64} />
                    <h2>处理失败</h2>
                    <p>{currentTask.message}</p>
                    <button className="reset-btn" onClick={handleReset}>
                      重新尝试
                    </button>
                  </>
                )}
              </div>

              <div className="task-info">
                <p><strong>任务 ID:</strong> {currentTask.task_id}</p>
                <p><strong>文件名:</strong> {currentTask.filename}</p>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 页脚 */}
      <footer className="footer">
        <p>小说速读生成器 © 2024</p>
      </footer>
    </div>
  )
}

export default App
