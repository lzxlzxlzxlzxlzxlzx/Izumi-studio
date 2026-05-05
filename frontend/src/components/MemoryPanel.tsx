import { useEffect, useState } from 'react';
import { Drawer, Tag, Spin, Empty, message } from 'antd';
import { BookOutlined } from '@ant-design/icons';
import { fetchMemories } from '@/api/client';
import type { ILongTermMemory } from '@/types';

const CATEGORY_COLORS: Record<string, string> = {
  '人物关系': 'green',
  '世界观设定': 'blue',
  '重要事件': 'orange',
  '其他': 'default',
};

interface Props {
  open: boolean;
  sessionId: string;
  onClose: () => void;
}

export default function MemoryPanel({ open, sessionId, onClose }: Props) {
  const [memories, setMemories] = useState<ILongTermMemory[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !sessionId) return;
    loadMemories();
  }, [open, sessionId]);

  async function loadMemories() {
    setLoading(true);
    try {
      const data = await fetchMemories(sessionId);
      setMemories(data);
    } catch {
      message.error('加载记忆失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Drawer
      title={
        <div className="flex items-center gap-2 text-gray-800">
          <BookOutlined />
          <span>长期记忆</span>
          <span className="text-gray-400 text-sm font-normal ml-2">
            共 {memories.length} 条
          </span>
        </div>
      }
      placement="right"
      width={400}
      onClose={onClose}
      open={open}
      className=""
      styles={{ body: { background: '#ffffff', padding: '16px' } }}
    >
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Spin size="large" />
        </div>
      ) : memories.length === 0 ? (
        <Empty
          description={<span className="text-gray-400">暂无长期记忆</span>}
          className="py-20"
        />
      ) : (
        <div className="flex flex-col gap-3">
          {memories.map((m) => (
            <div
              key={m.id}
              className="bg-white rounded-lg border border-gray-200 p-4 hover:border-primary-500/30 transition-colors"
            >
              <div className="mb-2">
                <Tag color={CATEGORY_COLORS[m.category] || 'default'} className="m-0 text-xs">
                  {m.category}
                </Tag>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                {m.content}
              </p>
              <div className="mt-2 text-xs text-gray-300">
                {m.created_at?.slice(0, 10) || ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  );
}
