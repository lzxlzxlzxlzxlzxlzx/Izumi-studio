import { useState, useEffect } from 'react';
import { Input, Button, Select, message, Popconfirm, Spin, Tag } from 'antd';
import { SaveOutlined, CopyOutlined, DeleteOutlined, PlusOutlined, BookOutlined, ArrowLeftOutlined, RightOutlined } from '@ant-design/icons';
import { useCreationStore } from '@/stores/creationStore';
import { updateCreationCard, getWorldbook } from '@/api/client';
import type { ICharacterCard } from '@/types';

const FIELD_META: Record<string, { label: string; type: 'text' | 'textarea' | 'tags' | 'json' | 'npcs' | 'worldbooks' }> = {
  name: { label: '名称', type: 'text' },
  description: { label: '描述', type: 'textarea' },
  tags: { label: '标签', type: 'tags' },
  personality: { label: '性格', type: 'textarea' },
  background: { label: '背景', type: 'textarea' },
  scenario: { label: '场景', type: 'textarea' },
  speaking_style: { label: '说话风格', type: 'textarea' },
  first_mes: { label: '开场白', type: 'textarea' },
  mes_example: { label: '示例对话', type: 'textarea' },
  creator_notes: { label: '创作者备注', type: 'textarea' },
  system_prompt: { label: '系统提示词', type: 'textarea' },
  post_history_instructions: { label: '后置指令', type: 'textarea' },
  writing_style: { label: '写作风格', type: 'textarea' },
  style_tags: { label: '风格标签', type: 'text' },
  character_appearance: { label: '外观描述', type: 'textarea' },
  model: { label: '模型', type: 'text' },
  temperature: { label: 'Temperature', type: 'text' },
  top_p: { label: 'Top P', type: 'text' },
  max_tokens: { label: 'Max Tokens', type: 'text' },
  npcs: { label: 'NPC列表', type: 'npcs' },
  worldbook_ids: { label: '世界书', type: 'worldbooks' },
  authors_note: { label: '作者注', type: 'textarea' },
  cover: { label: '封面', type: 'text' },
};

function getFieldValue(card: ICharacterCard, field: string): unknown {
  if (!card) return '';
  switch (field) {
    case 'name': return card.name || '';
    case 'description': return card.description || '';
    case 'tags': return card.tags || [];
    case 'system_prompt': return card.system_prompt || '';
    case 'post_history_instructions': return card.post_history_instructions || '';
    case 'personality': return card.character?.personality || '';
    case 'background': return card.character?.background || '';
    case 'scenario': return card.character?.scenario || '';
    case 'speaking_style': return card.character?.speaking_style || '';
    case 'first_mes': return card.character?.first_mes || '';
    case 'mes_example': return card.character?.mes_example || '';
    case 'creator_notes': return card.character?.creator_notes || '';
    case 'npcs': return card.character?.npcs || [];
    case 'writing_style': return card.preset_config?.writing_style || '';
    case 'model': return card.preset_config?.model || '';
    case 'temperature': return card.preset_config?.temperature ?? '';
    case 'top_p': return card.preset_config?.top_p ?? '';
    case 'max_tokens': return card.preset_config?.max_tokens ?? '';
    case 'style_tags': return card.image_config?.style_tags || '';
    case 'character_appearance': return card.image_config?.character_appearance || '';
    case 'worldbook_ids': return card.worldbook_ids || [];
    case 'authors_note': return card.authors_note?.content || '';
    default: return '';
  }
}

export default function FieldEditor({ onCopyRef }: { onCopyRef?: (text: string) => void }) {
  const store = useCreationStore();
  const field = store.selectedField;
  const card = store.card;

  const [value, setValue] = useState<string>('');
  const [tagsValue, setTagsValue] = useState<string[]>([]);
  const [npcs, setNpcs] = useState<Array<{ name: string; description: string; attributes: Record<string, unknown>; start_active: boolean }>>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!field || !card) return;
    const val = getFieldValue(card, field);
    const meta = FIELD_META[field];
    if (meta?.type === 'tags') {
      setTagsValue(Array.isArray(val) ? val : []);
    } else if (meta?.type === 'npcs') {
      setNpcs(Array.isArray(val) ? val as typeof npcs : []);
    } else if (meta?.type === 'worldbooks') {
      // worldbooks are read from store.linkedWorldbooks, no local state needed
    } else {
      setValue(typeof val === 'string' ? val : JSON.stringify(val, null, 2));
    }
  }, [field, card]);

  if (!field || !card) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm p-4">
        <div className="text-center">
          <p>选择一个字段开始编辑</p>
          <p className="text-xs mt-1">点击左侧目录中的字段</p>
        </div>
      </div>
    );
  }

  const meta = FIELD_META[field];
  if (!meta) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm p-4">
        未知字段: {field}
      </div>
    );
  }

  async function handleSave() {
    if (!card) return;
    setSaving(true);
    try {
      let saveValue: unknown = value;
      if (meta.type === 'tags') saveValue = tagsValue;
      if (meta.type === 'npcs') saveValue = npcs;

      const updated = await updateCreationCard(card.id, { field: field!, value: saveValue });
      store.setCard(updated);
      store.setEditorDirty(false);
      message.success('已保存');
    } catch (err: any) {
      message.error(err?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  }

  function handleCopyRef() {
    const text = `【字段:${field}】`;
    navigator.clipboard.writeText(text).catch(() => {});
    onCopyRef?.(text);
  }

  function handleValueChange(newVal: string) {
    setValue(newVal);
    store.setEditorDirty(true);
  }

  return (
    <div className="h-full flex flex-col bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex-shrink-0 px-3 py-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">{meta.label}</span>
          <span className="text-xs text-gray-400">{field}</span>
        </div>
        <div className="flex gap-1.5 mt-2">
          <Button
            size="small"
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
            className="text-xs"
          >
            保存
          </Button>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopyRef}
            className="text-xs"
          >
            复制到对话框
          </Button>
        </div>
      </div>

      {/* Editor Body */}
      <div className="flex-1 overflow-auto p-3">
        {meta.type === 'text' && (
          <Input
            value={value}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder={`输入${meta.label}...`}
          />
        )}
        {meta.type === 'textarea' && (
          <Input.TextArea
            value={value}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder={`输入${meta.label}...`}
            autoSize={{ minRows: 4 }}
            className="text-sm"
          />
        )}
        {meta.type === 'tags' && (
          <Select
            mode="tags"
            value={tagsValue}
            onChange={(val) => {
              setTagsValue(val);
              store.setEditorDirty(true);
            }}
            placeholder="输入标签后按回车"
            className="w-full"
          />
        )}
        {meta.type === 'worldbooks' && (
          <WorldbookSection />
        )}
        {meta.type === 'json' && (
          <Input.TextArea
            value={value}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="JSON 格式"
            autoSize={{ minRows: 6 }}
            className="text-xs font-mono"
          />
        )}
        {meta.type === 'npcs' && (
          <div className="flex flex-col gap-3">
            {npcs.map((npc, idx) => (
              <div key={idx} className="border border-gray-200 rounded p-2 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <Input
                    size="small"
                    value={npc.name}
                    onChange={(e) => {
                      const updated = [...npcs];
                      updated[idx] = { ...updated[idx], name: e.target.value };
                      setNpcs(updated);
                      store.setEditorDirty(true);
                    }}
                    placeholder="NPC 名称"
                    className="flex-1 mr-1"
                  />
                  <Popconfirm
                    title="删除此NPC?"
                    onConfirm={() => {
                      setNpcs(npcs.filter((_, i) => i !== idx));
                      store.setEditorDirty(true);
                    }}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} type="text" />
                  </Popconfirm>
                </div>
                <Input.TextArea
                  size="small"
                  value={npc.description}
                  onChange={(e) => {
                    const updated = [...npcs];
                    updated[idx] = { ...updated[idx], description: e.target.value };
                    setNpcs(updated);
                    store.setEditorDirty(true);
                  }}
                  placeholder="NPC 描述"
                  autoSize={{ minRows: 2 }}
                  className="text-xs"
                />
                <div className="flex items-center gap-2 mt-1">
                  <label className="text-xs text-gray-400">
                    <input
                      type="checkbox"
                      checked={npc.start_active}
                      onChange={(e) => {
                        const updated = [...npcs];
                        updated[idx] = { ...updated[idx], start_active: e.target.checked };
                        setNpcs(updated);
                        store.setEditorDirty(true);
                      }}
                      className="mr-1"
                    />
                    初始出场
                  </label>
                </div>
              </div>
            ))}
            <Button
              size="small"
              icon={<PlusOutlined />}
              onClick={() => {
                setNpcs([...npcs, { name: '', description: '', attributes: {}, start_active: true }]);
                store.setEditorDirty(true);
              }}
              className="text-xs"
            >
              添加NPC
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function WorldbookSection() {
  const store = useCreationStore();
  const linkedWbs = store.linkedWorldbooks;
  const wbIds = store.card?.worldbook_ids || [];
  const selectedWbId = store.selectedWorldbookId;
  const selectedEntryId = store.selectedEntryId;
  const wbCache = store.worldbookDataCache;
  const [loading, setLoading] = useState(false);

  // Fetch worldbook data when selected
  useEffect(() => {
    if (selectedWbId && !wbCache[selectedWbId]) {
      setLoading(true);
      getWorldbook(selectedWbId).then((data: any) => {
        store.setWorldbookData(selectedWbId, { entries: data.entries || [] });
      }).catch(() => {}).finally(() => setLoading(false));
    }
  }, [selectedWbId]);

  // Empty state
  if (linkedWbs.length === 0 && wbIds.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-4 text-center">
        <p>暂无关联世界书</p>
        <p className="text-xs mt-1">在对话中告诉泉此方"帮我把背景设定拆分为世界书"，她会帮你拆分</p>
      </div>
    );
  }

  // Level 2: Show specific entry content
  if (selectedEntryId && selectedWbId && wbCache[selectedWbId]) {
    const entry = wbCache[selectedWbId].entries.find((e: any) => e.id === selectedEntryId);
    const wbName = linkedWbs.find((w: any) => w.id === selectedWbId)?.name || '';
    if (entry) {
      return (
        <div className="flex flex-col">
          <div className="flex items-center gap-2 mb-3">
            <Button size="small" type="text" icon={<ArrowLeftOutlined />}
              onClick={() => store.selectEntry(null)}
              className="text-gray-400" />
            <span className="text-xs text-gray-400">{wbName}</span>
          </div>
          <div className="text-sm font-semibold text-gray-800 mb-2">{entry.title}</div>
          {entry.keys && entry.keys.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {entry.keys.map((k: string) => (
                <Tag key={k} color="orange" className="text-xs">{k}</Tag>
              ))}
            </div>
          )}
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded p-3 max-h-96 overflow-auto">
            {entry.content}
          </div>
        </div>
      );
    }
  }

  // Loading state
  if (selectedWbId && loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spin size="small" />
        <span className="ml-2 text-sm text-gray-400">加载世界书...</span>
      </div>
    );
  }

  // Level 1: Show entries of selected worldbook
  if (selectedWbId && wbCache[selectedWbId]) {
    const cached = wbCache[selectedWbId];
    const wbName = linkedWbs.find((w: any) => w.id === selectedWbId)?.name || '';
    return (
      <div className="flex flex-col">
        <div className="flex items-center gap-2 mb-3">
          <Button size="small" type="text" icon={<ArrowLeftOutlined />}
            onClick={() => store.selectWorldbook(null)}
            className="text-gray-400" />
          <span className="text-sm font-medium text-gray-700">{wbName}</span>
          <span className="text-xs text-gray-400">{cached.entries.length} 条</span>
        </div>
        <div className="flex flex-col gap-1">
          {cached.entries.map((entry: any) => (
            <div key={entry.id}
              className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-amber-50 transition-colors border border-gray-100"
              onClick={() => store.selectEntry(entry.id)}
            >
              <span className="flex-1 text-sm text-gray-700 truncate">{entry.title}</span>
              <RightOutlined className="text-xs text-gray-300" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Level 0: Show worldbook list
  return (
    <div className="flex flex-col gap-2">
      {linkedWbs.map((wb: any) => (
        <div key={wb.id}
          className={`border rounded-lg p-3 cursor-pointer transition-colors ${
            selectedWbId === wb.id
              ? 'border-amber-300 bg-amber-50'
              : 'border-gray-200 hover:border-amber-200 hover:bg-amber-50/50'
          }`}
          onClick={() => store.selectWorldbook(wb.id)}
        >
          <div className="flex items-center gap-2 mb-1">
            <BookOutlined className="text-amber-500" />
            <span className="text-sm font-medium text-gray-700">{wb.name}</span>
          </div>
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <span>{wb.entry_count} 个条目</span>
            <span className="text-gray-300">点击查看</span>
          </div>
        </div>
      ))}
      {linkedWbs.length === 0 && wbIds.length > 0 && wbIds.map((id: string) => (
        <div key={id} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
          <div className="text-xs text-gray-400">世界书 {id.slice(0, 8)}...</div>
        </div>
      ))}
    </div>
  );
}
