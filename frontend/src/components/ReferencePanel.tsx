import { useEffect, useState } from 'react';
import { Spin, Tag, Button, message } from 'antd';
import { CopyOutlined, UserOutlined, CommentOutlined, ReloadOutlined } from '@ant-design/icons';
import { fetchCardsSummary, type ICardSummary } from '@/api/client';

interface Props {
  onCopyRef: (text: string) => void;
}

const TAG_COLORS: Record<string, string> = {
  '奇幻': 'purple',
  '现代': 'blue',
  '历史': 'gold',
  '科幻': 'cyan',
  '悬疑': 'orange',
  '恋爱': 'pink',
  '冒险': 'green',
  '战斗': 'red',
};

export default function ReferencePanel({ onCopyRef }: Props) {
  const [cards, setCards] = useState<ICardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const data = await fetchCardsSummary();
      setCards(data.cards);
    } catch {
      message.error('加载角色卡列表失败');
    } finally {
      setLoading(false);
    }
  }

  function handleCopyCard(card: ICardSummary) {
    onCopyRef(`【角色卡: ${card.name}】`);
    message.success(`已引用: ${card.name}`);
  }

  function handleCopySession(sessionId: string, sessionName: string) {
    onCopyRef(`【会话: ${sessionId}】`);
    message.success(`已引用: ${sessionName}`);
  }

  return (
    <div className="flex flex-col h-full bg-[#f9fafb] border-l border-gray-200">
      {/* Header */}
      <div className="flex-shrink-0 px-3 py-3 border-b border-gray-200 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700">数据浏览</span>
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          onClick={loadData}
          className="text-gray-400 hover:text-gray-700"
        />
      </div>

      {/* Cards List */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Spin size="small" />
          </div>
        ) : cards.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">
            暂无角色卡
          </div>
        ) : (
          <div className="p-2 flex flex-col gap-2">
            {cards.map((card) => {
              const isExpanded = expandedCard === card.id;
              return (
                <div
                  key={card.id}
                  className="rounded-lg bg-white border border-gray-200 overflow-hidden"
                >
                  {/* Card header */}
                  <div
                    className="px-3 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => setExpandedCard(isExpanded ? null : card.id)}
                  >
                    <div className="flex items-center gap-2">
                      <UserOutlined className="text-gray-400 text-sm" />
                      <span className="text-sm font-medium text-gray-800 flex-1 truncate">
                        {card.name}
                      </span>
                      <Button
                        type="text"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCopyCard(card);
                        }}
                        className="text-gray-400 hover:text-primary-500"
                        title="复制角色卡引用"
                      />
                    </div>
                    {card.tags.length > 0 && (
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {card.tags.map((t) => (
                          <Tag key={t} color={TAG_COLORS[t] || 'default'} className="text-xs m-0 leading-tight">
                            {t}
                          </Tag>
                        ))}
                      </div>
                    )}
                    <div className="text-xs text-gray-400 mt-1">
                      {card.sessions.length} 个会话
                    </div>
                  </div>

                  {/* Sessions (expandable) */}
                  {isExpanded && card.sessions.length > 0 && (
                    <div className="border-t border-gray-100 bg-gray-50/50">
                      {card.sessions.map((s) => (
                        <div
                          key={s.id}
                          className="flex items-center gap-2 px-3 py-2 hover:bg-gray-100 transition-colors group"
                        >
                          <CommentOutlined className="text-gray-400 text-xs flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs text-gray-700 truncate">
                              {s.name}
                            </div>
                            <div className="text-xs text-gray-400">
                              {s.message_count} 条消息 · {s.updated_at?.slice(0, 10)}
                            </div>
                          </div>
                          <Button
                            type="text"
                            size="small"
                            icon={<CopyOutlined />}
                            onClick={() => handleCopySession(s.id, s.name)}
                            className="flex-shrink-0 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-primary-500"
                            title="复制会话引用"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                  {isExpanded && card.sessions.length === 0 && (
                    <div className="px-3 py-2 border-t border-gray-100 text-xs text-gray-400 text-center">
                      暂无游玩会话
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
