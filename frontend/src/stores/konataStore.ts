import { create } from 'zustand';
import type { IChatSession, IChatMessage, IToolCall } from '@/types';
import type { ICardSummary } from '@/api/client';

interface KonataState {
  sessions: IChatSession[];
  currentSessionId: string | null;
  messages: IChatMessage[];
  isGenerating: boolean;
  streamingContent: string;
  streamingToolCalls: IToolCall[];

  // Right panel data
  cardsSummary: ICardSummary[];

  // Actions
  setSessions: (sessions: IChatSession[]) => void;
  setCurrentSessionId: (id: string | null) => void;
  setMessages: (messages: IChatMessage[]) => void;
  appendMessage: (message: IChatMessage) => void;
  setGenerating: (v: boolean) => void;
  appendStreamToken: (token: string) => void;
  addStreamToolCall: (tc: IToolCall) => void;
  resetStreaming: () => void;
  setCardsSummary: (cards: ICardSummary[]) => void;
  clear: () => void;
}

export const useKonataStore = create<KonataState>((set) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isGenerating: false,
  streamingContent: '',
  streamingToolCalls: [],
  cardsSummary: [],

  setSessions: (sessions) => set({ sessions }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (message) =>
    set((s) => ({ messages: [...s.messages, message] })),
  setGenerating: (v) => set({ isGenerating: v }),
  appendStreamToken: (token) =>
    set((s) => ({ streamingContent: s.streamingContent + (token || '') })),
  addStreamToolCall: (tc) =>
    set((s) => ({ streamingToolCalls: [...s.streamingToolCalls, tc] })),
  resetStreaming: () =>
    set({ streamingContent: '', streamingToolCalls: [], isGenerating: false }),
  setCardsSummary: (cards) => set({ cardsSummary: cards }),
  clear: () =>
    set({
      sessions: [],
      currentSessionId: null,
      messages: [],
      isGenerating: false,
      streamingContent: '',
      streamingToolCalls: [],
      cardsSummary: [],
    }),
}));
