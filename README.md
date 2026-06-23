# Izumi Studio

AI 角色卡聊天与创作工具。支持角色扮演对话、泉此方系统助手、世界观/角色卡创作模块，兼容 SillyTavern 角色卡与世界书导入。

**在线预览（仅前端 UI）**：https://lzxlzxlzxlzxlzxlzx.github.io/Izumi-studio/

> 在线预览无法使用聊天、创作等需后端的功能。完整体验请本地部署。

## 功能

| 模块 | 说明 |
|------|------|
| **游玩** | 角色卡画廊、多会话聊天、流式回复、图片上传理解、剧情记忆 |
| **对话** | 泉此方系统助手，可查询数据库、管理角色与会话 |
| **创作** | 三栏创作工作台：卡片目录 / SSE 流式对话 / 字段编辑器，支持世界书拆分 |
| **导入** | SillyTavern V3 角色卡（`.json` / `.png`）、世界书、预设 |
| **设置** | 模型偏好、API Key 配置（存本地，不入库） |

## 环境要求

- Python 3.10+
- Node.js 18+（推荐 20+）
- DeepSeek API Key（必需，用于聊天与创作）
- 百炼 DashScope API Key（可选，用于图片理解）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/lzxlzxlzxlzxlzxlzx/Izumi-studio.git
cd Izumi-studio
```

### 2. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt
cd ..

# 前端
cd frontend
npm install
cd ..
```

### 3. 配置 API Key

任选其一：

**方式 A（推荐）**：启动后在应用内 **设置 → API 配置** 填写，保存至 `data/local_config.json`。

**方式 B**：编辑项目根目录 `.env`：

```env
API_KEY = 你的DeepSeek密钥
API_URL = "https://api.deepseek.com/v1/chat/completions"
DASHSCOPE_API_KEY = 你的百炼密钥（可选）
```

### 4. 启动

**一键启动（Git Bash / Linux / macOS）**：

```bash
./start.sh
```

**手动启动**：

```bash
# 终端 1 — 后端
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004

# 终端 2 — 前端
cd frontend
npm run dev
```

**Windows 仅后端**：`backend\run.bat`

### 5. 访问

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 本机 |
| http://\<本机IP\>:5173 | 局域网（已绑定 `0.0.0.0`） |
| http://localhost:8004/api/health | 后端健康检查 |

## 项目结构

```
Izumi-studio/
├── .env                 # 端口与 API 占位配置（可提交，密钥留空）
├── backend/             # FastAPI 后端
│   └── app/
│       ├── routers/     # API 路由
│       └── services/    # 业务逻辑、LLM 调用
├── frontend/            # React + Vite + Ant Design 前端
│   └── src/
│       ├── pages/       # 页面
│       └── components/  # 组件
├── data/                # 运行时数据（角色卡、数据库、上传等，大部分不入库）
│   ├── izumi.db         # SQLite 主数据库
│   ├── local_config.json # 本地 API 配置（gitignore）
│   ├── cards/           # 角色卡 JSON 备份
│   ├── worldbooks/      # 世界书 JSON
│   └── uploads/         # 上传图片
├── scripts/
│   └── reset_public_data.py  # 重置为公开安全状态（清空私有卡）
└── start.sh / stop.sh   # 启停脚本
```

## 数据说明

- 角色卡运行时数据在 `data/izumi.db`，JSON 备份在 `data/cards/`
- 私有角色卡、上传文件、数据库**不提交**到 Git
- 首次克隆后画廊为空，通过 **导入** 或 **创作** 添加角色卡
- 重置公开数据：`python scripts/reset_public_data.py`

## 开发与构建

```bash
# 前端开发
cd frontend && npm run dev

# 前端生产构建
cd frontend && npm run build

# 前端预览构建产物
cd frontend && npm run preview
```

## GitHub Pages

推送到 `master` 分支后，GitHub Actions 自动构建并部署静态前端预览。

仓库需开启：**Settings → Pages → Source: GitHub Actions**

## 技术栈

- **后端**：FastAPI、SQLite、httpx（LLM 流式调用）
- **前端**：React 18、TypeScript、Vite、Ant Design、Zustand、Tailwind CSS
- **模型**：DeepSeek（主聊天）、百炼 Qwen（图像理解）

## License

私有项目，未经授权请勿二次分发。
