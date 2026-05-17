import { useEffect, useState } from 'react'
import { Card, Tabs, Tag, List, Spin, Empty, Input, Select, Switch, message, Collapse, Badge, Button, Modal } from 'antd'
import {
  BookOutlined, BulbOutlined, SearchOutlined,
  ReadOutlined, RocketOutlined, PlusOutlined, FileTextOutlined,
} from '@ant-design/icons'
import { knowledgeBaseApi, type KnowledgeEntryResponse } from '../services/api'

const SUBJECT_COLORS: Record<string, string> = {
  '语文': '#4F46E5', '数学': '#0891B2', '天文': '#CA8A04',
  '地理': '#059669', '动植物': '#65A30D', '科学': '#7C3AED',
}

function renderEntryItem(
  item: KnowledgeEntryResponse,
  onToggle?: (id: number, approved: boolean) => void,
  onViewContent?: (title: string, content: string) => void,
) {
  const isLessonContent = item.title.includes('课文原文')
  return (
    <List.Item
      style={isLessonContent ? { background: '#fafae8', cursor: 'pointer' } : undefined}
      onClick={isLessonContent ? () => onViewContent?.(item.title, item.content) : undefined}
      actions={[
        item.source === 'auto_generated' ? (
          <Switch
            checkedChildren="可用" unCheckedChildren="隐藏"
            checked={item.auto_approved}
            onChange={(v) => onToggle?.(item.id, v)}
            size="small" key="sw"
          />
        ) : null,
        <Tag key="src" color={
          item.source === 'textbook_preload' ? (isLessonContent ? 'gold' : 'green') :
          item.source === 'auto_generated' ? 'blue' :
          item.source === 'article_backfeed' ? 'purple' : 'default'
        }>
          {item.source === 'textbook_preload' ? (isLessonContent ? '课文原文' : '课本预置') :
           item.source === 'auto_generated' ? 'AI生成' :
           item.source === 'article_backfeed' ? '文章回哺' : '手动录入'}
        </Tag>,
        <span key="use" style={{ fontSize: 11, color: '#999' }}>引用 {item.used_count} 次</span>,
      ].filter(Boolean)}
    >
      <div style={{ width: '100%' }}>
        <div style={{ fontWeight: 500, marginBottom: 4 }}>
          {isLessonContent ? (
            <><FileTextOutlined style={{ marginRight: 6, color: '#CA8A04' }} /></>
          ) : null}
          {item.title.replace(/^.+? - /, '')}
          {item.grade_level && (
            <Tag style={{ marginLeft: 8, fontSize: 10 }}>
              {item.grade_level === 'grade_1_first' ? '一上' :
               item.grade_level === 'grade_1_second' ? '一下' :
               item.grade_level === 'grade_2_first' ? '二上' :
               item.grade_level === 'grade_2_second' ? '二下' : item.grade_level}
            </Tag>
          )}
        </div>
        <div style={{ color: '#666', fontSize: 13, lineHeight: 1.6 }}>
          {isLessonContent ? (
            <span style={{ color: '#CA8A04' }}>点击查看课文原文 →</span>
          ) : item.content}
        </div>
        {item.keywords_json && item.keywords_json.length > 0 && (
          <div style={{ marginTop: 4 }}>
            {item.keywords_json.map((k: string) => <Tag key={k} style={{ fontSize: 10 }}>{k}</Tag>)}
          </div>
        )}
      </div>
    </List.Item>
  )
}

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState('school')

  // 校内
  const [schoolEntries, setSchoolEntries] = useState<KnowledgeEntryResponse[]>([])
  const [schoolLoading, setSchoolLoading] = useState(true)
  const [schoolSearch, setSchoolSearch] = useState('')
  const [schoolSubject, setSchoolSubject] = useState<string>('')
  const [schoolGrade, setSchoolGrade] = useState<string>('')  // '' = all

  // 课文原文弹窗
  const [lessonModal, setLessonModal] = useState<{ open: boolean; title: string; content: string }>({ open: false, title: '', content: '' })

  // 手动录入弹窗
  const [manualOpen, setManualOpen] = useState(false)
  const [manualSubject, setManualSubject] = useState('')
  const [manualContent, setManualContent] = useState('')
  const [manualSaving, setManualSaving] = useState(false)

  // 校外
  const [extEntries, setExtEntries] = useState<KnowledgeEntryResponse[]>([])
  const [extLoading, setExtLoading] = useState(false)
  const [extSearch, setExtSearch] = useState('')

  useEffect(() => { loadSchool() }, [])

  const loadSchool = async () => {
    setSchoolLoading(true)
    try {
      const { data } = await knowledgeBaseApi.getSchool()
      setSchoolEntries(data)
    } catch { message.error('加载校内知识失败') }
    finally { setSchoolLoading(false) }
  }

  const loadExtracurricular = async () => {
    if (extEntries.length > 0) return // 已加载
    setExtLoading(true)
    try {
      const { data } = await knowledgeBaseApi.getExtracurricular()
      setExtEntries(data)
    } catch { message.error('加载校外知识失败') }
    finally { setExtLoading(false) }
  }

  const handleToggle = async (id: number, approved: boolean) => {
    try {
      await knowledgeBaseApi.toggleApprove(id, approved)
      setSchoolEntries(prev => prev.map(e => e.id === id ? { ...e, auto_approved: approved } : e))
      setExtEntries(prev => prev.map(e => e.id === id ? { ...e, auto_approved: approved } : e))
      message.success(approved ? '已通过' : '已隐藏')
    } catch { message.error('操作失败') }
  }

  // 校内：按课文分组
  const filteredSchool = schoolEntries.filter(e => {
    if (schoolSubject && e.subject !== schoolSubject) return false
    if (schoolGrade && e.grade_level !== schoolGrade) return false
    if (schoolSearch && !e.title.includes(schoolSearch) && !e.content.includes(schoolSearch)) return false
    return true
  })

  // 手动录入
  const handleManualAdd = async () => {
    if (!manualSubject.trim() || !manualContent.trim()) return
    setManualSaving(true)
    try {
      await knowledgeBaseApi.createManual({
        subject: manualSubject.trim(),
        content: manualContent.trim(),
      })
      message.success('已添加')
      setManualSubject('')
      setManualContent('')
      setManualOpen(false)
      loadExtracurricular()
    } catch { message.error('添加失败') }
    finally { setManualSaving(false) }
  }
  const schoolGrouped: Record<string, KnowledgeEntryResponse[]> = {}
  for (const e of filteredSchool) {
    const key = e.lesson || e.subject || '其他'
    if (!schoolGrouped[key]) schoolGrouped[key] = []
    schoolGrouped[key].push(e)
  }
  const schoolSubjects = [...new Set(schoolEntries.map(e => e.subject))].sort()

  // 校外：按学科/兴趣标签分组
  const filteredExt = extEntries.filter(e => {
    if (extSearch && !e.title.includes(extSearch) && !e.content.includes(extSearch)) return false
    return e.auto_approved
  })
  const extGrouped: Record<string, KnowledgeEntryResponse[]> = {}
  for (const e of filteredExt) {
    const key = e.subject || '其他'
    if (!extGrouped[key]) extGrouped[key] = []
    extGrouped[key].push(e)
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1><BookOutlined style={{ marginRight: 8 }} />知识库</h1>
        <p>校内课本知识（系统预置）+ 校外科普（兴趣驱动 AI 自动生成），AI 写文章时会自动引用</p>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => {
          setActiveTab(k)
          if (k === 'extracurricular') loadExtracurricular()
        }}
        items={[
          {
            key: 'school',
            label: (
              <span>
                <ReadOutlined /> 校内知识
                <Badge count={schoolEntries.length} style={{ marginLeft: 8 }} showZero color="#4F46E5" />
              </span>
            ),
            children: (
              <div>
                <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <Input
                    prefix={<SearchOutlined />}
                    placeholder="搜索课本知识..."
                    value={schoolSearch}
                    onChange={e => setSchoolSearch(e.target.value)}
                    style={{ width: 240 }}
                    allowClear
                  />
                  <Select value={schoolSubject} onChange={setSchoolSubject} placeholder="学科" style={{ width: 120 }} allowClear>
                    {schoolSubjects.map(s => <Select.Option key={s} value={s}><Tag color={SUBJECT_COLORS[s] || '#888'}>{s}</Tag></Select.Option>)}
                  </Select>
                  <Select value={schoolGrade} onChange={setSchoolGrade} placeholder="年级" style={{ width: 120 }} allowClear>
                    <Select.Option value="grade_1_first">一年级上册</Select.Option>
                    <Select.Option value="grade_1_second">一年级下册</Select.Option>
                    <Select.Option value="grade_2_first">二年级上册</Select.Option>
                    <Select.Option value="grade_2_second">二年级下册</Select.Option>
                  </Select>
                  <span style={{ color: '#999', fontSize: 12, lineHeight: '32px' }}>
                    共 {filteredSchool.length} 条知识点，覆盖 {schoolSubjects.length} 个学科
                  </span>
                </div>

                <Spin spinning={schoolLoading}>
                  {filteredSchool.length === 0 && !schoolLoading ? (
                    <Empty description="未找到匹配的校内知识" />
                  ) : (
                    <Collapse
                      size="small"
                      items={Object.entries(schoolGrouped).map(([lesson, items]) => ({
                        key: lesson,
                        label: (
                          <span>
                            <Tag color={SUBJECT_COLORS[items[0]?.subject] || '#888'} style={{ marginRight: 8 }}>{items[0]?.subject}</Tag>
                            {lesson}
                            <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>{items.length} 条</span>
                          </span>
                        ),
                        children: (
                          <List size="small" dataSource={items} renderItem={(item) => renderEntryItem(item, handleToggle, (title, content) => setLessonModal({ open: true, title, content }))} />
                        ),
                      }))}
                    />
                  )}
                </Spin>
              </div>
            ),
          },
          {
            key: 'extracurricular',
            label: (
              <span>
                <RocketOutlined /> 校外科普
                <Badge count={extEntries.length} style={{ marginLeft: 8 }} showZero color="#CA8A04" />
              </span>
            ),
            children: (
              <div>
                <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Input
                    prefix={<SearchOutlined />}
                    placeholder="搜索科普知识..."
                    value={extSearch}
                    onChange={e => setExtSearch(e.target.value)}
                    style={{ width: 240 }}
                    allowClear
                  />
                  <Button type="primary" ghost icon={<PlusOutlined />} onClick={() => setManualOpen(true)}>
                    手动录入
                  </Button>
                  <span style={{ color: '#999', fontSize: 12 }}>
                    兴趣标签热度升高时，系统会自动生成对应科普内容
                  </span>
                </div>

                <Spin spinning={extLoading}>
                  {extEntries.length === 0 && !extLoading ? (
                    <Empty description="暂无课外科普知识">
                      <span style={{ color: '#999' }}>
                        当孩子的兴趣标签（如天文、动植物）热度升高后，系统会自动生成科普条目
                      </span>
                    </Empty>
                  ) : filteredExt.length === 0 ? (
                    <Empty description="无匹配结果" />
                  ) : (
                    <Collapse
                      size="small"
                      items={Object.entries(extGrouped).map(([subject, items]) => ({
                        key: subject,
                        label: (
                          <span>
                            <Tag color={SUBJECT_COLORS[subject] || '#CA8A04'} style={{ marginRight: 8 }}>{subject}</Tag>
                            <span style={{ color: '#999', fontSize: 12 }}>{items.length} 条</span>
                          </span>
                        ),
                        children: (
                          <List size="small" dataSource={items} renderItem={(item) => renderEntryItem(item, handleToggle)} />
                        ),
                      }))}
                    />
                  )}
                </Spin>
              </div>
            ),
          },
        ]}
      />

      {/* 课文原文弹窗 */}
      <Modal
        title={lessonModal.title.replace(/ - 课文原文$/, '')}
        open={lessonModal.open}
        onCancel={() => setLessonModal({ open: false, title: '', content: '' })}
        footer={null}
        width={700}
      >
        <div style={{
          fontSize: 20, lineHeight: 1.8, padding: '16px 24px',
          background: '#fafae8', borderRadius: 8, whiteSpace: 'pre-wrap',
          fontFamily: '"楷体", "KaiTi", serif',
        }}>
          {lessonModal.content}
        </div>
      </Modal>

      {/* 手动录入弹窗 */}
      <Modal
        title="手动录入科普知识"
        open={manualOpen}
        onCancel={() => { setManualOpen(false); setManualSubject(''); setManualContent('') }}
        onOk={handleManualAdd}
        confirmLoading={manualSaving}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>学科/兴趣标签</div>
          <Input
            value={manualSubject}
            onChange={e => setManualSubject(e.target.value)}
            placeholder="如：天文、地理、动植物、科学..."
          />
        </div>
        <div>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>知识内容</div>
          <Input.TextArea
            value={manualContent}
            onChange={e => setManualContent(e.target.value)}
            placeholder="粘贴科普内容（100-2000字），适合一年级孩子阅读..."
            rows={8}
            maxLength={2000}
            showCount
          />
        </div>
      </Modal>
    </div>
  )
}
