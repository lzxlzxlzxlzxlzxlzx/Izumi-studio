# SillyTavern 核心功能分析

> 版本：V1
> 用途：作为 Izumi Studio 开发参考文档，游玩模式核心逻辑需与此保持一致
> 来源：SillyTavern Release (2025-11-19) 源码分析

---

## 目录

1. [整体架构与数据流](#1-整体架构与数据流)
2. [角色卡系统](#2-角色卡系统)
3. [世界书系统](#3-世界书系统)
4. [预设系统：上下文模板](#4-预设系统上下文模板)
5. [预设系统：指令模板](#5-预设系统指令模板)
6. [PromptManager 提示顺序管理](#6-promptmanager-提示顺序管理)
7. [Chat Completion 消息组装流程](#7-chat-completion-消息组装流程)
8. [Text Completion 文本组装流程](#8-text-completion-文本组装流程)
9. [Token 预算管理](#9-token-预算管理)
10. [消息操作系统](#10-消息操作系统)
11. [Author's Note 系统](#11-authors-note-系统)
12. [User Persona 系统](#12-user-persona-系统)
13. [Quick Reply 系统](#13-quick-reply-系统)
14. [Regex 脚本系统](#14-regex-脚本系统)
15. [Extension 扩展系统](#15-extension-扩展系统)
16. [多模型适配层](#16-多模型适配层)
17. [关键数据结构总结](#17-关键数据结构总结)

---

## 1. 整体架构与数据流

### 1.1 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端 (Browser)                               │
│  ┌─────────┐  ┌──────────┐  ┌────────────────────────────────┐     │
│  │ 用户输入 │─→│ Generate │─→│ Message Assembly Pipeline      │     │
│  │ textarea│  │ (script) │  │ ① World Info Scan              │     │
│  └─────────┘  └──────────┘  │ ② Story String Render          │     │
│                              │ ③ Instruct Mode Wrap           │     │
│                              │ ④ Prompt Ordering              │     │
│                              │ ⑤ Extension Injection          │     │
│                              │ ⑥ Token Budget Trim            │     │
│                              └───────────┬────────────────────┘     │
│                                          │                          │
│                              ┌───────────▼────────────────────┐     │
│                              │    generate_data (JSON)         │     │
│                              │  { messages, model, params }   │     │
│                              └───────────┬────────────────────┘     │
└──────────────────────────────────────────┼──────────────────────────┘
                                           │ POST /generate
┌──────────────────────────────────────────┼──────────────────────────┐
│                         后端 (Node.js)    │                          │
│                              ┌───────────▼────────────────────┐     │
│                              │ chat-completions.js             │     │
│                              │ ① postProcessPrompt (可选)     │     │
│                              │ ② Provider 格式转换            │     │
│                              │ ③ 添加模型参数                  │     │
│                              └───────────┬────────────────────┘     │
│                                          │                          │
│                              ┌───────────▼────────────────────┐     │
│                              │    最终请求体 (JSON)             │     │
│                              │  ↓ POST /v1/chat/completions    │     │
│                              └────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流全景

```
用户输入 → sendTextareaMessage() → Generate()
                                      │
                        ┌─────────────▼─────────────┐
                        │   ① 预处理阶段              │
                        │   - 处理 slash command     │
                        │   - 初始化角色/用户名称      │
                        │   - 准备聊天历史             │
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │   ② 世界书扫描              │
                        │   getWorldInfoPrompt()     │
                        │   → worldInfoBefore       │
                        │   → worldInfoAfter        │
                        │   → worldInfoExamples     │
                        │   → atDepth 条目           │
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │   ③ 故事字符串渲染          │
                        │   renderStoryString()      │
                        │   + formatInstructModeStory│
                        │   String() (如启用指令模式)  │
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │   ④ 路由分发                │
                        │   main_api 判断             │
                        │                            │
                        │   ┌─────── OpenAI ────────┐│
                        │   │ prepareOpenAI          ││
                        │   │ Messages()            ││
                        │   │ → ChatCompletion 对象  ││
                        │   └──────────────────────┘│
                        │   ┌─── Text Completion ───┐│
                        │   │ 直接拼接字符串         ││
                        │   │ formatInstructModeChat ││
                        │   └──────────────────────┘│
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │   ⑤ 后端处理               │
                        │   postProcessPrompt()     │
                        │   convertClaudeMessages() │
                        │   等 provider 适配         │
                        └─────────────┬─────────────┘
                                      ▼
                              最终模型请求
```

---

## 2. 角色卡系统

### 2.1 角色卡数据结构（SillyTavern V3 兼容格式）

```json
{
  "name": "角色名称",
  "description": "角色详细描述（性格、背景、外貌等）",
  "personality": "性格摘要，简短的个性标签",
  "scenario": "场景设定，对话发生的初始背景",
  "first_mes": "默认开场白，角色说的第一句话",
  "alt_greetings": ["备选开场白1", "备选开场白2"],
  "mes_example": "<START>\n{{user}}: 示例用户输入\n{{char}}: 示例角色回复\n<START>",
  "creator_notes": "创作者备注（不注入上下文）",
  "system_prompt": "覆盖全局 System Prompt 的角色卡专属提示（可选）",
  "post_history_instructions": "注入到消息历史末尾的持续指令（可选）",
  "character_book": "角色卡绑定的内联世界书（可选）",
  "tags": ["标签1", "标签2"],
  "avatar": "头像文件路径",
  "create_date": "创建时间戳"
}
```

### 2.2 角色卡字段在上下文中的使用

| 字段 | 注入位置 | 格式 | 说明 |
|------|---------|------|------|
| `description` | `charDescription` prompt | 经 `description_format` 格式化 | 角色外貌/背景详细描述 |
| `personality` | `charPersonality` prompt | 经 `personality_format` 格式化 | 性格标签摘要 |
| `scenario` | `scenario` prompt | 经 `scenario_format` 格式化 | 场景设定 |
| `first_mes` / `alt_greetings` | 聊天历史首条 | 原始文本 | 开场白，选择后进入历史 |
| `mes_example` | `dialogueExamples` prompt | 经示例分隔符和指令模式格式化 | few-shot 示例 |
| `system_prompt` | 覆盖 `main` prompt | 替换 story_string 渲染结果 | 完全控制系统提示 |
| `post_history_instructions` | 聊天历史末尾（jailbreak） | system role | 注入到最后一条消息之后 |
| `character_book` | 同世界书系统 | 同世界书逻辑 | 角色专属内联世界书 |

### 2.3 角色卡栏位格式模板

角色卡的三个核心字段（description、personality、scenario）在注入前会使用用户配置的格式模板进行包装。这些模板定义在 OpenAI 预设中：

- **`description_format`**：`关于 {{char}}：{{description}}`（默认）
- **`personality_format`**：`{{char}} 的性格：{{personality}}`（默认）
- **`scenario_format`**：`场景：{{scenario}}`（默认）

当对应字段为空时，格式模板不会被应用。

---

## 3. 世界书系统

### 3.1 世界书结构

```json
{
  "id": "uuid",
  "name": "世界书名称",
  "description": "简介",
  "scan_depth": 100,
  "token_budget": 2048,
  "token_budget_ratio": 0.25,
  "recursive_scanning": false,
  "max_recursion_steps": 3,
  "case_sensitive": false,
  "match_whole_words": false,
  "insertion_strategy": "character_first",
  "min_activations": 0,
  "overflow_alert": false,
  "entries": [ ... ]
}
```

### 3.2 条目结构

```json
{
  "id": "uuid",
  "title": "条目标题",
  "comment": "创作者备注（不注入上下文）",
  "keys": ["主关键词1", "主关键词2"],
  "keys_secondary": ["次关键词1", "次关键词2"],
  "selective_logic": "AND_ANY | AND_ALL | NOT_ANY | NOT_ALL",
  "content": "条目正文，注入上下文的实际内容",
  "enabled": true,
  "constant": false,
  "priority": 100,
  "insertion_order": 100,
  "position": "before_char | after_char | at_depth | examples | an_top | an_bottom | em_top | em_bottom | outlet",
  "depth": 4,
  "role": "system | user | assistant",
  "case_sensitive": false,
  "match_whole_words": false,
  "probability": 100,
  "sticky": 0,
  "cooldown": 0,
  "delay": 0,
  "group": "",
  "group_weight": 100,
  "prevent_recursion": false,
  "exclude_recursion": false,
  "delay_until_recursion": false,
  "match_persona_description": false,
  "match_character_description": false,
  "match_character_personality": false,
  "match_character_scenario": false,
  "vectorized": false
}
```

### 3.3 触发机制

#### 3.3.1 扫描流程

```
checkWorldInfo(chat, maxContext)
  │
  ├── 1. 构建 WorldInfoBuffer（从聊天历史提取扫描文本）
  │
  ├── 2. 遍历已排序的世界书条目
  │     ├── 检查启用/禁用状态
  │     ├── 检查生成类型过滤器（normal/continue/impersonate）
  │     ├── 检查角色过滤器（名称/标签包含或排除）
  │     ├── 检查时序效果（sticky/cooldown/delay）
  │     ├── 检查"延迟到递归阶段"标记
  │     ├── 关键词匹配（主关键词 + 次关键词逻辑）
  │     ├── 概率判定（0-100）
  │     │
  │     └── 通过所有检查 → 标记为激活
  │
  ├── 3. 分组评分：同 group 内只保留 group_weight 最高的条目
  │
  ├── 4. Token 预算裁剪：按 priority 排序，预算耗尽后丢弃
  │
  ├── 5. 递归扫描（如开启 recursive_scanning）
  │     └── 新激活条目的 content 加入扫描缓冲区，重复步骤 2-4
  │
  └── 6. 按 position 分类输出
        ├── worldInfoBefore (position = before_char)
        ├── worldInfoAfter  (position = after_char)
        ├── EMEntries       (position = em_top / em_bottom → 示例对话)
        ├── WIDepthEntries  (position = at_depth)
        ├── ANBeforeEntries (position = an_top / an_bottom → Author's Note 区域)
        ├── ANAfterEntries
        └── outletEntries   (position = outlet → 扩展系统)
```

#### 3.3.2 关键词匹配逻辑

| Selective Logic | 触发条件 |
|----------------|---------|
| `AND_ANY` | 主关键词至少命中一个 **AND** 次关键词至少命中一个 |
| `AND_ALL` | 主关键词至少命中一个 **AND** 次关键词全部命中 |
| `NOT_ANY` | 主关键词至少命中一个 **AND** 次关键词一个都没命中 |
| `NOT_ALL` | 主关键词至少命中一个 **AND** 次关键词没有全部命中 |

- 当 `keys_secondary` 为空时，只需主关键词命中即可触发。
- 支持大小写敏感和全词匹配（每个条目可独立配置，覆盖全局设置）。

#### 3.3.3 时序效果

| 参数 | 说明 |
|------|------|
| `sticky` | 条目激活后，保持激活 N 轮（无需重复匹配关键词），超出深度后释放 |
| `cooldown` | 条目激活后，冷却 N 轮才能再次激活 |
| `delay` | 从对话开始算，经过 N 轮后才开始扫描此条目 |

这三个参数通过 `WorldInfoTimedEffects` 类管理，跨轮次持久化在 `timed_effects` 映射中。

#### 3.3.4 插入位置详解

| Position | 含义 | 在消息数组中的位置 |
|----------|------|-------------------|
| `before_char` | 角色描述之前 | System Prompt 最前面，在 main prompt 之前 |
| `after_char` | 角色描述之后 | 在 main prompt 与 charDescription 之间 |
| `at_depth` | 对话历史中特定深度 | 从最新消息往旧消息数第 N 条处插入 |
| `examples` | 对话示例区域 | 插入到 dialogueExamples 块中 |
| `an_top` | Author's Note 上方 | AN 区域前 |
| `an_bottom` | Author's Note 下方 | AN 区域后 |
| `em_top` | 示例对话上方 | 示例块前 |
| `em_bottom` | 示例对话下方 | 示例块后 |
| `outlet` | 扩展出口 | 由扩展系统决定 |

#### 3.3.5 扫描范围扩展

世界书条目可以配置从以下额外来源匹配关键词（不仅限于聊天历史）：

- `match_persona_description`：扫描用户人设描述
- `match_character_description`：扫描角色描述
- `match_character_personality`：扫描角色性格
- `match_character_scenario`：扫描角色场景

这些字段也被加入扫描缓冲区，使得角色卡本身的内容可以触发世界书。

### 3.4 世界书格式化

世界书内容在注入前会使用 `wi_format` 模板进行包装：

```
export function formatWorldInfo(value) {
    const format = oai_settings.wi_format;
    if (!format.trim()) return value;
    return stringFormat(format, value);  // 如 "[世界观: {0}]" → "[世界观: 内容]"
}
```

默认格式为空（直接使用原始内容）。

---

## 4. 预设系统：上下文模板

### 4.1 定位

上下文模板（Context Template）控制**系统提示（main prompt）的内容和结构**。它定义了一个 Handlebars 模板字符串（称为 `story_string`），在每次生成时被渲染为实际的 system prompt。

### 4.2 结构

上下文模板存储在 `power_user.context` 中：

```typescript
interface ContextSettings {
    preset: string;                    // 预设名称
    story_string: string;              // Handlebars 模板
    chat_start: string;                // 对话开始标记
    example_separator: string;         // 示例对话分隔符
    use_stop_strings: boolean;         // 使用停止字符串
    names_as_stop_strings: boolean;    // 角色名作为停止字符串
    story_string_position: number;     // 注入位置（IN_PROMPT / IN_CHAT）
    story_string_role: number;         // 注入角色（SYSTEM / USER / ASSISTANT）
    story_string_depth: number;        // 注入深度
}
```

### 4.3 默认 Story String

```
{{#if system}}{{system}}
{{/if}}{{#if description}}{{description}}
{{/if}}{{#if personality}}{{char}}'s personality: {{personality}}
{{/if}}{{#if scenario}}Scenario: {{scenario}}
{{/if}}{{#if persona}}{{persona}}
{{/if}}
```

这是一个 Handlebars 模板，渲染时填充以下变量：

| 变量 | 来源 | 说明 |
|------|------|------|
| `description` | 角色卡 | 角色描述 |
| `personality` | 角色卡 | 角色性格 |
| `scenario` | 角色卡 | 场景设定 |
| `system` | Sysprompt 设置 | 全局系统提示 |
| `persona` | User Persona | 用户人设描述（当位置为 IN_PROMPT 时） |
| `char` | 角色卡 | 角色名称 |
| `user` | 用户设置 | 用户名称 |
| `wiBefore` | 世界书 | 世界书 before 内容 |
| `wiAfter` | 世界书 | 世界书 after 内容 |
| `loreBefore` | (同 wiBefore) | 兼容旧版字段名 |
| `loreAfter` | (同 wiAfter) | 兼容旧版字段名 |
| `anchorBefore` | 扩展系统 | BEFORE_PROMPT 扩展提示 |
| `anchorAfter` | 扩展系统 | IN_PROMPT 扩展提示 |
| `mesExamples` | 角色卡 | 示例对话（合并后） |
| `mesExamplesRaw` | 角色卡 | 示例对话（原始数组） |

### 4.4 渲染流程

```
renderStoryString(params)
  │
  ├── ① 获取 story_string 模板（从 power_user.context.story_string）
  │
  ├── ② 编译 Handlebars 模板
  │
  ├── ③ 代入 params 渲染
  │
  ├── ④ substituteParams() 处理 {{macro}} 宏
  │
  ├── ⑤ formatInstructModeStoryString()（如启用指令模式）
  │     ├── 添加 story_string_prefix（指令模式前缀）
  │     └── 添加 story_string_suffix（指令模式后缀）
  │
  └── ⑥ 返回最终的 main prompt 字符串
```

### 4.5 注入位置控制

story_string 的注入位置有两种模式：

- **`IN_PROMPT`**（默认）：渲染后直接作为 `main` prompt 放入 system prompt 区域（Chat Completion 路线）
- **`IN_CHAT`**：渲染后作为 `at_depth` 注入到聊天历史的特定深度位置（非 OpenAI 路线），此时 `story_string_depth` 和 `story_string_role` 控制具体深度和角色

### 4.6 上下文预设在预设配置文件中的存储

上下文预存在 `context_presets` 数组中，每个预设是一个包含上述 `ContextSettings` 字段的对象。预设通过名称索引，用户可在 UI 中切换。

```json
{
  "name": "Default",
  "story_string": "{{#if system}}{{system}}\n{{/if}}...",
  "chat_start": "***",
  "example_separator": "***",
  "use_stop_strings": true,
  "names_as_stop_strings": true,
  "story_string_position": 1,
  "story_string_role": 0,
  "story_string_depth": 1
}
```

---

## 5. 预设系统：指令模板

### 5.1 定位

指令模板（Instruct Template）控制**每条消息在发送前的包装格式**——即消息应该用什么前缀/后缀包裹。这对于适配不同模型（如 Alpaca、ChatML、Mistral 等格式）至关重要。

### 5.2 结构

```typescript
interface InstructSettings {
    enabled: boolean;                    // 是否启用
    preset: string;                      // 预设名称
    wrap: boolean;                       // 是否在序列后加换行
    macro: boolean;                      // 是否替换 {{name}} 宏
    input_sequence: string;              // 用户输入前缀（如 "### User:\n"）
    input_suffix: string;                // 用户输入后缀
    output_sequence: string;             // AI 回复前缀（如 "### Assistant:\n"）
    output_suffix: string;               // AI 回复后缀
    system_sequence: string;             // 系统消息前缀
    system_suffix: string;               // 系统消息后缀
    last_system_sequence: string;        // 最后一条系统指令的前缀（生成前的提示）
    first_output_sequence: string;       // 首次输出的前缀（第一轮回复用）
    last_output_sequence: string;        // 最后输出的前缀（当前要生成的回复）
    first_input_sequence: string;        // 第一条用户输入前缀
    last_input_sequence: string;         // 最后一条用户输入前缀
    stop_sequence: string;               // 停止序列
    system_same_as_user: boolean;        // 系统消息是否使用用户格式
    skip_examples: boolean;              // 是否跳过示例格式化
    names_behavior: 'none' | 'force' | 'always';  // 名称处理策略
    sequences_as_stop_strings: boolean;  // 序列是否作为停止字符串
    story_string_prefix: string;         // 故事字符串前缀
    story_string_suffix: string;         // 故事字符串后缀
    activation_regex: string;            // 自动激活正则（按模型 ID 匹配）
    bind_to_context: boolean;            // 是否绑定到同名的上下文模板
    user_alignment_message: string;      // 用户对齐消息
}
```

### 5.3 消息格式化函数

#### 5.3.1 对话消息格式化

核心函数 `formatInstructModeChat()`：

```typescript
function formatInstructModeChat(
    name: string,          // 发送者名称
    mes: string,           // 消息内容
    isUser: boolean,       // 是否为用户消息
    isNarrator: boolean,   // 是否为旁白消息
    forceAvatar: string,   // 强制头像
    name1: string,         // 用户名称
    name2: string,         // 角色名称
    forceOutputSequence: number | boolean,  // 强制输出序列类型
    customInstruct?: InstructSettings
): string
```

格式化逻辑：

```
① 确定名称是否包含
   - ALWAYS: 所有消息都包含名称
   - FORCE: 群聊或强制头像时（且不是用户自己）包含名称
   - NONE: 不包含名称

② 确定前缀
   - 旁白（isNarrator）: system_same_as_user ? input_sequence : system_sequence
   - 用户（isUser）: input_sequence（可选 first/last 变体）
   - AI: output_sequence（可选 first/last 变体）

③ 确定后缀
   - 旁白: system_same_as_user ? input_suffix : system_suffix
   - 用户: input_suffix
   - AI: output_suffix

④ 替换宏: {{name}} → 实际的发送者名称

⑤ 组装: 前缀 + 分隔符 + (名称: + 内容) + 后缀
```

#### 5.3.2 故事字符串格式化

`formatInstructModeStoryString()` 在指令模式下给 story_string 添加前缀/后缀：

```
story_string_prefix + 内容 + story_string_suffix
```

当注入位置为 `IN_CHAT` 时不应用包装（交由消息序列处理）。

#### 5.3.3 示例对话格式化

`formatInstructModeExamples()` 格式化示例对话：

```
① 确定是否跳过格式化（skip_examples）
② 确定名称包含策略
③ 对每条示例：
   - 用户示例: input_sequence + 内容 + input_suffix
   - AI 示例: output_sequence + 内容 + output_suffix
④ 添加示例分隔符（example_separator）
```

#### 5.3.4 最后一行格式化

`formatInstructModePrompt()` 格式化最后一行的生成提示：

```
① 根据场景获取序列
   - 用户冒充（impersonate）: input_sequence
   - 安静生成（quiet）: last_system_sequence || output_sequence
   - 安静转大声（quietToLoud）: last_output_sequence || output_sequence
   - 默认: last_output_sequence || output_sequence

② 添加 promptBias（如存在）
③ 如有名称包含，添加 "名称:" 后缀
```

### 5.4 停止序列

`getInstructStoppingSequences()` 收集所有停止字符串：

```
① 指令序列（启用时）:
   stop_sequence, input_sequence, output_sequence,
   first_output_sequence, last_output_sequence,
   system_sequence, last_system_sequence

② 上下文停止字符串（启用时）:
   chat_start, example_separator
```

### 5.5 指令模板与上下文模板的绑定

- `bind_to_context` 启用时，选择指令模板自动选择同名上下文模板
- `model_templates_mappings` 支持按模型 ID 自动选择模板对
- 通过 `activation_regex` 正则匹配模型 ID 自动激活

---

## 6. PromptManager 提示顺序管理

### 6.1 定位

PromptManager 是 SillyTavern 消息组装的**总调度器**。它控制所有提示片段（角色描述、世界书、扩展等）在最终消息数组中的**顺序和启用状态**。

### 6.2 核心概念

#### 6.2.1 Prompt 定义

每个提示片段是一个 `Prompt` 对象：

```typescript
interface Prompt {
    identifier: string;              // 唯一标识符，如 "main", "worldInfoBefore"
    name: string;                    // 显示名称
    role: 'system' | 'user' | 'assistant';   // 消息角色
    content: string;                 // 提示内容
    system_prompt: boolean;          // 是否为系统提示
    marker: boolean;                 // 是否为标记（占位符，内容由其他函数填充）
    injection_position: number;      // 注入位置（RELATIVE=0, ABSOLUTE=1）
    injection_depth: number;         // 注入深度（仅 ABSOLUTE）
    injection_order: number;         // 注入顺序（同深度时排序）
    injection_trigger: string[];     // 触发类型
    forbid_overrides: boolean;       // 禁止角色卡覆盖
    extension: string;               // 所属扩展名
}
```

#### 6.2.2 默认提示列表

```typescript
const defaultPrompts = [
    { name: 'Main Prompt',             identifier: 'main',               system_prompt: true, role: 'system', marker: true  },
    { name: 'Auxiliary Prompt',        identifier: 'nsfw',               system_prompt: true, role: 'system', marker: false },
    { name: 'Chat Examples',           identifier: 'dialogueExamples',   system_prompt: true, role: 'system', marker: true  },
    { name: 'Post-History Instructions',identifier: 'jailbreak',          system_prompt: true, role: 'system', marker: false },
    { name: 'Chat History',            identifier: 'chatHistory',         system_prompt: true, role: 'system', marker: true  },
    { name: 'World Info (after)',       identifier: 'worldInfoAfter',     system_prompt: true, role: 'system', marker: true  },
    { name: 'World Info (before)',      identifier: 'worldInfoBefore',    system_prompt: true, role: 'system', marker: true  },
    { name: 'Enhance Definitions',     identifier: 'enhanceDefinitions', system_prompt: true, role: 'system', marker: false },
    { name: 'Char Description',        identifier: 'charDescription',     system_prompt: true, role: 'system', marker: true  },
    { name: 'Char Personality',        identifier: 'charPersonality',     system_prompt: true, role: 'system', marker: true  },
    { name: 'Scenario',                identifier: 'scenario',            system_prompt: true, role: 'system', marker: true  },
    { name: 'Persona Description',     identifier: 'personaDescription',  system_prompt: true, role: 'system', marker: true  },
];
```

其中 `marker: true` 的提示是**占位符**，其内容由 `preparePromptsForChatCompletion()` 在实际运行时动态填充。

### 6.3 默认顺序

```typescript
const defaultOrder = [
    { identifier: 'main',               enabled: true },
    { identifier: 'worldInfoBefore',     enabled: true },
    { identifier: 'personaDescription',  enabled: true },
    { identifier: 'charDescription',     enabled: true },
    { identifier: 'charPersonality',     enabled: true },
    { identifier: 'scenario',            enabled: true },
    { identifier: 'enhanceDefinitions',  enabled: false },
    { identifier: 'nsfw',                enabled: true },
    { identifier: 'worldInfoAfter',      enabled: true },
    { identifier: 'dialogueExamples',    enabled: true },
    { identifier: 'chatHistory',         enabled: true },
    { identifier: 'jailbreak',           enabled: true },
];
```

用户可以：
- 通过拖拽 UI **重新排序** 任何 prompt
- 通过开关 **启用/禁用** 任何 prompt
- 为每个角色卡设置**独立顺序**（未设置时使用全局默认顺序）
- 配置每个 prompt 的**注入位置、深度、角色**覆盖

### 6.4 PromptCollection

`PromptCollection` 是一个有序集合，存储按角色配置的顺序排列的活跃 prompt：

```
getPromptCollection(generationType)
  │
  ├── ① 获取当前角色的 prompt 顺序（或全局默认顺序）
  │
  ├── ② 遍历顺序列表
  │     ├── 检查 enabled 状态
  │     ├── 检查生成类型 trigger
  │     │   └── shouldTrigger(prompt, generationType)
  │     └── 通过 → 加入 collection
  │         └── 未通过但 identifier 为 "main" → 加入空内容占位
  │
  └── ③ 返回有序的 PromptCollection
```

---

## 7. Chat Completion 消息组装流程

这是 SillyTavern 最核心的消息组装路径（对应 `main_api === 'openai'` 的分支）。

### 7.1 入口函数：prepareOpenAIMessages

**定义位置**: `public/scripts/openai.js`

```typescript
async function prepareOpenAIMessages({
    name2,            // 角色名称
    charDescription,  // 角色描述
    charPersonality,  // 角色性格
    scenario,         // 场景设定
    worldInfoBefore,  // 世界书 before 内容
    worldInfoAfter,   // 世界书 after 内容
    bias,             // 对话偏置
    type,             // 生成类型（normal / continue / impersonate）
    quietPrompt,      // 安静生成提示
    quietImage,       // 安静生成图片
    extensionPrompts, // 扩展提示
    cyclePrompt,      // 循环提示
    systemPromptOverride,    // 角色卡系统提示覆盖
    jailbreakPromptOverride, // 角色卡后历史指令覆盖
    messages,         // 聊天历史
    messageExamples,  // 示例对话
}, dryRun)
```

### 7.2 第一阶段：准备提示集合

`preparePromptsForChatCompletion()` 将所有提示片段收集到 `PromptCollection` 中：

**① 构建 systemPrompts 基础数组：**

```javascript
const systemPrompts = [
    { role: 'system', content: formatWorldInfo(worldInfoBefore), identifier: 'worldInfoBefore' },
    { role: 'system', content: formatWorldInfo(worldInfoAfter),  identifier: 'worldInfoAfter' },
    { role: 'system', content: charDescription,                 identifier: 'charDescription' },
    { role: 'system', content: charPersonalityText,             identifier: 'charPersonality' },
    { role: 'system', content: scenarioText,                     identifier: 'scenario' },
    { role: 'system', content: impersonationPrompt,              identifier: 'impersonate' },
    { role: 'system', content: quietPrompt,                      identifier: 'quietPrompt' },
    { role: 'system', content: groupNudge,                       identifier: 'groupNudge' },
    { role: 'assistant', content: bias,                          identifier: 'bias' },
];
```

**② 添加扩展提示：**

```javascript
// Summary（对话摘要）
{ role: getPromptRole(summary.role), content: summary.text, identifier: 'summary' }

// Author's Note
{ role: getPromptRole(authorsNote.role), content: authorsNote.text, identifier: 'authorsNote' }

// Vector Memory / DataBank
{ role: getPromptRole(vectors.role), content: vectors.text, identifier: 'vectorsMemory' }

// Smart Context
{ role: 'system', content: smartContext.text, identifier: 'smartContext' }

// Persona Description
{ role: 'system', content: power_user.persona_description, identifier: 'personaDescription' }
```

**③ 应用 PromptManager 覆盖：**

对每个 systemPrompt，从 PromptCollection 中查找同名 prompt，应用其 `injection_position`、`injection_depth`、`injection_order`、`role` 的覆盖值。

**④ 处理角色卡覆盖：**

- `systemPromptOverride` → 替换 `main` prompt 的 content
- `jailbreakPromptOverride` → 替换 `jailbreak` prompt 的 content

### 7.3 第二阶段：填充 ChatCompletion

`populateChatCompletion()` 负责按预算和顺序将所有内容填入最终的 `ChatCompletion` 对象：

#### 7.3.1 添加顺序（最终消息数组顺序）

```
消息数组顺序（从上到下）：

  SYSTEM PROMPT 区域:
  ┌─────────────────────────────────────────────────────────┐
  │ 1. worldInfoBefore     ← 世界书(before char)            │
  │ 2. main                ← Story String 渲染的主提示      │
  │ 3. worldInfoAfter      ← 世界书(after char)             │
  │ 4. charDescription     ← 角色描述                       │
  │ 5. charPersonality     ← 角色性格                       │
  │ 6. scenario            ← 场景设定                        │
  │ 7. personaDescription  ← 用户人设描述                    │
  │ 8. nsfw                ← NSFW 辅助提示                  │
  │ 9. userRelativePrompts ← 用户自定义提示                  │
  │10. jailbreak           ← 后历史指令                      │
  │11. enhanceDefinitions  ← 定义增强（默认禁用）            │
  │12. bias                ← 对话偏置（assistant role）      │
  │13. summary             ← 对话摘要（如启用）              │
  │14. authorsNote         ← Author's Note（如启用）          │
  │15. vectorsMemory       ← 向量记忆（如启用）              │
  │16. vectorsDataBank     ← 向量数据银行                    │
  │17. smartContext        ← 智能上下文                      │
  │18. extensions          ← 扩展提示                        │
  ├─────────────────────────────────────────────────────────┤
  │ CHAT HISTORY 区域:                                      │
  │19. dialogueExamples    ← 示例对话（few-shot）             │
  │20. chatHistory         ← 实际聊天历史                     │
  │    ├── 消息 1 (最早)                                     │
  │    ├── 消息 2                                            │
  │    ├── ...  (可能插入 atDepth 世界书条目)                │
  │    └── 消息 N (最新)                                     │
  ├─────────────────────────────────────────────────────────┤
  │ CONTROL PROMPT 区域:                                    │
  │21. impersonate/quiet/continue 控制提示                   │
  └─────────────────────────────────────────────────────────┘
```

#### 7.3.2 重要添加细节

**对话历史填充** (`populateChatHistory`)：

1. 在 `chatHistory` 标记处创建一个 `MessageCollection`
2. 预留 `newChat` 消息的 token 预算（用于注入"新对话开始"提示）
3. 从最新消息开始反向遍历聊天历史：
   - 每个消息创建为 `Message` 对象
   - 处理媒体附件（图片/视频/音频内联）
   - 处理工具调用（tool_calls 和 tool_results）
   - `canAfford()` 检查 token 预算 → 超预算则停止添加
4. 插入新对话提示消息
5. 插入群聊 nudge 消息（群聊模式）
6. 插入继续生成（continue）的提示消息

**示例对话填充** (`populateDialogueExamples`)：

1. 在 `dialogueExamples` 标记处创建 `MessageCollection`
2. 添加 `newExampleChat` 提示消息
3. 遍历 `messageExamples`，批量添加示例对话
4. 同样受 token 预算约束

**绝对位置注入** (`populationInjectionPrompts`)：

- 处理 `injection_position === ABSOLUTE` 的 prompt
- 按 `injection_depth` 将消息插入聊天历史的指定位置
- 相同深度按 `injection_order` 排序
- 按 `role` 分组（system → user → assistant）

**角色名称处理**：

| `names_behavior` 模式 | 行为 |
|----------------------|------|
| `NONE` | 不添加名称字段 |
| `DEFAULT` | 仅当消息有名称时添加 `name` 字段 |
| `CONTENT` | 将角色名作为内容前缀拼入消息文本 |
| `COMPLETION` | 使用特定格式的名称映射（文本补全模式） |

### 7.4 最终输出

`prepareOpenAIMessages()` 返回：

```javascript
const chat = chatCompletion.getChat();
// 格式: [{role, content, name?, tool_calls?}, ...]
return [chat, tokenHandler.counts];
```

然后通过 `sendOpenAIRequest()` 发送给后端。

---

## 8. Text Completion 文本组装流程

对于非 OpenAI 的 API（Kobold、Text Generation WebUI 等），SillyTavern 使用另一种消息组装方式——直接拼接字符串。

### 8.1 入口：Generate() 中的非 OpenAI 分支

在 `script.js` 的 `Generate()` 函数中，当 `main_api !== 'openai'` 时，走文本补全路径。

### 8.2 组装步骤

```
① 渲染 story_string → combinedStoryString
   ② 如位置为 IN_CHAT → 设置为扩展注入（不在 system prompt 区域）
   ③ 否则 → combinedStoryString 保持为 system prompt

   ④ 格式化聊天历史
   for each message:
       ⑤ formatMessageHistoryItem(message, isInstruct, forceOutputSequence)
       ⑥ 如启用指令模式 → formatInstructModeChat()
       ⑦ 否则 → 直接拼接 "名称: 内容"

   ⑧ 注入 jailbreak / post-history instructions（作为最后一条用户消息）

   ⑨ 注入扩展深度提示（atDepth 位置）

   ⑩ 组装最终 prompt 字符串:
   combinedStoryString + 示例对话 + 聊天历史 + 最后一行提示
```

### 8.3 formatMessageHistoryItem

```typescript
function formatMessageHistoryItem(
    chatItem: { name: string, mes: string, is_user: boolean, extra?: { type: string } },
    isInstruct: boolean,
    forceOutputSequence: number | boolean
): string {
    if (isInstruct) {
        return formatInstructModeChat(
            chatItem.name, chatItem.mes, chatItem.is_user,
            chatItem.extra?.type === system_message_types.NARRATOR,
            chatItem.force_avatar, name1, name2, forceOutputSequence
        );
    } else {
        // 非指令模式：简单拼接
        return `${chatItem.name}: ${chatItem.mes}`;
    }
}
```

### 8.4 最终 prompt 示例（指令模式）

```
<|system|>
你是一个角色扮演助手...
<|end|>

<|user|>
用户: 你好
<|end|>

<|assistant|>
角色: 你好啊，旅行者
<|end|>

<|user|>
用户: 你是谁
<|end|>

<|im_start|>assistant
角色:
```

（具体格式取决于使用的指令模板）

---

## 9. Token 预算管理

### 9.1 核心机制

ChatCompletion 类 (`openai.js`) 管理 token 预算：

```typescript
class ChatCompletion {
    private budget: number;       // 可用 token 预算
    private collections: MessageCollection[];  // 消息集合

    // 设置预算 = max_context - max_tokens（保留给生成的空间）
    setTokenBudget(maxContext: number, maxTokens: number): void {
        this.budget = maxContext - maxTokens;
    }

    // 检查是否可容纳
    canAfford(message: Message | MessageCollection): boolean {
        return message.getTokens() <= this.budget;
    }

    // 预留预算（先占位再释放）
    reserveBudget(message: Message | MessageCollection): void {
        this.budget -= message.getTokens();
    }

    // 释放预算
    freeBudget(message: Message | MessageCollection): void {
        this.budget += message.getTokens();
    }
}
```

### 9.2 预算分配策略

```
总预算 = max_context - max_tokens（由预设配置）

按添加顺序消耗预算：
  ① 系统提示（main、worldInfo、description 等）→ 必须全部容纳
  ② 为"新对话提示"预留预算
  ③ 示例对话 → 能容纳多少加多少
  ④ 聊天历史 → 从最新消息开始反向添加，预算用完即止

核心原则：
  - 重要的（系统提示）优先保证
  - 历史消息从最新开始保留，越旧的越可能被裁剪
  - 确保始终至少保留最新的对话轮次
```

### 9.3 裁剪链

当总 token 超出时，按以下优先级裁剪：

```
1. 中期摘要（保留最新几段，删除最早的）
2. 世界书条目（按 priority 排序，最低优先级的先裁）
3. 示例对话（全部移除）
4. 聊天历史（移除最旧的消息）
```

---

## 10. 消息操作系统

### 10.1 Swipe 系统

- 每次生成的新回复作为 `swipe` 添加到当前消息位置
- 用户可以通过左右切换查看不同的生成结果
- 数据结构：`messages[位置].swipes = [{content, timestamp}, ...]`
- 当前显示的 swipe 由 `swipe_index` 标记

### 10.2 Checkpoint 系统

- 在任意消息处创建快照标记
- 不创建新的对话分支，只在消息上显示标记图标
- 点击标记图标可跳转到该位置查看

### 10.3 Branch 系统

- 从任意消息创建新的独立对话分支
- 新分支复制该消息之前的所有历史
- 分支以"原对话名 - Branch #N"命名

### 10.4 继续生成（Continue）

- 从角色最后一条未完成的消息继续生成
- 触发条件：最后一条消息为 assistant role
- 通过预填充（prefill）机制实现：
  - `continue_prefill` 为 true 时，将最后一条消息作为 assistant 预填充发送
  - `continue_prefill` 为 false 时，使用 `continue_nudge_prompt` 作为系统提示

### 10.5 消息编辑与撤回

- **编辑**：直接修改任意历史消息的文本内容
- **撤回**：删除最后一轮对话（用户输入 + 模型回复）
- **消息锁定**：锁定指定消息，防止被撤回或覆盖

---

## 11. Author's Note 系统

### 11.1 定位

Author's Note 是一种轻量级的上下文注入机制，允许用户在**对话进行中**动态注入短文本指令，无需修改系统提示。

### 11.2 注入行为

在 `preparePromptsForChatCompletion()` 中，Author's Note 作为扩展提示处理：

```javascript
// 从扩展系统获取 AN 配置
const authorsNote = {
    text: "当前引导词内容",
    role: extension_prompt_roles.SYSTEM,  // system / user / assistant
    position: extension_prompt_types.IN_PROMPT,  // BEFORE_PROMPT / IN_PROMPT / IN_CHAT
    depth: 4,       // IN_CHAT 时的深度
    interval: 1,    // 注入间隔（每 N 轮）
};
```

### 11.3 注入位置

| 位置 | 说明 |
|------|------|
| `BEFORE_PROMPT` | 注入到 system prompt 之前（最顶部） |
| `IN_PROMPT` | 注入到 system prompt 之后、聊天历史之前（默认） |
| `IN_CHAT` | 注入到聊天历史中的特定深度（由 depth 控制） |

### 11.4 注入间隔

- `interval = 1`：每轮对话都注入（默认）
- `interval = 0`：禁用
- `interval > 1`：每 N 轮注入一次

---

## 12. User Persona 系统

### 12.1 定位

User Persona 允许用户定义"自己"在故事中的角色描述，使模型能够正确理解和称呼用户。

### 12.2 数据结构

```typescript
interface Persona {
    name: string;              // 人设名称（替换 {{user}} 宏）
    description: string;       // 人设描述，注入上下文
    avatar_path?: string;      // 头像路径
    injection_depth: number;   // 注入深度（IN_CHAT 时）
    injection_role: number;    // 注入角色（system / user / assistant）
}
```

### 12.3 注入方式

Persona 描述在 `preparePromptsForChatCompletion()` 中作为 `personaDescription` 注入：

- 默认位置在 `charDescription` 和 `charPersonality` 之间（由 PromptManager 顺序控制）
- 当 `persona_description_position` 设置为 `IN_PROMPT` 时，也会作为变量传入 `renderStoryString()` 参与 main prompt 渲染
- 名称替换 `{{user}}` 宏变量在所有提示文本中

---

## 13. Quick Reply 系统

### 13.1 定位

预设快捷按钮，位于输入框上方，点击后快速插入或发送预定义内容。

### 13.2 配置结构

```typescript
interface QuickReplyButton {
    id: string;
    label: string;                 // 显示标签
    message: string;               // 发送内容（支持宏变量）
    show_label: boolean;           // 是否显示标签
    is_auto: boolean;              // 自动发送（不显示到输入框）
    is_hotkey: boolean;            // 是否绑定热键
    hotkey?: string;               // 热键组合
}

interface QuickReplySet {
    id: string;
    name: string;
    buttons: QuickReplyButton[];
}
```

### 13.3 作用域

- **全局 Quick Reply**：所有对话可用
- **角色卡 Quick Reply**：仅特定角色卡可用
- 多个 Set 可同时激活，按钮合并显示

---

## 14. Regex 脚本系统

### 14.1 定位

通过正则表达式对用户输入和模型输出进行格式处理。

### 14.2 脚本结构

```typescript
interface RegexScript {
    id: string;
    script_name: string;
    enabled: boolean;
    find_regex: string;            // 查找正则
    replace_string: string;        // 替换字符串
    trim_strings: string[];        // 裁剪字符串
    placement: ('user_input' | 'model_output' | 'slash_command')[];  // 应用阶段
    run_on_edit: boolean;          // 编辑时是否运行
    markdown_only: boolean;        // 仅 markdown 渲染时
    min_depth: number | null;      // 最小深度
    max_depth: number | null;      // 最大深度
}
```

### 14.3 处理阶段

| placement | 说明 | 执行时机 |
|-----------|------|---------|
| `user_input` | 处理用户输入 | 用户发送前，进入 Generate() 前 |
| `model_output` | 处理模型输出 | 模型返回后，显示到 UI 前 |
| `slash_command` | 处理 slash command 输出 | Slash Command 执行后 |

### 14.4 层级

- **全局 Regex**：对所有对话生效
- **角色卡 Regex**：仅对当前角色卡对话生效，优先级高于全局

---

## 15. Extension 扩展系统

### 15.1 定位

SillyTavern 通过事件系统和扩展 API 支持第三方功能扩展。

### 15.2 注入机制

扩展可以在 `preparePromptsForChatCompletion()` 中通过以下方式注入内容：

```typescript
interface ExtensionPrompt {
    text: string;                          // 提示文本
    role: extension_prompt_roles;          // SYSTEM / USER / ASSISTANT
    position: extension_prompt_types;      // BEFORE_PROMPT / IN_PROMPT / IN_CHAT
    depth: number;                         // 注入深度
}
```

**注入位置：**

- `extension_prompt_types.BEFORE_PROMPT` → 在 story_string 之前，通过 `anchorBefore` 变量注入
- `extension_prompt_types.IN_PROMPT` → 在 story_string 之后，通过 `anchorAfter` 变量注入
- `extension_prompt_types.IN_CHAT` → 在聊天历史的指定深度注入

### 15.3 主要扩展

| 扩展 | 说明 | 注入方式 |
|------|------|---------|
| Summary | 对话摘要记忆 | IN_PROMPT，system prompt 区域 |
| Author's Note | 引导词 | BEFORE_PROMPT / IN_PROMPT / IN_CHAT |
| Vector Memory | 向量检索记忆 | IN_PROMPT |
| Smart Context | 智能上下文 | IN_PROMPT |
| Character Depth Prompt | 角色深度提示 | IN_CHAT |

### 15.4 事件系统

```
GENERATE_AFTER_DATA        → 请求数据已准备好，但尚未发送
CHAT_COMPLETION_PROMPT_READY → 消息数组已组装完成
CHAT_COMPLETION_SETTINGS_READY → 完整 generate_data 已准备好
WORLD_INFO_ACTIVATED       → 世界书条目已激活
MESSAGE_SENT               → 消息已发送
MESSAGE_RECEIVED           → 消息已接收
MESSAGE_DELETED            → 消息已删除
MESSAGE_EDITED             → 消息已编辑
IMPERSONATE_READY          → 冒充消息已准备好
GROUP_UPDATED              → 群聊已更新
CHARACTER_DRAFTED          → 角色卡已更新
```

---

## 16. 多模型适配层

### 16.1 前端调度

`script.js` 中的 `Generate()` 根据 `main_api` 值路由到不同处理路径：

```
main_api 取值:
  - 'openai'  → Chat Completion 路线（prepareOpenAIMessages + sendOpenAIRequest）
  - 'kobold'  → Text Completion 路线
  - 'textgenerationwebui' → Text Completion 路线
  - 'novel'   → Text Completion 路线
  - 'horde'   → Text Completion 路线
```

### 16.2 后端 Provider 转换

`src/endpoints/backends/chat-completics.js` 的路由分发：

```javascript
switch (request.body.chat_completion_source) {
    case CHAT_COMPLETION_SOURCES.CLAUDE:
        return sendClaudeRequest(request, response);
        // 调用 convertClaudeMessages() 转换格式

    case CHAT_COMPLETION_SOURCES.MAKERSUITE:
    case CHAT_COMPLETION_SOURCES.VERTEXAI:
        return sendMakerSuiteRequest(request, response);
        // 调用 convertGooglePrompt() 转换格式

    case CHAT_COMPLETION_SOURCES.COHERE:
        return sendCohereRequest(request, response);
        // 调用 convertCohereMessages() 转换格式

    case CHAT_COMPLETION_SOURCES.MISTRALAI:
        return sendMistralAIRequest(request, response);

    case CHAT_COMPLETION_SOURCES.DEEPSEEK:
        return sendDeepSeekRequest(request, response);

    // ... 其他 provider ...

    default:
        // OpenAI 兼容路径：直接透传 messages
}
```

### 16.3 Provider 转换示例：Claude

`convertClaudeMessages()` 的核心转换：

```
① 提取 system prompt
   - 将开头的 system 消息提取为 systemPrompt 数组
   - 从 messages 数组中移除

② 消息角色映射
   - system → user（并添加名称前缀）
   - tool → user（内容包装为 tool_result 格式）
   - assistant → 添加 tool_use 格式的 content

③ 内容格式转换
   - 纯文本 → [{ type: 'text', text: '内容' }]
   - image_url → [{ type: 'image', source: { type: 'base64', ... } }]

④ 消息合并
   - 连续相同 role 的消息合并为一条
   - 确保严格交替 user/assistant

⑤ 预填充
   - 如配置 assistant_prefill，在末尾追加 assistant 消息
```

---

## 17. 关键数据结构总结

### 17.1 Generate 传入参数

```typescript
interface GenerateData {
    // 角色信息
    name2: string;                    // 角色名称
    charDescription: string;          // 角色描述
    charPersonality: string;          // 角色性格
    scenario: string;                 // 场景设定
    messageExamples: MessageExample[]; // 示例对话

    // 世界书
    worldInfoBefore: string;          // 世界书 before
    worldInfoAfter: string;           // 世界书 after

    // 聊天历史
    messages: ChatMessage[];

    // 覆盖
    systemPromptOverride: string | null;     // 角色卡覆盖系统提示
    jailbreakPromptOverride: string | null;  // 角色卡覆盖后历史指令

    // 扩展
    extensionPrompts: ExtensionPrompt[];
    quietPrompt: string;
    bias: string;

    // 控制
    type: 'normal' | 'continue' | 'impersonate';
    cyclePrompt: string | null;
}
```

### 17.2 最终 messages 数组元素

```typescript
interface ChatMessage {
    role: 'system' | 'user' | 'assistant' | 'tool';
    content: string | ContentPart[];
    name?: string;
    tool_calls?: ToolCall[];
    tool_call_id?: string;
}
```

### 17.3 Token 统计结构

```typescript
interface TokenCounts {
    [identifier: string]: {
        tokens: number;
        count: number;
    };
    // 每个 prompt 片段的 token 消耗
    // 如: { main: { tokens: 500, count: 1 }, chatHistory: { tokens: 2000, count: 10 } }
}
```

### 17.4 发送给后端的 generate_data

```typescript
interface GenerateRequestBody {
    messages: ChatMessage[];                      // 组装好的消息数组
    model: string;                                // 模型名称
    temperature: number;
    max_tokens: number;
    stream: boolean;
    chat_completion_source: string;               // 目标 provider

    // 可选参数
    presence_penalty?: number;
    frequency_penalty?: number;
    top_p?: number;
    top_k?: number;
    stop?: string[];
    logit_bias?: object;
    seed?: number;

    // Provider 特定
    assistant_prefill?: string;
    custom_prompt_post_processing?: string;       // merge/semi/strict/single
    json_schema?: object;

    // 工具调用
    tools?: ToolDefinition[];
    tool_choice?: 'auto' | 'none' | 'required';
}
```

---

## 附录：与 Izumi Studio 的映射关系

| SillyTavern 概念 | Izumi Studio 对应 | 差异说明 |
|-----------------|-------------------|---------|
| `Generate()` | LLMRouter + MessageBuilder | 拆分为路由和组装两层，职责分离 |
| `prepareOpenAIMessages()` | MessageBuilder.assemble() | 核心逻辑保持一致 |
| `worldInfoBefore/After` | WorldBookEngine.getActivatedEntries() | 接口定义对齐 |
| `renderStoryString()` | ContextTemplate.render() | 改用 Jinja2 或保留 Handlebars |
| `formatInstructModeChat()` | InstructTemplate.format() | 逻辑对齐 |
| `PromptManager` | PromptManager（同名） | 逻辑完全对齐 |
| `ChatCompletion` | ContextBuilder | Token 预算管理逻辑对齐 |
| `power_user.context` | 上下文模板预设 | 结构对齐 |
| `power_user.instruct` | 指令模板预设 | 结构对齐 |
| `main_api` 路由 | LLMRouter 内部路由 | 前端不再直接判断 |

---

> 本文档基于 SillyTavern Release (2025-11-19) 源码分析，覆盖了其核心功能的完整数据流和关键接口。
> 游玩模式的核心消息组装逻辑应与本文档保持一致，其余模块可在此基础上优化和扩展。
