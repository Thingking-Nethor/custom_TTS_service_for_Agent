# customized_voice_service.py 运行原理

## 整体架构流程图

```mermaid
flowchart TB
    subgraph 初始化["🔧 初始化阶段"]
        A[创建 TTSStreamer 实例] --> B[创建 CVS 实例]
        B --> C[加载 JSON 配置文件<br/>voice/config/xxx.json]
        C --> D{加载成功?}
        D -->|是| E[读取配置项:<br/>text_sign / curl / params /<br/>filter_brackets / save_audio 等]
        D -->|否| F[❌ 记录错误日志]
        E --> G[初始化 mixer 标志位<br/>is_playing = False]
    end

    subgraph 文本输入["📝 文本输入阶段"]
        H[_push_text 推送文本] --> I[_filter_text 文本过滤]
        I --> J{filter_brackets?}
        J -->|true| K["移除 【】和[] 括号内容"]
        K --> L{filter_special_chars?}
        J -->|false| L
        L -->|true| M[移除特殊字符/emoji<br/>保留中文及常用标点]
        L -->|false| N[文本过滤完成]
        M --> N
        N --> O[文本入队 sentence_queue]
    end

    subgraph 生成播放["🎤 流式生成与播放 (generate_stream)"]
        direction TB
        
        subgraph 生产者["生产者 Producer"]
            P[等待 update_texts 完成] --> Q{sentence_queue 非空?}
            Q -->|是| R[取出文本]
            Q -->|否| S[等待 0.5s 再检查]
            S --> Q
            R --> T[_change_tone 选择语气索引]
            T --> U[调用 CVS.send_requests]
        end

        subgraph 请求处理["🌐 HTTP 请求处理"]
            U --> V{params 是否为 None?}
            V -->|params = None| W[replace_in_string<br/>将文本替换到 URL 中]
            V -->|params 存在| X[replace_in_dict<br/>将文本替换到参数字典中]
            W --> Y[发送 GET 请求<br/>超时: total=30s, sock_read=20s]
            X --> Z[发送 POST 请求<br/>JSON body, 超时同上]
            Y --> AA[_handle_response]
            Z --> AA
        end

        subgraph 响应处理["📦 响应处理"]
            AA --> AB{status == 200?}
            AB -->|否| AC[❌ 记录错误并返回 None]
            AB -->|是| AD[读取响应字节流]
            AD --> AE{save_audio?}
            AE -->|true| AF[保存 WAV 文件至<br/>voice/output/outputN.wav]
            AE -->|false| AG[返回音频 bytes]
            AF --> AG
        end

        subgraph 播放器["🔊 音频播放"]
            AG --> AH[放入 mission_queue]
            AH --> AI{消费者 Consumer 循环}
            AI -->|收到数据| AJ[CVS.play_audio]
            AJ --> AK{mixer 已初始化?}
            AK -->|否| AL[pygame.mixer.init<br/>frequency/size/channels]
            AK -->|是| AM[停止当前播放中的音频]
            AL --> AM
            AM --> AN[pygame.mixer.Sound<br/>从 io.BytesIO 加载]
            AN --> AO[播放音频, is_playing=True]
            AO --> AP[轮询等待播放完成<br/>最长 300s 超时]
            AP --> AQ[is_playing=False, 播放结束]
            AI -->|收到 None<br/>结束信号| AR[消费者退出]
        end

        subgraph 后台任务["🔄 后台更新任务 update_texts"]
            AS[每 3 秒检查一次] --> AT{sentence_queue 非空?}
            AT -->|是| AS
            AT -->|否| AU{mission_queue 空<br/>且有缓存?}
            AU -->|是| AV[clear_audio_cache<br/>清除内存缓存]
            AU -->|否| AW[挂起 1s 等待输入<br/>is_processing=False]
        end
    end

    初始化 --> 文本输入
    文本输入 --> 生成播放
    生产者 & 后台任务 -->|asyncio.gather 并发运行| 完成[Done]
```

## 类关系图

```mermaid
classDiagram
    class CVS {
        -audio_available: bool
        -json: dict
        -ts: str
        -url: str
        -params: dict
        -_mixer_initialized: bool
        -_current_sound: Sound
        -is_playing: bool
        -_response: bytes
        +__init__(config_file)
        +_filter_text(text) str
        +replace_in_string(text) str
        +replace_in_dict(text) dict
        +send_requests(text, tone_index) bytes
        -_handle_response() bytes
        +play_audio(audio_data)
        +clear_audio_cache()
    }

    class TTSStreamer {
        -cvs: CVS
        -is_processing: bool
        -sentence_queue: Queue
        -mission_queue: asyncio.Queue
        -tone_index: int
        +__init__(config_file)
        +_push_text(text)
        +_change_tone(tone_index)
        +generate_stream()
    }

    TTSStreamer *-- CVS : 组合
```

## 数据流时序图

```mermaid
sequenceDiagram
    actor User
    participant Streamer as TTSStreamer
    participant CVS
    participant Server as TTS 服务器
    participant Pygame as pygame.mixer

    User->>Streamer: _push_text("你好世界")
    Streamer->>CVS: _filter_text("你好世界")
    CVS-->>Streamer: 过滤后文本
    Streamer->>Streamer: 文本入队 sentence_queue

    User->>Streamer: generate_stream()

    par 并发执行
        loop Producer
            Streamer->>Streamer: 从 sentence_queue 取文本
            Streamer->>CVS: send_requests(text, tone_index)
            CVS->>CVS: replace_in_url / replace_in_dict
            CVS->>Server: GET/POST 请求
            Server-->>CVS: 200 OK + 音频数据
            CVS->>CVS: _handle_response()
            opt save_audio = true
                CVS->>CVS: 保存到 voice/output/
            end
            CVS-->>Streamer: audio bytes
            Streamer->>Streamer: 放入 mission_queue
        end
    and
        loop Consumer
            Streamer->>Streamer: 从 mission_queue 取数据
            Streamer->>CVS: play_audio(bytes)
            CVS->>Pygame: init (首次)
            CVS->>Pygame: Sound(io.BytesIO)
            CVS->>Pygame: play()
            Pygame-->>CVS: 播放完成
        end
    and
        loop update_texts
            Streamer->>Streamer: 每 3s 检查队列状态
            opt 队列全空
                Streamer->>CVS: clear_audio_cache()
                Streamer->>Streamer: is_processing = False
            end
        end
    end
```

## 核心流程说明

| 阶段 | 说明 |
|------|------|
| **配置加载** | 从 `voice/config/xxx.json` 读取 TTS 服务 URL、参数、过滤规则等 |
| **文本过滤** | 根据配置移除括号内容 `【】[]`、emoji 及特殊字符，保留中文标点 |
| **文本替换** | 使用 `text_sign` 作为占位符，将实际文本替换到 URL(GET) 或参数字典(POST) 中 |
| **HTTP 请求** | 异步发送请求(30s 总超时)，支持 GET/POST 两种模式 |
| **响应处理** | 检查状态码，读取音频字节流，可选保存为 WAV 文件 |
| **音频播放** | 通过 pygame.mixer 从内存直接播放，无需落盘，支持停止当前播放 |
| **流式调度** | Producer-Consumer 模式 + 后台监控任务，三者通过 `asyncio.gather` 并发运行 |
