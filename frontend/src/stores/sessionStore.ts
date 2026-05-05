import { create } from 'zustand';
import type { ICharacterCard, IChatSession, IChatMessage, IToolCall } from '@/types';

interface SessionState {
  currentSession: IChatSession | null;
  currentCard: ICharacterCard | null;
  messages: IChatMessage[];
  isGenerating: boolean;
  streamingContent: string;
  streamingToolCalls: IToolCall[];

  loadSession: (session: IChatSession) => void;
  setCard: (card: ICharacterCard) => void;
  setMessages: (messages: IChatMessage[]) => void;
  appendMessage: (message: IChatMessage) => void;
  setGenerating: (v: boolean) => void;
  appendStreamToken: (token: string) => void;
  addStreamToolCall: (tc: IToolCall) => void;
  resetStreaming: () => void;
  clear: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  currentSession: null,
  currentCard: null,
  messages: [],
  isGenerating: false,
  streamingContent: '',
  streamingToolCalls: [],

  loadSession: (session) => set({ currentSession: session }),
  setCard: (card) => set({ currentCard: card }),
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
  clear: () =>
    set({
      currentSession: null,
      currentCard: null,
      messages: [],
      isGenerating: false,
      streamingContent: '',
      streamingToolCalls: [],
    }),
}));
