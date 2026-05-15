# customized_voice_service.py 流程图与时序图

---

## 一、流程图 (Flowchart)

```mermaid
flowchart TD
    A([程序入口开始]) --> B[创建 TTSStreamer 实例<br/>加载 JSON 配置文件<br/>初始化各队列和标志位]
    B --> C["_push_text(text)<br/>_filter_text() 过滤括号/特殊字符<br/>文本入 sentence_queue"]
    C --> D["generate_stream()<br/>创建 3 个异步协程并发运行"]

    D --> E["update_texts()<br/>每 3 秒轮询队列状态"]
    D --> F["producer()<br/>等待文本 + 请求 API"]
    D --> G["consumer()<br/>从 mission_queue 取音频并播放"]

    F --> H["send_requests()<br/>根据self.tone_index索引选择参考音频/文本<br/>构造 GET 或 POST 请求"]

    H --> I["_handle_response()<br/>检查 HTTP 状态码<br/>可选保存 WAV 文件<br/>返回音频 bytes"]

    I --> J["mission_queue.put()<br/>推入 (index, audio_data)"]

    J --> G

    G --> K["play_audio(data)<br/>按需初始化 pygame mixer<br/>停止旧音频<br/>Sound(io.BytesIO) 从内存播放<br/>轮询 get_busy() 等待结束"]

    K --> L{"sentence_queue<br/>还有文本?"}
    L -->|是| F
    L -->|否| M["producer 发送 None 信号"]

    M --> N["consumer 收到 None<br/>break 退出循环"]

    E --> O{"文本队列 + 任务队列<br/>均空?"}
    O -->|是| P["clear_audio_cache()<br/>is_processing = False"]
    O -->|否| E

    N --> Q["asyncio.gather 全部完成"]
    P --> Q
    Q --> R([流程结束])
```

---

## 二、时序图 (Sequence Diagram)

```mermaid
sequenceDiagram
    actor User
    participant push as _push_text
    participant gen as generate_stream
    participant prod as producer
    participant send as send_requests
    participant handle as _handle_response
    participant API as TTS_API
    participant mq as mission_queue
    participant cons as consumer
    participant play as play_audio
    participant pg as pygame

    User->>push: push_text(text)
    push->>push: _filter_text() 过滤
    push->>gen: sentence_queue.put(text)

    User->>gen: asyncio.run(generate_stream)

    par 并发执行
        gen->>gen: create_task(update_texts)
        gen->>gen: create_task(producer)
        gen->>gen: create_task(consumer)
    end

    Note over gen: update_texts 每 3 秒轮询队列状态

    prod->>prod: 等待 update_texts_task 结束
    prod->>push: sentence_queue.get()
    push-->>prod: sentences = text

    prod->>send: send_requests()

    send->>send: 根据 self.tone_index 选择参考音频/文本
    send->>send: replace_in_dict() 替换参数

    alt params 为 None
        send->>API: GET 请求 (URL 含文本)
    else params 不为 None
        send->>API: POST 请求 (JSON body 含文本)
    end

    API-->>send: HTTP Response (audio bytes)

    send->>handle: _handle_response(response)

    alt status == 200
        handle->>handle: read bytes
        opt save_audio == True
            handle->>handle: 保存 WAV 至 voice/output/
        end
        handle-->>send: return audio_data
    else status != 200
        handle->>handle: log error
        handle-->>send: return None
    end

    send-->>prod: audio_data

    prod->>mq: mission_queue.put((index, audio_data))

    mq->>cons: mission_queue.get()
    cons->>cons: 解包 (index, audio_data)

    cons->>play: play_audio(data)

    alt 首次播放
        play->>pg: pygame.mixer.init(freq, size, channels)
        pg-->>play: 初始化完成
    end

    play->>pg: stop 旧音频
    play->>play: await asyncio.sleep(0.05)
    play->>pg: Sound(io.BytesIO(audio_data))
    play->>pg: .play()

    loop 等待播放完成
        play->>pg: get_busy()?
        pg-->>play: True/False
        alt 超时 300s
            play->>pg: mixer.stop() 强制停止
        end
    end

    pg-->>play: 播放结束
    play-->>cons: 返回

    opt 还有下一段文本
        cons->>cons: 继续循环取下一段
    end

    prod->>mq: mission_queue.put(None)
    mq->>cons: 收到 None → break 退出

    Note over gen: producer 和 consumer 完成

    Note over gen: update_texts: 队列空 + 任务空<br/>→ clear_audio_cache()<br/>→ is_processing = False

    Note over gen: asyncio.gather 全部完成
```

---

## 三、核心流程说明

| 阶段 | 方法 | 说明 |
|------|------|------|
| **初始化** | `__init__` | 加载 JSON 配置 (URL/参数/参考音频等)，初始化 `sentence_queue`(文本队列)、`mission_queue`(asyncio音频任务队列) |
| **文本入队** | `_push_text` → `_filter_text` | 外部调用，过滤括号/特殊字符后放入 `sentence_queue` |
| **流式启动** | `generate_stream` | 创建 3 个协程并发运行：`update_texts`(监控)、`producer`(生产者)、`consumer`(消费者) |
| **生产者** | `producer` | 等待 `update_texts_task` 结束；从 `sentence_queue` 取文本 → `send_requests()` → 音频入 `mission_queue` |
| **请求API** | `send_requests` | 根据 `self.tone_index` 选择参考音频/文本，构造 GET 或 POST 请求发送给 TTS 服务 |
| **处理响应** | `_handle_response` | 校验 HTTP 200 → 读 bytes → 可选保存 WAV 文件 → 返回音频数据 |
| **消费者** | `consumer` | 从 `mission_queue` 取 `(index, audio_data)` → 调用 `play_audio()` |
| **播放** | `play_audio` | 按需初始化 pygame mixer → 停止旧音频 → `Sound(io.BytesIO)` 从内存播放 → 轮询 `get_busy()` 等待结束 |
| **监控** | `update_texts` | 每3秒检查队列状态；队列空且任务完成时清除缓存、设置 `is_processing=False` |
| **终止信号** | `mission_queue.put(None)` | producer 结束后发送 None，consumer 收到后 break 退出循环 |

---

## 四、关键数据结构

```mermaid
classDiagram
    class TTSStreamer {
        +bool audio_available
        +dict json
        +str ts
        +str url
        +dict params
        +bool is_processing
        +bool is_playing
        +Queue~str~ sentence_queue
        +Queue mission_queue
        +str sentences
        +int tone_index
        -bool _mixer_initialized
        -Sound _current_sound
        -bytes _response
        +_push_text(text)
        +_change_tone(index)
        +generate_stream()
        -send_requests()
        -_handle_response()
        -play_audio(data)
        -_filter_text(text)
        -replace_in_string(text)
        -replace_in_dict(text)
        +clear_audio_cache()
    }
```
