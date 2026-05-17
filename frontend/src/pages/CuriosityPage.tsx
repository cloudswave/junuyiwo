import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Card, Tag, Button, Spin, Empty, Modal, Form, Input, DatePicker, Select, Space, message, List, Popconfirm } from 'antd'
import { PlusOutlined, QuestionCircleOutlined, LinkOutlined, DeleteOutlined, BranchesOutlined, ThunderboltOutlined, MessageOutlined, SendOutlined, StopOutlined, ReadOutlined } from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import { curiosityApi, articlesApi, conversationApi, answerApi, CuriosityEventResponse, CuriosityListResponse, ArticleResponse, type SeriesInfo } from '../services/api'
import { useStore } from '../store/useStore'

const TAG_OPTIONS = [
  { label: '天文', value: '天文' },
  { label: '动物', value: '动物' },
  { label: '自然', value: '自然' },
  { label: '科学', value: '科学' },
  { label: '历史', value: '历史' },
  { label: '地理', value: '地理' },
  { label: '人体', value: '人体' },
  { label: '数学', value: '数学' },
  { label: '艺术', value: '艺术' },
  { label: '生活', value: '生活' },
]

export default function CuriosityPage() {
  const { loading, setLoading } = useStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [data, setData] = useState<CuriosityListResponse | null>(null)
  const [filterTag, setFilterTag] = useState<string | undefined>(searchParams.get('tag') || undefined)
  const [filterAnswered, setFilterAnswered] = useState<boolean | undefined>(undefined)
  const [addOpen, setAddOpen] = useState(false)
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkEventId, setLinkEventId] = useState<number | null>(null)
  const [articles, setArticles] = useState<ArticleResponse[]>([])
  const [generating, setGenerating] = useState<Set<number>>(new Set())
  const [form] = Form.useForm()

  // Chat state (conversation mode)
  const [chatOpen, setChatOpen] = useState(false)
  const [chatEventId, setChatEventId] = useState<number | null>(null)
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; content: string }>>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatArticleId, setChatArticleId] = useState<number | null>(null)

  // Series state
  const [seriesState, setSeriesState] = useState<Record<number, SeriesInfo>>({})
  const [seriesGenerating, setSeriesGenerating] = useState<Set<number>>(new Set())

  // Sync URL ?tag= param to filter
  useEffect(() => {
    const tagFromUrl = searchParams.get('tag') || undefined
    if (tagFromUrl !== filterTag) setFilterTag(tagFromUrl)
  }, [searchParams])

  useEffect(() => { loadEvents() }, [filterTag, filterAnswered])

  const loadEvents = async () => {
    setLoading('curiosity', true)
    try {
      const { data: res } = await curiosityApi.listEvents({
        answered: filterAnswered,
        tag: filterTag,
        limit: 100,
      })
      setData(res)
    } catch { /* ignore */ } finally {
      setLoading('curiosity', false)
    }
  }

  const handleAdd = async (values: any) => {
    try {
      await curiosityApi.createEvent({
        event_date: values.event_date.format('YYYY-MM-DD'),
        raw_text: values.raw_text,
        tags: values.tags || [],
        keywords: values.raw_text.match(/[一-鿿]+/g) || [],
      })
      message.success('已记录问题')
      setAddOpen(false)
      form.resetFields()
      loadEvents()
    } catch { message.error('提交失败') }
  }

  const handleLinkArticle = async (articleId: number) => {
    if (!linkEventId) return
    try {
      await curiosityApi.linkArticle(linkEventId, articleId)
      message.success('已关联文章')
      setLinkOpen(false)
      loadEvents()
    } catch { message.error('关联失败') }
  }

  const openLinkModal = async (eventId: number) => {
    setLinkEventId(eventId)
    setLinkOpen(true)
    try {
      const { data } = await articlesApi.list()
      setArticles(data)
    } catch { /* ignore */ }
  }

  const handleGenerateAnswer = async (eventId: number) => {
    setGenerating(prev => new Set(prev).add(eventId))
    try {
      const { data: result } = await curiosityApi.generateAnswer(eventId)
      message.success('已生成文章回答！')
      setGenerating(prev => { const next = new Set(prev); next.delete(eventId); return next })
      loadEvents()
      // 可以直接跳转到文章页
      Modal.success({
        title: '文章已生成',
        content: `已根据问题「${result.event.raw_text}」生成文章，要去阅读吗？`,
        okText: '去看看',
        onOk: () => navigate(`/article/${result.article.id}`),
      })
    } catch (err: any) {
      setGenerating(prev => { const next = new Set(prev); next.delete(eventId); return next })
      const detail = err?.response?.data?.detail || '生成失败'
      message.error(detail)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await curiosityApi.deleteEvent(id)
      message.success('已删除')
      loadEvents()
    } catch { message.error('删除失败') }
  }

  // One-shot answer
  const handleOneShot = async (eventId: number) => {
    setGenerating(prev => new Set(prev).add(eventId))
    try {
      const { data } = await answerApi.oneShot(eventId)
      message.success('文章已生成！')
      loadEvents()
      if (data.article_id) window.open(`/article/${data.article_id}`, '_blank')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '生成失败')
    } finally { setGenerating(prev => { const n = new Set(prev); n.delete(eventId); return n }) }
  }

  // Conversation (deep chat) handlers — using graph API with event_id
  const openChat = async (eventId: number) => {
    setChatEventId(eventId)
    setChatMessages([])
    setChatInput('')
    setChatArticleId(null)
    setChatOpen(true)
    setChatLoading(true)
    try {
      const { data } = await answerApi.conversationStart(eventId)
      setChatMessages([{ role: 'assistant', content: data.reply }])
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '启动对话失败')
      setChatOpen(false)
    } finally { setChatLoading(false) }
  }

  const sendChatMessage = async () => {
    if (!chatInput.trim() || !chatEventId) return
    const msg = chatInput.trim()
    setChatInput('')
    setChatMessages(prev => [...prev, { role: 'user', content: msg }])
    setChatLoading(true)
    try {
      const { data } = await answerApi.conversationTurn(chatEventId, msg)
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '发送失败')
    } finally { setChatLoading(false) }
  }

  const finishChat = async () => {
    if (!chatEventId) return
    setChatLoading(true)
    try {
      const { data } = await answerApi.conversationGenerate(chatEventId)
      setChatArticleId(data.article_id!)
      message.success('文章已生成！')
      loadEvents()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '生成失败')
    } finally { setChatLoading(false) }
  }

  // Series handlers
  const handleSeriesStart = async (eventId: number) => {
    setSeriesGenerating(prev => new Set(prev).add(eventId))
    try {
      const { data } = await answerApi.seriesStart(eventId)
      setSeriesState(prev => ({ ...prev, [eventId]: data }))
      message.success(`系列已生成：${data.total_chapters}章`)
      loadEvents()
      if (data.series_id) navigate(`/series/${data.series_id}`)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '生成失败')
    } finally { setSeriesGenerating(prev => { const n = new Set(prev); n.delete(eventId); return n }) }
  }

  const handleSeriesNext = async (eventId: number, wantNext: boolean) => {
    setSeriesGenerating(prev => new Set(prev).add(eventId))
    try {
      const { data } = await answerApi.seriesNext(eventId, wantNext)
      if (!wantNext) {
        setSeriesState(prev => ({ ...prev, [eventId]: { ...prev[eventId], status: 'abandoned' } }))
        message.info('系列已完结')
      } else if (data.completed) {
        setSeriesState(prev => ({ ...prev, [eventId]: data }))
        message.success('系列全部读完！')
        loadEvents()
      } else {
        setSeriesState(prev => ({ ...prev, [eventId]: data }))
        navigate(`/series/${data.series_id}`)
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败')
    } finally { setSeriesGenerating(prev => { const n = new Set(prev); n.delete(eventId); return n }) }
  }

  const handleSeriesContinue = (seriesId: number) => {
    navigate(`/series/${seriesId}`)
  }

  const levelColor = (score: number | null) => {
    if (!score) return 'default'
    if (score >= 0.7) return 'red'
    if (score >= 0.4) return 'orange'
    return 'blue'
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>好奇心记录</h1>
        <p>记录孩子的每一个问题，追踪兴趣演化，用文章回应好奇心</p>
      </div>

      <Spin spinning={loading['curiosity']}>
        {/* Toolbar */}
        <Card style={{ marginBottom: 16 }}>
          <Space wrap>
            <Select
              placeholder="兴趣标签筛选"
              options={TAG_OPTIONS}
              value={filterTag}
              onChange={setFilterTag}
              allowClear
              style={{ width: 140 }}
            />
            <Select
              placeholder="状态"
              value={filterAnswered}
              onChange={setFilterAnswered}
              allowClear
              style={{ width: 120 }}
              options={[
                { label: '未回答', value: false },
                { label: '已回答', value: true },
              ]}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
              记录问题
            </Button>
          </Space>
        </Card>

        {/* Tag summary */}
        {data?.tags_summary && Object.keys(data.tags_summary).length > 0 && (
          <Card size="small" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ color: '#888', fontSize: 13 }}>兴趣分布：</span>
              {Object.entries(data.tags_summary).map(([tag, count]) => (
                <Tag key={tag} color={count > 3 ? 'blue' : 'default'} style={{ cursor: 'pointer' }}
                  onClick={() => setFilterTag(tag === filterTag ? undefined : tag)}>
                  {tag} ({count})
                </Tag>
              ))}
            </div>
          </Card>
        )}

        {/* Event list */}
        {!data || data.items.length === 0 ? (
          <Empty description="还没有记录问题" image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button type="primary" onClick={() => setAddOpen(true)}>记录第一个问题</Button>
          </Empty>
        ) : (
          <List
            dataSource={data.items}
            pagination={{ pageSize: 20, size: 'small' }}
            renderItem={(item) => (
              <Card key={item.id} size="small" style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 16, marginBottom: 4 }}>
                      {item.is_answered ? null : <QuestionCircleOutlined style={{ color: '#faad14', marginRight: 6 }} />}
                      "{item.raw_text}"
                    </div>
                    <div style={{ color: '#888', fontSize: 12 }}>
                      {item.event_date}
                      {item.parent_event_id && <Tag color="purple" style={{ marginLeft: 8 }}>追问</Tag>}
                      {item.tags_json?.map((t: string) => <Tag key={t} style={{ marginLeft: 4 }}>{t}</Tag>)}
                      <Tag color={item.is_answered ? 'green' : 'gold'} style={{ marginLeft: 4 }}>
                        {item.is_answered ? '已回应' : '待回答'}
                      </Tag>
                      {item.linked_article_id && (
                        <Tag color="blue" style={{ cursor: 'pointer' }}
                          onClick={() => window.open(`/article/${item.linked_article_id}`, '_blank')}>
                          查看文章
                        </Tag>
                      )}
                    </div>
                  </div>
                  <Space>
                    {!item.is_answered && (
                      <Space wrap>
                        <Button size="small" type="primary" icon={<ThunderboltOutlined />}
                          loading={generating.has(item.id)}
                          onClick={() => handleOneShot(item.id)}>
                          生成文章
                        </Button>
                        <Button size="small" icon={<MessageOutlined />}
                          onClick={() => openChat(item.id)}>
                          深入对话
                        </Button>
                        <Button size="small" icon={<ReadOutlined />}
                          loading={seriesGenerating.has(item.id)}
                          onClick={() => handleSeriesStart(item.id)}>
                          系列阅读
                        </Button>
                        <Button size="small" icon={<LinkOutlined />}
                          onClick={() => openLinkModal(item.id)}>
                          关联已有
                        </Button>
                      </Space>
                    )}
                    {/* Series progress */}
                    {seriesState[item.id] && !seriesState[item.id].completed && seriesState[item.id].status !== 'abandoned' && (
                      <div style={{ marginTop: 8, padding: '8px 12px', background: '#f6ffed', borderRadius: 6, border: '1px solid #b7eb8f' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 13, color: '#52c41a', fontWeight: 500 }}>
                            第{seriesState[item.id].current_chapter}/{seriesState[item.id].total_chapters}章
                          </span>
                          <Button size="small" type="link"
                            onClick={() => navigate(`/series/${seriesState[item.id].series_id}`)}>
                            继续阅读 →
                          </Button>
                        </div>
                        <div style={{ marginTop: 4, display: 'flex', gap: 6 }}>
                          <Button size="small" type="primary" ghost
                            loading={seriesGenerating.has(item.id)}
                            onClick={() => handleSeriesNext(item.id, true)}>下一章 ▶</Button>
                          <Button size="small" danger
                            onClick={() => handleSeriesNext(item.id, false)}>不看了</Button>
                        </div>
                      </div>
                    )}
                    {seriesState[item.id]?.completed && (
                      <Tag color="green">系列已完成 ✓</Tag>
                    )}
                    {item.parent_event_id && (
                      <Button size="small" icon={<BranchesOutlined />}
                        onClick={() => curiosityApi.getThread(item.id).then(({ data: t }) =>
                          Modal.info({ title: '追问链', content: t.map(e => e.raw_text).join(' → ') })
                        )}>
                        追问链
                      </Button>
                    )}
                    <Popconfirm title="确定删除？" onConfirm={() => handleDelete(item.id)}>
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                </div>
              </Card>
            )}
          />
        )}
      </Spin>

      {/* Add Event Modal */}
      <Modal title="记录孩子的问题" open={addOpen} onCancel={() => setAddOpen(false)} onOk={() => form.submit()} confirmLoading={loading['curiosity']}>
        <Form form={form} layout="vertical" onFinish={handleAdd} initialValues={{ event_date: dayjs() }}>
          <Form.Item name="event_date" label="日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="raw_text" label="孩子原话" rules={[{ required: true, message: '请输入孩子的原话' }]}>
            <Input.TextArea placeholder='例如："星星为什么会眨眼睛？"' rows={3} maxLength={500} showCount />
          </Form.Item>
          <Form.Item name="tags" label="兴趣标签">
            <Select mode="multiple" placeholder="选择标签" options={TAG_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Link Article Modal */}
      <Modal title="选择回应的文章" open={linkOpen} onCancel={() => setLinkOpen(false)} footer={null} width={600}>
        {articles.length === 0 ? (
          <Empty description="暂无文章，请先生成文章" />
        ) : (
          <List
            dataSource={articles}
            renderItem={(a) => (
              <Card size="small" hoverable style={{ marginBottom: 8 }}
                onClick={() => handleLinkArticle(a.id)}>
                <div>{a.topic}</div>
                <div style={{ color: '#888', fontSize: 12 }}>{a.record_date} · {a.character_count}字</div>
              </Card>
            )}
          />
        )}
      </Modal>

      {/* 深入聊聊 对话框 */}
      <Modal
        title={chatArticleId ? '对话已完成，文章已生成！' : '深入聊聊'}
        open={chatOpen}
        onCancel={() => setChatOpen(false)}
        footer={null}
        width={600}
        styles={{ body: { padding: 0, maxHeight: '60vh', overflow: 'auto' } }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: 400 }}>
          <div style={{ flex: 1, overflow: 'auto', padding: 16, background: '#f5f5f5' }}>
            {chatMessages.map((msg, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 12,
              }}>
                <div style={{
                  maxWidth: '80%', padding: '8px 14px', borderRadius: 12,
                  background: msg.role === 'user' ? '#1677ff' : '#fff',
                  color: msg.role === 'user' ? '#fff' : '#333',
                  fontSize: 14, lineHeight: 1.6,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div style={{ textAlign: 'center', color: '#999', fontSize: 13 }}>思考中...</div>
            )}
          </div>

          {!chatArticleId ? (
            <div style={{ padding: 12, borderTop: '1px solid #f0f0f0', display: 'flex', gap: 8 }}>
              <Input.TextArea
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onPressEnter={e => { e.preventDefault(); sendChatMessage() }}
                placeholder="输入你的问题，和老师深入聊聊..."
                rows={2}
                style={{ flex: 1 }}
                disabled={chatLoading}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <Button type="primary" icon={<SendOutlined />} onClick={sendChatMessage} loading={chatLoading}>
                  发送
                </Button>
                <Button icon={<StopOutlined />} onClick={finishChat} disabled={chatLoading || chatMessages.length === 0}>
                  生成文章
                </Button>
              </div>
            </div>
          ) : (
            <div style={{ padding: 16, textAlign: 'center', borderTop: '1px solid #f0f0f0' }}>
              <Button type="primary" onClick={() => { window.open(`/article/${chatArticleId}`, '_blank'); setChatOpen(false) }}>
                查看文章 →
              </Button>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
