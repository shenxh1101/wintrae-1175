"""通用工具函数"""

import os
import hashlib
from pathlib import Path
from datetime import datetime

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.wma', '.aiff'}
TEXT_EXTENSIONS = {'.txt', '.md', '.docx', '.doc', '.rtf'}
SRT_EXTENSIONS = {'.srt', '.vtt'}

def is_audio_file(filepath):
    """判断是否为音频文件"""
    return Path(filepath).suffix.lower() in AUDIO_EXTENSIONS

def is_text_file(filepath):
    """判断是否为文字稿文件"""
    return Path(filepath).suffix.lower() in TEXT_EXTENSIONS

def is_subtitle_file(filepath):
    """判断是否为字幕文件"""
    return Path(filepath).suffix.lower() in SRT_EXTENSIONS

def is_media_related(filepath):
    """判断是否为采访相关文件（音频、文字稿、字幕）"""
    ext = Path(filepath).suffix.lower()
    return ext in AUDIO_EXTENSIONS or ext in TEXT_EXTENSIONS or ext in SRT_EXTENSIONS

def get_file_hash(filepath, chunk_size=8192):
    """计算文件 MD5 哈希值，用于去重检测"""
    md5 = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
        return md5.hexdigest()
    except (IOError, OSError):
        return None

def get_file_size(filepath):
    """获取文件大小（字节）"""
    try:
        return os.path.getsize(filepath)
    except (IOError, OSError):
        return 0

def is_empty_file(filepath):
    """检查文件是否为空"""
    return get_file_size(filepath) == 0

def format_duration(seconds):
    """将秒数格式化为易读的时长字符串"""
    if seconds is None:
        return "未知"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    else:
        return f"{secs}秒"

def format_file_size(size_bytes):
    """将字节数格式化为易读的文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f}MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f}GB"

def safe_filename(name):
    """生成安全的文件名，移除非法字符"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip()

def parse_date_from_filename(filename):
    """从文件名中尝试解析日期"""
    import re
    patterns = [
        r'(\d{4})[-_](\d{1,2})[-_](\d{1,2})',
        r'(\d{4})(\d{2})(\d{2})',
        r'(\d{1,2})[-_](\d{1,2})[-_](\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            groups = match.groups()
            try:
                if len(groups[0]) == 4:
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
            except ValueError:
                continue
    return None

EXCLUDED_INTERVIEWEE_WORDS = {
    '采访', '访谈', '专访', '录音', '记录', '文字稿', '片段',
    '副本', '重复', '新建', '文本文档', '开场', '结束', '总结',
    '合并稿', '旧', '新', '测试', '空文件', '空文字稿', '张三访谈',
    '新建文本', '重复文件', '访谈录音', '访谈文字',
}


def extract_interviewee_from_filename(filename):
    """从文件名中尝试提取受访者姓名"""
    import re
    stem = Path(filename).stem
    
    date_str = None
    date_match = re.search(r'\d{4}[-_]?\d{2}[-_]?\d{2}', stem)
    if date_match:
        date_str = date_match.group()
    
    patterns = [
        r'([\u4e00-\u9fa5]{2,4})[_\-\s]*(?:采访|访谈|专访|录音)',
        r'(?:采访|访谈|专访)[_\-\s]*([\u4e00-\u9fa5]{2,4})',
        r'^([\u4e00-\u9fa5]{2,4})[_\-\s]',
        r'[_\-\s]([\u4e00-\u9fa5]{2,4})$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, stem)
        if match:
            for group in match.groups():
                if (group and len(group) >= 2 and len(group) <= 4 
                    and '\u4e00' <= group[0] <= '\u9fa5'
                    and group not in EXCLUDED_INTERVIEWEE_WORDS):
                    return group
    
    chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', stem)
    for word in chinese_words:
        if word not in EXCLUDED_INTERVIEWEE_WORDS and not word.isdigit():
            return word
    
    return None
