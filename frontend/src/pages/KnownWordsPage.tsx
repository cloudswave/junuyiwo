import { useState, useRef, useEffect, useCallback } from 'react'
import { Button, Input, message, Tag, Radio, Spin, List, Popconfirm } from 'antd'
import { AudioOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { zonesApi, ZoneCharItem, charactersApi, asrApi } from '../services/api'
import { useStore } from '../store/useStore'

type InputMode = 'manual' | 'paste' | 'voice'

export default function KnownWordsPage() {
  const { loading, setLoading } = useStore()

  const [inputMode, setInputMode] = useState<InputMode>('manual')
  const [manualChars, setManualChars] = useState('')
  const [pasteText, setPasteText] = useState('')
  const [extractedChars, setExtractedChars] = useState<string[]>([])
  const [allyChars, setAllyChars] = useState<ZoneCharItem[]>([])
  const [isRecording, setIsRecording] = useState(false)

  const audioCtxRef = useRef<AudioContext | null>(null)
  const pcmChunksRef = useRef<Float32Array[]>([])

  // Load existing ally chars
  const loadAllyChars = useCallback(() => {
    setLoading('known', true)
    zonesApi.listAlly().then(({ data }) => setAllyChars(data)).catch(() => {}).finally(() => setLoading('known', false))
  }, [setLoading])

  useEffect(() => { loadAllyChars() }, [loadAllyChars])

  const getCharList = (): string[] => {
    if (inputMode === 'paste' || inputMode === 'voice') return extractedChars
    const trimmed = manualChars.trim()
    if (!trimmed) return []
    if (/[,，、\s]/.test(trimmed)) {
      return trimmed.split(/[,，、\s]+/).map(s => s.trim()).filter(Boolean)
    }
    return trimmed.replace(/[^一-鿿]/g, '').split('')
  }

  // Paste → extract
  const handleExtract = async () => {
    if (!pasteText.trim()) { message.warning('请先粘贴文字'); return }
    setLoading('extract', true)
    try {
      const { data } = await charactersApi.extract(pasteText.trim())
      setExtractedChars(data.characters)
      message.success(`识别到 ${data.count} 个汉字`)
    } catch {
      message.error('提取失败')
    } finally {
      setLoading('extract', false)
    }
  }

  // Voice (ASR) — same pattern as AddWordsPage
  const startListening = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioCtxRef.current = new AudioContext({ sampleRate: 16000 })
      const source = audioCtxRef.current.createMediaStreamSource(stream)
      const processor = audioCtxRef.current.createScriptProcessor(4096, 1, 1)
      pcmChunksRef.current = []
      source.connect(processor)
      processor.connect(audioCtxRef.current.destination)
      processor.onaudioprocess = (e) => {
        pcmChunksRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      }
      setIsRecording(true)
    } catch {
      message.error('无法访问麦克风')
    }
  }

  const stopListening = async () => {
    setIsRecording(false)
    if (audioCtxRef.current) {
      await audioCtxRef.current.close()
      audioCtxRef.current = null
    }

    const chunks = pcmChunksRef.current
    if (chunks.length === 0) return
    const totalLen = chunks.reduce((s, c) => s + c.length, 0)
    const merged = new Float32Array(totalLen)
    let offset = 0
    for (const c of chunks) { merged.set(c, offset); offset += c.length }

    const int16 = new Int16Array(merged.length)
    for (let i = 0; i < merged.length; i++) {
      int16[i] = Math.max(-32768, Math.min(32767, Math.round(merged[i] * 32767)))
    }

    const wav = buildWav(int16, 16000)
    const file = new File([wav], 'recording.wav', { type: 'audio/wav' })

    setLoading('asr', true)
    try {
      const { data } = await asrApi.recognize(file)
      if (data.text) {
        const chars = [...new Set(data.text.replace(/[^一-鿿]/g, '').split(''))]
        setExtractedChars(prev => [...new Set([...prev, ...chars])])
        message.success(`识别: ${data.text}`)
      } else {
        message.info('未识别到文字')
      }
    } catch (err: any) {
      message.error(`语音识别失败: ${err?.response?.data?.detail || err?.message || '未知错误'}`)
    } finally {
      setLoading('asr', false)
    }
  }

  const handleSave = async () => {
    const chars = getCharList()
    if (chars.length === 0) { message.warning('请先输入已认识的字'); return }

    setLoading('save', true)
    try {
      await zonesApi.addAlly({ characters: chars, source: 'manual' })
      message.success(`已录入 ${chars.length} 个字到友军区`)
      setManualChars('')
      setPasteText('')
      setExtractedChars([])
      loadAllyChars()
    } catch (err: any) {
      message.error(`保存失败: ${err?.response?.data?.detail || err?.message || '网络连接失败'}`)
    } finally {
      setLoading('save', false)
    }
  }

  const handleDelete = async (char: string) => {
    try {
      await zonesApi.deleteAlly(char)
      message.success(`已删除「${char}」`)
      loadAllyChars()
    } catch {
      message.error('删除失败')
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>已学生字</h1>
        <p>录入俊宜在学校、生活中已经认识的字</p>
      </div>

      {/* Input section */}
      <div style={{ marginBottom: 24, background: '#fff', padding: 20, borderRadius: 8, border: '1px solid #f0f0f0' }}>
        <Radio.Group value={inputMode} onChange={(e) => setInputMode(e.target.value)} style={{ marginBottom: 16 }}>
          <Radio.Button value="manual">手动输入</Radio.Button>
          <Radio.Button value="paste">复制粘贴</Radio.Button>
          <Radio.Button value="voice">语音录入</Radio.Button>
        </Radio.Group>

        {inputMode === 'manual' && (
          <div>
            <Input.TextArea
              value={manualChars}
              onChange={(e) => setManualChars(e.target.value)}
              placeholder="输入已认识的字，用逗号、空格分隔，或直接连续输入"
              rows={3}
              style={{ marginBottom: 12 }}
            />
          </div>
        )}

        {inputMode === 'paste' && (
          <div>
            <Input.TextArea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="粘贴课文段落或生字表..."
              rows={3}
              style={{ marginBottom: 12 }}
            />
            <Button onClick={handleExtract} loading={loading['extract']}>提取汉字</Button>
            {extractedChars.length > 0 && (
              <div style={{ marginTop: 12 }}>
                {extractedChars.map((c, i) => (
                  <Tag key={i} closable onClose={() => setExtractedChars(prev => prev.filter((_, j) => j !== i))}
                       style={{ fontSize: 16, margin: 4, padding: '2px 8px' }}>
                    {c}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        )}

        {inputMode === 'voice' && (
          <div>
            <Button
              icon={<AudioOutlined />}
              type={isRecording ? 'primary' : 'default'}
              danger={isRecording}
              onClick={isRecording ? stopListening : startListening}
              loading={loading['asr']}
            >
              {isRecording ? '停止录音' : '开始录音'}
            </Button>
            {extractedChars.length > 0 && (
              <div style={{ marginTop: 12 }}>
                {extractedChars.map((c, i) => (
                  <Tag key={i} closable onClose={() => setExtractedChars(prev => prev.filter((_, j) => j !== i))}
                       style={{ fontSize: 16, margin: 4, padding: '2px 8px' }}>
                    {c}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        )}

        <Button type="primary" icon={<PlusOutlined />} onClick={handleSave}
                loading={loading['save']} style={{ marginTop: 12 }}>
          加入友军区
        </Button>
      </div>

      {/* Ally char list */}
      <Spin spinning={loading['known']}>
        <div style={{ background: '#fff', padding: 20, borderRadius: 8, border: '1px solid #f0f0f0' }}>
          <h3 style={{ marginBottom: 16 }}>友军区（{allyChars.length} 个字）</h3>
          {allyChars.length === 0 ? (
            <p style={{ color: '#bbb' }}>还没有录入已认识的字</p>
          ) : (
            <List
              dataSource={allyChars}
              renderItem={(item) => (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f5f5f5' }}>
                  <span>
                    <span style={{ fontSize: 20, fontWeight: 600, marginRight: 8 }}>{item.character}</span>
                    {item.pinyin && <span style={{ color: '#999', fontSize: 13 }}>{item.pinyin}</span>}
                    <Tag style={{ marginLeft: 8, fontSize: 11 }}>
                      {item.source === 'auto_promoted' ? '系统发现' : '手动录入'}
                    </Tag>
                  </span>
                  <Popconfirm title={`确定删除「${item.character}」？`} onConfirm={() => handleDelete(item.character)}>
                    <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                  </Popconfirm>
                </div>
              )}
            />
          )}
        </div>
      </Spin>
    </div>
  )
}

// WAV builder helper
function buildWav(pcm: Int16Array, sampleRate: number): ArrayBuffer {
  const byteCount = pcm.length * 2
  const buf = new ArrayBuffer(44 + byteCount)
  const v = new DataView(buf)
  writeStr(v, 0, 'RIFF'); v.setUint32(4, 36 + byteCount, true)
  writeStr(v, 8, 'WAVE'); writeStr(v, 12, 'fmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true)
  v.setUint16(22, 1, true); v.setUint32(24, sampleRate, true)
  v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true)
  v.setUint16(34, 16, true); writeStr(v, 36, 'data')
  v.setUint32(40, byteCount, true)
  const intView = new Int16Array(buf, 44)
  intView.set(pcm)
  return buf
}

function writeStr(v: DataView, offset: number, s: string) {
  for (let i = 0; i < s.length; i++) v.setUint8(offset + i, s.charCodeAt(i))
}
