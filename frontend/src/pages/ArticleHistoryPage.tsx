import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, List, Tag, Spin, Empty, Button, Popconfirm, message } from 'antd'
import { CalendarOutlined, DeleteOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { articlesApi, charactersApi, readStatusApi, ArticleResponse, ArticleWithPinyin } from '../services/api'
import { useStore } from '../store/useStore'
import ArticleReader from '../components/ArticleReader'

export default function ArticleHistoryPage() {
  const { date } = useParams()
  const navigate = useNavigate()
  const { articles, setArticles, loading, setLoading } = useStore()
  const [selectedArticle, setSelectedArticle] = useState<ArticleWithPinyin | null>(null)
  const [articleChars, setArticleChars] = useState<string[]>([])
  const [viewMode, setViewMode] = useState<'list' | 'detail'>(date ? 'detail' : 'list')
  const [readStatuses, setReadStatuses] = useState<Record<number, string>>({})

  useEffect(() => {
    if (date) {
      const id = parseInt(date)
      if (!isNaN(id)) {
        loadArticleById(id)
      }
    } else {
      loadAllArticles()
    }
  }, [date])

  const loadAllArticles = async () => {
    setLoading('articles', true)
    try {
      const { data } = await articlesApi.list()
      setArticles(data)
      // 批量获取阅读状态
      if (data.length > 0) {
        const ids = data.map((a: ArticleResponse) => a.id)
        readStatusApi.batchGet(ids).then(({ data: statuses }) => {
          const m: Record<number, string> = {}
          for (const [k, v] of Object.entries(statuses)) {
            m[parseInt(k)] = v as string
          }
          setReadStatuses(m)
        }).catch(() => {})
      }
    } catch {
      // ignore
    } finally {
      setLoading('articles', false)
    }
  }

  const loadArticleById = async (id: number) => {
    setLoading('article', true)
    try {
      const { data } = await articlesApi.getWithPinyin(id)
      setSelectedArticle(data)
      // Extract characters from the article content
      const chars = (data.content || '').match(/[\u4e00-\u9fff]/g) || []
      setArticleChars([...new Set(chars)])
    } catch {
      message.error('文章不存在')
      setViewMode('list')
    } finally {
      setLoading('article', false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await articlesApi.delete(id)
      message.success('已删除')
      loadAllArticles()
    } catch {
      message.error('删除失败')
    }
  }

  if (viewMode === 'detail' && selectedArticle) {
    return (
      <div className="page-container">
        <div style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => { setViewMode('list'); navigate('/articles') }}>
            返回列表
          </Button>
        </div>
        <Card
          title={selectedArticle.topic}
          extra={
            <Tag>{dayjs(selectedArticle.record_date).format('YYYY-MM-DD')}</Tag>
          }
        >
          <Spin spinning={loading['article']}>
            <ArticleReader
              paragraphs={selectedArticle.paragraphs}
              topic={selectedArticle.topic}
              imageUrl={selectedArticle.image_url}
              images={selectedArticle.images}
              characters={articleChars}
              articleId={selectedArticle.id}
              seriesId={(selectedArticle as any).series_id}
              chapterNumber={(selectedArticle as any).chapter_number}
              totalChapters={(selectedArticle as any).total_chapters}
            />
          </Spin>
        </Card>
      </div>
    )
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>历史文章</h1>
        <p>查看所有已生成的文章，支持打印和复习</p>
      </div>

      <Spin spinning={loading['articles']}>
        {articles.length === 0 ? (
          <Empty description="还没有生成过文章" image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button type="primary" onClick={() => navigate('/add')}>去生成第一篇文章</Button>
          </Empty>
        ) : (
          <List
            dataSource={articles}
            renderItem={(article) => (
              <Card
                key={article.id}
                hoverable
                style={{ marginBottom: 12 }}
                onClick={() => { setViewMode('detail'); navigate(`/article/${article.id}`) }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 18 }}>
                      {readStatuses[article.id] === 'read' ? '🟢' : readStatuses[article.id] === 'reading' ? '🟡' : '🔵'}
                    </span>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                        {article.topic}
                      </div>
                      <div style={{ color: '#888', fontSize: 13 }}>
                        <CalendarOutlined /> {article.record_date} · {article.character_count} 字 · {article.source === 'ai' ? 'AI生成' : '手动录入'}
                      </div>
                    </div>
                  </div>
                  <Popconfirm
                    title="确定删除这篇文章吗？"
                    onConfirm={(e) => { e?.stopPropagation(); handleDelete(article.id) }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              </Card>
            )}
          />
        )}
      </Spin>
    </div>
  )
}
