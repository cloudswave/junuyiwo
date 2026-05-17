import { useState, useEffect, useRef } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Select, Modal, Input, Badge, App, FloatButton, theme } from 'antd'
import {
  HomeOutlined,
  BookOutlined,
  PlusOutlined,
  ReloadOutlined,
  FileTextOutlined,
  BarChartOutlined,
  QuestionCircleOutlined,
  NodeIndexOutlined,
  AudioOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  CameraOutlined,
  StarOutlined,
  DatabaseOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import { studentsApi, curiosityApi, asrApi, zonesApi, knowledgeBaseApi, type StudentResponse, type ReadingLevelResponse } from '../services/api'

// 图片路径：APK 生产模式需补全绝对路径（在 frontend/.env 配置 VITE_API_HOST）
const API_HOST = import.meta.env.VITE_API_HOST || 'http://192.168.1.4:8000'
const IMG_BASE = import.meta.env.DEV ? '' : API_HOST
const resolveImg = (path: string) => path.startsWith('http') ? path : IMG_BASE + path

const { Header, Sider, Content } = Layout

const staticMenuItems = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/words', icon: <BookOutlined />, label: '新鲜字库' },
  { key: '/add', icon: <PlusOutlined />, label: '录入生字' },
  { key: '/known', icon: <StarOutlined />, label: '已学生字' },
  { key: '/review', icon: <ReloadOutlined />, label: '复习' },
  { key: '/articles', icon: <FileTextOutlined />, label: '历史文章' },
  { key: '/knowledge', icon: <NodeIndexOutlined />, label: '知识图谱' },
  { key: '/knowledge-base', icon: <DatabaseOutlined />, label: '知识库' },
  { key: '/stats', icon: <BarChartOutlined />, label: '学习统计' },
  { key: '/voice', icon: <AudioOutlined />, label: '真人录音' },
]

export default function AppLayout() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [students, setStudents] = useState<StudentResponse[]>([])
  const [currentId, setCurrentId] = useState(() => parseInt(localStorage.getItem('currentStudentId') || '1'))
  const [addOpen, setAddOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [unansweredCount, setUnansweredCount] = useState(0)
  const [readingLevel, setReadingLevel] = useState<ReadingLevelResponse | null>(null)
  const [avatarLoading, setAvatarLoading] = useState(false)

  // Textbook setup
  const [kbConfigured, setKbConfigured] = useState(true)
  const [kbSetupOpen, setKbSetupOpen] = useState(false)
  const [kbVersion, setKbVersion] = useState('人教版')
  const [kbGrade, setKbGrade] = useState('grade_1')
  const [kbSemester, setKbSemester] = useState('second')

  // Voice question state
  type VoiceState = 'idle' | 'recording' | 'recognizing' | 'success' | 'error'
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => { loadStudents() }, [])
  useEffect(() => {
    curiosityApi.getBadge().then(({ data }) => setUnansweredCount(data.unanswered_count)).catch(() => {})
    zonesApi.getReadingLevel().then(({ data }) => setReadingLevel(data)).catch(() => {})
    // Check textbook config
    knowledgeBaseApi.getConfig().then(({ data }) => {
      if (!data.configured) {
        setKbConfigured(false)
        setKbSetupOpen(true)
      }
    }).catch(() => {})
  }, [])

  const handleKbSetup = async () => {
    try {
      await knowledgeBaseApi.setup({
        textbook_version: kbVersion,
        current_grade: kbGrade,
        current_semester: kbSemester,
      })
      setKbConfigured(true)
      setKbSetupOpen(false)
      message.success('教材配置已保存！知识库已就绪')
    } catch {
      message.error('保存失败，请重试')
    }
  }

  const refreshBadge = () => {
    curiosityApi.getBadge().then(({ data }) => setUnansweredCount(data.unanswered_count)).catch(() => {})
  }

  const startVoiceQuestion = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size === 0) {
          setVoiceState('error')
          message.error('录音为空，请重试')
          return
        }

        setVoiceState('recognizing')
        try {
          const { data: asrResult } = await asrApi.recognize(new File([blob], 'question.webm'))
          if (!asrResult.text?.trim()) {
            setVoiceState('error')
            message.error('未能识别到内容，请再说一遍')
            return
          }

          await curiosityApi.createEvent({
            event_date: new Date().toISOString().slice(0, 10),
            raw_text: asrResult.text.trim(),
          })

          setVoiceState('success')
          refreshBadge()
          message.success('收到！你的问题已经记下来了～')

          setTimeout(() => setVoiceState('idle'), 2500)
        } catch (err: any) {
          setVoiceState('error')
          message.error(err?.response?.data?.detail || '识别失败，请重试')
          setTimeout(() => setVoiceState('idle'), 3000)
        }
      }

      mediaRecorder.start()
      setVoiceState('recording')
    } catch {
      message.error('无法访问麦克风，请检查权限')
    }
  }

  const stopVoiceQuestion = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
  }

  const handleVoiceButton = () => {
    if (voiceState === 'recording') {
      stopVoiceQuestion()
    } else if (voiceState === 'idle') {
      startVoiceQuestion()
    }
  }

  const loadStudents = async () => {
    try {
      const { data } = await studentsApi.list()
      setStudents(data)
    } catch { /* ignore */ }
  }

  const switchStudent = (id: number) => {
    setCurrentId(id)
    localStorage.setItem('currentStudentId', String(id))
    window.location.reload()
  }

  const handleAdd = async () => {
    if (!newName.trim()) return
    try {
      const { data } = await studentsApi.create({ name: newName.trim() })
      message.success(`已添加 ${data.name}`)
      setNewName('')
      setAddOpen(false)
      await loadStudents()
      switchStudent(data.id)
    } catch { message.error('添加失败') }
  }

  const handleGenerateAvatar = async (useGpu = false) => {
    setAvatarLoading(true)
    try {
      const { data } = await studentsApi.generateAvatar(currentId, useGpu)
      message.success(`已为 ${data.name} 生成专属头像`)
      await loadStudents()
    } catch { message.error('头像生成失败') }
    finally { setAvatarLoading(false) }
  }

  const selectedKey = '/' + location.pathname.split('/')[1]
  const currentStudent = students.find(s => s.id === currentId)

  const menuItems = [
    ...staticMenuItems.slice(0, 5),
    {
      key: '/curiosity',
      icon: <QuestionCircleOutlined />,
      label: (
        <span>
          好奇心
          {unansweredCount > 0 && (
            <Badge count={unansweredCount} size="small" style={{ marginLeft: 8 }} />
          )}
        </span>
      ),
    },
    ...staticMenuItems.slice(5),
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        breakpoint="lg"
        collapsedWidth={0}
        onBreakpoint={(broken) => setCollapsed(broken)}
        style={{ background: '#fff', borderRight: '1px solid #f0f0f0' }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid #f0f0f0',
        }}>
          <span style={{
            fontSize: collapsed ? 16 : 20,
            fontWeight: 700,
            color: '#4F46E5',
            whiteSpace: 'nowrap',
          }}>
            {collapsed ? '俊宜' : '俊宜识字'}
          </span>
        </div>

        {/* Student Switcher */}
        {!collapsed && (
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
            <Select
              value={currentId}
              onChange={switchStudent}
              style={{ width: '100%' }}
              popupRender={(menu) => (
                <>
                  {menu}
                  <div style={{ borderTop: '1px solid #f0f0f0', padding: 8 }}>
                    <Button type="text" icon={<PlusOutlined />} block onClick={() => setAddOpen(true)}>
                      添加孩子
                    </Button>
                  </div>
                </>
              )}
            >
              {students.map((s) => (
                <Select.Option key={s.id} value={s.id}>
                  {s.avatar.startsWith('/static') || s.avatar.startsWith('http')
                    ? <img src={resolveImg(s.avatar)} style={{ width: 22, height: 22, borderRadius: '50%', verticalAlign: 'middle' }} alt="" />
                    : s.avatar
                  } {s.name}
                </Select.Option>
              ))}
            </Select>
            <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
              <Button
                size="small"
                icon={<CameraOutlined />}
                loading={avatarLoading}
                onClick={() => handleGenerateAvatar(false)}
                style={{ flex: 1 }}
              >
                GLM生图
              </Button>
              <Button
                size="small"
                type="primary"
                ghost
                loading={avatarLoading}
                onClick={() => handleGenerateAvatar(true)}
                style={{ flex: 1 }}
              >
                GPU生图
              </Button>
            </div>

            {/* Reading Level Badge */}
            {readingLevel && (
              <div style={{
                padding: '8px 16px',
                borderBottom: '1px solid #f0f0f0',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  borderRadius: 8, padding: '8px 12px',
                  color: '#fff', fontSize: 13,
                }}>
                  <span style={{ fontSize: 20 }}>{readingLevel.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, lineHeight: 1.3 }}>
                      Lv.{readingLevel.level} {readingLevel.name}
                    </div>
                    {readingLevel.next && (
                      <div style={{ fontSize: 10, opacity: 0.8, lineHeight: 1.4 }}>
                        下一级：{readingLevel.next.icon} {readingLevel.next.name}
                        <br />
                        需识字 {readingLevel.next.known_current}/{readingLevel.next.known_required}
                        ，读完 {readingLevel.next.articles_current}/{readingLevel.next.articles_required} 篇
                      </div>
                    )}
                    {!readingLevel.next && (
                      <div style={{ fontSize: 10, opacity: 0.8 }}>已达最高等级</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none', marginTop: 8 }}
        />
      </Sider>

      <Modal
        title="添加孩子"
        open={addOpen}
        onOk={handleAdd}
        onCancel={() => { setAddOpen(false); setNewName('') }}
        okText="添加"
      >
        <Input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="输入孩子昵称，如：小美、俊宜"
          onPressEnter={handleAdd}
        />
      </Modal>
      <Layout>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          borderBottom: '1px solid #f0f0f0',
          height: 56,
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
        </Header>
        <Content style={{ overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>

      {/* Textbook Setup Modal */}
      <Modal
        title="📚 首次设置 — 选择教材"
        open={kbSetupOpen}
        closable={false}
        maskClosable={false}
        onOk={handleKbSetup}
        okText="确认，开始使用"
      >
        <p style={{ marginBottom: 16, color: '#666' }}>
          请选择俊宜学校使用的教材版本和当前年级。系统会自动同步课本知识到阅读中。
        </p>
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4, fontWeight: 500 }}>教材版本</div>
          <Select value={kbVersion} onChange={setKbVersion} style={{ width: '100%' }}>
            <Select.Option value="人教版">人教版</Select.Option>
            <Select.Option value="部编版">部编版</Select.Option>
            <Select.Option value="苏教版">苏教版</Select.Option>
          </Select>
        </div>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>年级</div>
          <Select value={kbGrade} onChange={(v) => { setKbGrade(v); setKbSemester('second') }} style={{ width: '100%' }}>
            <Select.Option value="grade_1">一年级</Select.Option>
            <Select.Option value="grade_2">二年级</Select.Option>
          </Select>
        </div>
        <div>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>学期</div>
          <Select value={kbSemester} onChange={setKbSemester} style={{ width: '100%' }}>
            <Select.Option value="first">上册</Select.Option>
            <Select.Option value="second">下册</Select.Option>
          </Select>
        </div>
      </Modal>

      {/* Voice Question FloatButton */}
      <FloatButton
        icon={
          voiceState === 'recording' ? <AudioOutlined style={{ color: '#ff4d4f' }} /> :
          voiceState === 'recognizing' ? <LoadingOutlined style={{ color: '#1677ff' }} /> :
          voiceState === 'success' ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
          voiceState === 'error' ? <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> :
          <QuestionCircleOutlined />
        }
        type={voiceState === 'recording' ? 'primary' : 'default'}
        style={{
          right: 32,
          bottom: 48,
          ...(voiceState === 'recording' && {
            animation: 'pulse 1.5s ease-in-out infinite',
            boxShadow: '0 0 0 0 rgba(255, 77, 79, 0.5)',
          }),
        }}
        tooltip={
          voiceState === 'recording' ? '点击停止录音' :
          voiceState === 'recognizing' ? '正在识别中...' :
          voiceState === 'success' ? '已记录！' :
          voiceState === 'error' ? '识别失败，点击重试' :
          '俊宜，你有什么想问的？'
        }
        onClick={handleVoiceButton}
      />
      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0.5); }
          50% { box-shadow: 0 0 0 12px rgba(255, 77, 79, 0); }
        }
      `}</style>
    </Layout>
  )
}
