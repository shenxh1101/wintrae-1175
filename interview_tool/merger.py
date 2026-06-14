"""文本合并模块 - 合并零散的文字稿片段"""

import os
import re
from pathlib import Path
from collections import defaultdict


def extract_segment_number(filename):
    """
    从文件名中提取片段序号
    
    支持多种格式：
    - 片段1, 片段2, ...
    - part1, part2, ...
    - 01_, 02_, ...
    - _1, _2, ...
    """
    stem = Path(filename).stem
    patterns = [
        r'(?:片段|part|segment|段)[_\-\s]*(\d+)',
        r'[_\-\s](\d+)[_\-\s]',
        r'^(\d+)[_\-\s]',
        r'[_\-\s](\d+)$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, stem, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    numbers = re.findall(r'\d+', stem)
    if len(numbers) == 1:
        return int(numbers[0])
    
    return None

def sort_segments(filepaths):
    """
    对片段文件进行排序
    
    优先按片段序号排序，其次按文件名排序
    """
    def sort_key(filepath):
        filename = os.path.basename(filepath)
        seg_num = extract_segment_number(filename)
        if seg_num is not None:
            return (0, seg_num, filename)
        return (1, 0, filename)
    
    return sorted(filepaths, key=sort_key)

def read_text_file(filepath):
    """
    读取文本文件内容
    
    自动检测编码，支持 .txt, .md 等纯文本格式
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def merge_text_files(filepaths, output_path=None, add_separator=True, add_filename=True):
    """
    合并多个文本文件
    
    Args:
        filepaths: 文件路径列表
        output_path: 输出文件路径（可选）
        add_separator: 是否在片段间添加分隔线
        add_filename: 是否在每个片段前添加文件名标题
    
    Returns:
        合并后的文本内容
    """
    sorted_files = sort_segments(filepaths)
    merged_parts = []
    
    for i, filepath in enumerate(sorted_files):
        filename = os.path.basename(filepath)
        content = read_text_file(filepath)
        
        if add_filename:
            title = f"=== {filename} ==="
            merged_parts.append(title)
        
        merged_parts.append(content)
        
        if add_separator and i < len(sorted_files) - 1:
            merged_parts.append("\n" + "-" * 60 + "\n")
    
    merged_text = "\n\n".join(merged_parts) if add_separator else "\n".join(merged_parts)
    
    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(merged_text)
    
    return merged_text

def extract_summary(text, max_length=200):
    """
    从文本中提取摘要
    
    简单策略：取前几段的关键句子
    """
    text = text.strip()
    if not text:
        return ""
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return text[:max_length]
    
    summary_lines = []
    current_length = 0
    
    for line in lines:
        if current_length + len(line) <= max_length:
            summary_lines.append(line)
            current_length += len(line)
        else:
            remaining = max_length - current_length
            if remaining > 20:
                summary_lines.append(line[:remaining] + "...")
            break
        
        if len(summary_lines) >= 3:
            break
    
    return " ".join(summary_lines) if summary_lines else text[:max_length]

def group_files_by_interviewee(filepaths):
    """
    按受访者对文件分组
    
    基于文件名中的受访者信息
    """
    from .utils import extract_interviewee_from_filename
    
    groups = defaultdict(list)
    
    for filepath in filepaths:
        filename = os.path.basename(filepath)
        interviewee = extract_interviewee_from_filename(filename) or "未知受访者"
        groups[interviewee].append(filepath)
    
    return dict(groups)

def merge_by_group(filepaths, output_dir, group_by='interviewee', **kwargs):
    """
    按分组批量合并文件
    
    Args:
        filepaths: 文件路径列表
        output_dir: 输出目录
        group_by: 分组方式 'interviewee' 或 'date'
        **kwargs: 传递给 merge_text_files 的参数
    
    Returns:
        合并结果列表 [(group_name, output_path, file_count), ...]
    """
    if group_by == 'interviewee':
        groups = group_files_by_interviewee(filepaths)
    else:
        from .utils import parse_date_from_filename
        groups = defaultdict(list)
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            date = parse_date_from_filename(filename)
            date_key = date.strftime("%Y%m%d") if date else "未知日期"
            groups[date_key].append(filepath)
        groups = dict(groups)
    
    results = []
    
    for group_name, group_files in groups.items():
        if len(group_files) < 2:
            continue
        
        safe_name = group_name.replace('/', '_').replace('\\', '_')
        output_path = os.path.join(output_dir, f"{safe_name}_合并稿.txt")
        
        merge_text_files(group_files, output_path, **kwargs)
        results.append((group_name, output_path, len(group_files)))
    
    return results
