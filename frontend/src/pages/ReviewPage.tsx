import { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Spin, Empty, Tag, Modal, Progress, message } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { reviewApi, ForgottenResponse } from '../services/api'
import { useStore } from '../store/useStore'

export default function ReviewPage() {
  const { forgottenItems, forgottenStats, setForgotten, loading, setLoading } = useStore()
  const [quizMode, setQuizMode] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showPinyin, setShowPinyin] = useState(false)
  const [results, setResults] = useState<{ char: string; correct: boolean }[]>([])
  const [filterLevel, setFilterLevel] = useState<string>('')

  useEffect(() => {
    loadForgotten()
  }, [filterLevel])

  const loadForgotten = async () => {
    setLoading('review', true)
    try {
      const { data } = await reviewApi.listForgotten(filterLevel || undefined)
      setForgotten(data.items, data.total)
    } catch {
      // ignore
    } finally {
      setLoading('review', false)
    }
  }

  const handleMarkLearned = async (id: number) => {
    try {
      await reviewApi.markLearned(id)
      message.success('已标记为学会')
      loadForgotten()
    } catch {
      message.error('操作失败')
    }
  }

  const startQuiz = () => {
    setQuizMode(true)
    setCurrentIndex(0)
    setShowPinyin(false)
    setResults([])
  }

  const handleQuizAnswer = (correct: boolean) => {
    const item = forgottenItems[currentIndex]
    setResults([...results, { char: item.character, correct }])

    if (currentIndex + 1 < forgottenItems.length) {
      setCurrentIndex(currentIndex + 1)
      setShowPinyin(false)
    } else {
      // Quiz complete
      const wrongChars = [...results, { char: item.character, correct }]
        .filter((r) => !r.correct)
        .map((r) => r.char)

      if (wrongChars.length > 0) {
        reviewApi.recordForgotten({
          date: new Date().toISOString().slice(0, 10),
          characters: wrongChars,
        }).then(() => loadForgotten())
      }

      Modal.info({
        title: '复习完成',
        content: `正确: ${results.filter(r => r.correct).length + (correct ? 1 : 0)} / ${forgottenItems.length}`,
        onOk: () => setQuizMode(false),
      })
    }
  }

  const levelColors: Record<string, string> = {
    '活跃': 'gold',
    '三次': 'orange',
    '五次以上': 'red',
    '已学会': 'green',
  }

  if (quizMode && forgottenItems.length > 0) {
    const item = forgottenItems[currentIndex]
    const progress = ((currentIndex + 1) / forgottenItems.length) * 100

    return (
      <div className="page-container">
        <div className="page-header">
          <h1>复习测试</h1>
          <p>{currentIndex + 1} / {forgottenItems.length}</p>
        </div>

        <Progress percent={Math.round(progress)} style={{ marginBottom: 24 }} />

        <Card style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 80, fontWeight: 700, marginBottom: 24, lineHeight: 1 }}>
            {item.character}
          </div>

          {showPinyin ? (
            <>
              <div style={{ fontSize: 28, color: '#4F46E5', marginBottom: 8 }}>
                {item.pinyin || '(无拼音)'}
              </div>
              <div style={{ color: '#888', marginBottom: 24 }}>
                遗忘 {item.forget_count} 次 · {item.level}
              </div>
            </>
          ) : (
            <div style={{ marginBottom: 24 }}>
              <Button size="large" onClick={() => setShowPinyin(true)} icon={<EyeOutlined />}>
                点击显示拼音
              </Button>
            </div>
          )}

          {showPinyin && (
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center' }}>
              <Button
                size="large"
                type="primary"
                icon={<CheckCircleOutlined />}
                style={{ background: '#52c41a', borderColor: '#52c41a' }}
                onClick={() => handleQuizAnswer(true)}
              >
                我认识了
              </Button>
              <Button
                size="large"
                danger
                icon={<CloseCircleOutlined />}
                onClick={() => handleQuizAnswer(false)}
              >
                还不认识
              </Button>
            </div>
          )}
        </Card>
      </div>
    )
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>复习</h1>
        <p>遗忘字卡片复习，温故而知新</p>
      </div>

      <Spin spinning={loading['review']}>
        {/* Level filter */}
        <Card style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ color: '#888' }}>筛选：</span>
            <Tag
              color={!filterLevel ? 'blue' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => setFilterLevel('')}
            >
              全部 ({forgottenItems.length})
            </Tag>
            {Object.entries(forgottenStats).map(([level, count]) => (
              <Tag
                key={level}
                color={filterLevel === level ? 'blue' : levelColors[level] || 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => setFilterLevel(filterLevel === level ? '' : level)}
              >
                {level} ({count})
              </Tag>
            ))}
          </div>
        </Card>

        {forgottenItems.length === 0 ? (
          <Empty description="太棒了，没有需要复习的生字！" image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button onClick={() => window.location.href = '/add'}>去学习新字</Button>
          </Empty>
        ) : (
          <>
            <div style={{ marginBottom: 16, textAlign: 'right' }}>
              <Button type="primary" size="large" icon={<ReloadOutlined />} onClick={startQuiz}>
                开始复习 ({forgottenItems.length} 字)
              </Button>
            </div>

            <div className="word-card-grid">
              {forgottenItems.map((item) => (
                <div
                  key={item.id}
                  className="word-card"
                  style={{
                    width: 100,
                    height: 100,
                    borderColor: levelColors[item.level] ? levelColors[item.level] : undefined,
                  }}
                  onClick={() => handleMarkLearned(item.id)}
                  title="点击标记为已学会"
                >
                  <span className="char">{item.character}</span>
                  <span className="pinyin">{item.pinyin || '?'}</span>
                  <Tag
                    color={levelColors[item.level] || 'default'}
                    style={{ fontSize: 10, marginTop: 2, lineHeight: '16px' }}
                  >
                    {item.forget_count}次
                  </Tag>
                </div>
              ))}
            </div>
          </>
        )}
      </Spin>
    </div>
  )
}
