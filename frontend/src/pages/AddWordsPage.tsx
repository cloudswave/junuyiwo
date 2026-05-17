import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Input, Button, DatePicker, Steps, message, Space, Tag, Form, Modal, Alert, Radio, Spin, Slider, Switch, Collapse, Select
} from 'antd'
import { PlusOutlined, ThunderboltOutlined, FileTextOutlined, AudioOutlined, AudioMutedOutlined, BulbOutlined, SettingOutlined } from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import { charactersApi, articlesApi, ArticleWithPinyin, memoryApi, MemoryContextResponse, asrApi, curiosityApi, TopicSuggestionResponse, zonesApi, ArticleParamsResponse } from '../services/api'
import { useStore } from '../store/useStore'
import ArticleReader from '../components/ArticleReader'

type Step = 'input' | 'generate' | 'done'
type ArticleMode = 'story' | 'answer'

export default function AddWordsPage() {
  const navigate = useNavigate()
  const { setLoading, loading } = useStore()

  const [currentStep, setCurrentStep] = useState<Step>('input')
  const [inputMode, setInputMode] = useState<'manual' | 'paste' | 'voice'>('manual')
  const [date, setDate] = useState<Dayjs>(dayjs())
  const [manualChars, setManualChars] = useState('')
  const [pasteText, setPasteText] = useState('')
  const [extractedChars, setExtractedChars] = useState<string[]>([])

  // Voice input (via backend 科大讯飞 ASR)
  const [isListening, setIsListening] = useState(false)
  const [asrProcessing, setAsrProcessing] = useState(false)  // 识别等待中
  const [voiceText, setVoiceText] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const voiceChunksRef = useRef<Blob[]>([])
  const voiceTargetRef = useRef<'chars' | 'topic'>('chars')  // 录音目标

  // Article generation
  const [topic, setTopic] = useState('')
  const [articleLength, setArticleLength] = useState(150)
  const [articleMode, setArticleMode] = useState<ArticleMode>('story')
  const [generatedArticle, setGeneratedArticle] = useState<ArticleWithPinyin | null>(null)

  // Density config (parent mode)
  const [densityParams, setDensityParams] = useState<ArticleParamsResponse | null>(null)
  const [densityOverride, setDensityOverride] = useState(false)
  const [overrideDensity, setOverrideDensity] = useState(7)
  const [overrideReinforce, setOverrideReinforce] = useState(2)
  const [overrideMinChars, setOverrideMinChars] = useState(300)

  useEffect(() => {
    zonesApi.computeArticleParams().then(({ data }) => {
      setDensityParams(data)
      setOverrideDensity(data.target_density)
      setOverrideReinforce(data.reinforce_density)
    }).catch(() => {})
  }, [])

  // Memory context
  const [memoryContext, setMemoryContext] = useState<MemoryContextResponse | null>(null)
  const [memoryModalOpen, setMemoryModalOpen] = useState(false)
  const [memoryLoading, setMemoryLoading] = useState(false)

  // Topic suggestions from curiosity
  const [topicSuggestions, setTopicSuggestions] = useState<TopicSuggestionResponse | null>(null)

  const handleExtract = async () => {
    if (!pasteText.trim()) return
    setLoading('extract', true)
    try {
      const { data } = await charactersApi.extract(pasteText)
      setExtractedChars(data.characters)
    } catch {
      message.error('提取失败，请重试')
    } finally {
      setLoading('extract', false)
    }
  }

  // ===== Voice input (Web Audio API → WAV → 科大讯飞 ASR) =====
  const audioCtxRef = useRef<AudioContext | null>(null)
  const pcmChunksRef = useRef<Float32Array[]>([])

  const startListening = async () => {
    if (voiceTargetRef.current !== 'topic') voiceTargetRef.current = 'chars'
    if (!navigator.mediaDevices?.getUserMedia) {
      message.error('浏览器不支持录音')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const audioCtx = new AudioContext({ sampleRate: 16000 })
      audioCtxRef.current = audioCtx
      pcmChunksRef.current = []

      const source = audioCtx.createMediaStreamSource(stream)
      // ScriptProcessorNode 用于获取原始 PCM 采样
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)

      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0)
        // 复制 Float32Array 数据
        pcmChunksRef.current.push(new Float32Array(input))
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)
      ;(processor as any)._stream = stream  // 引用以便清理

      mediaRecorderRef.current = processor as any
      setIsListening(true)
    } catch {
      message.error('无法访问麦克风')
    }
  }

  const stopListening = () => {
    const processor = mediaRecorderRef.current as any
    if (!processor) return

    const stream = processor._stream as MediaStream
    stream.getTracks().forEach((t) => t.stop())

    const audioCtx = audioCtxRef.current
    audioCtx?.close()

    processor.disconnect()
    mediaRecorderRef.current = null
    audioCtxRef.current = null
    setIsListening(false)

    // 打包为 WAV 并发送识别
    const allPcm = pcmChunksRef.current
    if (allPcm.length === 0) return

    // 合并所有 Float32Array 为单个 Float32Array
    const totalLen = allPcm.reduce((sum, a) => sum + a.length, 0)
    const merged = new Float32Array(totalLen)
    let offset = 0
    for (const chunk of allPcm) {
      merged.set(chunk, offset)
      offset += chunk.length
    }

    // Float32 → Int16 PCM
    const int16 = new Int16Array(merged.length)
    for (let i = 0; i < merged.length; i++) {
      const s = Math.max(-1, Math.min(1, merged[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
    }

    // 构建 WAV 文件
    const numChannels = 1
    const sampleRate = 16000
    const bitsPerSample = 16
    const byteRate = sampleRate * numChannels * bitsPerSample / 8
    const blockAlign = numChannels * bitsPerSample / 8
    const dataSize = int16.length * (bitsPerSample / 8)
    const headerSize = 44
    const buffer = new ArrayBuffer(headerSize + dataSize)
    const view = new DataView(buffer)

    function writeStr(off: number, s: string) {
      for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i))
    }
    writeStr(0, 'RIFF')
    view.setUint32(4, 36 + dataSize, true)
    writeStr(8, 'WAVE')
    writeStr(12, 'fmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, numChannels, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, byteRate, true)
    view.setUint16(32, blockAlign, true)
    view.setUint16(34, bitsPerSample, true)
    writeStr(36, 'data')
    view.setUint32(40, dataSize, true)

    // 写入 PCM 采样
    const int16View = new Int16Array(buffer, headerSize)
    int16View.set(int16)

    const blob = new Blob([buffer], { type: 'audio/wav' })
    const file = new File([blob], 'recording.wav', { type: 'audio/wav' })

    setAsrProcessing(true)
    asrApi.recognize(file).then(({ data }) => {
      const text = data.text || ''
      if (voiceTargetRef.current === 'topic') {
        if (text) {
          setTopic(text)
          message.success('已填入')
        } else {
          message.info('未识别到文字')
        }
      } else {
        setVoiceText(text)
        if (text) {
          const newChars = text.replace(/[^一-鿿]/g, '').split('')
          if (newChars.length > 0) {
            setExtractedChars((prev) => {
              const existing = new Set(prev)
              const added = newChars.filter((c) => !existing.has(c))
              return added.length > 0 ? [...prev, ...added] : prev
            })
          }
          message.success(`识别到 ${newChars.length} 个汉字`)
        } else {
          message.info('未识别到文字，请再试一次')
        }
      }
    }).catch((err: any) => {
      const msg = err?.response?.data?.detail || err?.message || '识别失败'
      message.error(`语音识别失败: ${msg}`)
    }).finally(() => {
      setAsrProcessing(false)
    })
  }

  const getCharList = (): string[] => {
    if (inputMode === 'paste' || inputMode === 'voice') return extractedChars
    const trimmed = manualChars.trim()
    if (!trimmed) return []
    // 如果包含分隔符，按分隔符拆分
    if (/[,，、\s]/.test(trimmed)) {
      return trimmed.split(/[,，、\s]+/).map(s => s.trim()).filter(Boolean)
    }
    // 否则自动拆成单个汉字（只保留中文字符）
    return trimmed.replace(/[^\u4e00-\u9fff]/g, '').split('')
  }

  const handleSave = async () => {
    const chars = getCharList()
    if (chars.length === 0) {
      message.warning('请先输入生字')
      return
    }

    setLoading('save', true)
    try {
      const { data } = await zonesApi.addTarget({
        characters: chars,
        source: 'manual',
      })
      const added = data.count || 0
      const skipped = chars.length - added
      if (skipped > 0) {
        message.success(`已录入 ${added} 个字，${skipped} 个已存在自动跳过`)
      } else {
        message.success(`已录入 ${added} 个字到教学区`)
      }
      setCurrentStep('generate')
      // 加载好奇心主题建议
      curiosityApi.getSuggestions().then(({ data }) => setTopicSuggestions(data)).catch(() => {})
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '网络连接失败'
      message.error(`保存失败: ${msg}`)
    } finally {
      setLoading('save', false)
    }
  }

  const handleCheckMemory = async () => {
    const chars = getCharList()
    if (!topic.trim()) {
      message.warning('请输入主题或孩子的问题')
      return
    }

    setMemoryLoading(true)
    try {
      const { data } = await memoryApi.getContext({
        topic: topic.trim(),
        characters: chars,
      })
      if (data.has_memory) {
        setMemoryContext(data)
        setMemoryModalOpen(true)
      } else {
        handleGenerate(null)
      }
    } catch {
      handleGenerate(null)
    } finally {
      setMemoryLoading(false)
    }
  }

  const handleGenerate = async (memoryCtx: string | null) => {
    const chars = getCharList()

    setMemoryModalOpen(false)
    setLoading('generate', true)
    try {
      const { data } = await articlesApi.generate({
        record_date: date.format('YYYY-MM-DD'),
        topic: topic.trim(),
        characters: chars,
        min_chars: articleLength,
        max_chars: articleLength <= 80 ? articleLength + 50 : articleLength <= 200 ? articleLength + 100 : articleLength + 300,
        category: articleMode,
        memory_context: memoryCtx || undefined,
      })
      setGeneratedArticle(data)
      setCurrentStep('done')
      message.success('文章生成成功')

      if (data.id) {
        const hide = message.loading('正在生成文章配图...', 0)
        articlesApi.generateImages(data.id).then(({ data: imgData }) => {
          hide()
          if (imgData.images?.length) {
            setGeneratedArticle((prev: any) => prev ? {
              ...prev,
              image_url: imgData.images[0].url,
              images: imgData.images,
            } : prev)
            message.success(`文章生成成功，已自动配 ${imgData.images.length} 张插图`)
          } else {
            message.success('文章生成成功（插图生成失败，可稍后重试）')
          }
        }).catch((err) => {
          hide()
          console.error('generateImages error:', err)
          message.success('文章生成成功（插图生成失败，可稍后重试）')
        })
      }
    } catch {
      message.error('文章生成失败，请重试')
    } finally {
      setLoading('generate', false)
    }
  }

  const handleGenerateWithMemory = () => {
    handleGenerate(memoryContext?.prompt_context || '')
  }

  const handleGenerateWithoutMemory = () => {
    handleGenerate(null)
  }

  const steps = [
    { title: '录入生字', status: currentStep === 'input' ? 'process' : 'finish' },
    { title: '生成文章', status: currentStep === 'generate' ? 'process' : currentStep === 'done' ? 'finish' : 'wait' },
    { title: '完成', status: currentStep === 'done' ? 'finish' : 'wait' },
  ]

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>录入生字</h1>
        <p>手工录入或粘贴文本自动提取生字，然后生成阅读文章</p>
      </div>

      <Steps
        current={currentStep === 'input' ? 0 : currentStep === 'generate' ? 1 : 2}
        items={steps.map((s, i) => ({ title: s.title, status: s.status as any }))}
        style={{ marginBottom: 24 }}
      />

      {currentStep === 'input' && (
        <Card>
          <Form layout="vertical">
            <Form.Item label="学习日期">
              <DatePicker
                value={date}
                onChange={(d) => d && setDate(d)}
                style={{ width: '100%' }}
                allowClear={false}
              />
            </Form.Item>

            <Form.Item label="录入方式">
              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  type={inputMode === 'manual' ? 'primary' : 'default'}
                  onClick={() => setInputMode('manual')}
                  icon={<PlusOutlined />}
                >
                  手工录入
                </Button>
                <Button
                  type={inputMode === 'paste' ? 'primary' : 'default'}
                  onClick={() => setInputMode('paste')}
                  icon={<FileTextOutlined />}
                >
                  粘贴文本
                </Button>
                <Button
                  type={inputMode === 'voice' ? 'primary' : 'default'}
                  onClick={() => setInputMode('voice')}
                  icon={<AudioOutlined />}
                >
                  语音录入
                </Button>
              </div>
            </Form.Item>

            {inputMode === 'manual' ? (
              <Form.Item label="生字（支持逗号分隔，也可直输汉字自动拆分）">
                <Input.TextArea
                  value={manualChars}
                  onChange={(e) => setManualChars(e.target.value)}
                  placeholder="例如：春暖花开 或 春,暖,花,开"
                  rows={3}
                  style={{ fontSize: 20 }}
                />
              </Form.Item>
            ) : inputMode === 'voice' ? (
              <>
                <Form.Item label="语音录入（科大讯飞）">
                  <div style={{
                    background: isListening ? '#fff1f0' : '#f6ffed',
                    border: `2px solid ${isListening ? '#ff4d4f' : '#52c41a'}`,
                    borderRadius: 12,
                    padding: 24,
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>
                      {asrProcessing ? (
                        <Spin size="large" />
                      ) : isListening ? (
                        <AudioOutlined style={{ color: '#ff4d4f' }} spin />
                      ) : (
                        <AudioOutlined style={{ color: '#52c41a' }} />
                      )}
                    </div>
                    <div style={{ fontSize: 16, marginBottom: 20, color: '#555' }}>
                      {asrProcessing ? '正在识别中，请稍候...' : isListening ? '正在聆听...请说出汉字或句子' : '点击按钮开始语音录入'}
                    </div>
                    <Button
                      type={isListening ? 'default' : 'primary'}
                      size="large"
                      danger={isListening}
                      icon={isListening ? <AudioMutedOutlined /> : <AudioOutlined />}
                      onClick={isListening ? stopListening : startListening}
                      loading={asrProcessing}
                      disabled={asrProcessing}
                    >
                      {isListening ? '停止录音' : '开始录音'}
                    </Button>
                  </div>
                </Form.Item>

                {voiceText && (
                  <Form.Item label="识别文本">
                    <Input.TextArea
                      value={voiceText}
                      readOnly
                      rows={3}
                      style={{ fontSize: 16 }}
                    />
                  </Form.Item>
                )}
                {extractedChars.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8, color: '#888' }}>
                      已识别 {extractedChars.length} 个不重复汉字：
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {extractedChars.map((ch) => (
                        <Tag
                          key={ch}
                          closable
                          onClose={() => setExtractedChars(extractedChars.filter((c) => c !== ch))}
                          style={{ fontSize: 18, padding: '4px 12px' }}
                        >
                          {ch}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <>
                <Form.Item label="粘贴文本内容">
                  <Input.TextArea
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    placeholder="粘贴一段中文文本，系统将自动提取其中的汉字..."
                    rows={5}
                  />
                </Form.Item>
                <Button
                  type="primary"
                  ghost
                  icon={<ThunderboltOutlined />}
                  onClick={handleExtract}
                  loading={loading['extract']}
                  style={{ marginBottom: 16 }}
                >
                  自动提取生字
                </Button>
                {extractedChars.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8, color: '#888' }}>
                      已提取 {extractedChars.length} 个不重复汉字：
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {extractedChars.map((ch) => (
                        <Tag
                          key={ch}
                          closable
                          onClose={() => setExtractedChars(extractedChars.filter((c) => c !== ch))}
                          style={{ fontSize: 18, padding: '4px 12px' }}
                        >
                          {ch}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            <Form.Item>
              <Button type="primary" size="large" htmlType="button" onClick={handleSave} loading={loading['save']} block>
                保存生字，然后生成文章
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}

      {currentStep === 'generate' && (
        <Card title="生成阅读文章">
          <Form layout="vertical">
            <Form.Item label="生成方式">
              <Radio.Group
                value={articleMode}
                onChange={(e) => setArticleMode(e.target.value)}
                buttonStyle="solid"
                optionType="button"
              >
                <Radio.Button value="story">
                  <FileTextOutlined /> 故事式
                </Radio.Button>
                <Radio.Button value="answer">
                  <BulbOutlined /> 百科回答式
                </Radio.Button>
              </Radio.Group>
              <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
                {articleMode === 'story'
                  ? '围绕主题写一篇有趣的短文，像讲故事一样'
                  : '用简单的话回答孩子的问题，像爸爸蹲下来跟孩子聊天'}
              </div>
            </Form.Item>

            <Form.Item label={articleMode === 'answer' ? '孩子的问题' : '文章主题'} required>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder={articleMode === 'answer'
                  ? '例如：星星为什么眨眼睛？霸王龙有多重？'
                  : '例如：春天来了、动物朋友们、恐龙世界...'}
                size="large"
                suffix={
                  asrProcessing ? (
                    <Spin size="small" />
                  ) : isListening ? (
                    <AudioOutlined
                      style={{ color: '#ff4d4f', cursor: 'pointer', fontSize: 18 }}
                      spin
                      onClick={stopListening}
                    />
                  ) : (
                    <AudioOutlined
                      style={{ color: '#1890ff', cursor: 'pointer', fontSize: 18 }}
                      onClick={() => {
                        voiceTargetRef.current = 'topic'
                        startListening()
                      }}
                      title="语音输入主题"
                    />
                  )
                }
              />
            </Form.Item>

            {/* Curiosity topic suggestions */}
            {topicSuggestions && (topicSuggestions.from_unanswered.length > 0 || topicSuggestions.from_hot_interests.length > 0) && (
              <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8, border: '1px solid #b7eb8f' }}>
                <div style={{ marginBottom: 8, color: '#52c41a', fontWeight: 500 }}>
                  <BulbOutlined /> 从好奇心选取主题
                </div>
                {topicSuggestions.from_unanswered.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <span style={{ color: '#888', fontSize: 12 }}>孩子问过的问题：</span>
                    {topicSuggestions.from_unanswered.map((q) => (
                      <Tag key={q.id} color="gold" style={{ cursor: 'pointer', marginBottom: 4 }}
                        onClick={() => { setTopic(q.raw_text); setArticleMode('answer') }}>
                        {q.raw_text.length > 20 ? q.raw_text.slice(0, 20) + '...' : q.raw_text}
                      </Tag>
                    ))}
                  </div>
                )}
                {topicSuggestions.from_hot_interests.length > 0 && (
                  <div>
                    <span style={{ color: '#888', fontSize: 12 }}>热门兴趣：</span>
                    {topicSuggestions.from_hot_interests.map((t) => (
                      <Tag key={t.tag_name} color="blue" style={{ cursor: 'pointer', marginBottom: 4 }}
                        onClick={() => { setTopic(`关于${t.tag_name}的故事`); setArticleMode('story') }}>
                        关于{t.tag_name}的故事
                      </Tag>
                    ))}
                  </div>
                )}
              </div>
            )}

            <Form.Item label="文章字数">
              <Select value={articleLength} onChange={setArticleLength} style={{ width: 160 }}>
                {[30, 50, 80, 100, 150, 200, 300, 500, 800].map((n) => (
                  <Select.Option key={n} value={n}>{n} 字</Select.Option>
                ))}
              </Select>
            </Form.Item>

            {/* 家长模式：生字密度调整 */}
            <Collapse
              ghost
              size="small"
              items={[{
                key: 'density',
                label: <span><SettingOutlined /> 家长模式：生字密度调整</span>,
                children: (
                  <div style={{ background: '#fafafa', padding: 12, borderRadius: 8 }}>
                    {densityParams && (
                      <div style={{ marginBottom: 12, fontSize: 13, color: '#666' }}>
                        系统推荐：
                        文章 {densityParams.article_min}-{densityParams.article_max} 字，
                        每100字含 <b>{densityParams.target_density}</b> 个生字，
                        复习 <b>{densityParams.reinforce_density}</b> 个困难字
                        <br />
                        字库：教学区 {densityParams.target_count} | 侦查区 {densityParams.scout_count} | 友军区 {densityParams.ally_count} | 战损区 {densityParams.lost_count}
                      </div>
                    )}
                    <Space style={{ marginBottom: 8 }}>
                      <span style={{ fontSize: 13 }}>自定义覆盖：</span>
                      <Switch
                        size="small"
                        checked={densityOverride}
                        onChange={setDensityOverride}
                        checkedChildren="开"
                        unCheckedChildren="关"
                      />
                    </Space>
                    {densityOverride && (
                      <>
                        <div style={{ marginBottom: 8 }}>
                          <span style={{ fontSize: 12, color: '#888' }}>生字密度（每100字）</span>
                          <Slider
                            min={1} max={20} step={1}
                            value={overrideDensity}
                            onChange={setOverrideDensity}
                            marks={{ 3: '轻松', 7: '标准', 12: '挑战', 18: '极限' }}
                          />
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <span style={{ fontSize: 12, color: '#888' }}>战损复习（每100字）</span>
                          <Slider
                            min={0} max={5} step={1}
                            value={overrideReinforce}
                            onChange={setOverrideReinforce}
                            marks={{ 0: '无', 1: '少量', 3: '适度', 5: '大量' }}
                          />
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <span style={{ fontSize: 12, color: '#888' }}>文章最短字数</span>
                          <Slider
                            min={50} max={1200} step={50}
                            value={overrideMinChars}
                            onChange={setOverrideMinChars}
                            marks={{ 50: '50', 300: '300', 500: '500', 800: '800', 1200: '1200' }}
                          />
                        </div>
                      </>
                    )}
                  </div>
                ),
              }]}
            />

            <div style={{ marginBottom: 16 }}>
              <span style={{ color: '#888' }}>融入生字：</span>
              {getCharList().map((ch) => (
                <Tag key={ch} style={{ marginBottom: 4 }}>{ch}</Tag>
              ))}
            </div>

            <Button
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              htmlType="button"
              onClick={handleCheckMemory}
              loading={loading['generate'] || memoryLoading}
              block
            >
              AI 生成文章
            </Button>
          </Form>
        </Card>
      )}

      {/* Memory confirmation modal */}
      <Modal
        title={
          <span>
            <BulbOutlined style={{ color: '#faad14', marginRight: 8 }} />
            发现孩子的学习记忆
          </span>
        }
        open={memoryModalOpen}
        onCancel={() => setMemoryModalOpen(false)}
        footer={[
          <Button key="skip" onClick={handleGenerateWithoutMemory}>
            跳过，直接生成
          </Button>,
          <Button key="use" type="primary" onClick={handleGenerateWithMemory}>
            融入记忆，生成文章
          </Button>,
        ]}
        width={560}
      >
        {memoryContext && (
          <div style={{ lineHeight: 2, fontSize: 15 }}>
            <p style={{ whiteSpace: 'pre-line', marginBottom: 16 }}>{memoryContext.summary_text}</p>

            {memoryContext.forgotten_chars.length > 0 && (
              <Alert
                type="warning"
                message={
                  <span>
                    高频遗忘字：
                    {memoryContext.forgotten_chars
                      .filter((f) => f.forget_count >= 2)
                      .map((f) => (
                        <Tag key={f.character} color="orange" style={{ margin: '2px 4px', fontSize: 14 }}>
                          {f.character}
                          {f.pinyin ? ` (${f.pinyin})` : ''}
                          <span style={{ fontSize: 11, color: '#999' }}> x{f.forget_count}</span>
                        </Tag>
                      ))}
                  </span>
                }
                style={{ marginTop: 12 }}
              />
            )}
          </div>
        )}
      </Modal>

      {currentStep === 'done' && generatedArticle && (
        <>
          <Card title="文章已生成！" style={{ marginBottom: 24 }}>
            <ArticleReader paragraphs={generatedArticle.paragraphs} topic={generatedArticle.topic} imageUrl={generatedArticle.image_url} images={generatedArticle.images} characters={getCharList()} articleId={generatedArticle.id} />
            {generatedArticle.char_breakdown && (
              <div style={{ marginTop: 16, padding: 12, background: '#f9f9f9', borderRadius: 8, fontSize: 13 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>📊 字库分布（共 {generatedArticle.char_breakdown.total} 个不重复字）</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
                  <div><span style={{ color: '#4F46E5' }}>🎯 教学区:</span> {generatedArticle.char_breakdown.from_target.join(' ') || '无'}</div>
                  <div><span style={{ color: '#52c41a' }}>✅ 友军区:</span> {generatedArticle.char_breakdown.from_ally.join(' ') || '无'}</div>
                  <div><span style={{ color: '#1890ff' }}>🔍 侦查区:</span> {generatedArticle.char_breakdown.from_scout.join(' ') || '无'}</div>
                  <div><span style={{ color: '#ff4d4f' }}>⚠️ 战损区:</span> {generatedArticle.char_breakdown.from_lost.join(' ') || '无'}</div>
                  <div><span style={{ color: '#faad14' }}>🆕 非字库:</span> {generatedArticle.char_breakdown.not_in_any.join(' ') || '无'}</div>
                </div>
              </div>
            )}
          </Card>

          <Space>
            <Button type="primary" onClick={() => navigate('/')}>
              回到首页
            </Button>
            <Button onClick={() => {
              setCurrentStep('input')
              setManualChars('')
              setPasteText('')
              setExtractedChars([])
              setTopic('')
              setGeneratedArticle(null)
            }}>
              继续录入
            </Button>
          </Space>
        </>
      )}
    </div>
  )
}
