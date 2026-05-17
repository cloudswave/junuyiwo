import { useState, useEffect, useRef } from 'react'
import { Button, Input, message, Popconfirm, Empty, Tag } from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  AudioOutlined,
  PlayCircleOutlined,
  AudioMutedOutlined,
  SoundOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons'
import { voiceApi, type VoiceProfileResponse } from '../services/api'

export default function VoiceManagePage() {
  const [profiles, setProfiles] = useState<VoiceProfileResponse[]>([])
  const [newName, setNewName] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  // Selected profile for recording mode
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [recordedChars, setRecordedChars] = useState<string[]>([])

  // New char input
  const [inputChar, setInputChar] = useState('')

  // Recording state
  const [recordingChar, setRecordingChar] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  // Playing state
  const [playingChar, setPlayingChar] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Reference audio (voice cloning) state
  const [refRecording, setRefRecording] = useState(false)
  const [refPromptText, setRefPromptText] = useState('')
  const refMediaRecorderRef = useRef<MediaRecorder | null>(null)
  const refChunksRef = useRef<Blob[]>([])
  const refInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => { loadProfiles() }, [])

  useEffect(() => {
    if (selectedId) loadRecordedChars(selectedId)
  }, [selectedId])

  const loadProfiles = async () => {
    try {
      const { data } = await voiceApi.listProfiles()
      setProfiles(data)
    } catch { /* ignore */ }
  }

  const loadRecordedChars = async (profileId: number) => {
    try {
      const { data } = await voiceApi.listRecordedChars(profileId)
      setRecordedChars(data)
    } catch { setRecordedChars([]) }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await voiceApi.createProfile(newName.trim())
      setNewName('')
      setShowCreate(false)
      message.success('已创建')
      await loadProfiles()
    } catch {
      message.error('创建失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await voiceApi.deleteProfile(id)
      if (selectedId === id) { setSelectedId(null); setRecordedChars([]) }
      await loadProfiles()
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  // === Per-character recording ===
  const startRecordChar = async (char: string) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      message.error('浏览器不支持录音')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const file = new File([blob], 'audio.webm', { type: 'audio/webm' })
        try {
          await voiceApi.uploadCharAudio(selectedId!, char, file)
          message.success(`「${char}」录音已保存`)
          await loadRecordedChars(selectedId!)
          await loadProfiles()
        } catch {
          message.error('保存失败')
        } finally {
          setRecordingChar(null)
        }
      }

      mediaRecorder.start()
      setRecordingChar(char)
    } catch (err: any) {
      const name = err?.name || ''
      if (name === 'NotAllowedError') {
        message.error('麦克风权限被拒绝，请用 localhost 访问并在弹窗中允许')
      } else if (name === 'NotFoundError') {
        message.error('未检测到麦克风设备')
      } else {
        message.error(`无法访问麦克风: ${err?.message || '未知错误'}`)
      }
    }
  }

  const stopRecordChar = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
  }

  const playChar = (profileId: number, char: string) => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    const audio = new Audio(`/api/audio/${profileId}/${encodeURIComponent(char)}.webm`)
    audio.onended = () => setPlayingChar(null)
    audio.onerror = () => { setPlayingChar(null); message.error('播放失败') }
    audio.play().catch(() => setPlayingChar(null))
    audioRef.current = audio
    setPlayingChar(char)
  }

  const deleteChar = async (profileId: number, char: string) => {
    try {
      await voiceApi.deleteCharAudio(profileId, char)
      await loadRecordedChars(profileId)
      await loadProfiles()
    } catch {
      message.error('删除失败')
    }
  }

  const handleAddChar = async () => {
    const ch = inputChar.trim()
    if (!ch) return
    // Take only first character
    const firstChar = ch[0]
    if (recordedChars.includes(firstChar)) {
      message.warning('该字已录音')
      setInputChar('')
      return
    }
    // Auto start recording
    setInputChar('')
    await startRecordChar(firstChar)
  }

  const selectedProfile = profiles.find(p => p.id === selectedId)

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>真人录音</h1>
        <p>录制真人发音，点字时优先播放录音而非机器合成音。比如录妈妈的声音，孩子听到的是妈妈念的字。</p>
      </div>

      {/* Profile list or recording panel */}
      {!selectedId ? (
        <>
          {/* Toolbar */}
          <div style={{ marginBottom: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
            {showCreate ? (
              <>
                <Input
                  style={{ width: 180 }}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="如：妈妈的声音"
                  onPressEnter={handleCreate}
                  autoFocus
                />
                <Button type="primary" onClick={handleCreate} icon={<PlusOutlined />}>添加</Button>
                <Button onClick={() => { setShowCreate(false); setNewName('') }}>取消</Button>
              </>
            ) : (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreate(true)}>
                新建声音档案
              </Button>
            )}
          </div>

          {profiles.length === 0 ? (
            <Empty description="还没有声音档案，点击「新建声音档案」开始录制" />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {profiles.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  style={{
                    border: '1.5px solid #e8e8e8',
                    borderRadius: 12,
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    cursor: 'pointer',
                    transition: 'border-color 0.2s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#1890ff')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#e8e8e8')}
                >
                  <div style={{
                    width: 48, height: 48, borderRadius: '50%',
                    background: p.char_count > 0 ? '#e6f7ff' : '#f5f5f5',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
                  }}>
                    <SoundOutlined style={{ color: p.char_count > 0 ? '#1890ff' : '#bbb' }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 16 }}>{p.name}</div>
                    <div style={{ fontSize: 13, color: '#888' }}>
                      {p.char_count > 0 ? `已录 ${p.char_count} 个字` : '暂无录音'} · {p.created_at?.slice(0, 10)}
                    </div>
                  </div>
                  <Popconfirm
                    title="确定删除？"
                    onConfirm={(e) => { e?.stopPropagation(); handleDelete(p.id) }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      size="small"
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {/* Recording mode for selected profile */}
          <div style={{ marginBottom: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
            <Button onClick={() => { setSelectedId(null); setRecordedChars([]) }}>← 返回</Button>
            <span style={{ fontSize: 18, fontWeight: 600 }}>{selectedProfile?.name}</span>
            <Tag color="blue">{recordedChars.length} 个字已录音</Tag>
          </div>

          {/* Add character */}
          <div style={{
            background: '#fafafa', border: '1px solid #e8e8e8', borderRadius: 12,
            padding: 20, marginBottom: 24,
          }}>
            <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 15 }}>录入新字发音</div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Input
                style={{ width: 120, fontSize: 22, textAlign: 'center' }}
                value={inputChar}
                onChange={(e) => setInputChar(e.target.value)}
                onPressEnter={handleAddChar}
                placeholder="字"
                maxLength={1}
                disabled={recordingChar !== null}
              />
              {recordingChar ? (
                <Button
                  danger
                  type="primary"
                  icon={<AudioMutedOutlined />}
                  onClick={stopRecordChar}
                  size="large"
                >
                  停止录音
                </Button>
              ) : (
                <Button
                  type="primary"
                  icon={<AudioOutlined />}
                  onClick={handleAddChar}
                  size="large"
                  disabled={!inputChar.trim()}
                >
                  录入发音
                </Button>
              )}
              <span style={{ fontSize: 13, color: '#999' }}>
                输入一个汉字，点击"录入发音"开始录音，说完后点击停止
              </span>
            </div>
            {recordingChar && (
              <div style={{ marginTop: 12, color: '#ff4d4f', fontWeight: 600, fontSize: 18, textAlign: 'center' }}>
                ● 正在录制「{recordingChar}」...
              </div>
            )}
          </div>

          {/* Recorded chars grid */}
          {recordedChars.length === 0 ? (
            <Empty description="该档案下还没有录音，请输入汉字并录入发音" />
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {recordedChars.map((ch) => {
                const isPlaying = playingChar === ch
                const isRecording = recordingChar === ch
                return (
                  <div
                    key={ch}
                    style={{
                      border: isRecording ? '2px solid #ff4d4f' : '1.5px solid #d9d9d9',
                      borderRadius: 10,
                      padding: '8px 12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      background: isPlaying ? '#e6f7ff' : '#fff',
                      minWidth: 80,
                      justifyContent: 'center',
                    }}
                  >
                    <span style={{ fontSize: 28, fontWeight: 600, lineHeight: 1 }}>{ch}</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <Button
                        type="text"
                        size="small"
                        icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                        onClick={() => playChar(selectedId!, ch)}
                      />
                      <Popconfirm title="删除此录音？" onConfirm={() => deleteChar(selectedId!, ch)}>
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
