import asyncio
from pathlib import Path
from pydantic_ai import Agent
from queue import Queue
from dotenv import load_dotenv
from threading import Thread
from typing import Any
import voice.customized_voice_service as cvs
import re
import tools

load_dotenv()
prompt_file = Path(r"characters/$your_character/conversation_style_prompt.txt")
with open(prompt_file, "r", encoding="utf-8") as f:
    system_prompt = f.read()
agent = Agent(model="deepseek:deepseek-reasoner", name="", description="An agent that does something useful.",
              system_prompt=system_prompt,
              tools=[tools.read_file, tools.list_files, tools.rename_file])

def tts_service(text: str):
    # 测试文本列表
    text0: Queue[str] = Queue()
    for t in re.split(r'[。！？；……]', text):
        text0.put(t)
    streamer = cvs.TTSStreamer()
    # 运行tts主程序
    asyncio.run(streamer.generate_stream(text0))
    if streamer.cvs.json["auto_delete"]:
        streamer.cvs.delete_audio()

def main():
    history: list[Any] = []
    #Thread(target=tts_service, args=(resp.output,)).start()
    while True:
        user_input = input("Input:")
        resp: Agent[str] = agent.run_sync(user_input, message_history = history)
        history = list(resp.all_messages())
        print(resp.output)
        tts_service(resp.output)

if __name__ == "__main__":
    main()
