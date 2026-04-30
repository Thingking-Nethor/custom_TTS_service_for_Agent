import asyncio
from dotenv import load_dotenv
import json
from pydantic_ai import Agent
from queue import Queue
import re
from threading import Thread
import tools
from typing import Any
import voice.customized_voice_service as cvs

load_dotenv()
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
with open(f"characters//{config['character_name']}//conversation_style_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()
ref_audio_path_index = 0
prompt_text_index = 0
text0: Queue[str] = Queue()
streamer = cvs.TTSStreamer(config["voice_config_filename"])  #根据需要替换为你的配置文件名（json文件，不带扩展名）

def update_index(i: int) -> None:
    """
    请根据需要写入代表语气的参数i，来更新ref_audio_path_index和prompt_text_index的值
    0为默认语气，1为开心，2为生气，3为伤心，4为惊讶，5为厌恶，6为恐惧
    """
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

agent = Agent(model="deepseek:deepseek-v4-flash", name="Dandelion",
              description="An agent that does something useful.",
              system_prompt=system_prompt,
              tools=[update_index])


def run_tts_async():
    asyncio.run(streamer.generate_stream())

# 运行tts主程序
Thread(target=run_tts_async, args=(), daemon=True).start()


def main():
    history: Agent.Sequence[Agent.ModelMessage] = []
    global ref_audio_path_index, prompt_text_index
    while True:
        user_input = input("Input:")
        ref_audio_path_index, prompt_text_index = 0, 0
        resp: Agent[str] = agent.run_sync(user_input, message_history = history)
        history = list(resp.all_messages())
        print(f"{config['character_name']}: {resp.output}")
        # 测试文本列表
        for t in re.split(r'[。！？；……]', resp.output):
            streamer._push_text(t)

if __name__ == "__main__":
    main()
