import { create } from 'zustand';
import type { IChatSession, IChatMessage, IToolCall, ICharacterCard } from '@/types';

interface CreationSessionSummary {
  id: string;
  name: string;
  card_name: string;
  card_id: string;
  updated_at: string;
  created_at: string;
}

interface LinkedWorldbook {
  id: string;
  name: string;
  entry_count: number;
}

interface CreationState {
  // Session & card
  session: IChatSession | null;
  card: ICharacterCard | null;
  sessions: CreationSessionSummary[];

  // Chat
  messages: IChatMessage[];
  isGenerating: boolean;
  streamingContent: string;
  streamingToolCalls: IToolCall[];

  // UI
  selectedField: string | null;
  selectedWorldbookId: string | null;
  selectedEntryId: string | null;
  outlineExpanded: boolean;
  editorDirty: boolean;
  cardChanges: Array<{ field: string; value: unknown }>;

  // Worldbooks
  linkedWorldbooks: LinkedWorldbook[];
  worldbookDataCache: Record<string, { entries: Array<{ id: string; title: string; content: string; keys: string[] }> }>;

  // Actions
  setSession: (session: IChatSession | null) => void;
  setCard: (card: ICharacterCard | null) => void;
  setSessions: (sessions: CreationSessionSummary[]) => void;
  setMessages: (messages: IChatMessage[]) => void;
  appendMessage: (message: IChatMessage) => void;
  setGenerating: (v: boolean) => void;
  appendStreamToken: (token: string) => void;
  addStreamToolCall: (tc: IToolCall) => void;
  resetStreaming: () => void;
  setSelectedField: (field: string | null) => void;
  selectWorldbook: (wbId: string | null) => void;
  selectEntry: (entryId: string | null) => void;
  setOutlineExpanded: (v: boolean) => void;
  setEditorDirty: (v: boolean) => void;
  setCardChanges: (changes: Array<{ field: string; value: unknown }>) => void;
  clearCardChanges: () => void;
  setLinkedWorldbooks: (wbs: LinkedWorldbook[]) => void;
  setWorldbookData: (wbId: string, data: { entries: Array<{ id: string; title: string; content: string; keys: string[] }> }) => void;
  clear: () => void;
}

export const useCreationStore = create<CreationState>((set) => ({
  session: null,
  card: null,
  sessions: [],
  messages: [],
  isGenerating: false,
  streamingContent: '',
  streamingToolCalls: [],
  selectedField: null,
  selectedWorldbookId: null,
  selectedEntryId: null,
  outlineExpanded: true,
  editorDirty: false,
  cardChanges: [],
  linkedWorldbooks: [],
  worldbookDataCache: {},

  setSession: (session) => set({ session }),
  setCard: (card) => set({ card }),
  setSessions: (sessions) => set({ sessions }),
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
  setSelectedField: (field) => set({ selectedField: field, editorDirty: false }),
  selectWorldbook: (wbId) => set({ selectedWorldbookId: wbId, selectedEntryId: null, selectedField: 'worldbook_ids', editorDirty: false }),
  selectEntry: (entryId) => set({ selectedEntryId: entryId }),
  setOutlineExpanded: (v) => set({ outlineExpanded: v }),
  setEditorDirty: (v) => set({ editorDirty: v }),
  setCardChanges: (changes) => set({ cardChanges: changes }),
  clearCardChanges: () => set({ cardChanges: [] }),
  setLinkedWorldbooks: (wbs) => set({ linkedWorldbooks: wbs }),
  setWorldbookData: (wbId, data) =>
    set((s) => ({ worldbookDataCache: { ...s.worldbookDataCache, [wbId]: data } })),
  clear: () =>
    set({
      session: null,
      card: null,
      sessions: [],
      messages: [],
      isGenerating: false,
      streamingContent: '',
      streamingToolCalls: [],
      selectedField: null,
      selectedWorldbookId: null,
      selectedEntryId: null,
      outlineExpanded: true,
      editorDirty: false,
      cardChanges: [],
      linkedWorldbooks: [],
      worldbookDataCache: {},
    }),
}));
