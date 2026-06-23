import axios from 'axios';
import type { IToolCall } from '@/types';

/** UUID v4, fallback when crypto.randomUUID unavailable (HTTP IP access). */
export function genId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// Cards
export async function fetchCards(search = '', tags = '') {
  const { data } = await api.get('/cards', { params: { search, tags } });
  return data;
}

export async function fetchCard(cardId: string) {
  const { data } = await api.get(`/cards/${cardId}`);
  return data;
}

export async function deleteCard(cardId: string) {
  await api.delete(`/cards/${cardId}`);
}

// Sessions
export async function fetchSessions(cardId: string) {
  const { data } = await api.get(`/sessions/card/${cardId}`);
  return data;
}

export async function createSession(cardId: string) {
  const { data } = await api.post('/sessions', { card_id: cardId });
  return data;
}

export async function deleteSession(sessionId: string) {
  await api.delete(`/sessions/${sessionId}`);
}

export async function fetchCharacters(sessionId: string) {
  const { data } = await api.get(`/sessions/${sessionId}/characters`);
  return data;
}

export async function updateCard(cardId: string, updates: Record<string, unknown>) {
  const { data } = await api.patch(`/cards/${cardId}`, updates);
  return data;
}

// Chat
export async function fetchMessages(sessionId: string) {
  const { data } = await api.get(`/chat/messages/${sessionId}`);
  return data;
}

export async function sendMessage(sessionId: string, input: string) {
  const { data } = await api.post('/chat', { session_id: sessionId, input });
  return data;
}

export async function rollbackSession(sessionId: string, targetIndex: number) {
  const { data } = await api.post(`/chat/rollback/${sessionId}`, null, {
    params: { target_index: targetIndex },
  });
  return data;
}

// Presets
export async function fetchPresets() {
  const { data } = await api.get('/presets');
  return data;
}

export async function getPreset(name: string) {
  const { data } = await api.get(`/presets/${encodeURIComponent(name)}`);
  return data;
}

export async function deletePreset(name: string) {
  await api.delete(`/presets/${encodeURIComponent(name)}`);
}

export async function updatePreset(name: string, preset: Record<string, unknown>) {
  const { data } = await api.put(`/presets/${encodeURIComponent(name)}`, preset);
  return data;
}

// Worldbooks
export async function fetchWorldbooks() {
  const { data } = await api.get('/worldbooks');
  return data;
}

export async function getWorldbook(id: string) {
  const { data } = await api.get(`/worldbooks/${id}`);
  return data;
}

export async function deleteWorldbook(id: string) {
  await api.delete(`/worldbooks/${id}`);
}

// Upload
export async function uploadImage(file: File): Promise<{
  ok: boolean;
  filename: string;
  image_path: string;
  description: string;
}> {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch('/api/upload/image', { method: 'POST', body: form });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'upload failed');
  }
  return resp.json();
}

// SSE streaming

export interface SSEEvent {
  type: 'token' | 'tool_call' | 'done' | 'error';
  token?: string;
  tool_call?: IToolCall;
  full_response?: string;
  tool_calls?: IToolCall[];
  character_changes?: Array<{ action: string; name: string }>;
  error?: string;
}

export async function uploadCharacterImage(
  sessionId: string,
  characterId: string,
  file: File,
) {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch(
    `/api/sessions/${sessionId}/characters/${characterId}/image`,
    { method: 'POST', body: form },
  );
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'upload failed');
  }
  return resp.json();
}

export function streamChat(
  sessionId: string,
  input: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `/api/chat/stream/${sessionId}?input=${encodeURIComponent(input)}`;

  return fetch(url, {
    method: 'POST',
    headers: { Accept: 'text/event-stream' },
    signal,
  }).then(async (response) => {
    if (!response.ok) {
      let detail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errBody = await response.json();
        detail = errBody.detail || detail;
      } catch { /* use status text */ }
      throw new Error(detail);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('ReadableStream not supported');

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: SSEEvent = JSON.parse(line.slice(6));
              onEvent(event);
            } catch {
              // skip malformed JSON lines
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  });
}

export async function fetchMemories(sessionId: string) {
  const { data } = await api.get(`/chat/${sessionId}/memories`);
  return data;
}

// ====== Creation Module ======

export async function fetchCreationSessions() {
  const { data } = await api.get('/creation/sessions');
  return data;
}

export async function createCreationSession(): Promise<{
  session: import('@/types').IChatSession;
  card: import('@/types').ICharacterCard;
}> {
  const { data } = await api.post('/creation/sessions');
  return data;
}

export async function deleteCreationSession(sessionId: string) {
  await api.delete(`/creation/sessions/${sessionId}`);
}

export async function fetchCreationSession(sessionId: string): Promise<{
  session: import('@/types').IChatSession;
  card: import('@/types').ICharacterCard;
}> {
  const { data } = await api.get(`/creation/sessions/${sessionId}`);
  return data;
}

export async function fetchCreationMessages(sessionId: string) {
  const { data } = await api.get(`/creation/messages/${sessionId}`);
  return data;
}

export async function updateCreationCard(
  cardId: string,
  body: { field: string; value: unknown },
) {
  const { data } = await api.patch(`/creation/card/${cardId}`, body);
  return data;
}

export async function publishCreationCard(sessionId: string) {
  const { data } = await api.post(`/creation/publish/${sessionId}`);
  return data;
}

export async function fetchLinkedWorldbooks(cardId: string) {
  const { data } = await api.get(`/creation/card/${cardId}/worldbooks`);
  return data;
}

export async function uploadCreationFile(
  sessionId: string,
  file: File,
): Promise<{ ok: boolean; filename: string; content_preview: string; char_count: number }> {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch(`/api/creation/upload/${sessionId}`, {
    method: 'POST',
    body: form,
  });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || 'upload failed');
  }
  return resp.json();
}

export function streamCreation(
  sessionId: string,
  input: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `/api/creation/stream/${sessionId}?input=${encodeURIComponent(input)}`;

  return fetch(url, {
    method: 'POST',
    headers: { Accept: 'text/event-stream' },
    signal,
  }).then(async (response) => {
    if (!response.ok) {
      let detail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errBody = await response.json();
        detail = errBody.detail || detail;
      } catch { /* use status text */ }
      throw new Error(detail);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('ReadableStream not supported');

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: SSEEvent = JSON.parse(line.slice(6));
              onEvent(event);
            } catch {
              // skip malformed JSON lines
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  });
}

// ====== Konata Chat ======

export interface ICardSummary {
  id: string;
  name: string;
  description: string;
  tags: string[];
  sessions: Array<{
    id: string;
    name: string;
    updated_at: string;
    created_at: string;
    message_count: number;
  }>;
}

export async function fetchKonataSessions() {
  const { data } = await api.get('/konata/sessions');
  return data;
}

export async function createKonataSession() {
  const { data } = await api.post('/konata/sessions');
  return data;
}

export async function deleteKonataSession(sessionId: string) {
  await api.delete(`/konata/sessions/${sessionId}`);
}

export async function fetchKonataMessages(sessionId: string) {
  const { data } = await api.get(`/konata/messages/${sessionId}`);
  return data;
}

export async function fetchCardsSummary(): Promise<{ cards: ICardSummary[] }> {
  const { data } = await api.get('/konata/cards-summary');
  return data;
}

export function streamKonata(
  sessionId: string,
  input: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `/api/konata/stream/${sessionId}?input=${encodeURIComponent(input)}`;

  return fetch(url, {
    method: 'POST',
    headers: { Accept: 'text/event-stream' },
    signal,
  }).then(async (response) => {
    if (!response.ok) {
      let detail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errBody = await response.json();
        detail = errBody.detail || detail;
      } catch { /* use status text */ }
      throw new Error(detail);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('ReadableStream not supported');

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: SSEEvent = JSON.parse(line.slice(6));
              onEvent(event);
            } catch {
              // skip malformed JSON lines
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  });
}

// Runtime LLM config (stored server-side in data/local_config.json)
export interface LlmConfigStatus {
  deepseek_configured: boolean;
  dashscope_configured: boolean;
  llm_configured: boolean;
  api_url: string;
  dashscope_api_url: string;
  source: string;
}

export async function fetchLlmConfig(): Promise<LlmConfigStatus> {
  const { data } = await api.get('/config');
  return data;
}

export async function saveLlmConfig(payload: {
  API_KEY?: string;
  API_URL?: string;
  DASHSCOPE_API_KEY?: string;
  DASHSCOPE_API_URL?: string;
}): Promise<LlmConfigStatus> {
  const { data } = await api.put('/config', payload);
  return data;
}
