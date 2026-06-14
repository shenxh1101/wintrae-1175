"""文本合并模块 - 合并零散的文字稿片段"""

import os
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from .utils import (
    extract_interviewee_from_filename,
    parse_date_from_filename,
    extract_topic_from_filename
)
from .state import StateManager
from .confirmation import ConfirmationManager


def extract_segment_number(filename):
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
    def sort_key(filepath):
        filename = os.path.basename(filepath)
        seg_num = extract_segment_number(filename)
        if seg_num is not None:
            return (0, seg_num, filename)
        return (1, 0, filename)

    return sorted(filepaths, key=sort_key)


def read_text_file(filepath):
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def extract_interview_brief(text, source_files=None, interviewee=None, date=None, topic=None, max_length=500):
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    meta_interviewee = interviewee
    meta_date = date
    meta_topic = topic or "采访"

    if not meta_interviewee:
        for line in lines[:10]:
            match = re.search(r'受访者[：:]\s*([\u4e00-\u9fa5]{2,4})', line)
            if match:
                meta_interviewee = match.group(1)
                break

    if not meta_date:
        for line in lines[:10]:
            match = re.search(r'(?:采访时间|时间)[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)', line)
            if match:
                meta_date = match.group(1)
                break

    questions = []
    key_points = []
    quotes = []

    q_pattern = re.compile(r'^[问Q][：:]\s*(.+)$')
    a_pattern = re.compile(r'^[答A][：:]\s*(.+)$')

    for line in lines:
        q_match = q_pattern.match(line)
        if q_match:
            q_text = q_match.group(1).strip()
            if q_text and len(q_text) < 100:
                questions.append(q_text)
            continue

        a_match = a_pattern.match(line)
        if a_match:
            a_text = a_match.group(1).strip()
            if a_text and 20 < len(a_text) < 150:
                if '我认为' in a_text or '我觉得' in a_text or '重要的是' in a_text:
                    key_points.append(a_text)
                if '。' in a_text and len(a_text) > 30:
                    quotes.append(a_text[:80] + '...' if len(a_text) > 80 else a_text)

    brief_lines = []
    brief_lines.append("╔" + "═" * 58 + "╗")
    brief_lines.append("║" + " " * 15 + "采 访 提 要" + " " * 31 + "║")
    brief_lines.append("╠" + "═" * 58 + "╣")

    brief_lines.append(f"║ 受访者: {meta_interviewee or '待确认':<49}║")
    date_str = meta_date.strftime('%Y年%m月%d日') if isinstance(meta_date, datetime) else (meta_date or '待确认')
    brief_lines.append(f"║ 日  期: {date_str:<49}║")
    brief_lines.append(f"║ 主  题: {meta_topic:<49}║")

    if source_files:
        segment_count = len(source_files)
        total_chars = len(text)
        brief_lines.append(f"║ 片段数: {segment_count} 个 | 总字数: {total_chars} 字{'':<23}║")

    brief_lines.append("╠" + "═" * 58 + "╣")

    if questions:
        brief_lines.append("║ 【主要话题】" + " " * 45 + "║")
        for i, q in enumerate(questions[:5], 1):
            q_display = q[:48] + "..." if len(q) > 48 else q
            brief_lines.append(f"║   {i}. {q_display:<53}║")

    if key_points:
        brief_lines.append("║ " + " " * 58 + "║")
        brief_lines.append("║ 【核心观点】" + " " * 45 + "║")
        for i, point in enumerate(key_points[:3], 1):
            point_display = point[:48] + "..." if len(point) > 48 else point
            brief_lines.append(f"║   {i}. {point_display:<53}║")

    if quotes:
        brief_lines.append("║ " + " " * 58 + "║")
        brief_lines.append("║ 【关键引语】" + " " * 45 + "║")
        for i, quote in enumerate(quotes[:2], 1):
            quote_display = quote[:52] + ("..." if len(quote) > 52 else "")
            brief_lines.append(f"║   \"{quote_display}\"" + " " * (55 - len(quote_display)) + "║")

    brief_lines.append("╚" + "═" * 58 + "╝")
    brief_lines.append("")

    return "\n".join(brief_lines)


def extract_summary(text, max_length=200):
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
    groups = defaultdict(list)

    for filepath in filepaths:
        filename = os.path.basename(filepath)
        interviewee = extract_interviewee_from_filename(filename) or "未知受访者"
        groups[interviewee].append(filepath)

    return dict(groups)


def group_files_by_topic(filepaths):
    groups = defaultdict(list)

    for filepath in filepaths:
        filename = os.path.basename(filepath)
        topic = extract_topic_from_filename(filename) or "未分类主题"
        groups[topic].append(filepath)

    return dict(groups)


def merge_text_files(filepaths, output_path=None, add_separator=True, add_filename=True,
                    add_brief=False, interviewee=None, date=None, topic=None):
    sorted_files = sort_segments(filepaths)
    merged_parts = []

    if add_brief:
        all_content = "\n".join(read_text_file(f) for f in sorted_files)
        brief = extract_interview_brief(
            all_content,
            source_files=sorted_files,
            interviewee=interviewee,
            date=date,
            topic=topic
        )
        merged_parts.append(brief)
        merged_parts.append("")

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


def _build_groups(filepaths, group_by):
    if group_by == 'interviewee':
        return group_files_by_interviewee(filepaths)
    elif group_by == 'topic':
        return group_files_by_topic(filepaths)
    else:
        groups = defaultdict(list)
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            date = parse_date_from_filename(filename)
            date_key = date.strftime("%Y%m%d") if date else "未知日期"
            groups[date_key].append(filepath)
        return dict(groups)


def _group_has_confirmed_interviewee(group_name, group_files, confirmation_manager):
    if confirmation_manager is None:
        return True

    for filepath in group_files:
        filename = os.path.basename(filepath)
        confirmed_info = confirmation_manager.get_confirmed_info(filename)
        if confirmed_info and confirmed_info.get('interviewee'):
            return True

    detected = extract_interviewee_from_filename(os.path.basename(group_files[0]))
    if detected and detected != '未知受访者':
        return True

    return False


def preview_merge(filepaths, output_dir, group_by='interviewee', state_manager=None):
    groups = _build_groups(filepaths, group_by)

    confirmation_manager = None
    if state_manager and hasattr(state_manager, 'directory'):
        confirmation_manager = ConfirmationManager(state_manager.directory)

    preview_results = []

    for group_name, group_files in groups.items():
        sample_file = group_files[0]
        sample_name = os.path.basename(sample_file)
        interviewee = extract_interviewee_from_filename(sample_name)
        date = parse_date_from_filename(sample_name)
        topic = extract_topic_from_filename(sample_name)

        safe_name = group_name.replace('/', '_').replace('\\', '_')
        output_path = os.path.join(output_dir, f"{safe_name}_合并稿.txt")

        if confirmation_manager and not _group_has_confirmed_interviewee(group_name, group_files, confirmation_manager):
            preview_results.append({
                'group_name': group_name,
                'files': group_files,
                'output_path': output_path,
                'file_count': len(group_files),
                'interviewee': interviewee,
                'date': date,
                'topic': topic,
                'status': 'pending_confirmation',
            })
        else:
            preview_results.append({
                'group_name': group_name,
                'files': group_files,
                'output_path': output_path,
                'file_count': len(group_files),
                'interviewee': interviewee,
                'date': date,
                'topic': topic,
                'status': 'ready',
            })

    return preview_results


def format_merge_preview(preview_results):
    ready_groups = [r for r in preview_results if r['status'] == 'ready']
    pending_groups = [r for r in preview_results if r['status'] == 'pending_confirmation']

    lines = []
    lines.append("合并预览")
    lines.append("========")
    lines.append(f"可合并分组: {len(ready_groups)} 组")
    lines.append(f"待确认分组: {len(pending_groups)} 组")

    if ready_groups:
        lines.append("")
        lines.append("【可合并分组】")
        for i, group in enumerate(ready_groups, 1):
            lines.append(f"  {i}. {group['group_name']}")
            date_display = group['date'].strftime('%Y年%m月%d日') if isinstance(group['date'], datetime) else (group['date'] or '未知')
            lines.append(f"     受访者: {group['interviewee'] or '未知受访者'} | 日期: {date_display} | 主题: {group['topic'] or '采访'}")
            lines.append(f"     文件: {group['file_count']} 个")
            lines.append(f"     预计输出: {os.path.basename(group['output_path'])}")

    if pending_groups:
        lines.append("")
        lines.append("【待确认分组 - 需补录后才能合并】")
        for i, group in enumerate(pending_groups, 1):
            lines.append(f"  {i}. {group['group_name']}")
            lines.append(f"     受访者: (未确认) | 文件: {group['file_count']} 个")
            lines.append("     文件列表:")
            for filepath in group['files']:
                lines.append(f"       - {os.path.basename(filepath)}")

    return "\n".join(lines)


def merge_by_group(filepaths, output_dir, group_by='interviewee', state_manager=None, confirmation_manager=None, **kwargs):
    groups = _build_groups(filepaths, group_by)

    if state_manager:
        state_manager.mark_merge_started()

    results = []

    for group_name, group_files in groups.items():
        if len(group_files) < 2:
            if state_manager:
                state_manager.add_skipped_group(group_name, "文件数少于2，跳过合并")
            continue

        sample_file = group_files[0]
        sample_name = os.path.basename(sample_file)
        interviewee = extract_interviewee_from_filename(sample_name)
        date = parse_date_from_filename(sample_name)
        topic = extract_topic_from_filename(sample_name)

        if confirmation_manager:
            if interviewee is None or interviewee == '未知受访者':
                has_confirmed = False
                for filepath in group_files:
                    filename = os.path.basename(filepath)
                    confirmed_info = confirmation_manager.get_confirmed_info(filename)
                    if confirmed_info and confirmed_info.get('interviewee'):
                        interviewee = confirmed_info['interviewee']
                        has_confirmed = True
                        break
                if not has_confirmed:
                    if state_manager:
                        state_manager.add_skipped_group(group_name, "受访者未确认，跳过合并")
                    continue

        safe_name = group_name.replace('/', '_').replace('\\', '_')
        output_path = os.path.join(output_dir, f"{safe_name}_合并稿.txt")

        merge_kwargs = kwargs.copy()
        merge_kwargs['interviewee'] = interviewee
        merge_kwargs['date'] = date
        merge_kwargs['topic'] = topic

        merge_text_files(group_files, output_path, **merge_kwargs)
        results.append((group_name, output_path, len(group_files), interviewee, date, topic))

        if state_manager:
            state_manager.add_merged_group(
                group_name, output_path, group_files,
                interviewee=interviewee, date=date, topic=topic
            )

    if state_manager:
        state_manager.mark_merge_completed()

    return results
