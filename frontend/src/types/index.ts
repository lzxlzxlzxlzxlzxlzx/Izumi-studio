// Re-export all types from a single entry point
// These mirror the backend Pydantic models / TypeScript definitions from 数据类型定义_V1.md

// ====== Enums ======

export enum ECardStatus {
  DRAFT = 'draft',
  PUBLISHED = 'published',
}

export enum ECoverSource {
  UPLOAD = 'upload',
  AI_GENERATED = 'ai_generated',
}

export enum ERole {
  SYSTEM = 'system',
  USER = 'user',
  ASSISTANT = 'assistant',
}

export enum EChatMode {
  CREATION = 'creation',
  PLAY = 'play',
  CHAT = 'chat',
}

// ====== Character Card ======

export interface INPC {
  name: string;
  attributes: Record<string, string | number | boolean>;
  start_active: boolean;
  description: string;
}

export interface ICoverInfo {
  image_path: string;
  source: ECoverSource;
  generation_prompt: string;
}

export interface IAvatarInfo {
  image_path: string;
  source: ECoverSource;
  generation_prompt: string;
}

export interface IBackgroundInfo {
  image_path: string;
  source: ECoverSource;
}

export interface ICharacterDefinition {
  name: string;
  description: string;
  personality: string;
  scenario: string;
  speaking_style: string;
  background: string;
  first_mes: string;
  alternate_greetings: string[];
  mes_example: string;
  creator_notes: string;
  npcs: INPC[];
}

export interface IPresetConfig {
  writing_style: string;
  chain_of_thought: boolean;
  word_count_min: number;
  word_count_max: number;
  model: string;
  temperature: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  max_tokens: number;
}

export interface IImageConfig {
  style_tags: string;
  character_appearance: string;
  reference_images: string[];
  aspect_ratio: string;
  generation_service: string;
  auto_generate: boolean;
}

export interface IAuthorsNoteConfig {
  content: string;
  position: string;
  depth: number;
  interval: number;
  role: ERole;
}

export interface ICharacterCard {
  id: string;
  name: string;
  description: string;
  tags: string[];
  spec: string;
  spec_version: string;
  extensions: Record<string, unknown>;
  cover: ICoverInfo;
  avatar: IAvatarInfo;
  background: IBackgroundInfo;
  character: ICharacterDefinition;
  system_prompt: string | null;
  post_history_instructions: string | null;
  depth_prompt: unknown | null;
  worldbook_ids: string[];
  preset_name: string | null;
  preset_config: IPresetConfig;
  image_config: IImageConfig;
  authors_note: IAuthorsNoteConfig | null;
  quick_reply_set_ids: string[];
  regex_script_ids: string[];
  status: ECardStatus;
  version: number;
  created_at: string;
  published_at: string | null;
}

// ====== Session ======

export interface IChatSession {
  id: string;
  card_id: string;
  mode: EChatMode;
  name: string;
  greeting_index: number;
  model: string;
  worldbook_ids: string[];
  preset_name: string;
  background_image: string | null;
  parent_session_id: string | null;
  branch_number: number | null;
  created_at: string;
  updated_at: string;
}

// ====== Message ======

export interface IContentPart {
  type: 'text' | 'image';
  text?: string;
  image_url?: string;
}

export interface ISwipe {
  index: number;
  content: string;
  created_at: string;
}

export interface IChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  name: string;
  content: string | IContentPart[];
  media: IMediaAttachment[];
  index: number;
  round_index: number;
  created_at: string;
  swipes: ISwipe[];
  swipe_index: number;
  has_checkpoint: boolean;
  locked: boolean;
  tool_calls: IToolCall[];
  tool_call_id: string | null;
}

export interface IMediaAttachment {
  type: 'image' | 'audio' | 'video';
  url: string;
  alt_text?: string;
}

export interface IToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

// ====== Character ======

export interface ICharacterImage {
  id: string;
  url: string;
  label?: string;
  filename: string;
  created_at: string;
}

export interface IStoryCharacter {
  id: string;
  session_id: string;
  name: string;
  attributes: Record<string, string | number | boolean>;
  is_active: boolean;
  is_alive: boolean;
  first_seen_round: number;
  last_seen_round: number;
  source: 'card_definition' | 'model_creation';
  images: ICharacterImage[];
  created_at: string;
  updated_at: string;
}

export interface ILongTermMemory {
  id: string;
  session_id: string;
  category: string;
  content: string;
  created_at: string;
}
