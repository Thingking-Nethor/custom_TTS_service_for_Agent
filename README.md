# Customized_TTS_service_for_Agent

一个基于 LLM 的 AI 角色对话桌面应用，集成 GPT-SoVITS 语音合成，设计上也可以支持其他语音合成服务, 支持个性化角色设定与实时语音交互。

## 项目简介

My_Agent 是一个带有图形界面的 AI 伴侣对话系统。你可以自定义角色的人格、语言风格和声音，通过文字输入与角色实时对话，角色的回复会以文本 + 语音（TTS）双通道呈现。

## 功能特性

- **角色对话** — 基于 DeepSeek API 的流式对话，支持完整的自定义角色人设 prompt
- **语音合成 (TTS)** — 集成 GPT-SoVITS，支持多语气切换（默认/开心/生气/伤心/惊讶/厌恶/恐惧）
- **流式播放** — Producer-Consumer 模式，文本按句子切分后逐段生成语音并播放，低延迟
- **GUI 界面** — 基于 Tkinter 的暗色主题对话窗口，支持 Enter 快捷发送
- **工具调用** — Agent 可调用文件读写、外部程序启动等自定义工具
- **对话记录** — 自动按日期保存对话日志到 `logs/` 目录
- **角色配置** — 角色人设、语音参数、参考音频等全部通过 JSON 配置文件管理

## 项目结构

```
My_Agent/
├── main.py                          # 主入口：Agent 创建、TTS 启动、对话循环
├── config.json                      # 主配置文件
├── config.json.example              # 配置文件模板
├── pyproject.toml                   # 项目元信息与依赖
├── requirments.txt                  # pip 依赖列表
├── start.ps1                        # Windows 一键启动脚本
├── characters/                      # 角色资源目录
│   └── your_character_name/                      # 角色名作为目录名
│       ├── conversation_style_prompt.txt  # 角色人设系统提示词
├── voice/                           # 语音模块
│   ├── customized_voice_service.py  # TTS 核心服务（CVS + TTSStreamer）
│   ├── config/                      # TTS 配置文件
│   │   ├── your_character_name.json           # 自定义角色的 GPT-SoVITS 参数
│   │   └── config.json.example      # TTS 配置模板
│   └── output/                      # 音频保存目录（save_audio=true 时）
├── ui/                              # 界面模块
│   └── conversation_ui.py           # Tkinter 对话窗口
├── tools/                           # 工具模块
│   ├── tools.py                     # Agent 可调用的工具函数
│   ├── todo.py                      # 命令行待办事项管理器
│   └── go_api_v2.bat                # GPT-SoVITS API 启动脚本
└── logs/                            # 对话日志
    └── YYYY-MM-DD.txt               # 按日期保存的对话记录
```

## 环境要求

- Python >= 3.11
- uv
- Windows
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)（如需 TTS 功能，推荐使用该语音合成软件）
- DeepSeek API 访问权限

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirments.txt
```

### 2. 配置文件

首次运行会自动从 `config.json.example` 生成默认 `config.json`，按需修改：

```json
{
    "voice_config_filename": "your_character_name",   // TTS 配置文件名（不含扩展名）
    "character_name": "你的智能体名称",             // 角色名称
    "user_name": "你的名字",                // 用户名
    "tts": {
        "tts_service": true,                // 是否启用 TTS
        "auto_start_GPT-SoVITS_api": true,  // 是否自动启动 GPT-SoVITS
        "GPT-SoVITS_directory_path": "D:\\GPT-SoVITS\\..."  // GPT-SoVITS 根目录
    }
}
```

### 3. 配置 DeepSeek API

在 `.env` 文件中设置 API 密钥和模型：

```env
DEEPSEEK_API_KEY=your-api-key
CONFIG_MODIFICATION_TIMESTAMP=last-modified-timestamp-of-config.json
```

### 4. 启动 GPT-SoVITS（如需语音）

确保 GPT-SoVITS 已正确安装，选择外部程序拉起API服务或设置 `auto_start_GPT-SoVITS_api: true` 让程序自动拉起 API 服务。

### 5. 运行

```bash
# Windows 一键启动
.\start.ps1

# 或直接运行
uv run -p 3.11 main.py
```

## 使用说明

1. 启动后弹出暗色对话窗口
2. 在底部输入栏输入消息，按 **Enter** 发送
3. 角色回复以流式方式逐字显示，同时按句子切分进行 TTS 语音播放
4. 对话自动保存至 `logs/YYYY-MM-DD.txt`

### 语气切换

Agent 会根据对话上下文自动调用 `update_index(i)` 函数切换 TTS 语气：

| 索引 | 语气 |
|------|------|
| 0 | 默认 |
| 1 | 开心 |
| 2 | 生气 |
| 3 | 伤心 |
| 4 | 惊讶 |
| 5 | 厌恶 |
| 6 | 恐惧 |

你也可以根据自己的需要修改该函数的文档字符串

## 添加自定义角色

1. 在 `characters/` 下新建角色名目录
2. 创建以下文件：
   - `conversation_style_prompt.txt` — 角色人设 prompt
   - `<角色名>.json` — 角色元信息
3. 在 `voice/config/` 下创建对应的 TTS 配置文件（参考 `config.json.example`）
4. 修改 `config.json` 中的 `character_name` 和 `voice_config_filename`

## 架构概览

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Tkinter UI  │────▶│   main.py       │────▶│  DeepSeek API    │
│  (对话窗口)   │◀────│  (Agent 调度)    │◀────│  (LLM 推理)       │
└──────────────┘     └───────┬─────────┘     └──────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  TTSStreamer     │
                    │  ┌─────────────┐ │
                    │  │  Producer   │ │     ┌──────────────────┐
                    │  │  (生成音频)  │─┼────▶│  GPT-SoVITS API  │
                    │  └─────────────┘ │     └──────────────────┘
                    │  ┌─────────────┐ │
                    │  │  Consumer   │ │     ┌──────────────────┐
                    │  │  (播放音频)  │─┼────▶│  pygame.mixer    │
                    │  └─────────────┘ │     └──────────────────┘
                    └─────────────────┘
```

详细的 TTS 服务运行原理见 [voice/customized_voice_service_flow.md](voice/output/customized_voice_service_flow.md)。

## 依赖项

| 包名 | 用途 |
|------|------|
| `pydantic-ai` | LLM Agent 框架 |
| `aiohttp` | 异步 HTTP 请求（TTS API 调用） |
| `pygame` | 音频播放 |
| `python-dotenv` | 环境变量管理 |

## License

GPL 3.0
