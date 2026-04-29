import asyncio
from dotenv import load_dotenv
from pathlib import Path
from pydantic_ai import Agent
from queue import Queue
import re
from threading import Thread
import tools
from typing import Any
import voice.customized_voice_service as cvs

load_dotenv()
ref_audio_path_index = 0
prompt_text_index = 0
prompt_file = Path(r"characters/XXX/conversation_style_prompt.txt")
with open(prompt_file, "r", encoding="utf-8") as f:
    system_prompt = f.read()
text0: Queue[str] = Queue()
streamer = cvs.TTSStreamer()

def update_index(i: int) -> None:
    """
    请根据需要写入代表语气的参数i，来更新ref_audio_path_index和prompt_text_index的值
    0为默认语气，1为生气，2为开心，3为伤心，4为惊讶，5为厌恶，6为恐惧
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

agent = Agent(model="deepseek:deepseek-reasoner", name="XXX",
              description="An agent that does something useful.",
              system_prompt=system_prompt,
              tools=[update_index])


def run_tts_async():
    asyncio.run(streamer.generate_stream())

# 运行tts主程序
Thread(target=run_tts_async, args=(), daemon=True).start()


def main():
    history: list[Any] = []
    global ref_audio_path_index, prompt_text_index
    while True:
        user_input = input("Input:")
        ref_audio_path_index, prompt_text_index = 0, 0
        resp: Agent[str] = agent.run_sync(user_input, message_history = history)
        history = list(resp.all_messages())
        print("XXX：" + resp.output)
        # 测试文本列表
        for t in re.split(r'[。！？；……]', resp.output):
            streamer._push_text(t)

if __name__ == "__main__":
    main()
