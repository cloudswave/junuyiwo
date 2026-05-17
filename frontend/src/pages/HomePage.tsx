import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Row, Col, Statistic, Button, Spin, Empty, Tag, Alert, Progress, Space } from 'antd'
import {
  BookOutlined,
  FileTextOutlined,
  WarningOutlined,
  ArrowRightOutlined,
  QuestionCircleOutlined,
  BulbOutlined,
  CalendarOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { dashboardApi, CuriosityEventResponse, InterestEvolutionResponse, articlesApi, LearnedCharsByDate } from '../services/api'
import { useStore } from '../store/useStore'
import ArticleReader from '../components/ArticleReader'

export default function HomePage() {
  const navigate = useNavigate()
  const {
    todayCharacters, todayMathCharacters, todayArticle, forgottenStats, totalLearned, totalMathLearned,
    setTodayData, loading, setLoading,
  } = useStore()
  const [recentQuestions, setRecentQuestions] = useState<CuriosityEventResponse[]>([])
  const [hotInterests, setHotInterests] = useState<InterestEvolutionResponse[]>([])
  const [learnedCharsReview, setLearnedCharsReview] = useState<LearnedCharsByDate | null>(null)
  const [staleUnansweredCount, setStaleUnansweredCount] = useState(0)

  useEffect(() => {
    loadDashboard()
    // 页面可见时重新加载（从文章页回来等场景）
    const onVisible = () => { if (document.visibilityState === 'visible') loadDashboard() }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  const loadDashboard = async () => {
    setLoading('dashboard', true)
    try {
      const { data } = await dashboardApi.get()
      setTodayData(
        data.today_characters,
        data.today_article,
        data.forgotten_stats,
        data.total_characters_learned,
        data.today_math_characters,
        data.total_math_characters,
      )
      setRecentQuestions(data.recent_questions || [])
      setHotInterests(data.hot_interests || [])
      setStaleUnansweredCount((data as any).stale_unanswered_count || 0)

      // If there's a today article, load the learned-chars cross-reference
      if (data.today_article) {
        try {
          const lcRes = await articlesApi.getLearnedChars(dayjs().format('YYYY-MM-DD'))
          setLearnedCharsReview(lcRes.data)
        } catch {
          setLearnedCharsReview(null)
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading('dashboard', false)
    }
  }

  const forgetTotal = Object.values(forgottenStats).reduce((a, b) => a + b, 0)
  const fivePlus = forgottenStats['五次以上'] || 0
  const unansweredCount = recentQuestions.filter(q => !q.is_answered).length

  // Date color palette for the review groups
  const dateColors = ['#4F46E5', '#7C3AED', '#2563EB', '#0891B2', '#0D9488', '#059669', '#65A30D', '#CA8A04', '#D97706', '#DC2626']

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>{dayjs().format('YYYY年M月D日')} 今日学习</h1>
        <p>每天进步一点点，在阅读中快乐识字</p>
      </div>

      <Spin spinning={loading['dashboard']}>
        {/* Stale unanswered questions warning */}
        {staleUnansweredCount > 0 && (
          <Alert
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            message={`有 ${staleUnansweredCount} 个问题超过3天未回答`}
            description={
              <span>
                俊宜提的问题还没被回答！<a onClick={() => navigate('/curiosity')} style={{ cursor: 'pointer', fontWeight: 600 }}>去回答问题 →</a>
              </span>
            }
            style={{ marginBottom: 16 }}
          />
        )}

        {/* ===== Primary: Article character review ===== */}
        {todayArticle && learnedCharsReview && learnedCharsReview.learned_count > 0 && (
          <Card
            title={
              <span>
                <BookOutlined style={{ marginRight: 8 }} />
                今日阅读中的已学生字
                <Tag color="blue" style={{ marginLeft: 8 }}>{learnedCharsReview.learned_count}个字</Tag>
              </span>
            }
            style={{ marginBottom: 24, borderColor: '#4F46E5' }}
          >
            {/* Summary bar */}
            <Alert
              type="info"
              message={
                <span>
                  今日文章「{learnedCharsReview.article_topic}」共出现 <b>{learnedCharsReview.total_in_article}</b> 个不重复汉字，
                  其中 <b>{learnedCharsReview.learned_count}</b> 个已学过
                  {learnedCharsReview.not_learned_count > 0 && (
                    <>，<b>{learnedCharsReview.not_learned_count}</b> 个未学过</>
                  )}
                </span>
              }
              style={{ marginBottom: 20 }}
            />

            {/* Characters grouped by learn date */}
            <div className="review-date-groups">
              {Object.entries(learnedCharsReview.by_date).map(([dateKey, chars], idx) => {
                const dateLabel = dayjs(dateKey).format('M月D日')
                const daysAgo = dayjs().diff(dayjs(dateKey), 'day')
                const daysLabel = daysAgo === 0 ? '今天学' : daysAgo === 1 ? '昨天学' : `${daysAgo}天前学`
                const color = dateColors[idx % dateColors.length]

                return (
                  <div key={dateKey} className="review-date-group">
                    <div className="review-date-header">
                      <span className="review-date-dot" style={{ background: color }} />
                      <CalendarOutlined style={{ color, marginRight: 6 }} />
                      <strong>{dateLabel}</strong>
                      <Tag color={idx === 0 ? 'blue' : 'default'} style={{ marginLeft: 8 }}>
                        {daysLabel}
                      </Tag>
                      <span className="review-date-count">{chars.length}字</span>
                    </div>
                    <div className="review-char-list">
                      {chars.map((ch, ci) => (
                        <div key={`${ch.character}-${ci}`} className="review-char-item">
                          <span className="review-char-hz">{ch.character}</span>
                          {ch.pinyin && <span className="review-char-py">{ch.pinyin}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Not yet learned characters */}
            {learnedCharsReview.not_learned.length > 0 && (
              <div style={{ marginTop: 16, padding: '12px 16px', background: '#fffbe6', borderRadius: 8, border: '1px solid #ffe58f' }}>
                <span style={{ color: '#ad8b00', marginRight: 8 }}>未学过的字：</span>
                {learnedCharsReview.not_learned.map((ch) => (
                  <Tag key={ch} style={{ fontSize: 16, marginBottom: 4 }}>{ch}</Tag>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Stats cards */}
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={6}>
            <Card hoverable onClick={() => navigate('/words')}>
              <Statistic
                title="累计识字"
                value={totalLearned}
                prefix={<BookOutlined />}
                valueStyle={{ color: '#4F46E5' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card hoverable onClick={() => navigate('/add-math')} style={{ borderColor: '#FA8C16' }}>
              <Statistic
                title="数学生字"
                value={totalMathLearned}
                prefix={<BookOutlined />}
                valueStyle={{ color: '#FA8C16' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card hoverable onClick={() => navigate('/articles')}>
              <Statistic
                title="文章"
                value={todayArticle ? 1 : 0}
                suffix="篇"
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card hoverable onClick={() => navigate('/review')}>
              <Statistic
                title="待复习"
                value={forgetTotal}
                prefix={<WarningOutlined />}
                valueStyle={{ color: forgetTotal > 0 ? '#faad14' : '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card hoverable onClick={() => navigate('/curiosity')}>
              <Statistic
                title="待回答问题"
                value={unansweredCount}
                prefix={<QuestionCircleOutlined />}
                valueStyle={{ color: unansweredCount > 0 ? '#faad14' : '#52c41a' }}
              />
            </Card>
          </Col>
        </Row>

        {/* Review alert */}
        {forgetTotal > 0 && (
          <Alert
            type="warning"
            icon={<WarningOutlined />}
            message={`你有 ${forgetTotal} 个遗忘字需要复习${fivePlus > 0 ? `，其中 ${fivePlus} 个为高频遗忘字` : ''}`}
            action={
              <Button size="small" type="primary" ghost onClick={() => navigate('/review')}>
                去复习 <ArrowRightOutlined />
              </Button>
            }
            style={{ marginBottom: 24 }}
          />
        )}

        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          {/* Hot interests */}
          {hotInterests.length > 0 && (
            <Col xs={24} md={8}>
              <Card title={<span><BulbOutlined /> 兴趣热点</span>} size="small">
                {hotInterests.map((t) => (
                  <div key={t.tag_name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <Tag color="blue" style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/curiosity?tag=${encodeURIComponent(t.tag_name)}`)}>
                      {t.tag_name}
                    </Tag>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Progress
                        percent={Math.round((t.intensity_score || 0) * 100)}
                        size="small"
                        style={{ width: 80, margin: 0 }}
                        strokeColor={t.trend === 'rising' ? '#52c41a' : t.trend === 'declining' ? '#ff4d4f' : '#faad14'}
                        showInfo={false}
                      />
                      <span style={{ fontSize: 10, color: '#888' }}>{t.mention_count}次</span>
                    </div>
                  </div>
                ))}
                <Button type="link" size="small" onClick={() => navigate('/curiosity')}>查看全部</Button>
              </Card>
            </Col>
          )}

          {/* Recent questions */}
          {recentQuestions.length > 0 && (
            <Col xs={24} md={hotInterests.length > 0 ? 16 : 24}>
              <Card
                title={<span><QuestionCircleOutlined /> 最近的问题</span>}
                size="small"
                extra={<Button type="link" size="small" onClick={() => navigate('/curiosity')}>全部 ({recentQuestions.length})</Button>}
              >
                {recentQuestions.slice(0, 3).map((q) => (
                  <div key={q.id} style={{ marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <Tag color={q.is_answered ? 'green' : 'gold'} style={{ flexShrink: 0 }}>
                      {q.is_answered ? '已答' : '待答'}
                    </Tag>
                    <span style={{ flex: 1 }}>"{q.raw_text}"</span>
                    <span style={{ color: '#aaa', fontSize: 12, whiteSpace: 'nowrap' }}>{q.event_date}</span>
                  </div>
                ))}
                {recentQuestions.length === 0 && <Empty description="还没有记录问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
              </Card>
            </Col>
          )}
        </Row>

        {/* Today's characters - now as a quick glance section */}
        <Card
          title="今日生字"
          extra={
            todayCharacters.length === 0 && (
              <Button type="link" onClick={() => navigate('/add')}>录入生字</Button>
            )
          }
          style={{ marginBottom: 24 }}
        >
          {todayCharacters.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              {todayCharacters.map((ch, ci) => (
                <div key={`${ch}-${ci}`} className="word-card"style={{ width: 72, height: 72 }}>
                  <span className="char" style={{ fontSize: 28 }}>{ch}</span>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              description="今天还没有录入生字"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button type="primary" onClick={() => navigate('/add')}>去录入生字</Button>
            </Empty>
          )}
        </Card>

        {/* Today's math characters — urgent priority */}
        {todayMathCharacters.length > 0 && (
          <Card
            title={
              <span>
                今日数学生字
                <Tag color="red" style={{ marginLeft: 8 }}>急攻</Tag>
              </span>
            }
            extra={
              <Button type="link" size="small" onClick={() => navigate('/add-math')}>录入数学生字</Button>
            }
            style={{ marginBottom: 24, borderColor: '#FA8C16' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              {todayMathCharacters.map((ch, ci) => (
                <div key={`math-${ch}-${ci}`} className="word-card word-card-math" style={{ width: 72, height: 72 }}>
                  <span className="char" style={{ fontSize: 28 }}>{ch}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Today's article */}
        <Card
          title="今日阅读"
          extra={
            todayArticle ? (
              <Tag color="blue">{todayArticle.character_count}字</Tag>
            ) : null
          }
        >
          {todayArticle ? (
            <>
              <ArticleReader paragraphs={todayArticle.paragraphs} topic={todayArticle.topic} imageUrl={todayArticle.image_url} images={todayArticle.images} characters={todayCharacters} articleId={todayArticle.id} />
              {todayArticle.char_breakdown && (
                <div style={{ marginTop: 16, padding: 12, background: '#f9f9f9', borderRadius: 8, fontSize: 13 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>📊 字库分布（共 {todayArticle.char_breakdown.total} 个不重复字）</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
                    <div><span style={{ color: '#4F46E5' }}>🎯 教学区:</span> {todayArticle.char_breakdown.from_target.join(' ') || '无'}</div>
                    <div><span style={{ color: '#52c41a' }}>✅ 友军区:</span> {todayArticle.char_breakdown.from_ally.join(' ') || '无'}</div>
                    <div><span style={{ color: '#1890ff' }}>🔍 侦查区:</span> {todayArticle.char_breakdown.from_scout.join(' ') || '无'}</div>
                    <div><span style={{ color: '#ff4d4f' }}>⚠️ 战损区:</span> {todayArticle.char_breakdown.from_lost.join(' ') || '无'}</div>
                    <div><span style={{ color: '#faad14' }}>🆕 非字库:</span> {todayArticle.char_breakdown.not_in_any.join(' ') || '无'}</div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <Empty
              description={unansweredCount > 0 ? `俊宜还有 ${unansweredCount} 个问题等你回答！用好奇心驱动阅读` : '今天还没有生成文章'}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              {unansweredCount > 0 ? (
                <Space>
                  <Button type="primary" onClick={() => navigate('/curiosity')}>
                    去回答好奇心问题
                  </Button>
                  <Button onClick={() => navigate('/add')}>手动录入生字</Button>
                </Space>
              ) : (
                <Button type="primary" onClick={() => navigate('/add')}>
                  先生成文章
                </Button>
              )}
            </Empty>
          )}
        </Card>
      </Spin>
    </div>
  )
}
