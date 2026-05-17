import { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Spin, Empty, Modal, Form, Input, Select, message, Table, Tag, Space, Popconfirm } from 'antd'
import { PlusOutlined, NodeIndexOutlined, LinkOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { knowledgeApi, KnowledgeNodeResponse, KnowledgeGraphResponse } from '../services/api'
import { useStore } from '../store/useStore'

const CATEGORIES = ['天文', '海洋', '恐龙', '动物', '植物', '科学', '历史', '地理', '人体', '生活']
const LINK_TYPES = [
  { label: '相似', value: 'similar' },
  { label: '因果关系', value: 'cause_effect' },
  { label: '属于', value: 'part_of' },
  { label: '相反', value: 'opposite' },
  { label: '故事关联', value: 'story_connection' },
]

export default function KnowledgePage() {
  const { loading, setLoading } = useStore()
  const [graph, setGraph] = useState<KnowledgeGraphResponse>({ nodes: [], links: [] })
  const [filterCat, setFilterCat] = useState<string>()
  const [addNodeOpen, setAddNodeOpen] = useState(false)
  const [addLinkOpen, setAddLinkOpen] = useState(false)
  const [neighborOpen, setNeighborOpen] = useState(false)
  const [neighborData, setNeighborData] = useState<any>(null)
  const [nodeForm] = Form.useForm()
  const [linkForm] = Form.useForm()

  useEffect(() => { loadGraph() }, [filterCat])

  const loadGraph = async () => {
    setLoading('knowledge', true)
    try {
      const { data } = await knowledgeApi.getGraph()
      if (filterCat) {
        data.nodes = data.nodes.filter(n => n.category === filterCat)
        const nodeIds = new Set(data.nodes.map(n => n.id))
        data.links = data.links.filter(l => nodeIds.has(l.node_a_id) && nodeIds.has(l.node_b_id))
      }
      setGraph(data)
    } catch { /* ignore */ } finally {
      setLoading('knowledge', false)
    }
  }

  const handleAddNode = async (values: any) => {
    try {
      await knowledgeApi.createNode(values)
      message.success('已添加知识点')
      setAddNodeOpen(false)
      nodeForm.resetFields()
      loadGraph()
    } catch { message.error('添加失败') }
  }

  const handleAddLink = async (values: any) => {
    try {
      await knowledgeApi.createLink(values)
      message.success('已创建关联')
      setAddLinkOpen(false)
      linkForm.resetFields()
      loadGraph()
    } catch { message.error('创建关联失败') }
  }

  const handleDeleteNode = async (id: number) => {
    try {
      await knowledgeApi.deleteNode(id)
      message.success('已删除')
      loadGraph()
    } catch { message.error('删除失败') }
  }

  const handleDeleteLink = async (id: number) => {
    try {
      await knowledgeApi.deleteLink(id)
      message.success('已删除关联')
      loadGraph()
    } catch { message.error('删除失败') }
  }

  const handleShowNeighbors = async (nodeId: number) => {
    try {
      const { data } = await knowledgeApi.getNeighbors(nodeId)
      setNeighborData(data)
      setNeighborOpen(true)
    } catch { message.error('查询失败') }
  }

  const nodeColumns = [
    { title: '知识点', dataIndex: 'node_name', key: 'name', render: (n: string) => <strong>{n}</strong> },
    { title: '分类', dataIndex: 'category', key: 'cat', render: (c: string | null) => c ? <Tag>{c}</Tag> : <Tag color="default">未分类</Tag> },
    { title: '关联文章', dataIndex: 'total_articles', key: 'articles', width: 80 },
    { title: '最近复习', dataIndex: 'last_review_date', key: 'review', render: (d: string | null) => d || '-' },
    {
      title: '操作', key: 'actions', width: 140,
      render: (_: any, record: KnowledgeNodeResponse) => (
        <Space size={0}>
          <Button size="small" type="link" icon={<EyeOutlined />}
            onClick={() => handleShowNeighbors(record.id)}>关联</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDeleteNode(record.id)}>
            <Button size="small" type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const filteredNodes = graph.nodes
  const filteredLinks = filterCat
    ? graph.links.filter(l => filteredNodes.some(n => n.id === l.node_a_id) && filteredNodes.some(n => n.id === l.node_b_id))
    : graph.links

  const nodeMap = new Map(filteredNodes.map(n => [n.id, n.node_name]))

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>知识图谱</h1>
        <p>构建孩子的知识网络，发现知识点之间的关联</p>
      </div>

      <Spin spinning={loading['knowledge']}>
        <Card style={{ marginBottom: 16 }}>
          <Space wrap>
            <Select
              placeholder="分类筛选"
              options={CATEGORIES.map(c => ({ label: c, value: c }))}
              value={filterCat}
              onChange={setFilterCat}
              allowClear
              style={{ width: 130 }}
            />
            <Button type="primary" icon={<PlusOutlined />}
              onClick={() => setAddNodeOpen(true)}>添加知识点</Button>
            <Button icon={<LinkOutlined />}
              onClick={() => setAddLinkOpen(true)}
              disabled={filteredNodes.length < 2}>创建关联</Button>
          </Space>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={14}>
            <Card title={`知识点 (${filteredNodes.length})`}>
              {filteredNodes.length === 0 ? (
                <Empty description="暂无知识点" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Table
                  columns={nodeColumns}
                  dataSource={filteredNodes}
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 20 }}
                />
              )}
            </Card>
          </Col>
          <Col xs={24} lg={10}>
            <Card title={`知识关联 (${filteredLinks.length})`}>
              {filteredLinks.length === 0 ? (
                <Empty description="暂无关联" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                filteredLinks.map((link) => (
                  <Card key={link.id} size="small" style={{ marginBottom: 8 }}>
                    <div>
                      <strong>{nodeMap.get(link.node_a_id) || `#${link.node_a_id}`}</strong>
                      <Tag color="blue" style={{ margin: '0 8px' }}>
                        {LINK_TYPES.find(t => t.value === link.link_type)?.label || link.link_type}
                      </Tag>
                      <strong>{nodeMap.get(link.node_b_id) || `#${link.node_b_id}`}</strong>
                      <span style={{ color: '#aaa', marginLeft: 8 }}>×{link.strength}</span>
                      <Popconfirm title="删除此关联？" onConfirm={() => handleDeleteLink(link.id)}>
                        <Button size="small" type="link" danger icon={<DeleteOutlined />} style={{ float: 'right' }} />
                      </Popconfirm>
                    </div>
                  </Card>
                ))
              )}
            </Card>
          </Col>
        </Row>
      </Spin>

      {/* Add Node Modal */}
      <Modal title="添加知识点" open={addNodeOpen} onCancel={() => setAddNodeOpen(false)}
        onOk={() => nodeForm.submit()} confirmLoading={loading['knowledge']}>
        <Form form={nodeForm} layout="vertical" onFinish={handleAddNode}>
          <Form.Item name="node_name" label="知识点名称" rules={[{ required: true }]}>
            <Input placeholder='例如："冥王星"、"光合作用"' />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select options={CATEGORIES.map(c => ({ label: c, value: c }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Add Link Modal */}
      <Modal title="创建知识关联" open={addLinkOpen} onCancel={() => setAddLinkOpen(false)}
        onOk={() => linkForm.submit()} confirmLoading={loading['knowledge']}>
        <Form form={linkForm} layout="vertical" onFinish={handleAddLink}>
          <Form.Item name="node_a_id" label="知识点 A" rules={[{ required: true }]}>
            <Select showSearch placeholder="选择知识点" filterOption={(input, option) =>
              (option?.label as string)?.includes(input)}
              options={filteredNodes.map(n => ({ label: n.node_name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="link_type" label="关联类型" rules={[{ required: true }]}>
            <Select options={LINK_TYPES} />
          </Form.Item>
          <Form.Item name="node_b_id" label="知识点 B" rules={[{ required: true }]}>
            <Select showSearch placeholder="选择知识点" filterOption={(input, option) =>
              (option?.label as string)?.includes(input)}
              options={filteredNodes.map(n => ({ label: n.node_name, value: n.id }))} />
          </Form.Item>
          <Form.Item name="strength" label="关联强度">
            <Select options={[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(v => ({ label: v, value: v }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Neighbors Modal */}
      <Modal title={neighborData?.node?.node_name ? `关联到 "${neighborData.node.node_name}"` : '知识关联'}
        open={neighborOpen} onCancel={() => setNeighborOpen(false)} footer={null}>
        {neighborData?.neighbors?.length > 0 ? (
          neighborData.neighbors.map((n: any) => (
            <Card key={n.node.id} size="small" style={{ marginBottom: 8 }}>
              <strong>{n.node.node_name}</strong>
              <Tag color="blue" style={{ marginLeft: 8 }}>
                {LINK_TYPES.find(t => t.value === n.link_type)?.label || n.link_type}
              </Tag>
              {n.node.category && <Tag style={{ marginLeft: 4 }}>{n.node.category}</Tag>}
            </Card>
          ))
        ) : (
          <Empty description="还没有关联的知识点" />
        )}
      </Modal>
    </div>
  )
}
