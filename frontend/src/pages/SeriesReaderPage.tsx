import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Menu, Spin, Empty, Button, Tag, Progress, message, Card } from 'antd'
import {
  BookOutlined, ReadOutlined, CheckCircleOutlined,
  ArrowLeftOutlined, PlayCircleOutlined,
} from '@ant-design/icons'
import { articlesApi, readStatusApi, type PinyinToken, type ArticleWithPinyin } from '../services/api'

const { Sider, Content } = Layout

interface ChapterItem {
  id: number
  chapter_number: number
  title: string
  character_count: number
  read_status: string
}

interface SeriesData {
  id: number
  topic: string
  status: string
  total_chapters: number
  current_chapter: number
  chapter_titles: Array<{ ch: number; title: string; summary: string }>
  chapters: ChapterItem[]
}

export default function SeriesReaderPage() {
  const { seriesId } = useParams()
  const navigate = useNavigate()
  const [series, setSeries] = useState<SeriesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [currentChapter, setCurrentChapter] = useState<ArticleWithPinyin | null>(null)
  const [chapterLoading, setChapterLoading] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    if (!seriesId) return
    setLoading(true)
    articlesApi.getSeries(parseInt(seriesId))
      .then(({ data }) => {
        setSeries(data)
        // Auto-select first unread chapter, or first chapter
        const firstUnread = data.chapters.find((c: ChapterItem) => c.read_status === 'unread')
        const toLoad = firstUnread || data.chapters[0]
        if (toLoad) loadChapter(toLoad.chapter_number)
      })
      .catch(() => message.error('加载系列失败'))
      .finally(() => setLoading(false))
  }, [seriesId])

  const loadChapter = async (chNum: number) => {
    setChapterLoading(true)
    try {
      const { data } = await articlesApi.getSeriesChapter(parseInt(seriesId!), chNum)
      setCurrentChapter(data)
      // Mark as reading
      readStatusApi.update(data.id, { status: 'reading', read_count: 0, total_count: 0 }).catch(() => {})
    } catch {
      message.error('加载章节失败')
    } finally {
      setChapterLoading(false)
    }
  }

  const handleChapterClick = (ch: ChapterItem) => {
    loadChapter(ch.chapter_number)
  }

  const handleFinishReading = (articleId: number) => {
    readStatusApi.update(articleId, { status: 'read', read_count: 0, total_count: 0 }).then(() => {
      setSeries(prev => {
        if (!prev) return prev
        return {
          ...prev,
          chapters: prev.chapters.map(c =>
            c.id === articleId ? { ...c, read_status: 'read' } : c
          ),
        }
      })
    }).catch(() => {})
  }

  if (loading || !series) return <Spin spinning style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />

  const readCount = series.chapters.filter(c => c.read_status === 'read').length
  const progress = Math.round((readCount / series.total_chapters) * 100)
  const currentCh = series.chapters.find(c => c.chapter_number === (currentChapter as any)?.chapter_number)

  return (
    <Layout style={{ minHeight: '100vh', background: '#fff' }}>
      {/* Chapter List Sidebar */}
      <Sider
        width={280}
        collapsedWidth={60}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ background: '#fafafa', borderRight: '1px solid #f0f0f0' }}
        breakpoint="lg"
      >
        <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
          {!collapsed && (
            <>
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={() => navigate('/curiosity')}
                style={{ marginBottom: 8 }}
              >
                返回
              </Button>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#333', lineHeight: 1.4 }}>
                {series.topic}
              </div>
              <div style={{ marginTop: 8 }}>
                <Progress percent={progress} size="small" status={progress === 100 ? 'success' : 'active'} />
                <span style={{ fontSize: 11, color: '#999' }}>{readCount}/{series.total_chapters} 章已读</span>
              </div>
              {series.status === 'completed' && progress === 100 && (
                <Tag color="green" style={{ marginTop: 4 }}>全部完成 ✓</Tag>
              )}
            </>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={currentCh ? [String(currentCh.chapter_number)] : []}
          style={{ border: 'none', background: 'transparent' }}
          items={series.chapters.map(ch => ({
            key: String(ch.chapter_number),
            icon: ch.read_status === 'read' ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : <ReadOutlined />,
            label: (
              <span>
                第{ch.chapter_number}章
                {!collapsed && (
                  <span style={{ fontSize: 12, color: '#888', marginLeft: 4 }}>
                    {ch.title.length > 20 ? ch.title.slice(0, 20) + '...' : ch.title}
                  </span>
                )}
              </span>
            ),
          }))}
          onClick={({ key }) => {
            const ch = series.chapters.find(c => c.chapter_number === parseInt(key))
            if (ch) handleChapterClick(ch)
          }}
        />
      </Sider>

      {/* Chapter Content */}
      <Content style={{ padding: '32px 48px', overflow: 'auto' }}>
        <Spin spinning={chapterLoading}>
          {currentChapter ? (
            <Card
              title={
                <span>
                  <Tag color="blue" style={{ marginRight: 8 }}>
                    第{currentChapter.chapter_number}章 / 共{series.total_chapters}章
                  </Tag>
                  {currentChapter.topic}
                </span>
              }
              extra={
                <Button
                  type="primary"
                  ghost
                  icon={<CheckCircleOutlined />}
                  onClick={() => handleFinishReading(currentChapter.id)}
                >
                  标记已读
                </Button>
              }
              style={{ maxWidth: 800, margin: '0 auto' }}
            >
              <div style={{
                fontSize: 20, lineHeight: 1.9, padding: '16px 24px',
                background: '#fafae8', borderRadius: 8, whiteSpace: 'pre-wrap',
                fontFamily: '"楷体", "KaiTi", serif',
              }}>
                {currentChapter.content}
              </div>

              {/* Chapter Navigation */}
              <div style={{
                display: 'flex', justifyContent: 'space-between', marginTop: 24,
                padding: '16px 24px', background: '#f6ffed', borderRadius: 8,
                border: '1px solid #b7eb8f',
              }}>
                <Button
                  disabled={!currentChapter.chapter_number || currentChapter.chapter_number <= 1}
                  onClick={() => {
                    if (currentChapter.chapter_number) loadChapter(currentChapter.chapter_number - 1)
                  }}
                >
                  上一章
                </Button>
                <span style={{ lineHeight: '32px', color: '#52c41a', fontWeight: 500 }}>
                  第{currentChapter.chapter_number}/{series.total_chapters}章
                </span>
                <Button
                  type="primary"
                  disabled={!currentChapter.chapter_number || currentChapter.chapter_number >= series.total_chapters}
                  onClick={() => {
                    if (currentChapter.chapter_number) loadChapter(currentChapter.chapter_number + 1)
                  }}
                  icon={<PlayCircleOutlined />}
                >
                  下一章
                </Button>
              </div>
            </Card>
          ) : (
            <Empty description="选择左侧章节开始阅读" />
          )}
        </Spin>
      </Content>
    </Layout>
  )
}
