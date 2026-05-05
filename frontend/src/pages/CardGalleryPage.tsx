import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input, Tag, Spin, Empty, Button, message } from 'antd';
import { SearchOutlined, InfoCircleOutlined, ImportOutlined, SettingOutlined, BookOutlined, FileTextOutlined, PlusOutlined } from '@ant-design/icons';
import { fetchCards, fetchSessions, createSession } from '@/api/client';
import type { ICharacterCard, IChatSession } from '@/types';

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

export default function CardGalleryPage() {
  const [cards, setCards] = useState<ICharacterCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    loadCards();
  }, []);

  async function loadCards() {
    setLoading(true);
    try {
      const data = await fetchCards();
      setCards(data.cards);
      const tags = [...new Set(data.cards.flatMap((c: ICharacterCard) => c.tags))] as string[];
      setAllTags(tags);
    } catch {
      message.error('加载角色卡失败');
    } finally {
      setLoading(false);
    }
  }

  const filtered = cards.filter((c) => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase()) &&
        !c.description.toLowerCase().includes(search.toLowerCase())) {
      return false;
    }
    if (activeTags.length && !activeTags.some((t) => c.tags.includes(t))) {
      return false;
    }
    return true;
  });

  async function handleCardClick(card: ICharacterCard) {
    try {
      const sessions: IChatSession[] = await fetchSessions(card.id);
      if (sessions.length > 0) {
        navigate(`/chat/${sessions[0].id}`);
      } else {
        const session: IChatSession = await createSession(card.id);
        navigate(`/chat/${session.id}`);
      }
    } catch {
      message.error('进入聊天失败');
    }
  }

  async function handleNewSession(card: ICharacterCard, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const session: IChatSession = await createSession(card.id);
      navigate(`/chat/${session.id}`);
    } catch {
      message.error('创建新会话失败');
    }
  }

  return (
    <div className="h-full flex flex-col bg-[#f8f4f0]">
      {/* Header */}
      <div className="flex-shrink-0 px-8 py-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-gray-800">Izumi Studio</h1>
          <div className="flex gap-2">
            <Button
              type="text"
              icon={<FileTextOutlined />}
              onClick={() => navigate('/presets')}
              className="text-gray-800/60 hover:text-gray-800"
            >
              预设
            </Button>
            <Button
              type="text"
              icon={<BookOutlined />}
              onClick={() => navigate('/worldbooks')}
              className="text-gray-800/60 hover:text-gray-800"
            >
              世界书
            </Button>
            <Button
              type="text"
              icon={<ImportOutlined />}
              onClick={() => navigate('/import')}
              className="text-gray-800/60 hover:text-gray-800"
            >
              导入
            </Button>
            <Button
              type="text"
              icon={<SettingOutlined />}
              onClick={() => navigate('/settings')}
              className="text-gray-800/60 hover:text-gray-800"
            >
              设置
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索角色卡..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
            size="large"
          />
          <div className="flex gap-2 flex-wrap">
            {allTags.map((tag) => (
              <Tag.CheckableTag
                key={tag}
                checked={activeTags.includes(tag)}
                onChange={(checked) => {
                  setActiveTags(checked ? [...activeTags, tag] : activeTags.filter((t) => t !== tag));
                }}
                style={{
                  borderColor: activeTags.includes(tag) ? TAG_COLORS[tag] || 'blue' : undefined,
                }}
              >
                {tag}
              </Tag.CheckableTag>
            ))}
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto p-8">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Spin size="large" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <Empty description="没有找到角色卡" />
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {filtered.map((card) => {
              const cardBgUrl = card.background?.image_path || card.cover?.image_path;
              return (
              <div
                key={card.id}
                className="group cursor-pointer rounded-xl overflow-hidden bg-white border border-gray-200
                           hover:border-primary-500/50 hover:shadow-lg hover:shadow-primary-500/10 transition-all duration-300 relative"
              >
                {/* Cover */}
                <div
                  onClick={() => handleCardClick(card)}
                  className="aspect-[16/9] bg-gradient-to-br from-[#f0ece8] to-[#e8e4e0] flex items-center justify-center overflow-hidden relative"
                >
                  {cardBgUrl ? (
                    <img
                      src={cardBgUrl}
                      alt={card.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <span className="text-5xl text-gray-300">{card.name.charAt(0)}</span>
                  )}
                  <div
                    onClick={(e) => { e.stopPropagation(); navigate(`/cards/${card.id}`); }}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <div className="bg-black/30 backdrop-blur-sm rounded-full p-1.5 hover:bg-primary-500/50 cursor-pointer">
                      <InfoCircleOutlined className="text-white text-sm" />
                    </div>
                  </div>
                  <div
                    onClick={(e) => handleNewSession(card, e)}
                    className="absolute top-2 right-12 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="创建新会话"
                  >
                    <div className="bg-black/30 backdrop-blur-sm rounded-full p-1.5 hover:bg-primary-500 cursor-pointer">
                      <PlusOutlined className="text-white text-sm" />
                    </div>
                  </div>
                </div>
                {/* Info */}
                <div onClick={() => handleCardClick(card)} className="p-4">
                  <h3 className="font-semibold text-gray-800 truncate">{card.name}</h3>
                  <p className="text-sm text-gray-800/50 mt-1 line-clamp-2">{card.description || '暂无描述'}</p>
                  {card.tags.length > 0 && (
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {card.tags.map((t) => (
                        <Tag key={t} color={TAG_COLORS[t] || 'default'} className="text-xs">
                          {t}
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
