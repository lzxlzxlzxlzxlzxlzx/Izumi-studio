import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Input, Spin, message, Tag, Dropdown, Popconfirm } from 'antd';
import type { MenuProps } from 'antd';
import {
  SendOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  SwapOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  fetchCreationMessages,
  streamCreation,
  createCreationSession,
  fetchCreationSession,
  uploadCreationFile,
  publishCreationCard,
  fetchCreationSessions,
  deleteCreationSession,
  fetchLinkedWorldbooks,
  type SSEEvent,
} from '@/api/client';
import { useCreationStore } from '@/stores/creationStore';
import CardOutlinePanel from '@/components/CardOutlinePanel';
import FieldEditor from '@/components/FieldEditor';
import type { ICharacterCard } from '@/types';

export default function CreationPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const store = useCreationStore();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [panelOpen, setPanelOpen] = useState(true);
  const [uploading, setUploading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!sessionId) {
      store.clear();
      loadDrafts();
      setLoading(false);
      return;
    }

    loadSession(sessionId);

    return () => {
      abortRef.current?.abort();
    };
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.messages, store.streamingContent, store.streamingToolCalls]);

  async function loadDrafts() {
    try {
      const sessions = await fetchCreationSessions();
      store.setSessions(sessions);
    } catch {
      // silent fail on welcome page
    }
  }

  async function loadSession(sid: string) {
    setLoading(true);
    try {
      const { session, card } = await fetchCreationSession(sid);
      store.setSession(session);
      store.setCard(card);

      const [msgs, wbs] = await Promise.all([
        fetchCreationMessages(sid),
        fetchLinkedWorldbooks(card.id).catch(() => []),
      ]);
      store.setMessages(msgs);
      store.setLinkedWorldbooks(wbs);
    } catch {
      message.error('加载创作会话失败');
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

    const userMsg: any = {
      id: crypto.randomUUID(),
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
      await streamCreation(
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
            case 'done': {
              // Refresh messages, card, and worldbooks
              Promise.all([
                fetchCreationMessages(sessionId!),
                fetchCreationSession(sessionId!),
              ]).then(async ([msgs, { card }]) => {
                store.setMessages(msgs);
                store.setCard(card);
                store.resetStreaming();

                // Refresh linked worldbooks
                try {
                  const wbs = await fetchLinkedWorldbooks(card.id);
                  store.setLinkedWorldbooks(wbs);
                } catch { /* ignore */ }

                // Track card changes
                const eventAny = event as any;
                if (eventAny.card_changes?.card_changes) {
                  store.setCardChanges(
                    eventAny.card_changes.card_changes.map((f: string) => ({
                      field: f,
                      value: getFieldLabel(f),
                    })),
                  );
                }
              });
              break;
            }
            case 'error':
              message.error(event.error || '创作对话出错');
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

  async function handleFileUpload(file: File) {
    if (!sessionId) return;
    setUploading(true);
    try {
      const result = await uploadCreationFile(sessionId, file);
      message.success(`文件已上传: ${result.filename} (${result.char_count} 字符)`);

      // Reload messages to show the injected file content
      const msgs = await fetchCreationMessages(sessionId);
      store.setMessages(msgs);
    } catch (err: any) {
      message.error(err?.message || '上传失败');
    } finally {
      setUploading(false);
    }
  }

  async function handlePublish() {
    if (!sessionId) return;
    try {
      const card = await publishCreationCard(sessionId);
      store.setCard(card);
      message.success('角色卡已发布！可在游玩界面中查看');
    } catch (err: any) {
      message.error(err?.message || '发布失败');
    }
  }

  async function handleDeleteDraft(sid: string, e?: React.MouseEvent) {
    e?.stopPropagation();
    try {
      await deleteCreationSession(sid);
      message.success('草稿已删除');
      if (sid === sessionId) {
        store.clear();
        navigate('/creation');
      }
      loadDrafts();
    } catch {
      message.error('删除失败');
    }
  }

  function handleSwitchDraft(sid: string) {
    if (sid === sessionId) return;
    abortRef.current?.abort();
    store.clear();
    navigate(`/creation/${sid}`);
  }

  function handleCopyRef(text: string) {
    setInput((prev) => (prev ? prev + ' ' + text : text));
  }

  function getFieldLabel(field: string): string {
    const labels: Record<string, string> = {
      name: '名称',
      description: '描述',
      tags: '标签',
      personality: '性格',
      background: '背景',
      scenario: '场景',
      speaking_style: '说话风格',
      first_mes: '开场白',
      mes_example: '示例对话',
      creator_notes: '创作者备注',
      writing_style: '写作风格',
      system_prompt: '系统提示词',
      post_history_instructions: '后置指令',
      style_tags: '风格标签',
      character_appearance: '外观描述',
    };
    return labels[field] || field;
  }

  const showWelcome = !sessionId;
  const card = store.card as ICharacterCard | null;
  const isDraft = card?.status === 'draft';

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Top Bar */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white z-10">
        <Button
          type="text"
          icon={sidebarOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="text-gray-400 hover:text-gray-700"
          title="切换卡片目录"
        />
        <div className="flex items-center gap-2 flex-1">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-xs font-bold text-white">
            创
          </div>
          <span className="font-semibold text-gray-800">
            {sessionId ? `创作 · ${card?.name || '未命名角色卡'}` : '创作 · 角色卡工坊'}
          </span>
          {sessionId && (
            <Tag color={isDraft ? 'default' : 'green'} className="ml-1 text-xs">
              {isDraft ? '草稿' : '已发布'}
            </Tag>
          )}
          {sessionId && store.sessions.length > 1 && (
            <Dropdown
              menu={{
                items: store.sessions
                  .filter((s: any) => s.id !== sessionId)
                  .map((s: any) => ({
                    key: s.id,
                    label: s.card_name || s.name || '未命名',
                    icon: <FileTextOutlined />,
                  })),
                onClick: ({ key }) => handleSwitchDraft(key),
              }}
              trigger={['click']}
            >
              <Button size="small" type="text" icon={<SwapOutlined />} className="text-gray-400 hover:text-amber-500 text-xs">
                切换
              </Button>
            </Dropdown>
          )}
        </div>
        {sessionId && (
          <>
            {isDraft && (
              <Button
                size="small"
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={handlePublish}
                className="bg-green-500 hover:bg-green-600 border-green-500 text-xs"
              >
                发布
              </Button>
            )}
            <Button
              type="text"
              icon={panelOpen ? <MenuFoldOutlined style={{ transform: 'scaleX(-1)' }} /> : <MenuUnfoldOutlined style={{ transform: 'scaleX(-1)' }} />}
              onClick={() => setPanelOpen(!panelOpen)}
              className="text-gray-400 hover:text-gray-700"
              title="切换编辑器"
            />
          </>
        )}
      </div>

      {/* Main Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar — Card Outline */}
        {sidebarOpen && (
          <div className="w-60 flex-shrink-0">
            <CardOutlinePanel onCopyRef={handleCopyRef} />
          </div>
        )}

        {/* Center — Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {showWelcome ? (
            <div className="flex-1 overflow-auto">
              <div className="max-w-3xl mx-auto px-8 py-12">
                {/* Hero */}
                <div className="text-center mb-10">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-2xl font-bold text-white mx-auto mb-4 shadow-lg">
                    创
                  </div>
                  <h2 className="text-xl font-bold text-gray-800 mb-2">
                    欢迎来到角色卡工坊～
                  </h2>
                  <p className="text-gray-500 leading-relaxed max-w-md mx-auto">
                    我是泉此方，你的创作搭档！从一张空白角色卡开始，用自然语言向我描述你心中的角色，我会帮你一步步填充设定。
                  </p>
                  <Button
                    onClick={async () => {
                      try {
                        const { session } = await createCreationSession();
                        navigate(`/creation/${session.id}`);
                      } catch {
                        message.error('创建创作会话失败');
                      }
                    }}
                    type="primary"
                    size="large"
                    icon={<PlusOutlined />}
                    className="mt-4 bg-amber-500 hover:bg-amber-600 border-amber-500"
                  >
                    新建创作
                  </Button>
                </div>

                {/* Draft list */}
                {store.sessions.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
                        草稿箱 ({store.sessions.length})
                      </h3>
                      <Button
                        size="small"
                        type="text"
                        icon={<ReloadOutlined />}
                        onClick={loadDrafts}
                        className="text-gray-400"
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      {store.sessions.map((s: any) => (
                        <div
                          key={s.id}
                          className="flex items-center gap-3 px-4 py-3 bg-white border border-gray-200 rounded-lg hover:border-amber-300 hover:shadow-sm cursor-pointer transition-all group"
                          onClick={() => handleSwitchDraft(s.id)}
                        >
                          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-100 to-orange-100 flex items-center justify-center flex-shrink-0">
                            <FileTextOutlined className="text-amber-500 text-sm" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-800 truncate">
                              {s.card_name || '未命名角色卡'}
                            </div>
                            <div className="text-xs text-gray-400">
                              {s.updated_at ? new Date(s.updated_at).toLocaleString('zh-CN') : ''}
                            </div>
                          </div>
                          <Popconfirm
                            title="确定删除此草稿？"
                            onConfirm={(e) => handleDeleteDraft(s.id, e as any)}
                            onCancel={(e) => e?.stopPropagation()}
                          >
                            <Button
                              size="small"
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              className="opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => e.stopPropagation()}
                            />
                          </Popconfirm>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Empty state */}
                {store.sessions.length === 0 && (
                  <div className="text-center py-8 text-gray-400 text-sm">
                    <FileTextOutlined className="text-3xl block mb-2 opacity-50" />
                    <p>还没有草稿，点击上方按钮开始创作吧～</p>
                  </div>
                )}
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
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-lg font-bold text-white mx-auto mb-3">
                          创
                        </div>
                        <p>开始创作你的角色卡吧～</p>
                        <p className="text-xs mt-1">描述角色的名字、性格、背景，泉此方会帮你填充设定</p>
                      </div>
                    )}

                    {/* Existing messages */}
                    {store.messages.map((msg) => (
                      <CreationBubble key={msg.id} msg={msg} />
                    ))}

                    {/* Thinking indicator */}
                    {store.isGenerating && !store.streamingContent && store.streamingToolCalls.length === 0 && (
                      <div className="flex justify-start">
                        <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-gray-50 text-gray-500 rounded-bl-md border border-gray-200">
                          <div className="flex items-center gap-2">
                            <span className="text-sm">泉此方正在思考</span>
                            <span className="flex gap-1">
                              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
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
                              <span className="inline-block w-1.5 h-4 bg-amber-400 ml-0.5 animate-pulse align-middle" />
                            </div>
                          )}
                          {store.streamingToolCalls.length > 0 && (
                            <div className={store.streamingContent ? 'mt-2 pt-2 border-t border-gray-200' : ''}>
                              {store.streamingToolCalls.map((tc, i) => (
                                <CreationToolBadge key={i} toolCall={tc} />
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Card changes summary */}
                    {store.cardChanges.length > 0 && !store.isGenerating && (
                      <div className="flex justify-center">
                        <div className="text-xs text-gray-400 bg-gray-50 rounded-full px-3 py-1">
                          本轮更新：
                          {store.cardChanges.map((c, i) => (
                            <span
                              key={c.field}
                              className="text-amber-600 cursor-pointer hover:underline ml-1"
                              onClick={() => store.setSelectedField(c.field)}
                            >
                              {c.value as string}{i < store.cardChanges.length - 1 ? '、' : ''}
                            </span>
                          ))}
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
                {/* File upload button */}
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.md,.docx"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileUpload(file);
                      e.target.value = '';
                    }}
                  />
                  <Button
                    type="text"
                    icon={<UploadOutlined />}
                    onClick={() => fileInputRef.current?.click()}
                    loading={uploading}
                    className="text-gray-400 hover:text-amber-500"
                    title="上传文件 (.txt, .md, .docx)"
                  />
                </>
                <Input.TextArea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onPressEnter={(e) => {
                    if (!e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="描述你的角色... (Enter 发送, Shift+Enter 换行)"
                  autoSize={{ minRows: 1, maxRows: 6 }}
                  className="flex-1"
                  disabled={store.isGenerating}
                />
                <Button
                  type="primary"
                  icon={store.isGenerating ? <Spin size="small" /> : <SendOutlined />}
                  onClick={handleSend}
                  disabled={!input.trim() || store.isGenerating}
                  className="bg-amber-500 hover:bg-amber-600 border-amber-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Right Panel — Field Editor */}
        {panelOpen && sessionId && (
          <div className="w-72 flex-shrink-0">
            <FieldEditor onCopyRef={handleCopyRef} />
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Sub-components
// ============================================================

function CreationBubble({ msg }: { msg: any }) {
  const isUser = msg.role === 'user';
  const isTool = msg.role === 'tool';
  const store = useCreationStore();

  if (isTool) return null;

  // Render 【字段:XXX】 references as clickable tags
  function renderContent(text: string) {
    const parts = text.split(/(【字段:[^】]+】)/g);
    return parts.map((part, i) => {
      const match = part.match(/^【字段:([^】]+)】$/);
      if (match) {
        const fieldKey = match[1];
        return (
          <Tag
            key={i}
            color="orange"
            className="cursor-pointer text-xs"
            onClick={() => store.setSelectedField(fieldKey)}
          >
            {part}
          </Tag>
        );
      }
      return <span key={i}>{part}</span>;
    });
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-amber-500 text-white rounded-br-md'
            : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-200'
        }`}
      >
        {!isUser && (
          <div className="text-xs text-amber-500 mb-1">泉此方</div>
        )}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {typeof msg.content === 'string' ? renderContent(msg.content) : '[内容]'}
        </div>
        {msg.tool_calls && msg.tool_calls.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-200">
            {msg.tool_calls.map((tc: any, i: number) => (
              <CreationToolBadge key={i} toolCall={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CreationToolBadge({ toolCall }: { toolCall: { function: { name: string; arguments: string } } }) {
  const fnName = toolCall.function?.name || '未知';
  const fnNameLabel: Record<string, string> = {
    set_card_basic: '设置基础信息',
    set_character_field: '更新角色设定',
    set_preset_config: '设置预设配置',
    set_system_prompt: '设置系统提示词',
    set_image_config: '设置图像配置',
    add_npc: '添加NPC',
    set_field_batch: '批量设置字段',
    split_field_to_worldbook: '拆分为世界书',
    link_worldbook: '关联世界书',
  };

  return (
    <div className="text-xs text-gray-500 bg-amber-50 rounded px-2 py-1 mt-1 inline-block mr-1">
      <span className="text-amber-500">🔧</span>
      <span className="ml-1">{fnNameLabel[fnName] || fnName}</span>
    </div>
  );
}
