import asyncio
from ui.conversation_ui import ConversationWindow
from dotenv import load_dotenv
import json
import os
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
    else:
        r = len(streamer.cvs.json["ref_audio_path_list"])
        p = len(streamer.cvs.json["prompt_text_list"])
        if r < 7 or p < 7:
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

def check():
    os.path.exists("logs") or os.mkdir("logs")

def main():
    history: list = []
    global ref_audio_path_index, prompt_text_index

    conv_win = ConversationWindow(config["character_name"], on_send=None, user_name=config["user_name"])
    conv_win.add_agent_prefix()
    conv_win.add_agent_chunk(f"你好！我是{config['character_name']}。\n")

    def handle_input(user_input: str):
        nonlocal history
        global ref_audio_path_index, prompt_text_index
        ref_audio_path_index, prompt_text_index = 0, 0
        accumulated = ""
        conv_win.add_agent_prefix()
        result = agent.run_stream_sync(user_input, message_history=history)
        for chunk in result.stream_text(delta=True):
            conv_win.add_agent_chunk(chunk)
            accumulated += chunk
            while True:
                m = re.search(r'[。！？；……]', accumulated)
                if not m:
                    break
                idx = m.end()
                sentence = accumulated[:idx].strip()
                accumulated = accumulated[idx:]
                if sentence and tts_service_enabled:
                    streamer._push_text(sentence)
        history = list(result.all_messages())
        timestamp: str = time.strftime("%Y-%m-%d", time.localtime())
        os.makedirs("logs", exist_ok=True)
        with open(f"logs\\{timestamp}.txt", "a", encoding="utf-8") as f:
            f.write(f"User: {user_input}\n\n")
            f.write(f"{config['character_name']}: {''.join(result.all_text())}\n\n")
        if accumulated.strip() and tts_service_enabled:
            streamer._push_text(accumulated.strip())

    def on_send(user_input: str):
        Thread(target=handle_input, args=(user_input,), daemon=True).start()

    conv_win.on_send = on_send
    conv_win.run()

if __name__ == "__main__":
    check()
    main()
