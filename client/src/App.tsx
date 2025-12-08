import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
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
import { LanguageSwitch } from './components/LanguageSwitch'
import './App.css'

// API 基础路径
const API_BASE = '/api'

// 风格选项 key 映射
const STYLE_OPTIONS = [
  { value: '', labelKey: 'styles.default' },
  { value: 'pingshu', labelKey: 'styles.pingshu' },
  { value: 'ancient', labelKey: 'styles.ancient' },
  { value: 'humor', labelKey: 'styles.humor' },
  { value: 'dramatic', labelKey: 'styles.dramatic' },
  { value: 'minimalist', labelKey: 'styles.minimalist' },
  { value: 'storytelling', labelKey: 'styles.storytelling' },
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
  const { t } = useTranslation()
  
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
        console.error(t('errors.pollFailed'), e)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [currentTask])

  // 处理文件选择并分析
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return
    
    if (!selectedFile.name.endsWith('.txt')) {
      setError(t('upload.txtOnly'))
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
        throw new Error(data.detail || t('errors.analyzeFailed'))
      }
      
      const data: AnalyzeResult = await res.json()
      setAnalyzeResult(data)
      
      // 设置推荐的阅读时间为默认值（乘以 1.1 倍并向上取整，增加冗余）
      setTargetTime(Math.ceil(data.recommended_reading_time * 1.1))
      
      // 设置初始推荐值
      setRecommendation({
        recommended_reading_time: data.recommended_reading_time,
        total_budget_chars: Math.round(data.recommended_reading_time * readingSpeed),
        effective_chapters: data.total_chapters,
        effective_chars: data.total_chars,
      })
      
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errors.analyzeFailed'))
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
        // 自动更新目标时间为推荐值（乘以 1.1 倍并向上取整，增加冗余）
        setTargetTime(Math.ceil(data.recommended_reading_time * 1.1))
      }
    } catch (e) {
      console.error(t('errors.calculateFailed'), e)
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
      setError(t('errors.uploadFirst'))
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
        message: t('status.inProgress'),
        created_at: new Date().toISOString(),
      })
      
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errors.createTaskFailed'))
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
            <h1>{t('header.title')}</h1>
          </div>
          <p className="subtitle">{t('header.subtitle')}</p>
          <LanguageSwitch />
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
                      <span>{t('upload.analyzing')}</span>
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
                      <span>{t('upload.selectFile')}</span>
                      <span className="hint">{t('upload.supportedEncoding')}</span>
                    </>
                  )}
                </label>
              </div>

              {/* 分析结果展示 */}
              {analyzeResult && (
                <div className="analyze-result">
                  <div className="result-header">
                    <Info size={20} />
                    <h3>{t('analysis.title')}</h3>
                  </div>
                  <div className="result-stats">
                    <div className="stat-item">
                      <Hash size={16} />
                      <span className="stat-label">{t('analysis.chapters')}</span>
                      <span className="stat-value">{analyzeResult.total_chapters} {t('analysis.chaptersUnit')}</span>
                    </div>
                    <div className="stat-item">
                      <Type size={16} />
                      <span className="stat-label">{t('analysis.totalChars')}</span>
                      <span className="stat-value">{analyzeResult.total_chars.toLocaleString()} {t('analysis.charsUnit')}</span>
                    </div>
                    <div className="stat-item recommended">
                      <Clock size={16} />
                      <span className="stat-label">{t('analysis.recommendedTime')}</span>
                      <span className="stat-value highlight">
                        {recommendation?.recommended_reading_time || analyzeResult.recommended_reading_time} {t('analysis.minutesUnit')}
                      </span>
                    </div>
                  </div>
                  {analyzeResult.chapters_preview.length > 0 && (
                    <div className="chapters-preview">
                      <span className="preview-label">{t('analysis.chapterPreview')}</span>
                      {analyzeResult.chapters_preview.slice(0, 3).map((ch, i) => (
                        <span key={i} className="preview-chapter">{ch.title}</span>
                      ))}
                      {analyzeResult.total_chapters > 3 && (
                        <span className="preview-more">{t('analysis.totalChapters', { count: analyzeResult.total_chapters })}</span>
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
                    {t('form.readingSpeed')}
                  </label>
                  <input
                    type="number"
                    value={readingSpeed}
                    onChange={(e) => setReadingSpeed(Number(e.target.value))}
                    min={100}
                    max={1000}
                    required
                  />
                  <span className="hint">{t('form.readingSpeedHint')}</span>
                </div>

                <div className="form-group">
                  <label>
                    <Clock size={16} />
                    {t('form.targetTime')}
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
                    {t('form.estimatedChars', { count: targetTime * readingSpeed })}
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
                  {showAdvanced ? t('form.collapseAdvanced') : t('form.expandAdvanced')}
                </button>
              </div>

              {showAdvanced && (
                <div className="advanced-options">
                  <div className="form-grid">
                    <div className="form-group">
                      <label>
                        <Sparkles size={16} />
                        {t('form.outputStyle')}
                      </label>
                      <select
                        value={style}
                        onChange={(e) => setStyle(e.target.value)}
                      >
                        {STYLE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {t(opt.labelKey)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group">
                      <label>{t('form.outputMode')}</label>
                      <select
                        value={outputMode}
                        onChange={(e) => setOutputMode(e.target.value)}
                      >
                        <option value="continuous">{t('outputModes.continuous')}</option>
                        <option value="chapter">{t('outputModes.chapter')}</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>{t('form.maxChapters')}</label>
                      <input
                        type="number"
                        value={maxChapters}
                        onChange={(e) => setMaxChapters(e.target.value ? Number(e.target.value) : '')}
                        min={1}
                        placeholder={t('form.maxChaptersPlaceholder')}
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
                        🔥 {t('features.climaxAnalysis')}
                        <span className="toggle-hint">
                          {enableClimaxAnalysis 
                            ? t('features.climaxEnabled')
                            : t('features.climaxDisabled')}
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
                        ✅ {t('features.qualityCheck')}
                        <span className="toggle-hint">
                          {enableQualityCheck 
                            ? t('features.qualityEnabled')
                            : t('features.qualityDisabled')}
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
                    {t('buttons.creating')}
                  </>
                ) : analyzing ? (
                  <>
                    <Loader2 size={20} className="spin" />
                    {t('buttons.analyzing')}
                  </>
                ) : !analyzeResult ? (
                  <>
                    <Upload size={20} />
                    {t('buttons.uploadFirst')}
                  </>
                ) : (
                  <>
                    <Sparkles size={20} />
                    {t('buttons.startGenerate')}
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
                    <h2>{t('status.processing')}</h2>
                    <p>{t('status.processingHint')}</p>
                    <div className="progress-bar">
                      <div className="progress-fill"></div>
                    </div>
                  </>
                )}

                {currentTask.status === 'completed' && (
                  <>
                    <CheckCircle size={64} />
                    <h2>{t('status.completed')}</h2>
                    <p>{currentTask.message}</p>
                    <div className="action-buttons">
                      <button className="download-btn" onClick={handleDownload}>
                        <Download size={20} />
                        {t('buttons.download')}
                      </button>
                      <button className="reset-btn" onClick={handleReset}>
                        {t('buttons.continueOther')}
                      </button>
                    </div>
                  </>
                )}

                {currentTask.status === 'failed' && (
                  <>
                    <AlertCircle size={64} />
                    <h2>{t('status.failed')}</h2>
                    <p>{currentTask.message}</p>
                    <button className="reset-btn" onClick={handleReset}>
                      {t('buttons.retry')}
                    </button>
                  </>
                )}
              </div>

              <div className="task-info">
                <p><strong>{t('status.taskId')}</strong> {currentTask.task_id}</p>
                <p><strong>{t('status.filename')}</strong> {currentTask.filename}</p>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 页脚 */}
      <footer className="footer">
        <p>{t('footer.copyright')}</p>
      </footer>
    </div>
  )
}

export default App
