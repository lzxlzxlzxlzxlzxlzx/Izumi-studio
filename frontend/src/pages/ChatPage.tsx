import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Input, Dropdown, Spin, message, Tag } from 'antd';
import {
  ArrowLeftOutlined,
  SendOutlined,
  PictureOutlined,
  MoreOutlined,
  TeamOutlined,
  SwapOutlined,
  BookOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { fetchMessages, fetchSessions, streamChat, uploadImage } from '@/api/client';
import type { SSEEvent } from '@/api/client';
import { useSessionStore } from '@/stores/sessionStore';
import CharacterRegistryModal from '@/components/CharacterRegistryModal';
import MemoryPanel from '@/components/MemoryPanel';
import type { IChatMessage, IChatSession } from '@/types';

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const store = useSessionStore();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [registryOpen, setRegistryOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [cardSessions, setCardSessions] = useState<IChatSession[]>([]);
  const [characterChanges, setCharacterChanges] = useState<
    Array<{ action: string; name: string }> | null
  >(null);
  const [charRefreshKey, setCharRefreshKey] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    loadSessionData();
    return () => {
      abortRef.current?.abort();
    };
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.messages, store.streamingContent, store.isGenerating]);

  async function loadSessionData() {
    setLoading(true);
    try {
      const msgs: IChatMessage[] = await fetchMessages(sessionId!);
      store.setMessages(msgs);

      try {
        const resp = await fetch(`/api/sessions/${sessionId}`);
        if (resp.ok) {
          const session = await resp.json();
          store.loadSession(session);
          const cardResp = await fetch(`/api/cards/${session.card_id}`);
          if (cardResp.ok) {
            const card = await cardResp.json();
            store.setCard(card);
            // Load all sessions for this card
            const sessions: IChatSession[] = await fetchSessions(session.card_id);
            setCardSessions(sessions);
          }
        }
      } catch {
        store.loadSession({
          id: sessionId!,
          card_id: '',
          mode: 'play' as any,
          name: 'chat',
          greeting_index: 0,
          model: '',
          worldbook_ids: [],
          preset_name: '',
          background_image: null,
          parent_session_id: null,
          branch_number: null,
          created_at: '',
          updated_at: '',
        });
      }
    } catch {
      message.error('加载聊天失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    if (!input.trim() || !sessionId) return;
    const content = input.trim();
    setInput('');
    setCharacterChanges(null); // Clear previous changes on new send
    store.setGenerating(true);
    store.resetStreaming();

    const userMsg: IChatMessage = {
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: 'user',
      name: 'user',
      content,
      media: [],
      index: store.messages.length,
      round_index: 0,
      created_at: new Date().toISOString(),
      swipes: [],
      swipe_index: 0,
      has_checkpoint: false,
      locked: false,
      tool_calls: [],
      tool_call_id: null,
    };
    store.appendMessage(userMsg);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        sessionId,
        content,
        (event: SSEEvent) => {
          switch (event.type) {
            case 'token':
              store.appendStreamToken(event.token || '');
              break;
            case 'tool_call':
              if (event.tool_call) {
                store.addStreamToolCall(event.tool_call);
              }
              break;
            case 'done':
              fetchMessages(sessionId).then((msgs) => {
                store.setMessages(msgs);
                store.resetStreaming();
              });
              if (event.character_changes && event.character_changes.length > 0) {
                setCharacterChanges(event.character_changes);
              }
              setCharRefreshKey((k) => k + 1);
              break;
            case 'error':
              message.error(event.error || '流式传输出错');
              store.resetStreaming();
              break;
          }
        },
        controller.signal,
      );
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        const detail = err?.message || err?.toString() || '连接失败';
        message.error(detail);
      }
      store.resetStreaming();
    }
  }

  async function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !sessionId) return;

    setUploading(true);
    try {
      const result = await uploadImage(file);
      const desc = `[图片: ${result.description}]`;
      setInput((prev) => (prev ? prev + '\n' + desc : desc));
      message.success('图片分析完成');
    } catch (err: any) {
      message.error(err.message || '图片上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleDeleteSession() {
    if (!sessionId) return;
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
      message.success('会话已删除');
      navigate('/cards');
    } catch {
      message.error('删除会话失败');
    }
  }

  const bgPath = store.currentCard?.background?.image_path || store.currentCard?.cover?.image_path;
  const bgStyle = bgPath
    ? { backgroundImage: `url(${bgPath})` }
    : {};

  const charName = store.currentCard?.character?.name || '助手';

  return (
    <div className="h-screen flex flex-col bg-[#f8f4f0]">
      {/* Top Bar */}
      <div className="flex-shrink-0 flex items-center gap-4 px-4 py-3 border-b border-gray-200 bg-white/95 backdrop-blur z-10">
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/cards')}
          className="text-gray-400 hover:text-gray-700"
        />
        <div className="flex items-center gap-2 flex-1">
          <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-sm font-bold text-primary-600 border border-primary-200">
            {store.currentCard?.name?.charAt(0) || '?'}
          </div>
          <span className="font-semibold text-gray-800">
            {store.currentCard?.name || '聊天'}
          </span>
          {cardSessions.length > 1 && (
            <Dropdown
              menu={{
                items: cardSessions.map((s) => ({
                  key: s.id,
                  label: (
                    <div className="flex items-center justify-between gap-4">
                      <span>{s.name || '未命名会话'}</span>
                      <span className="text-xs text-gray-300">{s.created_at?.slice(0, 10)}</span>
                    </div>
                  ),
                  onClick: () => {
                    if (s.id !== sessionId) {
                      navigate(`/chat/${s.id}`);
                    }
                  },
                })),
              }}
            >
              <Button
                type="text"
                icon={<SwapOutlined />}
                className="text-gray-400 hover:text-gray-700"
                title="切换会话"
              />
            </Dropdown>
          )}
        </div>
        <Button
          type="text"
          icon={<BookOutlined />}
          onClick={() => setMemoryOpen(true)}
          className="text-gray-400 hover:text-gray-700"
          title="剧情记忆"
        />
        <Button
          type="text"
          icon={<TeamOutlined />}
          onClick={() => setRegistryOpen(true)}
          className="text-gray-400 hover:text-gray-700"
        />
        <Dropdown
          menu={{
            items: [
              { key: 'delete', label: '删除会话', danger: true, onClick: handleDeleteSession },
            ],
          }}
        >
          <Button type="text" icon={<MoreOutlined />} className="text-gray-400 hover:text-gray-700" />
        </Dropdown>
      </div>

      {/* Character Changes Banner */}
      {characterChanges && characterChanges.length > 0 && (
        <div className="flex-shrink-0 px-4 py-2 bg-primary-50 border-b border-primary-200 flex items-center gap-2 text-sm">
          <span className="text-gray-600">角色变更:</span>
          <div className="flex flex-wrap gap-1">
            {characterChanges.map((c, i) => (
              <span key={i} className="text-xs">
                <Tag
                  color={
                    c.action === 'created'
                      ? 'green'
                      : c.action === 'updated'
                        ? 'blue'
                        : 'red'
                  }
                  className="m-0"
                >
                  {c.action === 'created' ? '创建' : c.action === 'updated' ? '更新' : '删除'}: {c.name}
                </Tag>
              </span>
            ))}
          </div>
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={() => setCharacterChanges(null)}
            className="text-gray-400 hover:text-gray-700 ml-auto"
          />
        </div>
      )}

      {/* Message Area */}
      <div
        className="flex-1 overflow-auto relative"
        style={{
          ...bgStyle,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      >
        {bgPath && (
          <div className="absolute inset-0 bg-white/40" />
        )}

        <div className="relative max-w-3xl mx-auto px-4 py-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Spin size="large" />
            </div>
          ) : store.messages.length === 0 && !store.isGenerating ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-300">开始一段对话...</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {store.messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} charName={charName} />
              ))}

              {/* Thinking indicator: shown when generating but no token or tool call has arrived yet */}
              {store.isGenerating && !store.streamingContent && store.streamingToolCalls.length === 0 && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-white text-gray-500 rounded-bl-md border border-gray-200">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">模型正在回复</span>
                      <span className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Streaming bubble: text response or tool calls in progress */}
              {(store.streamingContent || store.streamingToolCalls.length > 0) && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-white text-gray-800 rounded-bl-md border border-gray-200">
                    <div className="text-xs text-gray-400 mb-1">
                      {store.streamingContent ? charName : '模型正在查询角色信息...'}
                    </div>
                    {store.streamingContent && (
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">
                        {store.streamingContent}
                        <span className="inline-block w-1.5 h-4 bg-primary-400 ml-0.5 animate-pulse align-middle" />
                      </div>
                    )}
                    {store.streamingToolCalls.length > 0 && (
                      <div className={store.streamingContent ? 'mt-2 pt-2 border-t border-gray-200' : ''}>
                        {store.streamingToolCalls.map((tc, i) => (
                          <ToolCallBadge key={i} toolCall={tc} />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 px-4 py-3 bg-white/95 backdrop-blur border-t border-gray-200">
        <div className="max-w-3xl mx-auto flex items-end gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleImageSelect}
          />
          <Button
            type="text"
            icon={uploading ? <Spin size="small" /> : <PictureOutlined />}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || store.isGenerating}
            className="text-gray-400 hover:text-gray-700"
          />
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            autoSize={{ minRows: 1, maxRows: 6 }}
            className="flex-1"
            disabled={store.isGenerating}
          />
          <Button
            type="primary"
            icon={store.isGenerating ? <Spin size="small" /> : <SendOutlined />}
            onClick={handleSend}
            disabled={!input.trim() || store.isGenerating}
            className="bg-primary-500 hover:bg-primary-600"
          />
        </div>
      </div>

      <CharacterRegistryModal
        open={registryOpen}
        sessionId={sessionId!}
        refreshTrigger={charRefreshKey}
        onClose={() => setRegistryOpen(false)}
      />
      <MemoryPanel
        open={memoryOpen}
        sessionId={sessionId!}
        onClose={() => setMemoryOpen(false)}
      />
    </div>
  );
}

function MessageBubble({ msg, charName }: { msg: IChatMessage; charName: string }) {
  const isUser = msg.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-primary-500 text-white rounded-br-md'
            : 'bg-white text-gray-800 rounded-bl-md border border-gray-200'
        }`}
      >
        {!isUser && (
          <div className="text-xs text-gray-400 mb-1">{msg.name || charName}</div>
        )}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {typeof msg.content === 'string' ? msg.content : '[内容]'}
        </div>
        {msg.tool_calls && msg.tool_calls.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-200">
            {msg.tool_calls.map((tc, i) => (
              <ToolCallBadge key={i} toolCall={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCallBadge({ toolCall }: { toolCall: { function: { name: string; arguments: string } } }) {
  const fnName = toolCall.function?.name || '未知';
  let args: Record<string, unknown> = {};
  try {
    args = JSON.parse(toolCall.function?.arguments || '{}');
  } catch { /* ignore */ }

  return (
    <div className="text-xs text-gray-500 bg-gray-100 rounded px-2 py-1 mt-1 inline-block mr-1">
      <span className="text-primary-400">⚙ {fnName}</span>
      {Object.keys(args).length > 0 && (
        <span className="ml-1 text-gray-300">
          {JSON.stringify(args).slice(0, 60)}
        </span>
      )}
    </div>
  );
}
