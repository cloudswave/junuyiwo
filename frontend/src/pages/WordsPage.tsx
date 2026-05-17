import { useEffect, useState } from 'react'
import { Card, Tabs, Table, Tag, Spin, Empty, Input, Button, Space, Modal, Select, Popconfirm, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { SearchOutlined, DownloadOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { zonesApi, dashboardApi, ZoneCharItem, ScoutCharItem, LostCharItem } from '../services/api'
import { useStore } from '../store/useStore'
import dayjs from 'dayjs'

type ZoneTab = 'target' | 'scout' | 'ally' | 'lost'

export default function WordsPage() {
  const { loading, setLoading } = useStore()
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<ZoneTab>('target')

  // Zone data
  const [targetChars, setTargetChars] = useState<ZoneCharItem[]>([])
  const [scoutChars, setScoutChars] = useState<ScoutCharItem[]>([])
  const [allyChars, setAllyChars] = useState<ZoneCharItem[]>([])
  const [lostChars, setLostChars] = useState<LostCharItem[]>([])

  // Add modal
  const [addOpen, setAddOpen] = useState(false)
  const [addChar, setAddChar] = useState('')
  const [addPinyin, setAddPinyin] = useState('')
  const pinyinEditedRef = { current: false }

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    setLoading('words', true)
    try {
      const [targetRes, scoutRes, allyRes, lostRes] = await Promise.all([
        zonesApi.listTarget(), zonesApi.listScout(),
        zonesApi.listAlly(), zonesApi.listLost(),
      ])
      setTargetChars(targetRes.data)
      setScoutChars(scoutRes.data)
      setAllyChars(allyRes.data)
      setLostChars(lostRes.data)
    } catch { /* ignore */ }
    finally { setLoading('words', false) }
  }

  const handleExport = () => { window.open(dashboardApi.exportCsv(), '_blank') }

  const handleAdd = async () => {
    const chars = addChar.trim().replace(/[^一-鿿]/g, '').split('')
    if (chars.length === 0) { message.warning('请输入汉字'); return }
    try {
      await zonesApi.addTarget({
        characters: chars,
        pinyin: addPinyin ? [addPinyin] : undefined,
        source: 'manual',
      })
      message.success(`已添加 ${chars.join(' ')} 到教学区`)
      setAddOpen(false); setAddChar(''); setAddPinyin('')
      loadAll()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '添加失败')
    }
  }

  const handleDelete = async (zone: ZoneTab, character: string) => {
    try {
      if (zone === 'target') await zonesApi.deleteTarget(character)
      else if (zone === 'scout') await zonesApi.deleteScout(character)
      else if (zone === 'ally') await zonesApi.deleteAlly(character)
      else return
      message.success(`已删除「${character}」`)
      loadAll()
    } catch { message.error('删除失败') }
  }

  const handleRecover = async (character: string) => {
    try {
      await zonesApi.recoverLost(character)
      message.success(`「${character}」已移回侦查区`)
      loadAll()
    } catch { message.error('恢复失败') }
  }

  // Target zone columns
  const targetColumns: ColumnsType<ZoneCharItem> = [
    { title: '汉字', dataIndex: 'character', key: 'character', width: 80,
      render: (ch: string) => <span style={{ fontSize: 24, fontWeight: 600 }}>{ch}</span> },
    { title: '拼音', dataIndex: 'pinyin', key: 'pinyin', width: 100,
      render: (py: string | null) => py || '-' },
    { title: '来源', dataIndex: 'source', key: 'source', width: 80,
      render: (s: string) => <Tag>{s === 'migration' ? '历史数据' : '手动录入'}</Tag> },
    { title: '添加时间', dataIndex: 'added_at', key: 'added_at', width: 110,
      render: (d: string) => d ? dayjs(d).format('MM-DD HH:mm') : '-' },
    { title: '操作', key: 'action', width: 60,
      render: (_: any, r: ZoneCharItem) => (
        <Popconfirm title={`确定删除「${r.character}」？`} onConfirm={() => handleDelete('target', r.character)}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      )},
  ]

  // Scout zone columns
  const scoutColumns: ColumnsType<ScoutCharItem> = [
    { title: '汉字', dataIndex: 'character', key: 'character', width: 80,
      render: (ch: string) => <span style={{ fontSize: 24, fontWeight: 600 }}>{ch}</span> },
    { title: '拼音', dataIndex: 'pinyin', key: 'pinyin', width: 80,
      render: (py: string | null) => py || '-' },
    { title: '来源', dataIndex: 'source', key: 'source', width: 90,
      render: (s: string) => {
        const map: Record<string, { color: string; text: string }> = {
          reading: { color: 'blue', text: '阅读发现' },
          migration: { color: 'default', text: '历史数据' },
          lost_recovery: { color: 'orange', text: '复习恢复' },
          manual: { color: 'green', text: '手动添加' },
        }
        const info = map[s] || { color: 'default', text: s }
        return <Tag color={info.color}>{info.text}</Tag>
      }},
    { title: '已读完', dataIndex: 'appeared_in_read_count', key: 'appeared', width: 70 },
    { title: '未点击', dataIndex: 'never_tapped_in_read_count', key: 'never_tapped', width: 70,
      render: (n: number) => n >= 3 ? <span style={{ color: '#52c41a', fontWeight: 600 }}>{n}</span> : n },
    { title: '操作', key: 'action', width: 60,
      render: (_: any, r: ScoutCharItem) => (
        <Popconfirm title={`确定删除「${r.character}」？`} onConfirm={() => handleDelete('scout', r.character)}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      )},
  ]

  // Ally zone columns
  const allyColumns: ColumnsType<ZoneCharItem> = [
    { title: '汉字', dataIndex: 'character', key: 'character', width: 80,
      render: (ch: string) => <span style={{ fontSize: 24, fontWeight: 600 }}>{ch}</span> },
    { title: '拼音', dataIndex: 'pinyin', key: 'pinyin', width: 100,
      render: (py: string | null) => py || '-' },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100,
      render: (s: string) => (
        <Tag color={s === 'auto_promoted' ? 'blue' : 'green'}>
          {s === 'auto_promoted' ? '系统发现' : '手动录入'}
        </Tag>
      )},
    { title: '添加时间', dataIndex: 'created_at', key: 'created_at', width: 110,
      render: (d: string) => d ? dayjs(d).format('MM-DD HH:mm') : '-' },
    { title: '操作', key: 'action', width: 60,
      render: (_: any, r: ZoneCharItem) => (
        <Popconfirm title={`确定删除「${r.character}」？`} onConfirm={() => handleDelete('ally', r.character)}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      )},
  ]

  // Lost zone columns
  const lostColumns: ColumnsType<LostCharItem> = [
    { title: '汉字', dataIndex: 'character', key: 'character', width: 80,
      render: (ch: string) => <span style={{ fontSize: 24, fontWeight: 600 }}>{ch}</span> },
    { title: '拼音', dataIndex: 'pinyin', key: 'pinyin', width: 80,
      render: (py: string | null) => py || '-' },
    { title: '点击次数', dataIndex: 'tap_count', key: 'tap_count', width: 80,
      render: (n: number) => <span style={{ color: '#ff4d4f', fontWeight: 600 }}>{n}</span> },
    { title: '涉及文章', dataIndex: 'article_count', key: 'article_count', width: 80 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (s: string) => {
        const map: Record<string, { color: string; text: string }> = {
          active: { color: 'red', text: '待复习' },
          reviewing: { color: 'orange', text: '复习中' },
          recovered: { color: 'green', text: '已恢复' },
        }
        const info = map[s] || { color: 'default', text: s }
        return <Tag color={info.color}>{info.text}</Tag>
      }},
    { title: '操作', key: 'action', width: 80,
      render: (_: any, r: LostCharItem) => (
        <Button type="link" size="small" onClick={() => handleRecover(r.character)}
                disabled={r.status === 'recovered'}>
          恢复
        </Button>
      )},
  ]

  const getData = () => {
    let data: any[] = []
    if (activeTab === 'target') data = targetChars
    else if (activeTab === 'scout') data = scoutChars
    else if (activeTab === 'ally') data = allyChars
    else if (activeTab === 'lost') data = lostChars

    if (search) data = data.filter((c: any) => c.character.includes(search))
    return data
  }

  const getColumns = () => {
    if (activeTab === 'target') return targetColumns
    if (activeTab === 'scout') return scoutColumns
    if (activeTab === 'ally') return allyColumns
    if (activeTab === 'lost') return lostColumns
    return targetColumns
  }

  const zoneLabels: Record<ZoneTab, string> = {
    target: '教学区', scout: '侦查区', ally: '友军区', lost: '战损区',
  }

  const tabItems = [
    { key: 'target', label: `教学区 (${targetChars.length})` },
    { key: 'scout', label: `侦查区 (${scoutChars.length})` },
    { key: 'ally', label: `友军区 (${allyChars.length})` },
    { key: 'lost', label: `战损区 (${lostChars.length})` },
  ]

  const data = getData()

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>字库总览</h1>
        <p>教学区 · 侦查区 · 友军区 · 战损区 — 四区字库管理</p>
      </div>

      <Spin spinning={loading['words']}>
        <Card>
          <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
            <Space>
              <Input
                placeholder="搜索汉字..."
                prefix={<SearchOutlined />}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: 200 }}
                allowClear
              />
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
                添加生字
              </Button>
            </Space>
            <Button icon={<DownloadOutlined />} onClick={handleExport}>
              导出数据
            </Button>
          </Space>

          <Tabs activeKey={activeTab} onChange={(k) => setActiveTab(k as ZoneTab)} items={tabItems} />

          {data.length === 0 ? (
            <Empty description={`${zoneLabels[activeTab]}暂无数据`} image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Table
              columns={getColumns()}
              dataSource={data}
              rowKey="id"
              pagination={{ pageSize: 30, size: 'small' }}
              size="middle"
              scroll={{ x: 800 }}
            />
          )}
        </Card>
      </Spin>

      <Modal
        title="添加生字到教学区"
        open={addOpen}
        onOk={handleAdd}
        onCancel={() => { setAddOpen(false); setAddChar(''); setAddPinyin(''); pinyinEditedRef.current = false }}
        okText="添加"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ marginBottom: 4, color: '#555' }}>汉字</div>
            <Input
              value={addChar}
              onChange={async (e) => {
                const val = e.target.value
                setAddChar(val)
                if (pinyinEditedRef.current) return
                const ch = val.replace(/[^一-鿿]/g, '')
                if (ch) {
                  try {
                    const res = await fetch(`/api/articles/pinyin`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ text: ch }),
                    })
                    const pyData = await res.json()
                    const pyStr = (pyData.paragraphs || []).flat().filter((t: any) => t.pinyin).map((t: any) => t.pinyin).join(' ')
                    setAddPinyin(pyStr)
                  } catch { /* ignore */ }
                }
              }}
              placeholder="输入一个或多个汉字"
              style={{ fontSize: 20 }}
            />
          </div>
          <div>
            <div style={{ marginBottom: 4, color: '#555' }}>拼音（可选）</div>
            <Input
              value={addPinyin}
              onChange={(e) => { pinyinEditedRef.current = true; setAddPinyin(e.target.value) }}
              placeholder="自动获取或手动输入"
            />
          </div>
        </Space>
      </Modal>
    </div>
  )
}
