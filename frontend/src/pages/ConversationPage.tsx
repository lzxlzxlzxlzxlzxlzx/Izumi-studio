import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Input, Spin, message, Tag } from 'antd';
import { SendOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { fetchKonataMessages, streamKonata, createKonataSession, genId, type SSEEvent } from '@/api/client';
import { useKonataStore } from '@/stores/konataStore';
import ConversationSidebar from '@/components/ConversationSidebar';
import ReferencePanel from '@/components/ReferencePanel';

export default function ConversationPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const store = useKonataStore();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [panelOpen, setPanelOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!sessionId) {
      store.setMessages([]);
      store.resetStreaming();
      store.setCurrentSessionId(null);
      setLoading(false);
      return;
    }

    store.setCurrentSessionId(sessionId);
    loadMessages(sessionId);

    return () => {
      abortRef.current?.abort();
    };
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.messages, store.streamingContent, store.streamingToolCalls]);

  async function loadMessages(sid: string) {
    setLoading(true);
    try {
      const msgs = await fetchKonataMessages(sid);
      store.setMessages(msgs);
    } catch {
      message.error('加载消息失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    if (!input.trim() || !sessionId) return;
    const content = input.trim();
    setInput('');
    store.setGenerating(true);
    store.resetStreaming();

    // Append local user message for immediate display
    const userMsg: any = {
      id: genId(),
      session_id: sessionId,
      role: 'user',
      name: 'user',
      content,
      index: store.messages.length,
      round_index: 0,
      created_at: new Date().toISOString(),
      tool_calls: [],
    };
    store.appendMessage(userMsg);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamKonata(
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
              fetchKonataMessages(sessionId).then((msgs) => {
                store.setMessages(msgs);
                store.resetStreaming();
              });
              break;
            case 'error':
              message.error(event.error || '对话出错');
              store.resetStreaming();
              break;
          }
        },
        controller.signal,
      );
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        message.error(err?.message || '连接失败');
      }
      store.resetStreaming();
    }
  }

  function handleCopyRef(text: string) {
    setInput((prev) => (prev ? prev + ' ' + text : text));
  }

  const showWelcome = !sessionId;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Top Bar */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white z-10">
        <Button
          type="text"
          icon={sidebarOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="text-gray-400 hover:text-gray-700"
          title="切换侧边栏"
        />
        <div className="flex items-center gap-2 flex-1">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center text-xs font-bold text-white">
            泉
          </div>
          <span className="font-semibold text-gray-800">对话 · 泉此方</span>
          {sessionId && (
            <span className="text-xs text-gray-400 ml-1">
              ({store.messages.length} 条消息)
            </span>
          )}
        </div>
        <Button
          type="text"
          icon={panelOpen ? <MenuFoldOutlined style={{ transform: 'scaleX(-1)' }} /> : <MenuUnfoldOutlined style={{ transform: 'scaleX(-1)' }} />}
          onClick={() => setPanelOpen(!panelOpen)}
          className="text-gray-400 hover:text-gray-700"
          title="切换数据面板"
        />
      </div>

      {/* Main Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        {sidebarOpen && (
          <div className="w-64 flex-shrink-0">
            <ConversationSidebar />
          </div>
        )}

        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {showWelcome ? (
            /* Welcome state — no session selected */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center max-w-md px-8">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center text-2xl font-bold text-white mx-auto mb-4 shadow-lg">
                  泉
                </div>
                <h2 className="text-xl font-bold text-gray-800 mb-2">
                  哟～ 欢迎来到 Izumi Studio！
                </h2>
                <p className="text-gray-500 mb-6 leading-relaxed">
                  我是泉此方，你的专属系统向导。
                  <br />
                  想聊聊角色卡的设定？还是想看看最近有哪些有趣的对话？
                  <br />
                  左边新建一个对话，开始聊吧～
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  <Button
                    onClick={async () => {
                      try {
                        const session = await createKonataSession();
                        navigate(`/konata/${session.id}`);
                      } catch {
                        message.error('创建对话失败');
                      }
                    }}
                    type="default"
                    className="text-gray-600"
                  >
                    新建对话
                  </Button>
                  <Button
                    onClick={() => {
                      setSidebarOpen(true);
                    }}
                    type="default"
                    className="text-gray-600"
                  >
                    查看历史
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            /* Messages area */
            <div className="flex-1 overflow-auto">
              <div className="max-w-3xl mx-auto px-4 py-6">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <Spin size="large" />
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {store.messages.length === 0 && !store.isGenerating && (
                      <div className="text-center py-12 text-gray-400">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center text-lg font-bold text-white mx-auto mb-3">
                          泉
                        </div>
                        <p>开始和泉此方对话吧～</p>
                        <p className="text-xs mt-1">她可以帮你查看角色卡、回顾对话、讨论剧情</p>
                      </div>
                    )}

                    {/* Existing messages */}
                    {store.messages.map((msg) => (
                      <KonataBubble key={msg.id} msg={msg} />
                    ))}

                    {/* Thinking indicator */}
                    {store.isGenerating && !store.streamingContent && store.streamingToolCalls.length === 0 && (
                      <div className="flex justify-start">
                        <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-gray-50 text-gray-500 rounded-bl-md border border-gray-200">
                          <div className="flex items-center gap-2">
                            <span className="text-sm">泉此方正在思考</span>
                            <span className="flex gap-1">
                              <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                              <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                              <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Streaming bubble */}
                    {(store.streamingContent || store.streamingToolCalls.length > 0) && (
                      <div className="flex justify-start">
                        <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-gray-50 text-gray-800 rounded-bl-md border border-gray-200">
                          <div className="text-xs text-gray-400 mb-1">泉此方</div>
                          {store.streamingContent && (
                            <div className="whitespace-pre-wrap text-sm leading-relaxed">
                              {store.streamingContent}
                              <span className="inline-block w-1.5 h-4 bg-purple-400 ml-0.5 animate-pulse align-middle" />
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
          )}

          {/* Input Area */}
          {sessionId && (
            <div className="flex-shrink-0 px-4 py-3 bg-white border-t border-gray-200">
              <div className="max-w-3xl mx-auto flex items-end gap-2">
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
                  className="bg-purple-500 hover:bg-purple-600 border-purple-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Right Reference Panel */}
        {panelOpen && (
          <div className="w-64 flex-shrink-0">
            <ReferencePanel onCopyRef={handleCopyRef} />
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Sub-components
// ============================================================

function KonataBubble({ msg }: { msg: any }) {
  const isUser = msg.role === 'user';
  const isTool = msg.role === 'tool';

  if (isTool) return null; // Hide tool messages from display

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-purple-500 text-white rounded-br-md'
            : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-200'
        }`}
      >
        {!isUser && (
          <div className="text-xs text-purple-500 mb-1">泉此方</div>
        )}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {typeof msg.content === 'string' ? msg.content : '[内容]'}
        </div>
        {msg.tool_calls && msg.tool_calls.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-200">
            {msg.tool_calls.map((tc: any, i: number) => (
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
  const fnNameLabel: Record<string, string> = {
    query_cards_list: '查询角色卡列表',
    query_card_detail: '查询角色卡详情',
    query_session_detail: '查询会话详情',
    query_session_messages: '查询会话消息',
    query_session_characters: '查询角色信息',
    query_worldbook: '查询世界书',
    query_preset: '查询预设',
  };

  return (
    <div className="text-xs text-gray-500 bg-gray-100 rounded px-2 py-1 mt-1 inline-block mr-1">
      <span className="text-purple-400">查询</span>
      <span className="ml-1">{fnNameLabel[fnName] || fnName}</span>
    </div>
  );
}
