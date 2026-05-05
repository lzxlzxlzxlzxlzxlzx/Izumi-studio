import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Spin, Popconfirm, message } from 'antd';
import { PlusOutlined, DeleteOutlined, MessageOutlined } from '@ant-design/icons';
import { fetchKonataSessions, createKonataSession, deleteKonataSession } from '@/api/client';
import type { IChatSession } from '@/types';
import { useKonataStore } from '@/stores/konataStore';

export default function ConversationSidebar() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const store = useKonataStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSessions();
  }, []);

  async function loadSessions() {
    setLoading(true);
    try {
      const sessions: IChatSession[] = await fetchKonataSessions();
      store.setSessions(sessions);
    } catch {
      message.error('加载对话列表失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleNew() {
    try {
      const session: IChatSession = await createKonataSession();
      store.setSessions([session, ...store.sessions]);
      navigate(`/konata/${session.id}`);
    } catch {
      message.error('创建对话失败');
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await deleteKonataSession(id);
      store.setSessions(store.sessions.filter((s) => s.id !== id));
      if (id === sessionId) {
        navigate('/konata');
      }
    } catch {
      message.error('删除对话失败');
    }
  }

  const activeId = sessionId;

  return (
    <div className="flex flex-col h-full bg-[#f9fafb] border-r border-gray-200">
      {/* Header */}
      <div className="flex-shrink-0 p-3 border-b border-gray-200">
        <Button
          type="dashed"
          block
          icon={<PlusOutlined />}
          onClick={handleNew}
          className="text-gray-600 hover:text-gray-900 hover:border-gray-400"
        >
          新建对话
        </Button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Spin size="small" />
          </div>
        ) : store.sessions.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">
            还没有对话记录
          </div>
        ) : (
          <div className="p-2 flex flex-col gap-0.5">
            {store.sessions.map((s) => {
              const isActive = s.id === activeId;
              return (
                <div
                  key={s.id}
                  onClick={() => navigate(`/konata/${s.id}`)}
                  className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <MessageOutlined
                    className={`text-sm flex-shrink-0 ${
                      isActive ? 'text-primary-500' : 'text-gray-400'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">
                      {s.name || '新对话'}
                    </div>
                    <div className="text-xs text-gray-400 truncate">
                      {s.updated_at?.slice(0, 16) || ''}
                    </div>
                  </div>
                  <Popconfirm
                    title="确定删除此对话？"
                    onConfirm={(e) => handleDelete(s.id, e as any)}
                    okText="删除"
                    cancelText="取消"
                    placement="right"
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      className="flex-shrink-0 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
