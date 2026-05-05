import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Input, Tag, Spin, message, Tabs, Descriptions, Form, Empty, Select, Switch, Slider, Popconfirm } from 'antd';
import {
  ArrowLeftOutlined,
  SaveOutlined,
  EditOutlined,
  DeleteOutlined,
  UserOutlined,
  FileTextOutlined,
  TeamOutlined,
  SettingOutlined,
  BookOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import { fetchCard, updateCard, deleteCard, fetchWorldbooks, fetchPresets, uploadImage } from '@/api/client';
import type { ICharacterCard } from '@/types';

const MODEL_OPTIONS = [
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
  { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner' },
  { value: 'qwen-plus', label: 'Qwen Plus' },
  { value: 'qwen-max', label: 'Qwen Max' },
  { value: 'moonshot-v1-8k', label: 'Kimi (Moonshot)' },
];

export default function CardDetailPage() {
  const { cardId } = useParams<{ cardId: string }>();
  const navigate = useNavigate();
  const [card, setCard] = useState<ICharacterCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [worldbooks, setWorldbooks] = useState<Array<{ id: string; name: string }>>([]);
  const [presets, setPresets] = useState<Array<{ name: string }>>([]);
  const [bgUploading, setBgUploading] = useState(false);
  const [form] = Form.useForm();
  const bgFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!cardId) return;
    loadCard();
  }, [cardId]);

  async function loadCard() {
    setLoading(true);
    try {
      const [data, wbData, presetData] = await Promise.all([
        fetchCard(cardId!),
        fetchWorldbooks().catch(() => []),
        fetchPresets().catch(() => []),
      ]);
      setCard(data);
      setWorldbooks(wbData);
      setPresets(presetData);
    } catch {
      message.error('加载角色卡失败');
    } finally {
      setLoading(false);
    }
  }

  function startEditing() {
    if (!card) return;
    form.setFieldsValue({
      name: card.name,
      description: card.description,
      tags: card.tags?.join(', ') || '',
      personality: card.character?.personality || '',
      scenario: card.character?.scenario || '',
      speaking_style: card.character?.speaking_style || '',
      background: card.character?.background || '',
      first_mes: card.character?.first_mes || '',
      mes_example: card.character?.mes_example || '',
      creator_notes: card.character?.creator_notes || '',
      system_prompt: card.system_prompt || '',
      post_history_instructions: card.post_history_instructions || '',
      // preset config
      preset_model: card.preset_config?.model || 'deepseek-chat',
      preset_temperature: card.preset_config?.temperature ?? 0.7,
      preset_word_min: card.preset_config?.word_count_min ?? 100,
      preset_word_max: card.preset_config?.word_count_max ?? 500,
      preset_writing_style: card.preset_config?.writing_style || '',
      preset_chain_of_thought: card.preset_config?.chain_of_thought || false,
      // worldbooks / preset selection
      worldbook_ids: card.worldbook_ids || [],
      preset_name: card.preset_name || '',
    });
    setEditing(true);
  }

  async function handleBgUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !cardId) return;
    setBgUploading(true);
    try {
      const result = await uploadImage(file);
      const updated = await updateCard(cardId, {
        background: { image_path: result.image_path, source: 'upload' },
      });
      setCard(updated);
      message.success('背景图已上传');
    } catch {
      message.error('背景图上传失败');
    } finally {
      setBgUploading(false);
      if (bgFileInputRef.current) bgFileInputRef.current.value = '';
    }
  }

  async function handleDeleteBg() {
    if (!cardId) return;
    try {
      const updated = await updateCard(cardId, {
        background: { image_path: '', source: 'upload' },
      });
      setCard(updated);
      message.success('背景图已删除');
    } catch {
      message.error('删除背景图失败');
    }
  }

  async function handleSave() {
    if (!cardId) return;
    try {
      const values = await form.validateFields();
      setSaving(true);

      const tagList = values.tags
        ? values.tags.split(',').map((t: string) => t.trim()).filter(Boolean)
        : [];

      const updates: Record<string, unknown> = {
        name: values.name,
        description: values.description,
        tags: tagList,
        system_prompt: values.system_prompt || '',
        post_history_instructions: values.post_history_instructions || '',
        worldbook_ids: values.worldbook_ids || [],
        preset_name: values.preset_name || null,
        preset_config: {
          model: values.preset_model || '',
          temperature: values.preset_temperature ?? 0.7,
          word_count_min: values.preset_word_min ?? 100,
          word_count_max: values.preset_word_max ?? 500,
          writing_style: values.preset_writing_style || '',
          chain_of_thought: values.preset_chain_of_thought || false,
        },
        character: {
          name: values.name,
          description: values.description,
          personality: values.personality || '',
          scenario: values.scenario || '',
          speaking_style: values.speaking_style || '',
          background: values.background || '',
          first_mes: values.first_mes || '',
          alternate_greetings: card?.character?.alternate_greetings || [],
          mes_example: values.mes_example || '',
          creator_notes: values.creator_notes || '',
          npcs: card?.character?.npcs || [],
        },
      };

      const updated = await updateCard(cardId, updates);
      setCard(updated);
      setEditing(false);
      message.success('角色卡已保存');
    } catch (err: any) {
      if (err?.errorFields) return; // form validation error
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!cardId) return;
    try {
      await deleteCard(cardId);
      message.success('角色卡已删除');
      navigate('/cards');
    } catch {
      message.error('删除失败');
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-[#f8f4f0]">
        <Spin size="large" />
      </div>
    );
  }

  if (!card) {
    return (
      <div className="flex items-center justify-center h-full bg-[#f8f4f0]">
        <Empty description="未找到角色卡" />
      </div>
    );
  }

  const bgStyle = card.cover?.image_path
    ? { backgroundImage: `url(${card.cover.image_path})` }
    : {};

  return (
    <div className="h-full flex flex-col bg-[#f8f4f0]">
      {/* Header */}
      <div className="flex-shrink-0 z-10 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-4">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(-1)}
            className="text-gray-400 hover:text-gray-700"
          />
          <div className="flex items-center gap-3 flex-1">
            <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-lg font-bold text-gray-800"
                 style={card.avatar?.image_path ? { backgroundImage: `url(${card.avatar.image_path})`, backgroundSize: 'cover' } : {}}>
              {!card.avatar?.image_path && (card.name?.charAt(0) || '?')}
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-800">{card.name}</h1>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">{card.tags?.length || 0} 个标签</span>
                <span className="text-xs text-gray-400">v{card.version || 0}</span>
              </div>
            </div>
          </div>
          {editing ? (
            <div className="flex gap-2">
              <Button onClick={() => setEditing(false)} disabled={saving}>取消</Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
                className="bg-primary-500 hover:bg-primary-600"
              >
                保存
              </Button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Popconfirm
                title="确定删除此角色卡？"
                description="删除后无法恢复，相关的会话和消息也会被删除。"
                onConfirm={handleDelete}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button
                  icon={<DeleteOutlined />}
                  danger
                >
                  删除
                </Button>
              </Popconfirm>
              <Button
                type="primary"
                icon={<EditOutlined />}
                onClick={startEditing}
                className="bg-primary-500 hover:bg-primary-600"
              >
                编辑
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Cover image */}
      {card.cover?.image_path && (
        <div
          className="h-48 bg-cover bg-center relative"
          style={{ backgroundImage: `url(${card.cover.image_path})` }}
        >
          <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent" />
        </div>
      )}

      {/* Background image preview in view mode */}
      {!editing && card.background?.image_path && (
        <div className="h-32 bg-cover bg-center relative border-b border-gray-200"
             style={{ backgroundImage: `url(${card.background.image_path})` }}>
          <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent" />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
        {editing ? (
          <Form form={form} layout="vertical" className="text-gray-600">
            <Tabs
              defaultActiveKey="basic"
              items={[
                {
                  key: 'basic',
                  label: <span className="flex items-center gap-1"><FileTextOutlined />基本信息</span>,
                  children: (
                    <div className="grid grid-cols-1 gap-4 max-w-2xl">
                      <Form.Item name="name" label="名称" rules={[{ required: true }]}>
                        <Input />
                      </Form.Item>
                      <Form.Item name="description" label="描述">
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item name="tags" label="标签（用逗号分隔）">
                        <Input placeholder="奇幻, RPG, 冒险" />
                      </Form.Item>
                      <Form.Item name="system_prompt" label="系统提示">
                        <Input.TextArea rows={4} />
                      </Form.Item>
                      <Form.Item name="post_history_instructions" label="历史后指令">
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      {/* Background image upload */}
                      <div className="border-t border-gray-200 pt-4 mt-2">
                        <p className="text-sm font-medium text-gray-700 mb-2">角色卡背景图</p>
                        <p className="text-xs text-gray-400 mb-3">背景图将显示在角色卡选择和聊天界面作为背景</p>
                        {card.background?.image_path ? (
                          <div className="relative rounded-lg overflow-hidden border border-gray-200 mb-3">
                            <img src={card.background.image_path} alt="背景图" className="w-full h-32 object-cover" />
                            <Button
                              danger
                              size="small"
                              className="absolute top-2 right-2"
                              onClick={handleDeleteBg}
                            >
                              删除
                            </Button>
                          </div>
                        ) : (
                          <div className="bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 p-6 text-center mb-3">
                            <p className="text-gray-400 text-sm">暂无背景图</p>
                          </div>
                        )}
                        <Button
                          icon={<PictureOutlined />}
                          onClick={() => bgFileInputRef.current?.click()}
                          loading={bgUploading}
                        >
                          上传背景图
                        </Button>
                        <input
                          ref={bgFileInputRef}
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={handleBgUpload}
                        />
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'character',
                  label: <span className="flex items-center gap-1"><UserOutlined />角色设定</span>,
                  children: (
                    <div className="grid grid-cols-1 gap-4 max-w-2xl">
                      <Form.Item name="personality" label="性格">
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item name="scenario" label="场景">
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item name="speaking_style" label="说话风格">
                        <Input.TextArea rows={2} />
                      </Form.Item>
                      <Form.Item name="background" label="背景故事">
                        <Input.TextArea rows={4} />
                      </Form.Item>
                      <Form.Item name="first_mes" label="开场白">
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item name="mes_example" label="对话示例">
                        <Input.TextArea rows={3} />
                      </Form.Item>
                      <Form.Item name="creator_notes" label="创作者备注">
                        <Input.TextArea rows={2} />
                      </Form.Item>
                    </div>
                  ),
                },
                {
                  key: 'preset',
                  label: <span className="flex items-center gap-1"><SettingOutlined />预设配置</span>,
                  children: (
                    <div className="grid grid-cols-1 gap-4 max-w-2xl">
                      <Form.Item name="preset_name" label="全局预设">
                        <Select
                          allowClear
                          placeholder="选择预设..."
                          options={presets.map((p: any) => ({ value: p.name, label: p.name }))}
                        />
                      </Form.Item>
                      <Form.Item name="preset_model" label="模型">
                        <Select options={MODEL_OPTIONS} />
                      </Form.Item>
                      <Form.Item name="preset_temperature" label={`温度 (${form.getFieldValue('preset_temperature') ?? 0.7})`}>
                        <Slider min={0} max={2} step={0.1} />
                      </Form.Item>
                      <div className="grid grid-cols-2 gap-4">
                        <Form.Item name="preset_word_min" label="最低字数">
                          <Input type="number" min={10} max={1000} />
                        </Form.Item>
                        <Form.Item name="preset_word_max" label="最高字数">
                          <Input type="number" min={50} max={2000} />
                        </Form.Item>
                      </div>
                      <Form.Item name="preset_writing_style" label="写作风格">
                        <Input.TextArea rows={2} placeholder="例如：优美的奇幻文学风格..." />
                      </Form.Item>
                      <Form.Item name="preset_chain_of_thought" label="思维链" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </div>
                  ),
                },
                {
                  key: 'worldbook',
                  label: <span className="flex items-center gap-1"><BookOutlined />世界书 ({Array.isArray(form.getFieldValue('worldbook_ids')) ? form.getFieldValue('worldbook_ids').length : 0})</span>,
                  children: (
                    <div className="max-w-2xl">
                      <p className="text-sm text-gray-400 mb-4">
                        选择在此角色卡对话中生效的世界书。世界书条目会根据关键词自动匹配并注入上下文。
                      </p>
                      <Form.Item name="worldbook_ids" label="关联世界书">
                        <Select
                          mode="multiple"
                          allowClear
                          placeholder="选择世界书..."
                          style={{ width: '100%' }}
                          options={worldbooks.map((wb: any) => ({ value: wb.id, label: wb.name }))}
                        />
                      </Form.Item>
                      {worldbooks.length === 0 && (
                        <p className="text-xs text-gray-400 mt-2">
                          暂无可选世界书 — 请先在导入页面添加世界书
                        </p>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'npc',
                  label: <span className="flex items-center gap-1"><TeamOutlined />NPC ({card.character?.npcs?.length || 0})</span>,
                  children: (
                    <div>
                      {card.character?.npcs?.length ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {card.character.npcs.map((npc, i) => (
                            <div key={i} className="bg-white rounded-lg p-3 border border-gray-200">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium text-gray-800">{npc.name}</span>
                                <Tag color={npc.start_active ? 'green' : 'default'} className="text-[10px]">
                                  {npc.start_active ? '自动激活' : '休眠'}
                                </Tag>
                              </div>
                              <p className="text-xs text-gray-400">{npc.description || '无描述'}</p>
                              {Object.keys(npc.attributes || {}).length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {Object.entries(npc.attributes).map(([k, v]) => (
                                    <Tag key={k} className="text-[10px]">{k}: {String(v)}</Tag>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <Empty description="暂无NPC" />
                      )}
                    </div>
                  ),
                },
              ]}
            />
          </Form>
        ) : (
          <div className="space-y-6">
            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">描述</h2>
              <p className="text-gray-600 leading-relaxed whitespace-pre-wrap">
                {card.description || '暂无描述'}
              </p>
              {card.tags && card.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {card.tags.map((t) => (
                    <Tag key={t}>{t}</Tag>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">角色设定</h2>
              <Descriptions column={1} size="small" className="text-sm">
                {card.character?.personality && (
                  <Descriptions.Item label="性格">
                    <span className="text-gray-600">{card.character.personality}</span>
                  </Descriptions.Item>
                )}
                {card.character?.scenario && (
                  <Descriptions.Item label="场景">
                    <span className="text-gray-600">{card.character.scenario}</span>
                  </Descriptions.Item>
                )}
                {card.character?.speaking_style && (
                  <Descriptions.Item label="说话风格">
                    <span className="text-gray-600">{card.character.speaking_style}</span>
                  </Descriptions.Item>
                )}
                {card.character?.background && (
                  <Descriptions.Item label="背景故事">
                    <span className="text-gray-600 whitespace-pre-wrap">{card.character.background}</span>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </section>

            {card.character?.npcs && card.character.npcs.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  NPC ({card.character.npcs.length})
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {card.character.npcs.map((npc, i) => (
                    <div key={i} className="bg-white rounded-lg p-3 border border-gray-200">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-800">{npc.name}</span>
                        <Tag color={npc.start_active ? 'green' : 'default'} className="text-[10px]">
                          {npc.start_active ? '自动激活' : '休眠'}
                        </Tag>
                      </div>
                      <p className="text-xs text-gray-400">{npc.description || '无描述'}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {card.system_prompt && (
              <section>
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">系统提示</h2>
                <pre className="bg-white rounded-lg p-3 text-xs text-gray-400 whitespace-pre-wrap border border-gray-200">
                  {card.system_prompt}
                </pre>
              </section>
            )}

            {(card.worldbook_ids?.length > 0 || card.preset_name) && (
              <section>
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">关联配置</h2>
                <div className="text-sm space-y-1">
                  {card.preset_name && (
                    <div><span className="text-gray-400">预设:</span> <span className="text-gray-600 ml-2">{card.preset_name}</span></div>
                  )}
                  {card.worldbook_ids?.length > 0 && (
                    <div><span className="text-gray-400">世界书:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {card.worldbook_ids.map((wid) => {
                          const wb = worldbooks.find((w: any) => w.id === wid);
                          return <Tag key={wid} className="text-[10px]">{wb?.name || wid.slice(0, 8)}</Tag>;
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            )}

            <section className="text-xs text-gray-300 space-y-1">
              <div>ID: {card.id}</div>
              <div>版本: {card.version || 0}</div>
              <div>创建时间: {card.created_at}</div>
              <div>状态: {card.status}</div>
            </section>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
