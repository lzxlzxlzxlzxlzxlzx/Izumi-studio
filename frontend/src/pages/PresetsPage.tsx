import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Spin, Empty, message, Popconfirm, Drawer, Tag, Descriptions, Switch, Modal } from 'antd';
import {
  ArrowLeftOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { fetchPresets, getPreset, deletePreset, updatePreset } from '@/api/client';

interface PresetInfo {
  name: string;
  file_path: string;
  created_at: string;
  updated_at: string;
}

export default function PresetsPage() {
  const navigate = useNavigate();
  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<any>(null);
  const [promptsDraft, setPromptsDraft] = useState<any[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingContent, setEditingContent] = useState('');

  useEffect(() => { loadPresets(); }, []);

  async function loadPresets() {
    setLoading(true);
    try {
      const data = await fetchPresets();
      setPresets(data);
    } catch {
      message.error('加载预设失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleView(name: string) {
    try {
      const data = await getPreset(name);
      setDetail(data);
      setPromptsDraft(data.prompts ? data.prompts.map((p: any) => ({ ...p })) : []);
      setDetailOpen(true);
    } catch {
      message.error('加载预设详情失败');
    }
  }

  async function handleDelete(name: string) {
    try {
      await deletePreset(name);
      message.success('预设已删除');
      loadPresets();
    } catch {
      message.error('删除预设失败');
    }
  }

  function handleTogglePrompt(index: number, enabled: boolean) {
    setPromptsDraft((prev) => {
      if (!prev) return prev;
      const next = [...prev];
      next[index] = { ...next[index], enabled };
      return next;
    });
  }

  async function handleSavePrompts() {
    if (!detail || !promptsDraft) return;
    setSaving(true);
    try {
      const updated = { ...detail, prompts: promptsDraft };
      await updatePreset(detail.name, updated);
      setDetail(updated);
      message.success('预设已更新');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }

  function openEditor(index: number) {
    const p = promptsDraft?.[index];
    if (!p) return;
    setEditingIndex(index);
    setEditingContent(p.content || '');
    setEditModalOpen(true);
  }

  function handleEditSave() {
    if (editingIndex === null || !promptsDraft) return;
    setPromptsDraft((prev) => {
      if (!prev) return prev;
      const next = [...prev];
      next[editingIndex] = { ...next[editingIndex], content: editingContent };
      return next;
    });
    setEditModalOpen(false);
    setEditingIndex(null);
  }

  return (<>
    <div className="min-h-screen bg-[#f8f4f0]">
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-4">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/cards')}
            className="text-gray-400 hover:text-gray-700"
          />
          <h1 className="text-lg font-bold text-gray-800 flex-1">预设</h1>
          <span className="text-sm text-gray-400">共 {presets.length} 个</span>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8">
        {loading ? (
          <div className="flex justify-center py-12"><Spin size="large" /></div>
        ) : presets.length === 0 ? (
          <Empty description="暂无导入的预设 — 请使用导入页面添加预设" />
        ) : (
          <div className="flex flex-col gap-3">
            {presets.map((p) => (
              <div
                key={p.name}
                className="bg-white rounded-lg p-4 border border-gray-200 flex items-center gap-4"
              >
                <div className="flex-1">
                  <h3 className="font-medium text-gray-800">{p.name}</h3>
                  <p className="text-xs text-gray-400 mt-1">
                    更新于: {p.updated_at || p.created_at}
                  </p>
                </div>
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={() => handleView(p.name)}
                  className="text-gray-400 hover:text-gray-700"
                />
                <Popconfirm title="确定删除此预设？" onConfirm={() => handleDelete(p.name)}>
                  <Button
                    type="text"
                    icon={<DeleteOutlined />}
                    danger
                    className="text-gray-400 hover:text-red-400"
                  />
                </Popconfirm>
              </div>
            ))}
          </div>
        )}
      </div>

      <Drawer
        title={<span className="text-gray-800">预设: {detail?.name}</span>}
        placement="right"
        width={480}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        styles={{
          header: { background: '#ffffff', borderBottom: '1px solid #e5e7eb' },
          body: { background: '#ffffff', padding: '16px' },
        }}
      >
        {detail && (
          <div className="space-y-4">
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">参数</h3>
              <Descriptions column={2} size="small">
                <Descriptions.Item label="Temperature">{detail.temperature}</Descriptions.Item>
                <Descriptions.Item label="Top P">{detail.top_p}</Descriptions.Item>
                <Descriptions.Item label="Top K">{detail.top_k}</Descriptions.Item>
                <Descriptions.Item label="频率惩罚">{detail.frequency_penalty}</Descriptions.Item>
                <Descriptions.Item label="存在惩罚">{detail.presence_penalty}</Descriptions.Item>
                <Descriptions.Item label="最大Token">{detail.max_tokens}</Descriptions.Item>
                <Descriptions.Item label="最大上下文">{detail.max_context}</Descriptions.Item>
                <Descriptions.Item label="名称行为">{detail.names_behavior}</Descriptions.Item>
              </Descriptions>
            </section>

            {promptsDraft && promptsDraft.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    提示词 ({promptsDraft.length})
                  </h3>
                  <Button
                    type="primary"
                    size="small"
                    loading={saving}
                    onClick={handleSavePrompts}
                    className="bg-primary-500 hover:bg-primary-600 text-xs"
                  >
                    保存
                  </Button>
                </div>
                <div className="space-y-2">
                  {promptsDraft.map((p: any, i: number) => (
                    <div key={i} className="bg-white rounded p-2 border border-gray-200">
                      <div className="flex items-center gap-2 mb-1">
                        <Switch
                          size="small"
                          checked={p.enabled}
                          onChange={(checked) => handleTogglePrompt(i, checked)}
                        />
                        <span className="text-xs text-gray-800 flex-1 truncate">{p.name || p.identifier}</span>
                        <Tag className="text-[10px] flex-shrink-0">{p.role}</Tag>
                        <Button
                          type="text"
                          size="small"
                          icon={<EditOutlined />}
                          onClick={() => openEditor(i)}
                          className="text-gray-400 hover:text-gray-700"
                        />
                      </div>
                      <pre
                        className="text-xs text-gray-400 line-clamp-3 whitespace-pre-wrap cursor-pointer hover:text-gray-700"
                        onClick={() => openEditor(i)}
                      >
                        {p.content || '(空)'}
                      </pre>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {detail.instruct_config && (
              <section>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">指令配置</h3>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="启用">{String(detail.instruct_config.enabled)}</Descriptions.Item>
                  <Descriptions.Item label="包装">{String(detail.instruct_config.wrap)}</Descriptions.Item>
                  <Descriptions.Item label="输入序列">{detail.instruct_config.input_sequence}</Descriptions.Item>
                  <Descriptions.Item label="输出序列">{detail.instruct_config.output_sequence}</Descriptions.Item>
                </Descriptions>
              </section>
            )}
          </div>
        )}
      </Drawer>
    </div>

      <Modal
        title={<span className="text-gray-800">编辑提示词</span>}
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={handleEditSave}
        okText="保存"
        cancelText="取消"
        width={700}
        styles={{
          header: { background: '#ffffff', borderBottom: '1px solid #e5e7eb', borderRadius: 0 },
          content: { background: '#ffffff' },
          footer: { borderTop: '1px solid #e5e7eb' },
        }}
        className="dark-modal"
      >
        <textarea
          value={editingContent}
          onChange={(e) => setEditingContent(e.target.value)}
          className="w-full bg-white text-gray-700 border border-gray-200 rounded p-3 font-mono text-sm resize-y focus:outline-none focus:border-primary-500"
          rows={24}
        />
      </Modal>
  </>);
}
