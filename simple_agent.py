import asyncio
from dotenv import load_dotenv
import json
from pydantic_ai import Agent
from queue import Queue
import re
from threading import Thread
import time
import voice.customized_voice_service as cvs

load_dotenv()
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
with open(f"characters//{config['character_name']}//conversation_style_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()
ref_audio_path_index: int = 0
prompt_text_index: int = 0
tts_service_enabled: bool = config.get("tts_service", False)
text0: Queue[str] = Queue()
if tts_service_enabled:
    streamer = cvs.TTSStreamer(config["voice_config_filename"])  #根据需要替换为你的配置文件名（json文件，不带扩展名）

def update_index(i: int) -> None:
    """
    请根据需要写入代表语气的参数i，来更新ref_audio_path_index和prompt_text_index的值
    0为默认语气，1为开心，2为生气，3为伤心，4为惊讶，5为厌恶，6为恐惧
    """
    tone_map: dict[int, str] = {0: "默认", 1: "开心", 2: "生气", 3: "伤心", 4: "惊讶", 5: "厌恶", 6: "恐惧"}
    if i < 0:
        return
    if i > 6:
        i = 0
    elif (r:= len(streamer.cvs.json["ref_audio_path_list"])) < 7 or (p:= len(streamer.cvs.json["prompt_text_list"])) < 7:
        # 如果参考音频列表或参考文本列表的长度不足7，则重置索引为0，使用默认语气
        if min(r, p) <= i:
            i = 0
    global ref_audio_path_index, prompt_text_index
    ref_audio_path_index, prompt_text_index = i, i
    print("切换到语气：", tone_map.get(i))

agent = Agent(model="deepseek:deepseek-v4-flash", name="Dandelion",
              description="An agent that does something useful.",
              system_prompt=system_prompt,
              tools=[update_index])


def run_tts_async():
    asyncio.run(streamer.generate_stream())

# 运行tts主程序

if tts_service_enabled:
    Thread(target=run_tts_async, args=(), daemon=True).start()


def main():
    history: list = []
    global ref_audio_path_index, prompt_text_index
    while True:
        user_input = input("Input:")
        ref_audio_path_index, prompt_text_index = 0, 0
        accumulated = ""
        # 先打印角色名前缀，flush确保立即显示
        print(f"{config['character_name']}: ", end="", flush=True)
        # 使用流式同步调用，逐token获取LLM回复
        result = agent.run_stream_sync(user_input, message_history=history)
        for chunk in result.stream_text(delta=True):
            # 实时打印每个token块，形成打字机效果
            print(chunk, end="", flush=True)
            accumulated += chunk
            # 每遇到句末标点，立即将完整句子推入TTS队列
            while True:
                m = re.search(r'[。！？；……]', accumulated)
                if not m:
                    break
                idx = m.end()
                sentence = accumulated[:idx].strip()
                accumulated = accumulated[idx:]
                if sentence and tts_service_enabled:
                    streamer._push_text(sentence)
        print()  # 流式输出结束后换行
        # 从流式结果中提取完整对话历史
        history = list(result.all_messages())
        # 记录历史对话到文件
        timestamp: str = time.strftime("%Y-%m-%d", time.localtime())
        with open(f"log\\{timestamp}.txt", "a", encoding="utf-8") as f:
            f.write(f"User: {user_input}\n\n")
            f.write(f"{config['character_name']}: {''.join(result.all_text())}\n\n")
        # 推入最后剩余的文本（不含句末标点的尾部）
        if accumulated.strip() and tts_service_enabled:
            streamer._push_text(accumulated.strip())

if __name__ == "__main__":
    main()
