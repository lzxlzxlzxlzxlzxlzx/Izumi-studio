import { useState } from 'react';
import { Tooltip } from 'antd';
import {
  CopyOutlined,
  FileTextOutlined,
  UserOutlined,
  SettingOutlined,
  PictureOutlined,
  BookOutlined,
  MessageOutlined,
  DownOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useCreationStore } from '@/stores/creationStore';
import type { ICharacterCard } from '@/types';

interface OutlineSection {
  key: string;
  label: string;
  icon: React.ReactNode;
  children?: OutlineField[];
}

interface OutlineField {
  key: string;
  label: string;
  icon: string;
  getValue: (card: ICharacterCard) => string;
  isArray?: boolean;
}

const SECTIONS: OutlineSection[] = [
  {
    key: 'basic',
    label: '基础信息',
    icon: <FileTextOutlined />,
    children: [
      { key: 'name', label: '名称', icon: '📝', getValue: (c) => c.name || '' },
      { key: 'description', label: '描述', icon: '📝', getValue: (c) => c.description || '' },
      { key: 'tags', label: '标签', icon: '🏷️', getValue: (c) => (c.tags || []).join(', '), isArray: true },
      { key: 'cover', label: '封面', icon: '🖼️', getValue: (c) => c.cover?.image_path || '' },
    ],
  },
  {
    key: 'character',
    label: '角色设定',
    icon: <UserOutlined />,
    children: [
      { key: 'personality', label: '性格', icon: '💬', getValue: (c) => c.character?.personality || '' },
      { key: 'background', label: '背景', icon: '📖', getValue: (c) => c.character?.background || '' },
      { key: 'scenario', label: '场景', icon: '🌍', getValue: (c) => c.character?.scenario || '' },
      { key: 'speaking_style', label: '说话风格', icon: '🗣️', getValue: (c) => c.character?.speaking_style || '' },
      { key: 'first_mes', label: '开场白', icon: '👋', getValue: (c) => c.character?.first_mes || '' },
      { key: 'mes_example', label: '示例对话', icon: '💬', getValue: (c) => c.character?.mes_example || '' },
      { key: 'creator_notes', label: '创作者备注', icon: '📝', getValue: (c) => c.character?.creator_notes || '' },
      { key: 'npcs', label: 'NPC列表', icon: '👥', getValue: (c) => `${(c.character?.npcs || []).length} 个NPC`, isArray: true },
    ],
  },
  {
    key: 'preset',
    label: '预设配置',
    icon: <SettingOutlined />,
    children: [
      { key: 'writing_style', label: '写作风格', icon: '✍️', getValue: (c) => c.preset_config?.writing_style || '' },
      { key: 'model', label: '模型', icon: '🤖', getValue: (c) => c.preset_config?.model || '' },
    ],
  },
  {
    key: 'image',
    label: '图像配置',
    icon: <PictureOutlined />,
    children: [
      { key: 'style_tags', label: '风格标签', icon: '🎨', getValue: (c) => c.image_config?.style_tags || '' },
      { key: 'character_appearance', label: '外观描述', icon: '👤', getValue: (c) => c.image_config?.character_appearance || '' },
    ],
  },
  {
    key: 'system',
    label: '系统提示',
    icon: <MessageOutlined />,
    children: [
      { key: 'system_prompt', label: '系统提示词', icon: '💬', getValue: (c) => c.system_prompt || '' },
      { key: 'post_history_instructions', label: '后置指令', icon: '📋', getValue: (c) => c.post_history_instructions || '' },
    ],
  },
  {
    key: 'other',
    label: '其他',
    icon: <BookOutlined />,
    children: [
      { key: 'worldbook_ids', label: '世界书', icon: '📖', getValue: (c) => `${(c.worldbook_ids || []).length} 本`, isArray: true },
      { key: 'authors_note', label: '作者注', icon: '📝', getValue: (c) => c.authors_note?.content || '' },
    ],
  },
];

export default function CardOutlinePanel({ onCopyRef }: { onCopyRef?: (text: string) => void }) {
  const store = useCreationStore();
  const card = store.card;
  const linkedWbs = store.linkedWorldbooks;
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  function toggleSection(key: string) {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function hasContent(val: string) {
    return val && val.length > 0 && val !== '0 个NPC' && val !== '0 本';
  }

  function hasWorldbookContent() {
    return linkedWbs.length > 0 || (card?.worldbook_ids && card.worldbook_ids.length > 0);
  }

  function handleCopy(fieldKey: string) {
    const text = `【字段:${fieldKey}】`;
    navigator.clipboard.writeText(text).catch(() => {});
    onCopyRef?.(text);
  }

  function handleEdit(fieldKey: string) {
    store.setSelectedField(fieldKey);
  }

  function handleWorldbookClick(wbId: string) {
    store.selectWorldbook(wbId);
  }

  function handleEntryClick(wbId: string, entryId: string) {
    store.selectWorldbook(wbId);
    store.selectEntry(entryId);
  }

  if (!card) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm p-4">
        <div className="text-center">
          <FileTextOutlined className="text-2xl mb-2 block" />
          <p>暂无角色卡</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto bg-white border-r border-gray-200 select-none">
      <div className="px-3 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">
        卡片目录
      </div>
      {SECTIONS.map((section) => {
        const isCollapsed = collapsed[section.key] || false;
        return (
          <div key={section.key}>
            <div
              className="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer hover:bg-gray-50 text-sm font-medium text-gray-700"
              onClick={() => toggleSection(section.key)}
            >
              <span className="text-gray-400 text-xs">
                {isCollapsed ? <RightOutlined /> : <DownOutlined />}
              </span>
              <span className="text-gray-400">{section.icon}</span>
              <span>{section.label}</span>
            </div>
            {!isCollapsed &&
              section.children?.map((field) => {
                const val = field.getValue(card);
                const isWorldbookField = field.key === 'worldbook_ids';
                const filled = isWorldbookField ? hasWorldbookContent() : hasContent(val);
                return (
                  <div key={field.key}>
                    <div
                      className={`flex items-center gap-1.5 pl-10 pr-2 py-1 text-sm cursor-pointer hover:bg-purple-50 transition-colors ${
                        store.selectedField === field.key ? 'bg-purple-100 text-purple-700' : 'text-gray-600'
                      }`}
                      onClick={() => handleEdit(field.key)}
                    >
                      <span className="text-xs">{field.icon}</span>
                      <span className="flex-1 truncate">{field.label}</span>
                      <span
                        className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                          filled ? 'bg-green-400' : 'bg-gray-300'
                        }`}
                      />
                      <Tooltip title="复制引用到对话框">
                        <span
                          className="text-gray-400 hover:text-purple-500 text-xs cursor-pointer flex-shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCopy(field.key);
                          }}
                        >
                          <CopyOutlined />
                        </span>
                      </Tooltip>
                    </div>
                    {/* Linked worldbook entries — click to view in right panel */}
                    {isWorldbookField && linkedWbs.length > 0 && linkedWbs.map((wb) => {
                      const isSelected = store.selectedWorldbookId === wb.id;
                      return (
                        <div key={wb.id}>
                          <div
                            className={`flex items-center gap-1.5 pl-12 pr-2 py-1 text-xs cursor-pointer rounded transition-colors ${
                              isSelected ? 'bg-amber-100 text-amber-700' : 'text-gray-600 hover:bg-amber-50'
                            }`}
                            onClick={() => handleWorldbookClick(wb.id)}
                          >
                            <BookOutlined className={isSelected ? 'text-amber-500' : 'text-amber-400'} />
                            <span className="flex-1 truncate">{wb.name}</span>
                            <span className="text-gray-400">{wb.entry_count}条</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
          </div>
        );
      })}
    </div>
  );
}
