"""状态管理模块 - 持久化存储整理进度状态"""

import os
import json
from datetime import datetime
from pathlib import Path


STATE_FILENAME = 'interview_state.json'


class StateManager:
    """状态管理器 - 持久化存储 rename 和 merge 的完成状态"""
    
    def __init__(self, directory=None):
        """
        初始化状态管理器
        
        Args:
            directory: 状态文件所在目录，默认为当前目录
        """
        self.directory = directory or os.getcwd()
        self.state_file = os.path.join(self.directory, STATE_FILENAME)
        self._state = None
        self._load()
    
    def _load(self):
        """从文件加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._state = self._default_state()
        else:
            self._state = self._default_state()
    
    def _default_state(self):
        """返回默认的状态结构"""
        return {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'rename': {
                'completed': False,
                'completed_at': None,
                'renamed_files': [],
                'skipped_files': [],
                'failed_files': [],
            },
            'merge': {
                'completed': False,
                'completed_at': None,
                'merged_groups': [],
                'merged_files': [],
                'skipped_groups': [],
            },
            'interviews': {},
            'daily_log': {},
            'interview_snapshots': {},
        }
    
    def _save(self):
        """保存状态到文件"""
        self._state['updated_at'] = datetime.now().isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
    
    def reset(self):
        """重置所有状态"""
        self._state = self._default_state()
        self._save()
    
    # === Rename 相关方法 ===
    
    def mark_rename_started(self):
        """标记重命名开始"""
        self._state['rename']['completed'] = False
        self._state['rename']['completed_at'] = None
        self._save()
    
    def add_renamed_file(self, old_path, new_path, interviewee=None, date=None):
        """记录一个成功重命名的文件"""
        record = {
            'old_path': old_path,
            'new_path': new_path,
            'interviewee': interviewee,
            'date': date.isoformat() if date else None,
            'renamed_at': datetime.now().isoformat()
        }
        self._state['rename']['renamed_files'].append(record)
        
        # 更新采访分组状态
        if interviewee:
            date_str = date.strftime('%Y%m%d') if date else 'unknown_date'
            topic = '采访'
            key = f"{date_str}_{interviewee}_{topic}"
            if key not in self._state['interviews']:
                self._state['interviews'][key] = {
                    'interviewee': interviewee,
                    'date': date.isoformat() if date else None,
                    'renamed': True,
                    'merged': False,
                    'files': []
                }
            self._state['interviews'][key]['renamed'] = True
            if new_path not in self._state['interviews'][key]['files']:
                self._state['interviews'][key]['files'].append(new_path)
        
        self._save()
        self.log_daily_rename(old_path, new_path, interviewee)
    
    def add_skipped_file(self, old_path, reason="", conflict_with=None):
        """记录一个跳过的文件"""
        record = {
            'old_path': old_path,
            'reason': reason,
            'conflict_with': conflict_with,
            'skipped_at': datetime.now().isoformat()
        }
        self._state['rename']['skipped_files'].append(record)
        self._save()
    
    def add_failed_file(self, old_path, new_path, error=""):
        """记录一个重命名失败的文件"""
        record = {
            'old_path': old_path,
            'new_path': new_path,
            'error': error,
            'failed_at': datetime.now().isoformat()
        }
        self._state['rename']['failed_files'].append(record)
        self._save()
    
    def mark_rename_completed(self):
        """标记重命名完成"""
        self._state['rename']['completed'] = True
        self._state['rename']['completed_at'] = datetime.now().isoformat()
        self._save()
    
    def is_rename_completed(self):
        """检查重命名是否已完成"""
        return self._state['rename'].get('completed', False)
    
    # === Merge 相关方法 ===
    
    def mark_merge_started(self):
        """标记合并开始"""
        self._state['merge']['completed'] = False
        self._state['merge']['completed_at'] = None
        self._save()
    
    def add_merged_group(self, group_name, output_path, source_files, interviewee=None, date=None, topic=None):
        """记录一个成功合并的分组"""
        record = {
            'group_name': group_name,
            'output_path': output_path,
            'source_files': source_files,
            'interviewee': interviewee,
            'date': date.isoformat() if date else None,
            'topic': topic,
            'merged_at': datetime.now().isoformat()
        }
        self._state['merge']['merged_groups'].append(record)
        self._state['merge']['merged_files'].append(output_path)
        
        # 更新采访分组状态
        date_str = date.strftime('%Y%m%d') if date else 'unknown_date'
        # 优先使用标准topic"采访"作为key，确保能匹配到重命名时创建的条目
        standard_key = f"{date_str}_{interviewee or group_name}_采访"
        topic_key = f"{date_str}_{interviewee or group_name}_{topic or '采访'}"
        
        # 先检查是否已有标准key的条目
        if standard_key in self._state['interviews']:
            key = standard_key
        elif topic_key in self._state['interviews']:
            key = topic_key
        else:
            key = standard_key  # 默认使用标准key
        
        if key not in self._state['interviews']:
            self._state['interviews'][key] = {
                'interviewee': interviewee,
                'date': date.isoformat() if date else None,
                'topic': topic or '采访',
                'renamed': False,
                'merged': True,
                'files': []
            }
        self._state['interviews'][key]['merged'] = True
        self._state['interviews'][key]['merged_output'] = output_path
        self._state['interviews'][key]['topic'] = topic or self._state['interviews'][key].get('topic')
        self._state['interviews'][key]['has_audio'] = True
        self._state['interviews'][key]['has_text'] = True
        
        self._save()
        self.log_daily_merge(group_name, output_path, len(source_files) if isinstance(source_files, list) else 0)
    
    def add_skipped_group(self, group_name, reason=""):
        """记录一个跳过的合并分组"""
        record = {
            'group_name': group_name,
            'reason': reason,
            'skipped_at': datetime.now().isoformat()
        }
        self._state['merge']['skipped_groups'].append(record)
        self._save()
    
    def mark_merge_completed(self):
        """标记合并完成"""
        self._state['merge']['completed'] = True
        self._state['merge']['completed_at'] = datetime.now().isoformat()
        self._save()
    
    def is_merge_completed(self):
        """检查合并是否已完成"""
        return self._state['merge'].get('completed', False)
    
    # === 查询方法 ===
    
    def get_rename_summary(self):
        """获取重命名摘要"""
        rename = self._state['rename']
        return {
            '已完成': rename.get('completed', False),
            '完成时间': rename.get('completed_at'),
            '成功重命名': len(rename.get('renamed_files', [])),
            '跳过': len(rename.get('skipped_files', [])),
            '失败': len(rename.get('failed_files', [])),
        }
    
    def get_merge_summary(self):
        """获取合并摘要"""
        merge = self._state['merge']
        return {
            '已完成': merge.get('completed', False),
            '完成时间': merge.get('completed_at'),
            '合并分组数': len(merge.get('merged_groups', [])),
            '跳过分组数': len(merge.get('skipped_groups', [])),
        }
    
    def get_interview_summary(self):
        """获取各采访分组的整理状态"""
        interviews = self._state.get('interviews', {})
        result = []
        for key, info in interviews.items():
            result.append({
                'key': key,
                '受访者': info.get('interviewee', '未知'),
                '日期': info.get('date', '未知'),
                '主题': info.get('topic', '采访'),
                '已重命名': info.get('renamed', False),
                '已合并': info.get('merged', False),
                '文件数': len(info.get('files', [])),
                '合并输出': info.get('merged_output'),
            })
        return result
    
    def get_skipped_files(self):
        """获取所有跳过的文件（用于复核）"""
        return self._state['rename'].get('skipped_files', [])
    
    def get_renamed_files(self):
        """获取所有已重命名的文件"""
        return self._state['rename'].get('renamed_files', [])
    
    def get_full_state(self):
        """获取完整状态字典"""
        return self._state.copy()
    
    def get_state_file_path(self):
        """获取状态文件路径"""
        return self.state_file

    def _today_key(self):
        return datetime.now().strftime('%Y-%m-%d')

    def _ensure_daily_log(self, date_key=None):
        key = date_key or self._today_key()
        if key not in self._state['daily_log']:
            self._state['daily_log'][key] = {
                'renamed_files': [],
                'merged_groups': [],
                'confirmed_files': [],
            }
        return self._state['daily_log'][key]

    def log_daily_rename(self, old_path, new_path, interviewee=None):
        log = self._ensure_daily_log()
        log['renamed_files'].append({
            'old_path': old_path,
            'new_path': new_path,
            'interviewee': interviewee,
            'timestamp': datetime.now().isoformat(),
        })
        self._save()

    def log_daily_merge(self, group_name, output_path, file_count):
        log = self._ensure_daily_log()
        log['merged_groups'].append({
            'group_name': group_name,
            'output_path': output_path,
            'file_count': file_count,
            'timestamp': datetime.now().isoformat(),
        })
        self._save()

    def log_daily_confirmation(self, filename, field, value):
        log = self._ensure_daily_log()
        log['confirmed_files'].append({
            'filename': filename,
            'field': field,
            'value': value,
            'timestamp': datetime.now().isoformat(),
        })
        self._save()

    def get_daily_log(self, date_key=None):
        key = date_key or self._today_key()
        return self._state.get('daily_log', {}).get(key, {
            'renamed_files': [],
            'merged_groups': [],
            'confirmed_files': [],
        })

    def get_dashboard(self, scan_result=None, confirmation_manager=None):
        rename_summary = self.get_rename_summary()
        merge_summary = self.get_merge_summary()
        interviews = self._state.get('interviews', {})
        daily_log = self.get_daily_log()

        merged_keys = set()
        for k, v in interviews.items():
            if v.get('merged'):
                merged_keys.add(k)

        total_groups = len(interviews) if interviews else 1
        complete_groups = sum(
            1 for k, v in interviews.items()
            if v.get('has_audio') and v.get('has_text')
        ) if interviews else 0
        pairing_rate = (complete_groups / total_groups * 100) if total_groups > 0 else 0

        merged_but_incomplete = []
        for key, info in interviews.items():
            if info.get('merged') and (not info.get('has_audio') or not info.get('has_text')):
                merged_but_incomplete.append({
                    'key': key,
                    'interviewee': info.get('interviewee', '未知'),
                    'missing': '缺文字稿' if not info.get('has_text') else '缺录音',
                })

        unconfirmed_count = 0
        if confirmation_manager:
            unconfirmed_count = confirmation_manager.get_pending_count()

        return {
            'pairing_rate': f"{pairing_rate:.1f}%",
            'complete_groups': complete_groups,
            'total_groups': total_groups,
            'unconfirmed_count': unconfirmed_count,
            'merged_but_incomplete': merged_but_incomplete,
            'merged_but_incomplete_count': len(merged_but_incomplete),
            'rename_completed': rename_summary.get('已完成', False),
            'merge_completed': merge_summary.get('已完成', False),
            'today_renamed': len(daily_log.get('renamed_files', [])),
            'today_merged': len(daily_log.get('merged_groups', [])),
            'today_confirmed': len(daily_log.get('confirmed_files', [])),
        }

    def _get_week_key(self, date_obj=None):
        if date_obj is None:
            date_obj = datetime.now()
        year, week, _ = date_obj.isocalendar()
        return f"{year}-W{week:02d}"

    def _get_week_date_range(self, week_key=None):
        if week_key is None:
            week_key = self._get_week_key()
        parts = week_key.split('-W')
        year = int(parts[0])
        week = int(parts[1])
        try:
            monday = datetime.fromisocalendar(year, week, 1)
            sunday = datetime.fromisocalendar(year, week, 7)
        except AttributeError:
            jan4 = datetime(year, 1, 4)
            jan4_weekday = jan4.weekday()
            week1_monday = jan4 - __import__('datetime').timedelta(days=jan4_weekday)
            monday = week1_monday + __import__('datetime').timedelta(weeks=week - 1)
            sunday = monday + __import__('datetime').timedelta(days=6)
        return monday, sunday

    def take_interview_snapshot(self, interview_groups):
        date_key = self._today_key()
        snapshots = self._state.setdefault('interview_snapshots', {})
        snapshot_data = {}
        for key, info in interview_groups.items():
            snapshot_data[key] = {
                'interviewee': info.get('interviewee'),
                'date': info.get('date'),
                'topic': info.get('topic', '采访'),
                'has_audio': info.get('has_audio', False),
                'has_text': info.get('has_text', False),
                'is_complete': info.get('is_complete', False),
                'renamed': info.get('renamed', False),
                'merged': info.get('merged', False),
                'unconfirmed': info.get('unconfirmed', False),
                'snapshot_at': datetime.now().isoformat(),
            }
        snapshots[date_key] = snapshot_data
        self._save()
        return snapshot_data

    def get_weekly_report(self, week_key=None, confirmation_manager=None):
        if week_key is None:
            week_key = self._get_week_key()

        monday, sunday = self._get_week_date_range(week_key)
        date_format = '%Y-%m-%d'
        monday_str = monday.strftime(date_format)
        sunday_str = sunday.strftime(date_format)

        daily_log = self._state.get('daily_log', {})
        week_dates = []
        current = monday
        while current <= sunday:
            week_dates.append(current.strftime(date_format))
            current = current + __import__('datetime').timedelta(days=1)

        weekly_renamed = []
        weekly_merged = []
        weekly_confirmed = []
        for d in week_dates:
            day_log = daily_log.get(d, {})
            weekly_renamed.extend(day_log.get('renamed_files', []))
            weekly_merged.extend(day_log.get('merged_groups', []))
            weekly_confirmed.extend(day_log.get('confirmed_files', []))

        snapshots = self._state.get('interview_snapshots', {})
        week_snapshots = {d: snapshots.get(d, {}) for d in week_dates if d in snapshots}

        newly_complete = []
        stuck_groups = []
        group_timelines = {}

        if week_snapshots:
            first_day = min(week_snapshots.keys())
            last_day = max(week_snapshots.keys())
            first_snapshot = week_snapshots[first_day]
            last_snapshot = week_snapshots[last_day]

            for key, last_info in last_snapshot.items():
                first_info = first_snapshot.get(key)
                if last_info.get('is_complete'):
                    if first_info and not first_info.get('is_complete'):
                        newly_complete.append({
                            'key': key,
                            'interviewee': last_info.get('interviewee', '未知'),
                            'date': last_info.get('date', '未知'),
                            'topic': last_info.get('topic', '采访'),
                            'completed_at': last_info.get('snapshot_at', ''),
                        })

            days_incomplete = {}
            for d, snap in week_snapshots.items():
                for key, info in snap.items():
                    if not info.get('is_complete') or info.get('unconfirmed'):
                        if key not in days_incomplete:
                            days_incomplete[key] = {
                                'info': info,
                                'days': 0,
                                'first_seen': d,
                                'last_seen': d,
                            }
                        days_incomplete[key]['days'] += 1
                        days_incomplete[key]['last_seen'] = d
                        days_incomplete[key]['info'] = info

            for key, data in days_incomplete.items():
                if data['days'] >= 3:
                    stuck_groups.append({
                        'key': key,
                        'interviewee': data['info'].get('interviewee', '未知'),
                        'date': data['info'].get('date', '未知'),
                        'topic': data['info'].get('topic', '采访'),
                        'stuck_days': data['days'],
                        'first_seen': data['first_seen'],
                        'last_seen': data['last_seen'],
                        'has_audio': data['info'].get('has_audio', False),
                        'has_text': data['info'].get('has_text', False),
                        'unconfirmed': data['info'].get('unconfirmed', False),
                    })

            all_keys = set()
            for snap in week_snapshots.values():
                all_keys.update(snap.keys())

            for key in all_keys:
                timeline = []
                prev_status = None
                for d in sorted(week_snapshots.keys()):
                    info = week_snapshots[d].get(key)
                    if info is None:
                        continue
                    is_complete = info.get('is_complete', False)
                    has_audio = info.get('has_audio', False)
                    has_text = info.get('has_text', False)
                    unconfirmed = info.get('unconfirmed', False)

                    if is_complete and not unconfirmed:
                        status = 'complete'
                    elif unconfirmed:
                        status = 'unconfirmed'
                    elif has_audio and not has_text:
                        status = 'missing_text'
                    elif has_text and not has_audio:
                        status = 'missing_audio'
                    else:
                        status = 'incomplete'

                    day_events = []
                    day_log = daily_log.get(d, {})
                    for rf in day_log.get('renamed_files', []):
                        old_name = os.path.basename(rf.get('old_path', ''))
                        if key in old_name or info and (info.get('interviewee') in old_name or info.get('topic', '采访') in old_name):
                            day_events.append(f"rename: {old_name}")
                    for mg in day_log.get('merged_groups', []):
                        if mg.get('group_name') == key or (info and (info.get('interviewee') == mg.get('group_name') or info.get('topic', '采访') == mg.get('group_name'))):
                            day_events.append(f"merge: {mg.get('group_name')} ({mg.get('file_count', 0)} files)")
                    for cf in day_log.get('confirmed_files', []):
                        if info:
                            interviewee_match = info.get('interviewee') and info.get('interviewee') in cf.get('filename', '')
                            topic_match = info.get('topic', '采访') != '采访' and info.get('topic') in cf.get('filename', '')
                            if interviewee_match or topic_match:
                                field_cn = {'interviewee': '受访者', 'date': '日期', 'topic': '主题'}.get(cf.get('field', ''), cf.get('field', ''))
                                day_events.append(f"confirm: {field_cn} -> {cf.get('value', '')}")

                    entry = {
                        'date': d,
                        'status': status,
                        'changed': status != prev_status if prev_status is not None else True,
                        'events': day_events,
                    }
                    timeline.append(entry)
                    prev_status = status

                if timeline:
                    first_info = timeline[0]
                    snap_for_name = week_snapshots.get(sorted(week_snapshots.keys())[0], {}).get(key, {})
                    group_timelines[key] = {
                        'interviewee': snap_for_name.get('interviewee', '未知') if snap_for_name else '未知',
                        'topic': snap_for_name.get('topic', '采访') if snap_for_name else '采访',
                        'timeline': timeline,
                    }

        unconfirmed_count = 0
        if confirmation_manager:
            unconfirmed_count = confirmation_manager.get_pending_count()

        return {
            'week_key': week_key,
            'week_start': monday_str,
            'week_end': sunday_str,
            'renamed_count': len(weekly_renamed),
            'renamed_files': weekly_renamed,
            'merged_count': len(weekly_merged),
            'merged_groups': weekly_merged,
            'confirmed_count': len(weekly_confirmed),
            'confirmed_files': weekly_confirmed,
            'newly_complete': newly_complete,
            'newly_complete_count': len(newly_complete),
            'stuck_groups': stuck_groups,
            'stuck_count': len(stuck_groups),
            'unconfirmed_count': unconfirmed_count,
            'group_timelines': group_timelines,
        }
