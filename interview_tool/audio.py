"""音频分析模块 - 获取音频文件时长等信息"""

import os
from pathlib import Path

def get_audio_duration(filepath):
    """
    获取音频文件时长（秒）
    
    优先使用 mutagen 库，如果不可用则回退到基础方法
    """
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(filepath)
        if audio is not None and hasattr(audio, 'info') and audio.info is not None:
            if hasattr(audio.info, 'length'):
                return audio.info.length
    except ImportError:
        pass
    except Exception:
        pass
    
    return _get_audio_duration_basic(filepath)

def _get_audio_duration_basic(filepath):
    """
    基础音频时长估算（不依赖第三方库）
    仅支持部分格式，精度有限
    """
    ext = Path(filepath).suffix.lower()
    try:
        if ext == '.wav':
            return _get_wav_duration(filepath)
        elif ext == '.mp3':
            return _get_mp3_duration_estimate(filepath)
    except Exception:
        pass
    return None

def _get_wav_duration(filepath):
    """获取 WAV 文件时长"""
    import struct
    with open(filepath, 'rb') as f:
        riff = f.read(12)
        if len(riff) < 12 or riff[:4] != b'RIFF' or riff[8:12] != b'WAVE':
            return None
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id = chunk_header[:4]
            chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
            if chunk_id == b'fmt ':
                fmt_data = f.read(chunk_size)
                if len(fmt_data) >= 16:
                    sample_rate = struct.unpack('<I', fmt_data[4:8])[0]
                    byte_rate = struct.unpack('<I', fmt_data[8:12])[0]
                    channels = struct.unpack('<H', fmt_data[2:4])[0]
                    bits_per_sample = struct.unpack('<H', fmt_data[14:16])[0]
                    file_size = os.path.getsize(filepath)
                    data_size = file_size - 44
                    if byte_rate > 0:
                        return data_size / byte_rate
                break
            else:
                f.seek(chunk_size, 1)
    return None

def _get_mp3_duration_estimate(filepath):
    """
    粗略估算 MP3 时长
    基于文件大小和平均比特率估算，不准确
    """
    file_size = os.path.getsize(filepath)
    avg_bitrate = 128000
    if file_size > 0:
        return (file_size * 8) / avg_bitrate
    return None

def get_audio_info(filepath):
    """获取音频文件完整信息"""
    info = {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'duration': get_audio_duration(filepath),
        'size': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
        'format': Path(filepath).suffix.lower().lstrip('.'),
    }
    return info
