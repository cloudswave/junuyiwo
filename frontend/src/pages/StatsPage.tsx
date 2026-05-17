import { useEffect } from 'react'
import { Card, Row, Col, Statistic, Spin, Empty, Table, Progress } from 'antd'
import {
  BookOutlined,
  CalendarOutlined,
  WarningOutlined,
  FileTextOutlined,
  TrophyOutlined,
} from '@ant-design/icons'
import { dashboardApi } from '../services/api'
import { useStore } from '../store/useStore'

export default function StatsPage() {
  const { stats, loading, setLoading, setStats } = useStore()

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    setLoading('stats', true)
    try {
      const { data } = await dashboardApi.getStats()
      setStats(data)
    } catch {
      // ignore
    } finally {
      setLoading('stats', false)
    }
  }

  if (!stats) {
    return (
      <div className="page-container">
        <Spin spinning={loading['stats']}>
          <Empty description="暂无统计数据" />
        </Spin>
      </div>
    )
  }

  const forgottenTotal = Object.values(stats.forgotten_stats).reduce((a, b) => a + b, 0)
  const masteredRate = stats.total_characters_learned > 0
    ? Math.round(((stats.total_characters_learned - forgottenTotal) / stats.total_characters_learned) * 100)
    : 0

  const dailyData = stats.daily_progress.map((d) => ({
    date: d.date,
    每日识字: d.count,
  }))

  const levelData = Object.entries(stats.forgotten_stats).map(([level, count]) => ({
    type: level,
    value: count,
  }))

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>学习统计</h1>
        <p>跟踪孩子的识字学习进展</p>
      </div>

      <Spin spinning={loading['stats']}>
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={8}>
            <Card>
              <Statistic
                title="累计识字"
                value={stats.total_characters_learned}
                prefix={<BookOutlined />}
                valueStyle={{ color: '#4F46E5' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8}>
            <Card>
              <Statistic
                title="学习天数"
                value={stats.total_days}
                prefix={<CalendarOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={8}>
            <Card>
              <Statistic
                title="累计文章"
                value={stats.total_articles}
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12}>
            <Card title="掌握率">
              <Progress
                type="circle"
                percent={masteredRate}
                format={() => `${masteredRate}%`}
                strokeColor={masteredRate > 80 ? '#52c41a' : masteredRate > 50 ? '#faad14' : '#ff4d4f'}
              />
              <div style={{ textAlign: 'center', marginTop: 12, color: '#888' }}>
                {stats.total_characters_learned - forgottenTotal} / {stats.total_characters_learned} 字已掌握
              </div>
            </Card>
          </Col>
          <Col xs={24} sm={12}>
            <Card title="遗忘等级分布">
              {levelData.map((item) => (
                <div key={item.type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span>{item.type}</span>
                  <span style={{ fontWeight: 600 }}>{item.value}</span>
                </div>
              ))}
              {forgottenTotal === 0 && <div style={{ color: '#52c41a' }}>太棒了，没有遗忘字！</div>}
            </Card>
          </Col>
        </Row>

        <Card title="每日识字趋势">
          {dailyData.length > 0 ? (
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 200, overflow: 'auto' }}>
              {dailyData.slice(-30).map((d) => {
                const maxVal = Math.max(...dailyData.map(x => x["每日识字"]), 1)
                const h = (d['每日识字'] / maxVal) * 160
                return (
                  <div key={d.date} style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28 }}>
                    <span style={{ fontSize: 10, color: '#888', marginBottom: 4 }}>{d['每日识字']}</span>
                    <div style={{
                      width: 20,
                      height: Math.max(h, 4),
                      background: '#4F46E5',
                      borderRadius: '4px 4px 0 0',
                      transition: 'height 0.3s',
                    }} />
                    <span style={{ fontSize: 9, color: '#aaa', marginTop: 4, transform: 'rotate(-45deg)', transformOrigin: 'top left', whiteSpace: 'nowrap' }}>
                      {d.date.slice(5)}
                    </span>
                  </div>
                )
              })}
            </div>
          ) : (
            <Empty description="暂无数据" />
          )}
        </Card>
      </Spin>
    </div>
  )
}
