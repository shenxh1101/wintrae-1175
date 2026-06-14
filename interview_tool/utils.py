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
    '新建文本', '重复文件', '访谈录音', '访谈文字', '未知受访者',
    '受访者', '未知日期', '未知受访', '文档', '建文本',
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
        r'([\u4e00-\u9fa5]{2,3})[_\-\s]*(?:采访|访谈|专访|录音)',
        r'([\u4e00-\u9fa5]{2,3})(?:采访|访谈|专访|录音)',
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


def normalize_basename_for_pairing(filename):
    """
    规范化文件名用于配对匹配
    
    剔除日期、录音、文字稿、专访、访谈、片段等后缀，
    提取核心标识用于同一场采访的音频和文字稿配对
    
    示例:
        '20240115_张三访谈录音.wav' -> '张三'
        '20240115_张三访谈文字稿.txt' -> '张三'
        '李四_片段1.wav' -> '李四'
        '李四_片段2.txt' -> '李四'
    """
    import re
    stem = Path(filename).stem
    
    # 移除日期
    stem = re.sub(r'\d{4}[-_]?\d{2}[-_]?\d{2}', '', stem)
    
    # 移除常见的采访相关后缀和前缀
    suffixes_to_remove = [
        r'_采访_\d+$', r'_访谈_\d+$', r'_专访_\d+$',
        r'访谈录音.*$', r'访谈文字.*$', r'访谈记录.*$',
        r'专访录音.*$', r'专访文字.*$',
        r'采访录音.*$', r'采访文字.*$', r'采访记录.*$',
        r'录音$', r'文字稿$', r'记录$', r'访谈$', r'专访$', r'采访$',
        r'片段\d+', r'part\d+', r'segment\d+', r'第[一二三四五六七八九十\d]+段',
        r'副本\d*', r'_copy\d*',
        r'^\d+[_\-]', r'[_\-]\d+$',
    ]
    
    for pattern in suffixes_to_remove:
        stem = re.sub(pattern, '', stem, flags=re.IGNORECASE)
    
    # 清理分隔符
    stem = re.sub(r'[_\-\s]+', '_', stem)
    stem = stem.strip('_')
    
    # 如果还有日期或受访者信息，优先提取受访者
    interviewee = extract_interviewee_from_filename(filename)
    if interviewee:
        return interviewee
    
    # 尝试提取中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fa5]{2,}', stem)
    if chinese_chars:
        return ''.join(chinese_chars)
    
    return stem


def extract_topic_from_filename(filename):
    """
    从文件名中提取采访主题
    
    查找"XX主题"、"XX专题"或其他主题标识
    """
    import re
    stem = Path(filename).stem
    
    # 先移除日期和标准命名格式中的编号
    stem_clean = re.sub(r'\d{4}[-_]?\d{2}[-_]?\d{2}', '', stem)
    # 移除标准命名格式: {日期}_{受访者}_采访_{编号}
    stem_clean = re.sub(r'_采访_\d+$', '', stem_clean)
    stem_clean = re.sub(r'_访谈_\d+$', '', stem_clean)
    stem_clean = re.sub(r'_专访_\d+$', '', stem_clean)
    # 移除"未知日期"标识
    stem_clean = re.sub(r'^未知日期[_-]?', '', stem_clean)
    
    # 尝试匹配主题相关模式
    patterns = [
        r'[_\-\s]*([\u4e00-\u9fa5]{2,10}?)(?:主题|专题|项目|话题)[_\-\s]*',
        r'关于[_\-\s]*([\u4e00-\u9fa5]{2,20})[_\-\s]*',
        r'「([^」]+)」',
        r'【([^】]+)】',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, stem_clean)
        if match:
            topic = match.group(1).strip()
            if topic and topic not in EXCLUDED_INTERVIEWEE_WORDS:
                return topic
    
    # 如果有受访者信息，尝试提取受访者之外的内容
    interviewee = extract_interviewee_from_filename(filename)
    if interviewee:
        without_interviewee = stem_clean.replace(interviewee, '')
        without_interviewee = re.sub(r'[_\-\s]+', '', without_interviewee)
        
        # 移除其他常见词
        for word in EXCLUDED_INTERVIEWEE_WORDS:
            without_interviewee = without_interviewee.replace(word, '')
        
        if len(without_interviewee) >= 2:
            return without_interviewee
    
    return "采访"


def get_pairing_key(file_info):
    """
    生成文件配对的唯一键
    
    基于日期、受访者、主题的组合，用于判断是否属于同一场采访
    """
    date_str = file_info.date.strftime('%Y%m%d') if file_info.date else 'unknown_date'
    interviewee = file_info.interviewee or 'unknown_interviewee'
    topic = file_info.topic if hasattr(file_info, 'topic') else extract_topic_from_filename(file_info.filename)
    
    return f"{date_str}_{interviewee}_{topic}"

