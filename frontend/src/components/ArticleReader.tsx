import { useState, useMemo, useEffect, useCallback, useRef } from 'react'
import { Button, Input, Modal, message } from 'antd'
import { PrinterOutlined, ExpandOutlined, SoundOutlined, EditOutlined, PauseCircleOutlined, PlayCircleOutlined, StopOutlined, QuestionCircleOutlined, ReadOutlined } from '@ant-design/icons'
import type { PinyinToken, RecentCharInfo } from '../services/api'
import { charactersApi, behaviorApi, articlesApi, readStatusApi, curiosityApi, feedbackApi } from '../services/api'

// 开发模式用相对路径（Vite proxy），生产默认同源相对路径，APK 用 VITE_API_HOST 覆盖
const API_HOST = import.meta.env.VITE_API_HOST
const API_BASE = import.meta.env.DEV ? '' : (API_HOST || '')

// 点字发声：浏览器端音频缓存（Blob URL），避免每次 HTTP 请求
const audioBlobCache = new Map<string, string>()

// 图片路径：开发模式用相对路径（Vite proxy），APK 用绝对路径
function resolveImageUrl(path: string): string {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return API_BASE + path
}

interface InlineImage {
  url: string
  after_para: number
}

interface Props {
  paragraphs: PinyinToken[][]
  topic: string
  imageUrl?: string | null
  images?: InlineImage[]
  characters?: string[]
  articleId?: number
  seriesId?: number | null
  chapterNumber?: number | null
  totalChapters?: number | null
  onNextChapter?: () => void
  onStopSeries?: () => void
}

// Speech synthesis utility
let synthInitialized = false
function speakChar(char: string, pinyinOverride?: string) {
  const synth = window.speechSynthesis
  if (!synthInitialized) {
    synth.cancel()
    synthInitialized = true
  }
  synth.cancel()
  const utter = new SpeechSynthesisUtterance(pinyinOverride || char)
  utter.lang = 'zh-CN'
  utter.rate = 0.85
  utter.volume = 1
  synth.speak(utter)
}

// Web Audio tap sound — instant melodic "ding"
let audioCtx: AudioContext | null = null
function playTapSound() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
    if (audioCtx.state === 'suspended') audioCtx.resume()
    const osc = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    osc.connect(gain)
    gain.connect(audioCtx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, audioCtx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(660, audioCtx.currentTime + 0.12)
    gain.gain.setValueAtTime(0.25, audioCtx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15)
    osc.start(audioCtx.currentTime)
    osc.stop(audioCtx.currentTime + 0.15)
  } catch { /* Web Audio not available */ }
}

// Topic keywords -> fun emoji + gradient mapping
const TOPIC_EMOJI_MAP: [string[], string, string[]][] = [
  [['春天', '花', '草', '鸟', '太阳', '花园'], '🌸', ['#FFF5E6', '#E8F5E9', '#FFF9C4']],
  [['农场', '动物', '猫', '狗', '鱼', '鸡', '鸭', '马', '牛', '羊', '兔'], '🐮', ['#E8F5E9', '#FFF3E0', '#E1F5FE']],
  [['学校', '老师', '同学', '书', '学', '课', '教室'], '📚', ['#E3F2FD', '#FFF8E1', '#F3E5F5']],
  [['家', '爸爸', '妈妈', '爷爷', '奶奶', '家庭', '爱'], '🏠', ['#FFF3E0', '#FCE4EC', '#E8EAF6']],
  [['海', '水', '鱼', '船', '沙滩', '夏天'], '🌊', ['#E0F7FA', '#B2EBF2', '#E1F5FE']],
  [['森林', '树', '山', '星星', '月亮', '天空'], '🌳', ['#E8F5E9', '#C8E6C9', '#DCEDC8']],
  [['食物', '吃', '水果', '苹果', '香蕉', '饭', '菜'], '🍎', ['#FFF8E1', '#FFECB3', '#FFF3E0']],
  [['车', '火车', '飞机', '路', '交通', '旅行'], '🚂', ['#E3F2FD', '#BBDEFB', '#E8EAF6']],
  [['雨', '云', '风', '雪', '天气'], '🌈', ['#ECEFF1', '#E0E0E0', '#F3E5F5']],
  [['朋友', '玩', '快乐', '开心', '笑'], '🎈', ['#FCE4EC', '#F8BBD0', '#FFF9C4']],
  [['梦', '魔法', '公主', '王子', '城堡'], '🏰', ['#F3E5F5', '#E1BEE7', '#EDE7F6']],
  [['运动', '跑', '跳', '球', '游戏'], '⚽', ['#E8F5E9', '#C8E6C9', '#FFF3E0']],
]

function getTopicEmoji(topic: string): { emoji: string; colors: string[] } {
  for (const [keywords, emoji, colors] of TOPIC_EMOJI_MAP) {
    if (keywords.some((k) => topic.includes(k))) {
      return { emoji, colors }
    }
  }
  const defaults = ['🌟', '🎨', '🎵', '💫', '🌈', '🦋', '🌻', '🎪']
  return {
    emoji: defaults[Math.floor(topic.length % defaults.length)],
    colors: ['#FFF8E1', '#E8F5E9', '#E3F2FD'],
  }
}

function CoverDisplay({ topic, imageUrl }: { topic: string; imageUrl?: string | null }) {
  const [realImgOk, setRealImgOk] = useState(false)
  const { emoji, colors } = useMemo(() => getTopicEmoji(topic), [topic])

  useEffect(() => {
    setRealImgOk(false)
    if (!imageUrl) return
    const img = new Image()
    img.onload = () => setRealImgOk(true)
    img.onerror = () => setRealImgOk(false)
    img.src = resolveImageUrl(imageUrl)
  }, [imageUrl])

  if (realImgOk && imageUrl) {
    return (
      <div className="article-cover">
        <img src={resolveImageUrl(imageUrl)} alt={topic} className="article-cover-img-real" />
      </div>
    )
  }

  return (
    <div
      className="article-cover-emoji"
      style={{ background: `linear-gradient(135deg, ${colors[0]} 0%, ${colors[1]} 50%, ${colors[2]} 100%)` }}
    >
      <div className="article-cover-emoji-big">{emoji}</div>
      <div className="article-cover-emoji-topic">{topic}</div>
      <div className="article-cover-emoji-stars">
        {['⭐', '✨', '🌟', '💫'].map((s, i) => (
          <span key={i} className="cover-sparkle" style={{ animationDelay: `${i * 0.3}s` }}>
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}

function InlineImageDisplay({ url }: { url: string }) {
  return (
    <div className="article-inline-img-wrapper">
      <img src={resolveImageUrl(url)} alt="插图" className="article-inline-img" />
    </div>
  )
}

/** 学习字的分级 CSS class */
function charTierClass(daysAgo: number | undefined): string {
  if (daysAgo === undefined) return ''
  if (daysAgo === 0) return 'char-tier-today'
  if (daysAgo <= 3) return 'char-tier-recent'
  if (daysAgo <= 7) return 'char-tier-older'
  return ''
}

/** 学习字的分级 CSS class（打印用） */
function charTierPrintClass(daysAgo: number | undefined): string {
  if (daysAgo === undefined) return ''
  if (daysAgo === 0) return 'char-highlight'
  if (daysAgo <= 7) return 'char-highlight-recent'
  return ''
}

export default function ArticleReader({ paragraphs, topic, imageUrl, images = [], characters = [], articleId, seriesId, chapterNumber, totalChapters, onNextChapter, onStopSeries }: Props) {
  const [fullscreen, setFullscreen] = useState(false)
  const [tappedKey, setTappedKey] = useState<string | null>(null)
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Revise modal
  const [reviseOpen, setReviseOpen] = useState(false)
  const [reviseText, setReviseText] = useState('')
  const [revising, setRevising] = useState(false)
  const [revisedParagraphs, setRevisedParagraphs] = useState<PinyinToken[][] | null>(null)

  // Question modal (阅读中提问)
  const [questionOpen, setQuestionOpen] = useState(false)
  const [questionText, setQuestionText] = useState('')
  const [questionSubmitting, setQuestionSubmitting] = useState(false)
  const [feedbackGiven, setFeedbackGiven] = useState<string | null>(null)

  const handleAskQuestion = async () => {
    if (!questionText.trim()) return
    setQuestionSubmitting(true)
    try {
      await curiosityApi.createEvent({
        event_date: new Date().toISOString().slice(0, 10),
        raw_text: `[关于《${topic}》] ${questionText.trim()}`,
      })
      message.success('收到！你的问题已经记下来了～')
      setQuestionText('')
      setQuestionOpen(false)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '提交失败')
    } finally {
      setQuestionSubmitting(false)
    }
  }

  const handleFeedback = async (type: 'too_easy' | 'too_hard') => {
    if (!articleId) return
    try {
      await feedbackApi.submit({ article_id: articleId, feedback: type, topic })
      setFeedbackGiven(type)
      message.success(type === 'too_easy' ? '收到！下次会更有深度' : '收到！下次会简单一些')
    } catch { message.error('反馈失败') }
  }

  // Revise handler

  // Immersive reading
  const [readParaCount, setReadParaCount] = useState(0)
  const [showCelebration, setShowCelebration] = useState(false)
  const [readingAloud, setReadingAloud] = useState(false)
  const [aloudPaused, setAloudPaused] = useState(false)
  const [aloudParaIdx, setAloudParaIdx] = useState(-1)
  const [showAllPinyin, setShowAllPinyin] = useState(false)
  const aloudIdxRef = useRef(0)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const articleRef = useRef<HTMLDivElement | null>(null)

  // Today's characters: from prop (字库1)
  const todaySet = useMemo(() => new Set(characters), [characters])



  // TTS 预加载：文章加载时提前生成+缓存所有生字音频
  useEffect(() => {
    const allChars = paragraphs.flatMap(p => p.filter(t => t.pinyin).map(t => t.char))
    const unique = [...new Set(allChars)].slice(0, 30)
    if (unique.length === 0) return

    // 触发后端预热
    fetch(`${API_BASE}/api/tts/preload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chars: unique }),
    }).catch(() => {})

    // 逐个拉取音频并缓存 Blob URL
    const fetchOne = (char: string) => {
      const cacheKey = `e_${char}`
      if (audioBlobCache.has(cacheKey)) return Promise.resolve()
      return fetch(`${API_BASE}/api/tts/speak/${encodeURIComponent(char)}`)
        .then(r => r.blob())
        .then(blob => { audioBlobCache.set(cacheKey, URL.createObjectURL(blob)) })
        .catch(() => {})
    }

    // 串行拉取前几个（避免并发打爆后端），剩余后台慢慢拉
    const head = unique.slice(0, 8)
    const tail = unique.slice(8)
    head.reduce((p, c) => p.then(() => fetchOne(c)), Promise.resolve())
    tail.forEach(c => fetchOne(c))
  }, [paragraphs])

  // Recent characters from API: {char: {d: daysAgo, t: tier}}
  const [recentChars, setRecentChars] = useState<Record<string, RecentCharInfo>>({})
  useEffect(() => {
    charactersApi.getRecentDates(7).then(({ data }) => setRecentChars(data)).catch((err) => { console.error('getRecentDates failed:', err) })
  }, [characters])


  // All known chars: daysAgo map (字库1 + 字库2 merged)
  const allKnown = useMemo(() => {
    const m: Record<string, number> = {}
    for (const [char, info] of Object.entries(recentChars)) {
      m[char] = info.d
    }
    for (const c of characters) {
      if (!(c in m)) m[c] = 0
    }
    return m
  }, [recentChars, characters])

  // Scout zone chars (t: 0, 系统发现) — 浅灰色背景标识
  const scoutSet = useMemo(() => {
    const s = new Set<string>()
    for (const [char, info] of Object.entries(recentChars)) {
      if (info.t === 0) s.add(char)
    }
    return s
  }, [recentChars])


  // Pinyin editing for multi-tone characters
  const [pinyinOverrides, setPinyinOverrides] = useState<Record<string, string>>({})
  const [editingPinyin, setEditingPinyin] = useState<{ key: string; original: string } | null>(null)
  const pinyinOverridesRef = useRef(pinyinOverrides)
  pinyinOverridesRef.current = pinyinOverrides

  // Ref for handleCharTap to avoid stale closure
  const allKnownRef = useRef(allKnown)
  allKnownRef.current = allKnown

  useEffect(() => {
    try {
      const saved = localStorage.getItem(`py_ov_${topic}`)
      if (saved) setPinyinOverrides(JSON.parse(saved))
    } catch { /* ignore */ }
  }, [topic])

  useEffect(() => {
    const keys = Object.keys(pinyinOverrides)
    if (keys.length > 0) {
      localStorage.setItem(`py_ov_${topic}`, JSON.stringify(pinyinOverrides))
    } else {
      localStorage.removeItem(`py_ov_${topic}`)
    }
  }, [pinyinOverrides, topic])

  const handleCharTap = useCallback((char: string, key: string) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    playTapSound()
    setTappedKey(key)

    const cacheKey = `e_${char}`
    const cached = audioBlobCache.get(cacheKey)
    if (cached) {
      const audio = new Audio(cached)
      audio.play().catch(() => speakChar(char))
      timerRef.current = setTimeout(() => setTappedKey(null), 550)
      if (articleId) {
        behaviorApi.report({ article_id: articleId, character: char, action_type: 'char_tap' }).catch(() => {})
      }
      return
    }

    const audioSrc = `${API_BASE}/api/tts/speak/${encodeURIComponent(char)}`
    fetch(audioSrc)
      .then(r => { if (!r.ok) throw new Error('http ' + r.status); return r.blob() })
      .then(b => {
        const url = URL.createObjectURL(b)
        audioBlobCache.set(cacheKey, url)
        const audio = new Audio(url)
        return audio.play()
      })
      .catch(() => speakChar(char))

    timerRef.current = setTimeout(() => setTappedKey(null), 550)

    if (articleId) {
      behaviorApi.report({ article_id: articleId, character: char, action_type: 'char_tap' }).catch(() => {})
    }
  }, [])
  const renderPinyinCell = (key: string, pinyin: string) => {
    const editing = editingPinyin?.key === key
    const display = pinyinOverrides[key] || pinyin
    const edited = !!pinyinOverrides[key]
    const tapped = tappedKey === key
    const visible = edited || showAllPinyin || tapped

    if (editing) {
      return (
        <input
          className="textbook-py-input"
          defaultValue={display}
          onBlur={(e) => {
            const val = e.target.value.trim()
            if (val && val !== pinyin) {
              setPinyinOverrides(prev => ({ ...prev, [key]: val }))
            } else {
              setPinyinOverrides(prev => {
                const next = { ...prev }
                delete next[key]
                return next
              })
            }
            setEditingPinyin(null)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
            if (e.key === 'Escape') setEditingPinyin(null)
          }}
          autoFocus
          onClick={(e) => e.stopPropagation()}
        />
      )
    }

    const cls = ['textbook-py']
    if (edited) {
      cls.push('textbook-py-edited')
    } else if (visible) {
      cls.push(tapped ? 'textbook-py-tap-reveal' : 'textbook-py-visible')
    } else {
      cls.push('textbook-py-hidden')
    }

    return (
      <span
        className={cls.join(' ')}
        onClick={(e) => {
          e.stopPropagation()
          setEditingPinyin({ key, original: pinyin })
        }}
        title="点击修改拼音"
      >
        {display}
      </span>
    )
  }

  // Build a map: paragraphIndex -> images to insert after
  const imageMap = useMemo(() => {
    const m = new Map<number, string[]>()
    for (const img of images) {
      const arr = m.get(img.after_para) || []
      arr.push(img.url)
      m.set(img.after_para, arr)
    }
    return m
  }, [images])

  const aloudAudioRef = useRef<HTMLAudioElement | null>(null)

  const handleReadAloud = () => {
    // 停止之前的播放
    if (aloudAudioRef.current) { aloudAudioRef.current.pause(); aloudAudioRef.current = null }
    setReadingAloud(false)
    setAloudPaused(false)
    setAloudParaIdx(-1)
    aloudIdxRef.current = 0

    setReadingAloud(true)
    setShowAllPinyin(true)

    const speakNext = async () => {
      if (aloudIdxRef.current >= displayParagraphs.length) {
        setReadingAloud(false)
        setAloudPaused(false)
        setAloudParaIdx(-1)
        setShowAllPinyin(false)
        return
      }
      setAloudParaIdx(aloudIdxRef.current)
      const plainText = displayParagraphs[aloudIdxRef.current].map((t) => t.char).join('')
      try {
        const resp = await fetch(`${API_BASE}/api/tts/speak-text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: plainText }),
        })
        const blob = await resp.blob()
        const audio = new Audio(URL.createObjectURL(blob))
        aloudAudioRef.current = audio
        audio.onended = () => {
          aloudIdxRef.current++
          speakNext()
        }
        audio.onerror = () => {
          aloudIdxRef.current++
          speakNext()
        }
        await audio.play()
      } catch {
        aloudIdxRef.current++
        speakNext()
      }
    }

    speakNext()
  }

  const handlePauseAloud = () => {
    if (aloudAudioRef.current) { aloudAudioRef.current.pause(); setAloudPaused(true) }
  }

  const handleResumeAloud = () => {
    if (aloudAudioRef.current) { aloudAudioRef.current.play(); setAloudPaused(false) }
  }

  const handleStopAloud = () => {
    if (aloudAudioRef.current) { aloudAudioRef.current.pause(); aloudAudioRef.current = null }
    setReadingAloud(false)
    setAloudPaused(false)
    setAloudParaIdx(-1)
    setShowAllPinyin(false)
    aloudIdxRef.current = 0
  }

  const handleRevise = async () => {
    if (!reviseText.trim() || !articleId) return
    setRevising(true)
    try {
      const { data } = await articlesApi.revise(articleId, reviseText.trim())
      message.success('文章已优化')
      setReviseOpen(false)
      setReviseText('')
      // 原地更新文章内容
      setRevisedParagraphs(data.paragraphs)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '修改失败'
      message.error(`修改失败: ${msg}`)
    } finally {
      setRevising(false)
    }
  }

  const handlePrint = () => {
    const win = window.open('', '_blank', 'width=900,height=700')
    if (!win) {
      message.error('请允许弹出窗口以打印')
      return
    }

    const bodyHtml = paragraphs.map((para, pi) => {
      let idx = 0
      const cells: string[] = []
      while (idx < para.length) {
        const t = para[idx]
        const wl = t.word_len || 0
        if (wl >= 2) {
          // Multi-char word — wrap as a unit
          const wordChars = para.slice(idx, idx + wl)
          const wordCells = wordChars.map((wt) => {
            const daysAgo = allKnown[wt.char]
            const tierCls = charTierPrintClass(daysAgo)
            const py = wt.pinyin || '&nbsp;'
            return `<span class="char-cell"><span class="py">${py}</span><span class="hz ${tierCls}">${wt.char}</span></span>`
          }).join('')
          cells.push(`<span class="word-group-print">${wordCells}</span>`)
          idx += wl
        } else if (t.pinyin) {
          const daysAgo = allKnown[t.char]
          const tierCls = charTierPrintClass(daysAgo)
          const py = t.pinyin || '&nbsp;'
          cells.push(`<span class="char-cell"><span class="py">${py}</span><span class="hz ${tierCls}">${t.char}</span></span>`)
          idx++
        } else {
          cells.push(`<span class="hz">${t.char}</span>`)
          idx++
        }
      }
      let html = `<p class="para">${cells.join('')}</p>`

      const imgs = imageMap.get(pi)
      if (imgs) {
        for (const url of imgs) {
          html += `<div class="inline-img"><img src="${resolveImageUrl(url)}" alt="插图" /></div>`
        }
      }
      return html
    }).join('\n')

    const { emoji } = getTopicEmoji(topic)
    const coverHtml = imageUrl
      ? `<div class="cover"><img src="${resolveImageUrl(imageUrl!)}" alt="${topic}" style="width:100%;max-width:480px;border-radius:12px;" /></div>`
      : `<div class="cover"><span class="cover-emoji">${emoji}</span></div>`

    win.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>${topic} - 俊宜识字</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: "PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;
    padding: 48px 56px;
    max-width: 900px;
    margin: 0 auto;
    background: #fff;
  }
  .cover { text-align:center; margin-bottom:24px; padding:32px; background:linear-gradient(135deg,#FFF8E1,#E8F5E9,#E3F2FD); border-radius:16px; }
  .cover-emoji { font-size:64px; }
  h1 { text-align:center; font-size:24px; margin-bottom:32px; letter-spacing:4px; }
  .para { text-align:justify; margin-bottom:20px; line-height:2.4; }
  .char-cell {
    display:inline-flex; flex-direction:column; align-items:center;
    vertical-align:baseline; margin:0 1px; min-width:28px;
  }
  .py { font-size:10px; color:#666; line-height:1.2; white-space:nowrap; }
  .hz { font-size:22px; line-height:1.3; font-weight:500; }
  .char-highlight {
    background: #d8f3dc;
    color: #e65100;
    border-radius: 3px;
  }
  .char-highlight-recent {
    background: #fff3e0;
    border-radius: 2px;
  }
  .word-group-print {
    display: inline;
    border-bottom: 1.5px dashed #95d5b2;
    padding-bottom: 1px;
  }
  .punct { font-size:22px; margin:0 1px; vertical-align:baseline; line-height:1.3; }
  .inline-img { text-align:center; margin:16px 0; }
  .inline-img img { max-width:80%; border-radius:12px; }
  .meta { text-align:center; color:#999; font-size:13px; margin-top:40px; }
  @media print { body { padding: 30px 40px; } }
</style>
<link href="https://fonts.googleapis.com/css2?family=ZCOOL+KuaiLe&display=swap" rel="stylesheet">
</head>
<body>
  ${coverHtml}
  <h1>${topic}</h1>
  ${bodyHtml}
  <div class="meta">俊宜识字系统 · ${new Date().toLocaleDateString('zh-CN')}</div>
</body>
</html>`)
    win.document.close()
    setTimeout(() => win.print(), 500)
  }

  const renderPara = (para: PinyinToken[], pIdx: number) => {
    const elements: React.ReactNode[] = []
    let i = 0
    while (i < para.length) {
      const t = para[i]
      if (t.pinyin) {
        const wl = t.word_len || 0
        if (wl >= 2) {
          // jieba-identified multi-char word
          const wordTokens = para.slice(i, i + wl)
          const hasToday = wordTokens.some(wt => todaySet.has(wt.char))
          elements.push(
            <span
              key={`w-${pIdx}-${i}`}
              className={hasToday ? 'textbook-word-group textbook-word-active' : 'textbook-word-group'}
            >
              {wordTokens.map((wt, wi) => {
                const daysAgo = allKnown[wt.char]
                const isScout = scoutSet.has(wt.char)
                const isToday = todaySet.has(wt.char)
                let tierCls = ''
                if (isToday) {
                  tierCls = 'char-tier-today'
                } else if (daysAgo !== undefined && !isScout) {
                  tierCls = charTierClass(daysAgo)
                }
                const extraCls = isScout ? ' char-tier-discovered' : ''
                const key = `w-${pIdx}-${i}-${wi}`
                const isTapped = tappedKey === key
                return (
                  <span key={wi} className={`textbook-char-cell${isTapped ? ' textbook-tap-flash textbook-speaking-glow' : ''}`} onClick={() => handleCharTap(wt.char, key)}>
                    {renderPinyinCell(key, wt.pinyin)}
                    <span className={`textbook-hz ${tierCls}${extraCls}`}>{wt.char}</span>
                  </span>
                )
              })}
            </span>
          )
          i += wl
        } else {
          // Single CJK char
          const daysAgo = allKnown[t.char]
          const isScout = scoutSet.has(t.char)
          const isToday = todaySet.has(t.char)
          let tierCls = ''
          if (isToday) {
            tierCls = 'char-tier-today'
          } else if (daysAgo !== undefined && !isScout) {
            tierCls = charTierClass(daysAgo)
          }
          const extraCls = isScout ? ' char-tier-discovered' : ''
          const key = `c-${pIdx}-${i}`
          const isTapped = tappedKey === key
          elements.push(
            <span key={key} className={`textbook-char-cell${isTapped ? ' textbook-tap-flash' : ''}`} onClick={() => handleCharTap(t.char, key)}>
              {renderPinyinCell(key, t.pinyin)}
              <span className={`textbook-hz ${tierCls}${extraCls}`}>{t.char}</span>
            </span>
          )
          i++
        }
      } else {
        // Punctuation / non-CJK
        elements.push(
          <span key={`p-${pIdx}-${i}`} className="textbook-char-cell">
            <span className="textbook-py">{' '}</span>
            <span className="textbook-hz">{t.char}</span>
          </span>
        )
        i++
      }
    }
    return elements
  }

  const displayParagraphs = revisedParagraphs || paragraphs
  const totalParas = displayParagraphs.length
  const progressPercent = totalParas > 0 ? Math.round((readParaCount / totalParas) * 100) : 0

  // Paragraph entrance + reading progress observer
  useEffect(() => {
    if (displayParagraphs.length === 0) return
    const paraEls = articleRef.current?.querySelectorAll('.textbook-para')
    if (!paraEls || paraEls.length === 0) return

    const seen = new Set<number>()

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const idx = parseInt((entry.target as HTMLElement).dataset.paraIndex || '0')
          if (entry.isIntersecting) {
            entry.target.classList.add('para-visible')
            entry.target.classList.remove('para-seen')
            seen.add(idx)
          } else if (seen.has(idx)) {
            // 已经看过但滚出视口的 → 半透明保留
            entry.target.classList.add('para-seen')
            entry.target.classList.remove('para-visible')
          }
        }
        setReadParaCount(seen.size)
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' },
    )

    paraEls.forEach((el) => observerRef.current!.observe(el))

    return () => observerRef.current?.disconnect()
  }, [displayParagraphs])

  // Report reading status: started
  useEffect(() => {
    if (!articleId || displayParagraphs.length === 0) return
    readStatusApi.update(articleId, {
      status: 'reading',
      read_count: 0,
      total_count: displayParagraphs.length,
    }).catch(() => {})
  }, [articleId, displayParagraphs.length])

  // Report progress on scroll (debounced by IntersectionObserver)
  useEffect(() => {
    if (!articleId || readParaCount === 0) return
    readStatusApi.update(articleId, {
      status: 'reading',
      read_count: readParaCount,
      total_count: displayParagraphs.length,
    }).catch(() => {})
  }, [articleId, readParaCount])

  // Celebration when reading complete → mark as read, trigger auto-promotion
  useEffect(() => {
    if (readParaCount > 0 && readParaCount >= displayParagraphs.length && !showCelebration) {
      setShowCelebration(true)
      if (articleId) {
        readStatusApi.update(articleId, {
          status: 'read',
          read_count: displayParagraphs.length,
          total_count: displayParagraphs.length,
        }).catch(() => {})
      }
      const timer = setTimeout(() => setShowCelebration(false), 3000)
      return () => clearTimeout(timer)
    }
  }, [readParaCount, displayParagraphs.length])

  const renderProgressBar = () => (
    <div className="reading-progress-bar-container no-print">
      <div className="reading-progress-bar-fill" style={{ width: `${progressPercent}%` }}>
        {progressPercent >= 25 && <span className="reading-progress-milestone" style={{ left: '25%' }}>📖</span>}
        {progressPercent >= 50 && <span className="reading-progress-milestone" style={{ left: '50%' }}>📚</span>}
        {progressPercent >= 75 && <span className="reading-progress-milestone" style={{ left: '75%' }}>🌟</span>}
        {progressPercent >= 100 && <span className="reading-progress-milestone" style={{ right: 0 }}>🎉</span>}
      </div>
    </div>
  )

  const renderContent = (maxHeight?: string) => (
    <div style={maxHeight ? { maxHeight, overflow: 'auto' } : undefined}>
      {displayParagraphs.map((para, pi) => (
        <div key={pi}>
          <p className={`textbook-para${aloudParaIdx === pi ? ' textbook-para-aloud' : ''}`} data-para-index={pi} style={{ transitionDelay: `${pi * 0.08}s` }}>
            {renderPara(para, pi)}
          </p>
          {imageMap.get(pi)?.map((url, idx) => (
            <InlineImageDisplay key={`${pi}-${idx}`} url={url} />
          ))}
        </div>
      ))}
    </div>
  )

  return (
    <div>
      <div className="textbook-toolbar no-print">
        <span style={{ fontSize: 12, color: '#bbb', marginRight: 8, lineHeight: '24px' }}>
          <SoundOutlined style={{ marginRight: 4 }} />点字发声
        </span>
        <div style={{ flex: 1 }} />
        <Button icon={<ExpandOutlined />} size="small" onClick={() => setFullscreen(true)}>
          全屏阅读
        </Button>
        {!readingAloud ? (
          <Button icon={<SoundOutlined />} size="small" onClick={handleReadAloud} style={{ marginLeft: 8 }}>
            朗读全文
          </Button>
        ) : aloudPaused ? (
          <>
            <Button icon={<PlayCircleOutlined />} size="small" onClick={handleResumeAloud} style={{ marginLeft: 8 }}>
              继续
            </Button>
            <Button icon={<StopOutlined />} size="small" onClick={handleStopAloud} style={{ marginLeft: 8 }}>
              停止
            </Button>
          </>
        ) : (
          <>
            <Button icon={<PauseCircleOutlined />} size="small" onClick={handlePauseAloud} style={{ marginLeft: 8 }}>
              暂停
            </Button>
            <Button icon={<StopOutlined />} size="small" onClick={handleStopAloud} style={{ marginLeft: 8 }}>
              停止
            </Button>
          </>
        )}
        <Button icon={<QuestionCircleOutlined />} size="small" onClick={() => { setQuestionText(''); setQuestionOpen(true) }} style={{ marginLeft: 8 }}>
          提问
        </Button>
        <Button icon={<EditOutlined />} size="small" onClick={() => { setReviseText(''); setReviseOpen(true) }} style={{ marginLeft: 8 }}>
          修改建议
        </Button>
        <Button icon={<PrinterOutlined />} size="small" onClick={handlePrint} style={{ marginLeft: 8 }}>
          打印
        </Button>
      </div>

      {renderProgressBar()}
      <div className="textbook-article" ref={articleRef}>
        <CoverDisplay topic={topic} imageUrl={imageUrl} />
        {renderContent()}
      </div>

      {/* Celebration overlay */}
      {showCelebration && (
        <div className="celebration-overlay">
          {Array.from({ length: 20 }).map((_, i) => (
            <span
              key={i}
              className="celebration-particle"
              style={{
                left: `${Math.random() * 100}%`,
                animationDelay: `${Math.random() * 2}s`,
                fontSize: `${18 + Math.random() * 24}px`,
                bottom: `-${20 + Math.random() * 40}px`,
              }}
            >
              {['🎉', '⭐', '✨', '🌟', '💫', '🎊', '🎈', '💖', '🌈', '🏆'][i % 10]}
            </span>
          ))}
        </div>
      )}

      {/* Series Next Chapter */}
      {seriesId && chapterNumber && totalChapters && chapterNumber < totalChapters && (
        <div className="no-print" style={{
          textAlign: 'center', marginTop: 24, padding: '16px 24px',
          background: 'linear-gradient(135deg, #f6ffed 0%, #e6f7ff 100%)',
          borderRadius: 8, border: '1px solid #b7eb8f',
        }}>
          <div style={{ fontSize: 14, color: '#52c41a', fontWeight: 500, marginBottom: 8 }}>
            第{chapterNumber}/{totalChapters}章 · 下一章预告
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
            <Button type="primary" icon={<ReadOutlined />} onClick={onNextChapter}>
              继续阅读下一章
            </Button>
            <Button onClick={onStopSeries}>
              先不看了
            </Button>
          </div>
        </div>
      )}

      {/* Difficulty Feedback */}
      {articleId && (
        <div className="no-print" style={{
          display: 'flex', justifyContent: 'center', gap: 16,
          marginTop: 24, paddingTop: 16, borderTop: '1px dashed #e8e8e8',
        }}>
          <span style={{ color: '#999', fontSize: 12, lineHeight: '28px' }}>这篇文章：</span>
          {feedbackGiven === 'too_easy' ? (
            <span style={{ color: '#52c41a', fontSize: 13, lineHeight: '28px' }}>已反馈 · 下次会更有深度 ✓</span>
          ) : (
            <Button size="small" onClick={() => handleFeedback('too_easy')}>
              太简单了 👶
            </Button>
          )}
          {feedbackGiven === 'too_hard' ? (
            <span style={{ color: '#ff7a45', fontSize: 13, lineHeight: '28px' }}>已反馈 · 下次会简单一些 ✓</span>
          ) : (
            <Button size="small" onClick={() => handleFeedback('too_hard')}>
              太难了 🧠
            </Button>
          )}
        </div>
      )}

      <Modal
        title={topic}
        open={fullscreen}
        onCancel={() => setFullscreen(false)}
        footer={null}
        width={860}
        style={{ top: 20 }}
        styles={{ body: { padding: '32px 40px' } }}
      >
        <CoverDisplay topic={topic} imageUrl={imageUrl} />
        {renderContent('70vh')}
      </Modal>

      <Modal
        title="回炉修改"
        open={reviseOpen}
        onCancel={() => setReviseOpen(false)}
        onOk={handleRevise}
        confirmLoading={revising}
        okText="开始修改"
        cancelText="取消"
      >
        <p style={{ marginBottom: 12, color: '#555' }}>输入修改建议，AI 将根据建议优化文章：</p>
        <Input.TextArea
          value={reviseText}
          onChange={(e) => setReviseText(e.target.value)}
          placeholder="例如：把刘静怡改成俊宜、缩短到300字、增加对话..."
          rows={4}
        />
      </Modal>

      <Modal
        title={`提问：${topic}`}
        open={questionOpen}
        onCancel={() => setQuestionOpen(false)}
        onOk={handleAskQuestion}
        confirmLoading={questionSubmitting}
        okText="提交问题"
        cancelText="取消"
      >
        <p style={{ marginBottom: 12, color: '#555' }}>
          读到不懂的地方？写下你的问题，爸爸妈妈会用它给你写文章～
        </p>
        <Input.TextArea
          value={questionText}
          onChange={(e) => setQuestionText(e.target.value)}
          placeholder="例如：为什么星星会眨眼睛？太阳为什么是圆的？"
          rows={4}
        />
      </Modal>
    </div>
  )
}