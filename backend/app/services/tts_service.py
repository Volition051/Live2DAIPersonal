# backend/app/services/tts_service.py
# =============================================
# 本文件提供文本转语音（TTS）与口型同步（Viseme）数据生成
# 纯文本模式，完全不使用SSML，兼容所有edge_tts版本
# 彻底解决XML标签被读出的问题
# =============================================

import edge_tts
import edge_tts.exceptions
import io
import re
import logging
import asyncio
from typing import List, Dict, Tuple, Any
# 新增：汉字转拼音依赖（执行 pip install pypinyin 安装）
from pypinyin import lazy_pinyin


# ===================================
# 全局 TTS 语音参数配置
# ===================================
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"   # 默认发音人
DEFAULT_RATE = "-6%"                     # 默认语速
DEFAULT_VOLUME = "+0%"                   # 默认音量
DEFAULT_PITCH = "-2Hz"                   # 默认音调
MAX_TEXT_LENGTH = 10000                    # 单次TTS最大文本长度


# ===================================
# 可用的发音人列表
# ===================================
AVAILABLE_VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural",  "name": "晓晓（女声·活泼）",  "gender": "female"},
    {"id": "zh-CN-YunxiNeural",     "name": "云希（男声·磁性）",  "gender": "male"},
    {"id": "zh-CN-YunjianNeural",   "name": "云健（男声·沉稳）",  "gender": "male"},
    {"id": "zh-CN-XiaoyiNeural",    "name": "晓伊（女声·温柔）",  "gender": "female"},
]


# ===================================
# OVR LipSync Viseme 映射表（已补全所有中文拼音）
# 完全保留你原有的命名规范，与OVR LipSync系统100%兼容
# 优先级：长韵母 > 短韵母 > 声母
# ===================================
PINYIN_TO_VISEME = {
    # 长韵母（优先匹配）
    'ai': 'aa', 'ao': 'aa', 'an': 'aa', 'ang': 'aa',
    'ei': 'aa', 'en': 'aa', 'eng': 'aa',
    'ui': 'ou', 'un': 'ou', 'ong': 'ou',
    'in': 'ih', 'ing': 'ih', 'ün': 'ih',
    'ia': 'aa', 'ian': 'aa', 'iang': 'aa', 'iao': 'aa',
    'ie': 'E', 'iu': 'ou', 'iong': 'ou',
    'ua': 'aa', 'uai': 'aa', 'uan': 'aa', 'uang': 'aa',
    'uo': 'aa', 'üe': 'E',
    # 单韵母
    'a': 'aa', 'o': 'aa', 'e': 'aa',
    'u': 'ou', 'v': 'ou', 'ü': 'ou',
    'i': 'ih',
    'er': 'E', 'ê': 'E',
    # 声母（韵母匹配失败时使用）
    'b': 'PP', 'p': 'PP', 'm': 'PP',
    'f': 'FF',
    'd': 'DD', 't': 'DD', 'n': 'DD', 'l': 'DD',
    'g': 'kk', 'k': 'kk', 'h': 'kk',
    'j': 'TH', 'q': 'TH', 'x': 'TH',
    'zh': 'CH', 'ch': 'CH', 'sh': 'CH', 'r': 'CH',
    'z': 'SS', 'c': 'SS', 's': 'SS',
    'ng': 'nn',
}

# 预排序：按拼音长度倒序，确保长韵母优先匹配
_SORTED_PINYIN_KEYS = sorted(PINYIN_TO_VISEME.keys(), key=len, reverse=True)


# ===================================
# 标点符号对应的停顿时间
# ===================================
PUNCTUATION_PAUSE = {
    '，': 300, '。': 500, '！': 400, '？': 400, '；': 300, '：': 200, '、': 200, '…': 600, '——': 500,
}

BASE_DURATION_PER_CHAR = 180


# ===================================
# 安全工具函数
# ===================================
def _clean_text(text: str) -> str:
    """清理文本中的特殊字符和控制字符"""
    return re.sub(r'[\x00-\x1F\x7F]', '', text)


def _validate_tts_params(voice: str, rate: str, volume: str, pitch: str) -> None:
    """验证TTS参数格式合法性"""
    valid_voice_ids = [v["id"] for v in AVAILABLE_VOICES]
    if voice not in valid_voice_ids:
        raise ValueError(f"无效发音人: {voice}")
    
    if not re.match(r'^[+-]\d+%$', rate):
        raise ValueError(f"无效语速格式: {rate}，必须为 ±X%")
    
    if not re.match(r'^[+-]\d+%$', volume):
        raise ValueError(f"无效音量格式: {volume}，必须为 ±X%")
    
    if not re.match(r'^[+-]\d+Hz$', pitch):
        raise ValueError(f"无效音调格式: {pitch}，必须为 ±XHz")


# ===================================
# 文本 → Viseme 序列生成（通用版）
# 实现逻辑：汉字 → 拼音 → 匹配最长拼音键 → 对应Viseme
# 完全兼容原有接口格式，返回值结构不变
# ===================================
def text_to_pinyin_visemes(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []

    visemes = [{"Lip": "sil", "Time": 100}]
    # 转换为不带声调的拼音列表（声调不影响口型）
    pinyin_list = lazy_pinyin(text)
    
    for char, pinyin in zip(text, pinyin_list):
        # 处理标点符号停顿
        if char in PUNCTUATION_PAUSE:
            visemes.append({"Lip": "sil", "Time": PUNCTUATION_PAUSE[char]})
            continue
        
        # 跳过非中文字符（数字、字母、符号等）
        if not re.match(r'[\u4e00-\u9fff]', char):
            continue
        
        # 核心：拼音转Viseme（优先匹配最长拼音键）
        viseme = 'E'  # 默认值
        for key in _SORTED_PINYIN_KEYS:
            if pinyin.endswith(key):
                viseme = PINYIN_TO_VISEME[key]
                break
        
        # 计算该Viseme的持续时间
        duration = _calculate_duration(char, viseme)
        visemes.append({"Lip": viseme, "Time": duration})
    
    # 结尾添加静默
    visemes.append({"Lip": "sil", "Time": 150})
    return visemes


def _calculate_duration(char: str, viseme: str) -> int:
    """根据Viseme类型计算口型持续时间（保留原有逻辑）"""
    duration = BASE_DURATION_PER_CHAR
    if viseme in ['sil']:
        duration = 100
    elif viseme in ['PP', 'FF', 'nn']:
        duration = int(duration * 0.8)
    elif viseme in ['TH', 'DD', 'CH', 'SS', 'ih']:
        duration = int(duration * 1.0)
    elif viseme in ['kk', 'E', 'oh']:
        duration = int(duration * 1.1)
    elif viseme in ['aa', 'ou']:
        duration = int(duration * 1.2)
    return max(80, duration)


# ===================================
# 纯音频生成（最终修复版）
# ===================================
async def generate_audio_stream(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    pitch: str = DEFAULT_PITCH
) -> bytes:
    if not text.strip():
        return b""
    
    # 打印完整待合成文本到控制台
    print(f"\n📢 [TTS请求] 完整文本: {text}")
    print(f"📢 [TTS参数] 发音人={voice}, 语速={rate}, 音量={volume}, 音调={pitch}\n")
    
    # 截断过长文本
    if len(text) > MAX_TEXT_LENGTH:
        logging.warning(f"TTS文本过长（{len(text)}字符），已自动截断为{MAX_TEXT_LENGTH}字符")
        text = text[:MAX_TEXT_LENGTH]
    
    try:
        # 验证参数
        _validate_tts_params(voice, rate, volume, pitch)
        
        # 清理文本
        clean_text = _clean_text(text)
        
        # 纯文本模式，兼容所有edge_tts版本
        communicate = edge_tts.Communicate(
            clean_text,
            voice,
            rate=rate,
            volume=volume,
            pitch=pitch
        )
        
        audio_buffer = io.BytesIO()
        try:
            # 正确的超时控制：包装整个流读取过程
            async def read_stream():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_buffer.write(chunk["data"])
            
            await asyncio.wait_for(read_stream(), timeout=30.0)
            
            result = audio_buffer.getvalue()
            if len(result) < 100:
                raise edge_tts.exceptions.NoAudioReceived("生成的音频为空")
            
            print(f" [TTS成功] 生成音频大小: {len(result)} 字节\n")
            return result
        finally:
            audio_buffer.close()
    
    except asyncio.TimeoutError:
        print(f"❌ [TTS失败] 生成超时（15秒）\n")
        raise RuntimeError("语音生成超时，请缩短文本长度后重试")
    except ValueError as e:
        print(f"❌ [TTS失败] 参数验证错误: {str(e)}\n")
        raise RuntimeError(f"TTS参数验证失败: {str(e)}") from e
    except edge_tts.exceptions.NoAudioReceived:
        print(f"❌ [TTS失败] 服务未返回音频数据\n")
        raise RuntimeError("TTS服务未返回音频数据，请检查网络连接")
    except Exception as e:
        print(f"❌ [TTS失败] 未知错误: {str(e)}\n")
        logging.error(f"TTS音频生成异常: {str(e)}", exc_info=True)
        raise RuntimeError(f"音频生成失败: {str(e)}") from e


# ===================================
#  必须保留的函数：带口型同步的音频生成
# ===================================
async def generate_audio_with_visemes(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    pitch: str = DEFAULT_PITCH
) -> Tuple[bytes, List[Dict[str, Any]]]:
    """生成音频字节流和对应的口型同步序列（admin.py和tourist.py都在使用）"""
    audio_bytes = await generate_audio_stream(text, voice, rate, volume, pitch)
    visemes = text_to_pinyin_visemes(text)
    return audio_bytes, visemes


# 本地测试代码
if __name__ == "__main__":
    # 测试口型生成
    test_text = "你好我是智能导游，请问有什么可以帮助您的？"
    viseme_result = text_to_pinyin_visemes(test_text)
    print("口型序列测试结果：")
    for item in viseme_result:
        print(f"{item['Lip']}: {item['Time']}ms")

# 在 tts_service.py 末尾添加（与 text_to_pinyin_visemes 并列）

def text_to_subtitle_data(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []

    subtitles = []
    current_time = 100  # 与 viseme 序列初始 silence 对齐
    pinyin_list = lazy_pinyin(text)

    for char, pinyin in zip(text, pinyin_list):
        # 处理标点符号（停顿，不显示为普通字符）
        if char in PUNCTUATION_PAUSE:
            start = current_time
            current_time += PUNCTUATION_PAUSE[char]
            subtitles.append({
                "char": char,
                "start": start,
                "end": current_time,
                "viseme": "sil"
            })
            continue

        # 跳过空白字符（空格、换行等）
        if not char.strip():
            continue

        # 计算 viseme 和持续时间
        viseme = 'E'           # 默认口型
        duration = BASE_DURATION_PER_CHAR

        if re.match(r'[\u4e00-\u9fff]', char):      # 中文字符
            for key in _SORTED_PINYIN_KEYS:
                if pinyin.endswith(key):
                    viseme = PINYIN_TO_VISEME[key]
                    break
            duration = _calculate_duration(char, viseme)
        else:                                        # 阿拉伯数字、英文字母等
            # 使用默认口型，时长略短
            viseme = 'E'
            duration = int(BASE_DURATION_PER_CHAR * 0.8)

        start = current_time
        current_time += duration
        subtitles.append({
            "char": char,
            "start": start,
            "end": current_time,
            "viseme": viseme
        })

    # 结尾静默
    subtitles.append({
        "char": "",
        "start": current_time,
        "end": current_time + 150,
        "viseme": "sil"
    })
    return subtitles