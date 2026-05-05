import { useEffect, useRef, useState } from 'react';
import { Modal, Button, Spin, Empty, message, Tag } from 'antd';
import {
  UserOutlined,
  UploadOutlined,
  PlusOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { fetchCharacters, uploadCharacterImage } from '@/api/client';
import type { IStoryCharacter, ICharacterImage } from '@/types';

interface Props {
  open: boolean;
  sessionId: string;
  refreshTrigger?: number;
  onClose: () => void;
}

export default function CharacterRegistryModal({ open, sessionId, refreshTrigger = 0, onClose }: Props) {
  const [characters, setCharacters] = useState<IStoryCharacter[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open || !sessionId) return;
    loadCharacters();
  }, [open, sessionId]);

  // Re-fetch when refreshTrigger changes (e.g., after SSE done)
  useEffect(() => {
    if (!open || !sessionId || refreshTrigger === 0) return;
    loadCharacters();
  }, [refreshTrigger]);

  async function loadCharacters() {
    setLoading(true);
    try {
      const data = await fetchCharacters(sessionId);
      setCharacters(data);
      // Auto-select first character if none selected
      if (data.length > 0) {
        setSelectedId((prev) => {
          if (prev && data.find((c) => c.id === prev)) return prev;
          return data[0].id;
        });
      }
    } catch {
      message.error('加载角色列表失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(file: File) {
    if (!selectedId) return;
    setUploading(true);
    try {
      const updated = await uploadCharacterImage(sessionId, selectedId, file);
      // Replace the character in the list
      setCharacters((prev) => prev.map((c) => (c.id === selectedId ? updated : c)));
      message.success('图片上传成功');
    } catch (err: any) {
      message.error(err.message || '图片上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  const selectedChar = characters.find((c) => c.id === selectedId) || null;
  const activeChars = characters.filter((c) => c.is_active && c.is_alive);
  const inactiveChars = characters.filter((c) => !c.is_active || !c.is_alive);

  return (
    <Modal
      title={
        <div className="flex items-center gap-2 text-gray-800">
          <UserOutlined />
          <span>角色登记簿</span>
          <span className="text-gray-400 text-sm font-normal ml-2">
            共 {characters.length} 个
          </span>
        </div>
      }
      open={open}
      onCancel={onClose}
      width={760}
      footer={null}
      className="character-registry-modal"
      closeIcon={<CloseOutlined className="text-gray-400 hover:text-gray-700" />}
      styles={{
        header: {
          background: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          borderRadius: '8px 8px 0 0',
        },
        body: {
          background: '#ffffff',
          padding: 0,
          borderRadius: '0 0 8px 8px',
        },
        content: {
          background: '#ffffff',
          padding: 0,
        },
      }}
    >
      {loading ? (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      ) : characters.length === 0 ? (
        <div className="py-20">
          <Empty description="暂无登记角色" />
        </div>
      ) : (
        <div className="flex h-[520px]">
          {/* Left: Character List */}
          <div className="w-56 flex-shrink-0 border-r border-gray-200 overflow-y-auto p-2">
            {activeChars.length > 0 && (
              <div className="mb-2">
                <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-2 mb-1">
                  活跃 ({activeChars.length})
                </div>
                {activeChars.map((char) => (
                  <CharListItem
                    key={char.id}
                    char={char}
                    selected={char.id === selectedId}
                    onClick={() => setSelectedId(char.id)}
                  />
                ))}
              </div>
            )}
            {inactiveChars.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-2 mb-1">
                  非活跃 / 已死亡 ({inactiveChars.length})
                </div>
                {inactiveChars.map((char) => (
                  <CharListItem
                    key={char.id}
                    char={char}
                    selected={char.id === selectedId}
                    onClick={() => setSelectedId(char.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Right: Character Detail */}
          <div className="flex-1 overflow-y-auto p-4">
            {selectedChar ? (
              <CharacterDetail
                char={selectedChar}
                onUpload={handleUpload}
                uploading={uploading}
                fileInputRef={fileInputRef}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-gray-400 text-sm">选择一个角色查看详情</p>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

/** Character list item (left panel) */
function CharListItem({
  char,
  selected,
  onClick,
}: {
  char: IStoryCharacter;
  selected: boolean;
  onClick: () => void;
}) {
  const hasImage = char.images && char.images.length > 0;
  return (
    <div
      onClick={onClick}
      className={`flex items-center gap-2 px-2 py-2 rounded-md cursor-pointer text-sm transition-colors ${
        selected
          ? 'bg-primary-100 text-primary-600'
          : 'text-gray-600 hover:bg-gray-100'
      }`}
    >
      <div
        className={`w-2 h-2 rounded-full flex-shrink-0 ${
          char.is_active && char.is_alive ? 'bg-green-500' : 'bg-gray-300'
        }`}
      />
      {hasImage ? (
        <div className="w-6 h-6 rounded-full overflow-hidden flex-shrink-0 bg-gray-100">
          <img
            src={char.images[0].url}
            alt=""
            className="w-full h-full object-cover"
          />
        </div>
      ) : (
        <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
          <UserOutlined className="text-xs text-gray-400" />
        </div>
      )}
      <span className="truncate flex-1">{char.name}</span>
    </div>
  );
}

/** Character detail panel (right side) */
function CharacterDetail({
  char,
  onUpload,
  uploading,
  fileInputRef,
}: {
  char: IStoryCharacter;
  onUpload: (file: File) => Promise<void>;
  uploading: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}) {
  const attrEntries = Object.entries(char.attributes || {}).filter(
    ([k]) => k !== 'name',
  );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div
          className={`w-3 h-3 rounded-full ${
            char.is_active && char.is_alive ? 'bg-green-500' : 'bg-gray-300'
          }`}
        />
        <h2 className="text-lg font-semibold text-gray-800">{char.name}</h2>
        <Tag
          color={char.source === 'card_definition' ? 'blue' : 'purple'}
          className="text-[10px]"
        >
          {char.source === 'card_definition' ? '角色卡' : '生成'}
        </Tag>
      </div>

      {/* Image Gallery */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            角色图
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUpload(file);
            }}
          />
          <Button
            type="text"
            size="small"
            icon={uploading ? <Spin size="small" /> : <UploadOutlined />}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="text-gray-400 hover:text-gray-700 text-xs"
          >
            上传
          </Button>
        </div>
        {char.images && char.images.length > 0 ? (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {char.images.map((img) => (
              <div
                key={img.id}
                className="w-32 h-32 rounded-lg overflow-hidden flex-shrink-0 bg-white border border-gray-200"
              >
                <img
                  src={img.url}
                  alt={img.label || char.name}
                  className="w-full h-full object-cover"
                />
              </div>
            ))}
          </div>
        ) : (
          <div
            className="w-32 h-32 rounded-lg border-2 border-dashed border-gray-200 flex items-center justify-center cursor-pointer hover:border-gray-300 transition-colors"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="text-center">
              <PlusOutlined className="text-gray-400 text-lg" />
              <div className="text-[10px] text-gray-300 mt-1">添加图片</div>
            </div>
          </div>
        )}
      </div>

      {/* All Attributes */}
      {attrEntries.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            属性 ({attrEntries.length})
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            {attrEntries.map(([key, val]) => (
              <div key={key} className="flex items-start gap-2 text-sm">
                <span className="text-gray-400 flex-shrink-0 min-w-[60px]">
                  {key}
                </span>
                <span className="text-gray-700 break-words">
                  {String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {attrEntries.length === 0 && (
        <div className="mb-4 text-sm text-gray-400">暂无属性</div>
      )}

      {/* Meta */}
      <div className="flex gap-4 text-xs text-gray-400 pt-3 border-t border-gray-200">
        <span>
          出现: r{char.first_seen_round}–r{char.last_seen_round}
        </span>
        <span>{char.is_alive ? '存活' : '死亡'}</span>
        <span>{char.is_active ? '出场' : '离场'}</span>
      </div>
    </div>
  );
}

