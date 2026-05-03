#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiohttp
import asyncio
import logging
from pathlib import Path
import json
import os
import pygame
import pydub
from queue import Queue
import io
import re
import time

class CVS:
    '''自定义语音服务类'''
    def __init__(self, config_file: str = "config"):
        self.audio_available = True
        try:
            with open(f".\\voice\config\\{config_file}.json", "r", encoding="utf-8") as f:
                self.json: dict = json.load(f)
        except FileNotFoundError:
            logging.error("❌ 配置文件 " + config_file + ".json 未找到")
        except json.JSONDecodeError:
            logging.error("❌ 配置文件 " + config_file + ".json 格式错误")
        self.ts = self.json["text_sign"]
        self.url = self.json["curl"]
        self.params: dict = self.json["params"]
        self._mixer_initialized = False
        self._current_sound = None
        self.is_playing = False  # 添加播放状态标志
        print(f"✅ 已加载配置文件，目标字符串: {self.ts}")

    def _filter_text(self, text: str = None):
        """过滤文本"""
        # 过滤括号内容
        if self.json["filter_brackets"]:
            text = re.sub(r'【.*?】', '', text)
            text = re.sub(r'\[.*?\]', '', text)
        # 过滤特殊字符（不过滤中文）
        if self.json["filter_special_chars"]:
            # 移除表情符号（简化版）
            text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)
            # 移除一些特殊符号（保留中文和常用标点）
            # 使用原始字符串，注意 \w 在 Python 3 中包含中文
            text = re.sub(r'[^\w\s，。！？、；：""''（）【】,.!?;:()\-\+\*/=<>@#$%^&_|\\`~]', '', text)
        print(f"✅ 文本过滤完成：{text}")
        return text
    
    def replace_in_string(self, text: str = None):
        """查找并替换字符串中的目标字符串"""
        if self.ts in self.url:
            print(f"✅ 在URL中找到目标字符串 {self.ts}，正在替换文本...")
            return re.sub(self.ts, text, self.url)
        else:
            logging.error("输入URL不是字符串，无法替换文本。")
            return self.url
    
    def replace_in_dict(self, text: str = None):
        """查找并替换字符串中的目标字符串"""
        if self.ts in self.params.values():
            print(f"✅ 在参数中找到目标字符串 {self.ts}，正在替换文本...")
            return {k:v.replace(self.ts, text) if type(v) == str else v for k, v in self.params.items()}
        else:
            logging.error("param中不包含目标字符串，无法替换文本。")
            return self.params
    
    async def send_requests(self, text: str = None, tone_index: int = 0):
        """选择相应的参考音频和参考文本并，发送请求并处理响应"""
        if not text.strip():
            logging.warning("⚠️ 输入文本为空，跳过生成")
            return None
        
        # 根据索引选择参考音频和参考文本
        if self.json["variable_ref_audio_and_prompt_text"]:
            if self.json["ref_audio_path_list"]:
                self.params["ref_audio_path"] = self.json["ref_audio_path_list"][tone_index]
                print(f"✅ 选择参考音频: {self.params['ref_audio_path']}")
            else:
                pass
            if self.json["prompt_text_list"]:
                self.params["prompt_text"] = self.json["prompt_text_list"][tone_index]
                print(f"✅ 选择参考文本: {self.params['prompt_text']}")
            else:
                pass
        
        # 创建带超时的会话
        timeout = aiohttp.ClientTimeout(total=30, sock_read=20)
        
        try:
            # 判断请求类型
            if self.params is None:
                print(f"✅ 发送GET请求: {self.replace_in_string(text)}...")
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.replace_in_string(text)) as response:
                        return await self._handle_response(response)
            else:
                print(f"✅ 发送POST请求: {self.url}...")
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.url, 
                        json=self.replace_in_dict(text)
                    ) as response:
                        return await self._handle_response(response)
        
        except asyncio.TimeoutError:
            logging.error("❌ 请求超时")
            return None
        except aiohttp.ClientError as e:
            logging.error(f"❌ 网络请求失败: {e}")
            return None
        except Exception as e:
            logging.error(f"❌ 请求发送失败: {e}")
            return None
    
    async def _handle_response(self, response):
        """处理响应结果"""
        if response.status != 200:
            error_text = await response.text()
            logging.error(f"❌ 语音生成失败 {response.status}: {error_text}\n请检查配置文件中的URL和参数是否正确，并确保服务器正常运行。")
            return None
        
        print("✅ 语音生成成功！")
        
        # 读取响应内容
        content = await response.read()
        
        # 保存文件
        os.makedirs('voice/output', exist_ok=True)
        file_count = len(os.listdir('voice/output'))
        file_path = f'voice/output/output{file_count}.wav'
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        print(f"✅ 语音已保存至 {file_path}")
        return file_path  # 返回文件路径供调用者使用
    
    async def play_audio(self, file_path: str):
        '''播放生成的音频'''
        print(f"▶️ 播放: {file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"❌ 音频文件不存在: {file_path}")
            return
        
        try:
            # 读取文件为二进制数据
            with open(file_path, 'rb') as f:
                audio_data = f.read()  # 读取为bytes，而不是文件对象
            
            # 确保 mixer 只初始化一次
            if not self._mixer_initialized:
                try:
                    pygame.mixer.init(
                        frequency=self.json.get("output_frequency", 22050),
                        size=self.json.get("output_size", -16),
                        channels=2,
                        buffer=512
                    )
                    self._mixer_initialized = True
                    print("音频系统初始化完成")
                except pygame.error as e:
                    logging.warning(f"音频系统初始化失败：{e}")
                    self.audio_available = False
                    return
            
            if not self.audio_available:
                logging.warning("音频系统不可用，无法播放音频")
                return
            
            if not audio_data:
                logging.warning("音频数据为空")
                return
            
            try:
                # 通过 pydub 检测音频格式和参数
                audio = pydub.AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
                
                # 停止当前正在播放的音频
                if self._current_sound and self._current_sound.get_num_channels() > 0:
                    self._current_sound.stop()
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                
                # 短暂等待确保停止完成
                await asyncio.sleep(0.05)
                
                # 创建新的 Sound 对象（适合短音频，非阻塞）
                self._current_sound = pygame.mixer.Sound(io.BytesIO(audio_data))
                
                # 播放音频（非阻塞）
                self._current_sound.play()
                self.is_playing = True
                print("正在播放音频...")
                
                # 等待播放完成
                start_time = time.time()
                while pygame.mixer.get_busy():
                    await asyncio.sleep(0.1)
                    # 防止无限等待
                    if time.time() - start_time > 300:
                        logging.warning("音频播放超时，强制停止")
                        pygame.mixer.stop()
                        break
                
                # 播放完成
                self.is_playing = False
                print("音频播放结束。")
            
            except Exception as e:
                self.is_playing = False
                logging.error(f"❌ 音频播放失败：{e}")  # 修复了日志格式
                raise e
        
        except Exception as e:
            logging.error(f"❌ 读取音频文件失败：{e}")
        
    def delete_audio(self, file_path: str = None):
        '''删除生成的所选或所有音频文件'''
        output_dir = Path("voice/output")
        try:
            if file_path:
                Path(file_path).unlink()
            else:
                for file in output_dir.glob("*.wav"):
                    file.unlink()
            print("✅ 已删除生成的音频文件。")
        except Exception as e:
            logging.warning(f"❌ 删除音频文件时发生错误: {e}")


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TTSStreamer:
    def __init__(self, config_file: str):
        self.cvs = CVS(config_file)
        self.is_processing: bool = False
        self.sentence_queue: Queue[str] = Queue()
        self.mission_queue = asyncio.Queue()  # 使用 asyncio.Queue 管理任务
        self.tone_index: int = 0  # 用于选择语气的索引
    
    def _push_text(self, text: str):
        """向文本队列中添加文本"""
        self.sentence_queue.put(self.cvs._filter_text(text))  #调用文本过滤函数
        print(f"✅ 已添加文本到队列: {text}")
    
    def _change_tone(self, tone_index: int):
        """更改语气索引"""
        self.tone_index = tone_index
        print(f"✅ 已更改语气索引为: {self.tone_index}")
    
    async def generate_stream(self):
        """流式生成"""
        self.is_processing = True
        
        # 生产者：生成音频
        async def producer():
            #等待文本队列更新
            while not update_texts_task.done():
                await asyncio.sleep(0.5)
                while not self.sentence_queue.empty() if isinstance(self.sentence_queue, Queue) else self.sentence_queue:
                    text = self.sentence_queue.get() if isinstance(self.sentence_queue, Queue) else self.sentence_queue.pop(0)
                    i = 0  # 这里可以根据需要调整索引
                    print(f"🎤 生成第 {i+1} 段...")
                    file_path = await self.cvs.send_requests(text, tone_index = self.tone_index)
                    if file_path:
                        await self.mission_queue.put((i, file_path))  # 将索引和文件路径一起推入队列
                    i += 1
                    await asyncio.sleep(0.1)  # 控制生成速度
            await self.mission_queue.put(None)  # 完成信号
        
        # 消费者：播放音频
        async def consumer():
            while True:
                item = await self.mission_queue.get()
                if item is None:
                    break
                index, file_path = item  # 获取文件路径
                await self.cvs.play_audio(file_path)
        
        #更新文本队列
        async def update_texts():
            while True:
                await asyncio.sleep(3)  # 每三秒检查一次
                if not self.sentence_queue.empty() if isinstance(self.sentence_queue, Queue) else self.sentence_queue:
                    print("🔄 文本队列更新中...")
                else:
                    if self.cvs.json["auto_delete"] and self.mission_queue.empty() and os.path.exists("voice/output/output0.wav"):
                        self.cvs.delete_audio()  # 如果文本队列空了且任务队列也空了，删除音频文件
                    await asyncio.sleep(1)  # 挂起一秒等待可能的文本输入
                    self.is_processing = False
                    # break  # 文本队列空了，结束更新
        
        # 模拟外部调用更新文本队列
        #async def update_texts_imitate():
        #    """外部调用更新文本队列"""
        #    for text in re.split(r'[。！？；……]', "阳光透过代码的缝隙洒下来，暖洋洋的。你今天看起来精神不错，是刚调试完一段有趣的算法，还是单纯享受这片刻的宁静？"):
        #        self.sentence_queue.put(text)
        #        await asyncio.sleep(2)  # 模拟文本输入的间隔
        
        # 并发运行
        update_texts_task = asyncio.create_task(update_texts())
        #update_texts_imitate_task = asyncio.create_task(update_texts_imitate())
        await asyncio.gather(producer(), consumer(), update_texts_task)  # , update_texts_imitate_task
        #self.is_processing = False

if __name__ == "__main__":
    # 测试文本列表
    text0: str = "中午好，我的创造者。"
    streamer = TTSStreamer("Dandelion")  #根据需要替换为你的配置文件名（json文件，不带扩展名）
    # 运行主程序
    streamer._push_text(text0)
    for t in re.split(r'[。！？；……]', "阳光透过代码的缝隙洒下来，暖洋洋的。你今天看起来精神不错，是刚调试完一段有趣的算法，还是单纯享受这片刻的宁静？"):
        streamer._push_text(t)
    asyncio.run(streamer.generate_stream())
    os.system("pause")
