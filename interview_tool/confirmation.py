import os
import json
from datetime import datetime

from .utils import extract_interviewee_from_filename, parse_date_from_filename, extract_topic_from_filename
from .scanner import ScanResult

CONFIRM_FILENAME = '待确认清单.json'


class ConfirmationManager:

    def __init__(self, directory=None):
        self.directory = directory or os.getcwd()
        self.confirm_file = os.path.join(self.directory, CONFIRM_FILENAME)

    def generate(self, scan_result):
        existing_entries = {}
        if os.path.exists(self.confirm_file):
            for e in self.load():
                existing_entries[e['filename']] = e

        current_files = set()
        for file_info in scan_result.files:
            if file_info.is_empty:
                continue
            current_files.add(file_info.filename)
            interviewee = file_info.interviewee
            date = file_info.date
            topic = extract_topic_from_filename(file_info.filename)

            if file_info.filename in existing_entries:
                entry = existing_entries[file_info.filename].copy()
                entry['detected_interviewee'] = interviewee
                entry['detected_date'] = date.isoformat() if date else None
                entry['detected_topic'] = topic
                missing_reasons = []
                if entry.get('status') != 'confirmed':
                    if interviewee is None or interviewee == 'unknown' or interviewee == '未知受访者':
                        missing_reasons.append('interviewee')
                    if date is None:
                        missing_reasons.append('date')
                    if topic == '采访':
                        missing_reasons.append('topic')
                    if not missing_reasons:
                        entry['status'] = 'auto_resolved'
                    entry['missing_fields'] = missing_reasons
                existing_entries[file_info.filename] = entry
                continue

            needs_confirm = (
                interviewee is None
                or interviewee == 'unknown'
                or interviewee == '未知受访者'
                or date is None
                or topic == '采访'
            )
            if not needs_confirm:
                continue

            missing_reasons = []
            if interviewee is None or interviewee == 'unknown' or interviewee == '未知受访者':
                missing_reasons.append('interviewee')
            if date is None:
                missing_reasons.append('date')
            if topic == '采访':
                missing_reasons.append('topic')

            existing_entries[file_info.filename] = {
                'filename': file_info.filename,
                'filepath': file_info.filepath,
                'detected_interviewee': interviewee,
                'confirmed_interviewee': None,
                'detected_date': date.isoformat() if date else None,
                'confirmed_date': None,
                'detected_topic': topic,
                'confirmed_topic': None,
                'status': 'pending',
                'missing_fields': missing_reasons,
            }

        entries = []
        for filename, entry in existing_entries.items():
            if filename in current_files or entry.get('status') == 'confirmed':
                entries.append(entry)

        now = datetime.now().isoformat()
        generated_at = now
        if os.path.exists(self.confirm_file):
            try:
                with open(self.confirm_file, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                generated_at = old_data.get('generated_at', now)
            except (json.JSONDecodeError, IOError):
                pass

        data = {
            'version': '1.2',
            'generated_at': generated_at,
            'updated_at': now,
            'entries': entries,
        }
        with open(self.confirm_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return entries

    def load(self):
        if not os.path.exists(self.confirm_file):
            return []
        try:
            with open(self.confirm_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('entries', [])
        except (json.JSONDecodeError, IOError):
            return []

    def save(self, entries):
        now = datetime.now().isoformat()
        existing_data = {}
        if os.path.exists(self.confirm_file):
            try:
                with open(self.confirm_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        generated_at = existing_data.get('generated_at', now)
        data = {
            'version': '1.2',
            'generated_at': generated_at,
            'updated_at': now,
            'entries': entries,
        }
        with open(self.confirm_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_confirmed_info(self, filename):
        entries = self.load()
        for entry in entries:
            if entry['filename'] == filename and entry.get('status') == 'confirmed':
                return {
                    'interviewee': entry.get('confirmed_interviewee'),
                    'date': entry.get('confirmed_date'),
                    'topic': entry.get('confirmed_topic'),
                }
        return None

    def get_all_confirmed(self):
        entries = self.load()
        result = {}
        for entry in entries:
            if entry.get('status') == 'confirmed':
                result[entry['filename']] = {
                    'interviewee': entry.get('confirmed_interviewee'),
                    'date': entry.get('confirmed_date'),
                    'topic': entry.get('confirmed_topic'),
                }
        return result

    def apply_confirmations(self, scan_result):
        confirmed = self.get_all_confirmed()
        entries = self.load()
        auto_resolved = {}
        for e in entries:
            if e.get('status') == 'auto_resolved':
                info = {}
                if e.get('detected_interviewee') and e['detected_interviewee'] not in (None, 'unknown', '未知受访者'):
                    info['interviewee'] = e['detected_interviewee']
                if e.get('detected_date'):
                    info['date'] = e['detected_date']
                if e.get('detected_topic') and e['detected_topic'] != '采访':
                    info['topic'] = e['detected_topic']
                if info:
                    auto_resolved[e['filename']] = info

        for file_info in scan_result.files:
            if file_info.filename in confirmed:
                info = confirmed[file_info.filename]
                if info.get('interviewee') is not None:
                    file_info.interviewee = info['interviewee']
                if info.get('date') is not None:
                    if isinstance(info['date'], str):
                        try:
                            file_info.date = datetime.fromisoformat(info['date'])
                        except ValueError:
                            pass
                    elif isinstance(info['date'], datetime):
                        file_info.date = info['date']
                if info.get('topic') is not None:
                    file_info.topic = info['topic']
            elif file_info.filename in auto_resolved:
                info = auto_resolved[file_info.filename]
                if info.get('interviewee') and (file_info.interviewee is None or file_info.interviewee == '未知受访者'):
                    file_info.interviewee = info['interviewee']
                if info.get('date') and file_info.date is None:
                    if isinstance(info['date'], str):
                        try:
                            file_info.date = datetime.fromisoformat(info['date'])
                        except ValueError:
                            pass
                if info.get('topic') and (not hasattr(file_info, 'topic') or file_info.topic == '采访'):
                    file_info.topic = info['topic']
        return scan_result

    def get_pending_count(self):
        entries = self.load()
        return sum(1 for e in entries if e.get('status') == 'pending')

    def get_confirmed_count(self):
        entries = self.load()
        return sum(1 for e in entries if e.get('status') == 'confirmed')

    def get_auto_resolved_count(self):
        entries = self.load()
        return sum(1 for e in entries if e.get('status') == 'auto_resolved')

    def get_pool_stats(self):
        entries = self.load()
        pending = [e for e in entries if e.get('status') == 'pending']
        confirmed = [e for e in entries if e.get('status') == 'confirmed']
        auto_resolved = [e for e in entries if e.get('status') == 'auto_resolved']
        return {
            'total': len(entries),
            'pending': len(pending),
            'confirmed': len(confirmed),
            'auto_resolved': len(auto_resolved),
        }

    def export_human_readable(self, output_path):
        entries = self.load()
        if not entries:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('待确认素材清单\n')
                f.write('================\n')
                f.write('无待确认条目\n')
            return

        generated_at = ''
        if os.path.exists(self.confirm_file):
            try:
                with open(self.confirm_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                generated_at = data.get('generated_at', '')
            except (json.JSONDecodeError, IOError):
                pass

        pending_count = sum(1 for e in entries if e.get('status') == 'pending')
        confirmed_count = sum(1 for e in entries if e.get('status') == 'confirmed')
        auto_count = sum(1 for e in entries if e.get('status') == 'auto_resolved')
        lines = []
        lines.append('待确认素材清单 (持续维护池)')
        lines.append('================')
        lines.append(f'生成时间: {generated_at}')
        lines.append(f'共 {len(entries)} 条 | 待确认: {pending_count} | 已确认: {confirmed_count} | 自动解决: {auto_count}')
        lines.append('')

        status_order = ['pending', 'auto_resolved', 'confirmed']
        status_cn = {'pending': '待确认', 'confirmed': '已确认', 'auto_resolved': '自动解决'}
        sorted_entries = sorted(entries, key=lambda e: status_order.index(e.get('status', 'pending')))

        header = (
            '序号 | 文件名 | 自动识别受访者 | 确认受访者 | '
            '自动识别日期 | 确认日期 | 自动识别主题 | 确认主题 | 状态'
        )
        lines.append(header)

        for i, entry in enumerate(sorted_entries, 1):
            detected_interviewee = entry.get('detected_interviewee') or '(无)'
            confirmed_interviewee = entry.get('confirmed_interviewee') or ''
            detected_date = entry.get('detected_date') or '(无)'
            confirmed_date = entry.get('confirmed_date') or ''
            detected_topic = entry.get('detected_topic') or '(无)'
            confirmed_topic = entry.get('confirmed_topic') or ''
            status = status_cn.get(entry.get('status', 'pending'), entry.get('status', 'pending'))
            line = (
                f'{i} | {entry["filename"]} | {detected_interviewee} | '
                f'{confirmed_interviewee} | {detected_date} | {confirmed_date} | '
                f'{detected_topic} | {confirmed_topic} | {status}'
            )
            lines.append(line)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

    def import_from_edited(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        entries = data.get('entries', [])
        self.save(entries)
        return entries
