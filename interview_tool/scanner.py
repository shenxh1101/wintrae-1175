"""目录扫描器 - 扫描目录并收集采访相关文件"""

import os
from pathlib import Path
from collections import defaultdict

from .utils import (
    is_audio_file, is_text_file, is_subtitle_file, is_media_related,
    get_file_hash, get_file_size, is_empty_file,
    parse_date_from_filename, extract_interviewee_from_filename
)
from .audio import get_audio_duration

class FileInfo:
    """文件信息类"""
    def __init__(self, filepath):
        self.filepath = os.path.abspath(filepath)
        self.filename = os.path.basename(filepath)
        self.extension = Path(filepath).suffix.lower()
        self.size = get_file_size(filepath)
        self.is_empty = is_empty_file(filepath)
        self.file_hash = None
        self._hash_computed = False
        
        self.is_audio = is_audio_file(filepath)
        self.is_text = is_text_file(filepath)
        self.is_subtitle = is_subtitle_file(filepath)
        
        self.duration = None
        if self.is_audio:
            self.duration = get_audio_duration(filepath)
        
        self.date = parse_date_from_filename(self.filename)
        self.interviewee = extract_interviewee_from_filename(self.filename)
    
    @property
    def hash(self):
        """延迟计算文件哈希"""
        if not self._hash_computed:
            self.file_hash = get_file_hash(self.filepath)
            self._hash_computed = True
        return self.file_hash
    
    def to_dict(self):
        return {
            'filepath': self.filepath,
            'filename': self.filename,
            'extension': self.extension,
            'size': self.size,
            'is_empty': self.is_empty,
            'is_audio': self.is_audio,
            'is_text': self.is_text,
            'is_subtitle': self.is_subtitle,
            'duration': self.duration,
            'date': self.date.isoformat() if self.date else None,
            'interviewee': self.interviewee,
        }

class ScanResult:
    """扫描结果类"""
    def __init__(self):
        self.files = []
        self.audio_files = []
        self.text_files = []
        self.subtitle_files = []
        self.empty_files = []
        self.duplicates = {}
        self.directories = set()
    
    @property
    def total_files(self):
        return len(self.files)
    
    @property
    def total_audio_duration(self):
        durations = [f.duration for f in self.audio_files if f.duration]
        return sum(durations) if durations else 0
    
    @property
    def total_size(self):
        return sum(f.size for f in self.files)

def scan_directory(directory, recursive=True, compute_hash=True):
    """
    扫描目录，收集所有采访相关文件
    
    Args:
        directory: 要扫描的目录路径
        recursive: 是否递归扫描子目录
        compute_hash: 是否计算文件哈希（用于去重）
    
    Returns:
        ScanResult 对象
    """
    result = ScanResult()
    directory = os.path.abspath(directory)
    
    if not os.path.exists(directory):
        raise FileNotFoundError(f"目录不存在: {directory}")
    
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"不是目录: {directory}")
    
    hash_map = defaultdict(list)
    
    if recursive:
        for root, dirs, files in os.walk(directory):
            result.directories.add(root)
            for filename in files:
                filepath = os.path.join(root, filename)
                if is_media_related(filepath):
                    file_info = FileInfo(filepath)
                    result.files.append(file_info)
                    
                    if file_info.is_audio:
                        result.audio_files.append(file_info)
                    elif file_info.is_text:
                        result.text_files.append(file_info)
                    elif file_info.is_subtitle:
                        result.subtitle_files.append(file_info)
                    
                    if file_info.is_empty:
                        result.empty_files.append(file_info)
                    
                    if compute_hash and not file_info.is_empty:
                        h = file_info.hash
                        if h:
                            hash_map[h].append(file_info)
    else:
        result.directories.add(directory)
        for item in os.listdir(directory):
            filepath = os.path.join(directory, item)
            if os.path.isfile(filepath) and is_media_related(filepath):
                file_info = FileInfo(filepath)
                result.files.append(file_info)
                
                if file_info.is_audio:
                    result.audio_files.append(file_info)
                elif file_info.is_text:
                    result.text_files.append(file_info)
                elif file_info.is_subtitle:
                    result.subtitle_files.append(file_info)
                
                if file_info.is_empty:
                    result.empty_files.append(file_info)
                
                if compute_hash and not file_info.is_empty:
                    h = file_info.hash
                    if h:
                        hash_map[h].append(file_info)
    
    for h, file_list in hash_map.items():
        if len(file_list) > 1:
            result.duplicates[h] = file_list
    
    return result
