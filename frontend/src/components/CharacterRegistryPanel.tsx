import { useEffect, useState } from 'react';
import { Drawer, Tag, Descriptions, Spin, Empty, message } from 'antd';
import { CloseOutlined, UserOutlined } from '@ant-design/icons';
import { fetchCharacters } from '@/api/client';
import type { IStoryCharacter } from '@/types';

interface Props {
  open: boolean;
  sessionId: string;
  onClose: () => void;
}

export default function CharacterRegistryPanel({ open, sessionId, onClose }: Props) {
  const [characters, setCharacters] = useState<IStoryCharacter[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !sessionId) return;
    loadCharacters();
  }, [open, sessionId]);

  async function loadCharacters() {
    setLoading(true);
    try {
      const data = await fetchCharacters(sessionId);
      setCharacters(data);
    } catch {
      message.error('加载角色列表失败');
    } finally {
      setLoading(false);
    }
  }

  const activeChars = characters.filter((c) => c.is_active && c.is_alive);
  const inactiveChars = characters.filter((c) => !c.is_active || !c.is_alive);

  return (
    <Drawer
      title={
        <div className="flex items-center gap-2 text-gray-800">
          <UserOutlined />
          <span>角色登记簿</span>
          <span className="text-gray-400 text-sm font-normal ml-2">
            共 {characters.length} 个
          </span>
        </div>
      }
      placement="right"
      width={360}
      onClose={onClose}
      open={open}
      className="character-registry-drawer"
      styles={{
        header: { background: '#ffffff', borderBottom: '1px solid #e5e7eb' },
        body: { background: '#ffffff', padding: '16px' },
      }}
      closeIcon={<CloseOutlined className="text-gray-400 hover:text-gray-700" />}
    >
      {loading ? (
        <div className="flex justify-center py-12">
          <Spin />
        </div>
      ) : characters.length === 0 ? (
        <Empty description="暂无登记角色" />
      ) : (
        <div className="flex flex-col gap-4">
          {activeChars.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                活跃 ({activeChars.length})
              </h3>
              {activeChars.map((char) => (
                <CharacterCard key={char.id} char={char} />
              ))}
            </section>
          )}

          {inactiveChars.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                非活跃 / 已死亡 ({inactiveChars.length})
              </h3>
              {inactiveChars.map((char) => (
                <CharacterCard key={char.id} char={char} />
              ))}
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}

function CharacterCard({ char }: { char: IStoryCharacter }) {
  const attrEntries = Object.entries(char.attributes || {});

  return (
    <div className="bg-white rounded-lg p-3 mb-2 border border-gray-200">
      <div className="flex items-center gap-2 mb-2">
        <div
          className={`w-3 h-3 rounded-full ${
            char.is_active && char.is_alive ? 'bg-green-500' : 'bg-gray-300'
          }`}
        />
        <span className="font-medium text-gray-800 text-sm">{char.name}</span>
        <Tag color={char.source === 'card_definition' ? 'blue' : 'purple'} className="ml-auto text-[10px]">
          {char.source === 'card_definition' ? '角色卡' : '生成'}
        </Tag>
      </div>

      {attrEntries.length > 0 && (
        <Descriptions size="small" column={2} className="text-xs">
          {attrEntries.slice(0, 6).map(([key, val]) => (
            <Descriptions.Item key={key} label={key} className="text-xs">
              <span className="text-gray-700">{String(val)}</span>
            </Descriptions.Item>
          ))}
        </Descriptions>
      )}

      {attrEntries.length > 6 && (
        <div className="text-xs text-gray-400 mt-1">还有 +{attrEntries.length - 6} 个属性</div>
      )}

      <div className="flex gap-4 mt-2 text-[10px] text-gray-400">
        <span>出现: r{char.first_seen_round}-{char.last_seen_round}</span>
        <span>{char.is_alive ? '存活' : '死亡'}</span>
        <span>{char.is_active ? '活跃' : '非活跃'}</span>
      </div>
    </div>
  );
}
