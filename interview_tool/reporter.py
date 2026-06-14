"""报告生成模块 - 生成统计报告、错误清单等"""

import os
import json
from datetime import datetime
from collections import defaultdict

from .utils import format_duration, format_file_size, normalize_basename_for_pairing, get_pairing_key, extract_topic_from_filename
from .state import StateManager
from .confirmation import ConfirmationManager


class InterviewGroup:

    def __init__(self, pairing_key, interviewee=None, date=None, topic=None):
        self.pairing_key = pairing_key
        self.interviewee = interviewee
        self.date = date
        self.topic = topic or "采访"
        self.audio_files = []
        self.text_files = []
        self.subtitle_files = []

    @property
    def has_audio(self):
        return len(self.audio_files) > 0

    @property
    def has_text(self):
        return len(self.text_files) > 0

    @property
    def is_complete(self):
        return self.has_audio and self.has_text

    @property
    def total_duration(self):
        durations = [f.duration for f in self.audio_files if f.duration]
        return sum(durations) if durations else 0

    @property
    def total_size(self):
        return sum(f.size for f in self.audio_files + self.text_files + self.subtitle_files)


class ReportGenerator:

    def __init__(self, scan_result=None, state_manager=None):
        self.scan_result = scan_result
        self.state_manager = state_manager
        self.confirmation_manager = None
        self.errors = []
        self.warnings = []
        self._interview_groups = None

    def add_error(self, message, filepath=None, error_type="error"):
        self.errors.append({
            'type': error_type,
            'message': message,
            'filepath': filepath,
            'timestamp': datetime.now().isoformat()
        })

    def add_warning(self, message, filepath=None):
        self.warnings.append({
            'message': message,
            'filepath': filepath,
            'timestamp': datetime.now().isoformat()
        })

    def _build_interview_groups(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = {}

        for f in result.files:
            if f.is_empty:
                continue

            key = get_pairing_key(f)
            norm_base = normalize_basename_for_pairing(f.filename)

            if key not in groups:
                topic = f.topic if hasattr(f, 'topic') else extract_topic_from_filename(f.filename)
                groups[key] = InterviewGroup(
                    pairing_key=key,
                    interviewee=f.interviewee,
                    date=f.date,
                    topic=topic
                )

            group = groups[key]

            if f.interviewee and not group.interviewee:
                group.interviewee = f.interviewee
            if f.date and not group.date:
                group.date = f.date
            if hasattr(f, 'topic') and f.topic and f.topic != '采访' and (not group.topic or group.topic == '采访'):
                group.topic = f.topic

            if f.is_audio:
                group.audio_files.append(f)
            elif f.is_text:
                group.text_files.append(f)
            elif f.is_subtitle:
                group.subtitle_files.append(f)

        self._interview_groups = groups
        return groups

    def get_interview_groups(self, scan_result=None):
        if self._interview_groups is None:
            self._build_interview_groups(scan_result)
        return self._interview_groups

    def generate_dashboard(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = self.get_interview_groups(result)

        complete_groups = sum(1 for g in groups.values() if g.is_complete)
        total_groups = len(groups)
        pairing_rate = (complete_groups / total_groups * 100) if total_groups > 0 else 0

        unconfirmed_count = 0
        if self.confirmation_manager:
            unconfirmed_count = self.confirmation_manager.get_pending_count()

        merged_but_incomplete = []
        if self.state_manager:
            interviews = self.state_manager._state.get('interviews', {})
            for key, info in interviews.items():
                if info.get('merged'):
                    has_audio = info.get('has_audio', False)
                    has_text = info.get('has_text', False)
                    if not has_audio or not has_text:
                        missing_parts = []
                        if not has_text:
                            missing_parts.append('文字稿')
                        if not has_audio:
                            missing_parts.append('音频')
                        merged_but_incomplete.append({
                            'key': key,
                            'interviewee': info.get('interviewee', '未知'),
                            'date': info.get('date', '未知'),
                            'missing': '、'.join(missing_parts),
                        })
        else:
            for key, group in groups.items():
                if not group.is_complete:
                    for f in group.audio_files + group.text_files:
                        state_info = {}
                        if hasattr(f, '_merged') and f._merged:
                            state_info = {'merged': True}
                    if hasattr(group, '_merged') and group._merged:
                        pass

        today_activity = {}
        if self.state_manager:
            daily_log = self.state_manager.get_daily_log()
            today_activity = {
                'renamed_count': len(daily_log.get('renamed_files', [])),
                'merged_count': len(daily_log.get('merged_groups', [])),
                'confirmed_count': len(daily_log.get('confirmed_files', [])),
            }
        else:
            today_activity = {
                'renamed_count': 0,
                'merged_count': 0,
                'confirmed_count': 0,
            }

        step_statuses = {}
        if self.state_manager:
            rename_summary = self.state_manager.get_rename_summary()
            merge_summary = self.state_manager.get_merge_summary()
            step_statuses = {
                '扫描': '已完成',
                '重命名': '已完成' if rename_summary.get('已完成', False) else ('进行中' if rename_summary.get('成功重命名', 0) > 0 else '待处理'),
                '合并': '已完成' if merge_summary.get('已完成', False) else ('进行中' if merge_summary.get('合并分组数', 0) > 0 else '待处理'),
            }
        else:
            step_statuses = {
                '扫描': '已完成',
                '重命名': '待处理',
                '合并': '待处理',
            }

        return {
            'pairing_rate': pairing_rate,
            'pairing_rate_display': f"{pairing_rate:.1f}%",
            'complete_groups': complete_groups,
            'total_groups': total_groups,
            'unconfirmed_count': unconfirmed_count,
            'merged_but_incomplete': merged_but_incomplete,
            'merged_but_incomplete_count': len(merged_but_incomplete),
            'today_activity': today_activity,
            'step_statuses': step_statuses,
        }

    def generate_daily_report(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        today_str = datetime.now().strftime('%Y-%m-%d')

        daily_log = {}
        if self.state_manager:
            daily_log = self.state_manager.get_daily_log()

        renamed_files = daily_log.get('renamed_files', [])
        merged_groups = daily_log.get('merged_groups', [])
        confirmed_files = daily_log.get('confirmed_files', [])

        groups = self.get_interview_groups(result)
        missing_groups = []
        for key, group in groups.items():
            if not group.is_complete:
                missing_parts = []
                if not group.has_text:
                    missing_parts.append('文字稿')
                if not group.has_audio:
                    missing_parts.append('音频')
                missing_groups.append({
                    'group_name': self._format_group_name(group),
                    'interviewee': group.interviewee or '未知',
                    'date': group.date.strftime('%Y-%m-%d') if group.date else '未知',
                    'missing': '、'.join(missing_parts),
                })

        unconfirmed_list = self.generate_unconfirmed_list(result)

        return {
            'date': today_str,
            'renamed_files': renamed_files,
            'renamed_count': len(renamed_files),
            'merged_groups': merged_groups,
            'merged_count': len(merged_groups),
            'confirmed_files': confirmed_files,
            'confirmed_count': len(confirmed_files),
            'missing_groups': missing_groups,
            'missing_count': len(missing_groups),
            'unconfirmed_list': unconfirmed_list,
            'unconfirmed_count': len(unconfirmed_list),
        }

    def generate_weekly_report(self, scan_result=None, week_key=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        weekly_data = {
            'week_key': '',
            'week_start': '',
            'week_end': '',
            'renamed_count': 0,
            'merged_count': 0,
            'confirmed_count': 0,
            'newly_complete': [],
            'newly_complete_count': 0,
            'stuck_groups': [],
            'stuck_count': 0,
            'unconfirmed_count': 0,
            'missing_groups': [],
            'missing_count': 0,
        }

        if self.state_manager:
            weekly_data = self.state_manager.get_weekly_report(
                week_key=week_key,
                confirmation_manager=self.confirmation_manager
            )

        groups = self.get_interview_groups(result)
        missing_groups = []
        for key, group in groups.items():
            if not group.is_complete:
                missing_parts = []
                if not group.has_text:
                    missing_parts.append('文字稿')
                if not group.has_audio:
                    missing_parts.append('音频')
                missing_groups.append({
                    'group_name': self._format_group_name(group),
                    'interviewee': group.interviewee or '未知',
                    'date': group.date.strftime('%Y-%m-%d') if group.date else '未知',
                    'topic': group.topic or '采访',
                    'missing': '、'.join(missing_parts),
                })

        weekly_data['missing_groups'] = missing_groups
        weekly_data['missing_count'] = len(missing_groups)

        return weekly_data

    def build_snapshot_data(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = self.get_interview_groups(result)
        snapshot = {}
        for key, group in groups.items():
            state_info = {}
            if self.state_manager:
                interviews = self.state_manager._state.get('interviews', {})
                state_info = interviews.get(key, {})

            unconfirmed = False
            if self.confirmation_manager:
                for f in group.audio_files + group.text_files + group.subtitle_files:
                    confirmed_info = self.confirmation_manager.get_confirmed_info(f.filename)
                    if not confirmed_info:
                        if f.interviewee is None or f.interviewee == '未知受访者' or f.date is None or f.topic == '采访':
                            unconfirmed = True
                            break

            snapshot[key] = {
                'interviewee': group.interviewee,
                'date': group.date.isoformat() if group.date else None,
                'topic': group.topic or '采访',
                'has_audio': group.has_audio,
                'has_text': group.has_text,
                'is_complete': group.is_complete,
                'renamed': state_info.get('renamed', False),
                'merged': state_info.get('merged', False),
                'unconfirmed': unconfirmed,
            }
        return snapshot

    def generate_unconfirmed_list(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        unconfirmed = []

        if self.confirmation_manager:
            entries = self.confirmation_manager.load()
            for entry in entries:
                if entry.get('status') == 'pending':
                    unconfirmed.append({
                        'filename': entry['filename'],
                        'filepath': entry.get('filepath', ''),
                        'interviewee': entry.get('detected_interviewee'),
                        'date': entry.get('detected_date'),
                        'topic': entry.get('detected_topic'),
                        'missing_fields': entry.get('missing_fields', []),
                    })
        else:
            for f in result.files:
                if f.is_empty:
                    continue
                interviewee = f.interviewee
                date = f.date
                topic = f.topic if hasattr(f, 'topic') else extract_topic_from_filename(f.filename)
                needs_confirm = (
                    interviewee is None
                    or interviewee == '未知受访者'
                    or date is None
                    or topic == '采访'
                )
                if not needs_confirm:
                    continue
                missing_fields = []
                if interviewee is None or interviewee == '未知受访者':
                    missing_fields.append('interviewee')
                if date is None:
                    missing_fields.append('date')
                if topic == '采访':
                    missing_fields.append('topic')
                unconfirmed.append({
                    'filename': f.filename,
                    'filepath': f.filepath,
                    'interviewee': interviewee,
                    'date': date.isoformat() if date else None,
                    'topic': topic,
                    'missing_fields': missing_fields,
                })

        return unconfirmed

    def generate_summary(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = self.get_interview_groups(result)
        complete_groups = [g for g in groups.values() if g.is_complete]
        incomplete_groups = [g for g in groups.values() if not g.is_complete]

        total_duration = sum(g.total_duration for g in groups.values())

        interviewees = set()
        for g in groups.values():
            if g.interviewee:
                interviewees.add(g.interviewee)

        dates = set()
        for g in groups.values():
            if g.date:
                dates.add(g.date.date().isoformat())

        duplicate_count = sum(len(files) for files in result.duplicates.values())
        duplicate_group_count = len(result.duplicates)

        summary = {
            '基本信息': {
                '扫描目录数': len(result.directories),
                '总文件数': result.total_files,
                '采访场数': len(groups),
                '总大小': format_file_size(result.total_size),
                '扫描时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            '采访分组统计': {
                '完整配对': len(complete_groups),
                '缺失配对': len(incomplete_groups),
                '仅有音频': sum(1 for g in groups.values() if g.has_audio and not g.has_text),
                '仅有文字稿': sum(1 for g in groups.values() if g.has_text and not g.has_audio),
            },
            '文件分类': {
                '音频文件': len(result.audio_files),
                '文字稿文件': len(result.text_files),
                '字幕文件': len(result.subtitle_files),
            },
            '音频统计': {
                '音频文件数': len(result.audio_files),
                '总时长': format_duration(total_duration),
                '平均时长': format_duration(total_duration / len(result.audio_files)) if result.audio_files else "0秒",
            },
            '内容统计': {
                '受访者人数': len(interviewees),
                '受访者列表': sorted(list(interviewees)),
                '涉及日期数': len(dates),
                '日期列表': sorted(list(dates)),
            },
            '问题统计': {
                '空文件数': len(result.empty_files),
                '重复文件组数': duplicate_group_count,
                '重复文件总数': duplicate_count,
            },
        }

        return summary

    def find_missing_pairs(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = self.get_interview_groups(result)

        missing_text = []
        missing_audio = []

        for key, group in groups.items():
            group_name = self._format_group_name(group)

            if group.has_audio and not group.has_text:
                audio_names = [f.filename for f in group.audio_files]
                missing_text.append((group_name, group.audio_files[0].filepath, audio_names))

            if group.has_text and not group.has_audio:
                text_names = [f.filename for f in group.text_files]
                missing_audio.append((group_name, group.text_files[0].filepath, text_names))

        return {
            '有音频无文字稿': missing_text,
            '有文字稿无音频': missing_audio,
        }

    def _format_group_name(self, group):
        parts = []
        if group.date:
            parts.append(group.date.strftime('%Y-%m-%d'))
        if group.interviewee:
            parts.append(group.interviewee)
        if group.topic and group.topic != "采访":
            parts.append(group.topic)

        if not parts:
            parts.append(group.pairing_key)

        return "_".join(parts)

    def generate_progress_report(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = self.get_interview_groups(result)

        rename_completed = False
        merge_completed = False
        rename_summary = None
        merge_summary = None
        interview_states = []

        if self.state_manager:
            rename_summary = self.state_manager.get_rename_summary()
            merge_summary = self.state_manager.get_merge_summary()
            interview_states = self.state_manager.get_interview_summary()
            rename_completed = rename_summary.get('已完成', False)
            merge_completed = merge_summary.get('已完成', False)

        named_files = 0
        total_files = result.total_files

        for f in result.files:
            if f.date and f.interviewee:
                named_files += 1

        renamed_count = rename_summary.get('成功重命名', 0) if rename_summary else 0
        merged_groups_count = merge_summary.get('合并分组数', 0) if merge_summary else 0

        naming_progress = (renamed_count / total_files * 100) if total_files > 0 else 0
        group_merge_progress = (merged_groups_count / len(groups) * 100) if len(groups) > 0 else 0

        total_tasks = 3
        completed_tasks = 1
        if rename_completed:
            completed_tasks += 1
        if merge_completed:
            completed_tasks += 1

        overall_progress = (completed_tasks / total_tasks) * 100

        dashboard = self.generate_dashboard(result)

        progress = {
            '整体进度': {
                '百分比': f"{overall_progress:.1f}%",
                '已完成步骤': completed_tasks,
                '总步骤': total_tasks,
            },
            '命名规范化进度': {
                '百分比': f"{naming_progress:.1f}%",
                '已重命名文件': renamed_count,
                '总文件数': total_files,
            },
            '合并进度': {
                '百分比': f"{group_merge_progress:.1f}%",
                '已合并分组': merged_groups_count,
                '总分组数': len(groups),
            },
            '步骤状态': {
                '扫描': '已完成',
                '重命名': '已完成' if rename_completed else ('进行中' if renamed_count > 0 else '待处理'),
                '合并': '已完成' if merge_completed else ('进行中' if merged_groups_count > 0 else '待处理'),
            },
            'pairing_rate': dashboard['pairing_rate'],
            'pairing_rate_display': dashboard['pairing_rate_display'],
            'unconfirmed_count': dashboard['unconfirmed_count'],
            'merged_but_incomplete_count': dashboard['merged_but_incomplete_count'],
        }

        if interview_states:
            progress['各采访分组状态'] = interview_states

        return progress

    def generate_error_list(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        errors = {
            '空文件': [],
            '重复文件': [],
            '跳过文件': [],
            '重命名失败': [],
            '其他错误': self.errors.copy(),
        }

        for f in result.empty_files:
            errors['空文件'].append({
                '文件': f.filepath,
                '大小': f.size,
            })

        for h, files in result.duplicates.items():
            errors['重复文件'].append({
                '哈希': h,
                '文件数': len(files),
                '文件列表': [f.filepath for f in files],
                '大小': format_file_size(files[0].size) if files else "0",
            })

        if self.state_manager:
            skipped = self.state_manager.get_skipped_files()
            for s in skipped:
                errors['跳过文件'].append({
                    '原文件': s['old_path'],
                    '原因': s.get('reason', ''),
                    '冲突文件': s.get('conflict_with'),
                    '时间': s.get('skipped_at', ''),
                })

            failed = self.state_manager._state.get('rename', {}).get('failed_files', [])
            for f in failed:
                errors['重命名失败'].append({
                    '原文件': f['old_path'],
                    '目标文件': f['new_path'],
                    '错误': f.get('error', ''),
                    '时间': f.get('failed_at', ''),
                })

        return errors

    def generate_interview_groups_detail(self, scan_result=None):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        groups = self.get_interview_groups(result)
        group_states = {}

        if self.state_manager:
            for state in self.state_manager.get_interview_summary():
                group_states[state['key']] = state

        details = []
        for key, group in sorted(groups.items()):
            state = group_states.get(key, {})
            detail = {
                '分组键': key,
                '受访者': group.interviewee or '未知',
                '日期': group.date.strftime('%Y-%m-%d') if group.date else '未知',
                '主题': group.topic,
                '状态': '完整' if group.is_complete else ('仅有音频' if group.has_audio else '仅有文字稿'),
                '音频文件数': len(group.audio_files),
                '文字稿文件数': len(group.text_files),
                '字幕文件数': len(group.subtitle_files),
                '总时长': format_duration(group.total_duration),
                '总大小': format_file_size(group.total_size),
                '已重命名': state.get('已重命名', False),
                '已合并': state.get('已合并', False),
                '合并输出': state.get('合并输出'),
                '音频文件': [f.filename for f in group.audio_files],
                '文字稿文件': [f.filename for f in group.text_files],
            }
            details.append(detail)

        return details

    def generate_full_report(self, scan_result=None, output_path=None, format='text', daily=False, weekly=False):
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")

        summary = self.generate_summary(result)
        missing_pairs = self.find_missing_pairs(result)
        errors = self.generate_error_list(result)
        progress = self.generate_progress_report(result)
        group_details = self.generate_interview_groups_detail(result)
        dashboard = self.generate_dashboard(result)
        unconfirmed_list = self.generate_unconfirmed_list(result)

        if self.state_manager:
            snapshot_data = self.build_snapshot_data(result)
            self.state_manager.take_interview_snapshot(snapshot_data)

        report_data = {
            '摘要': summary,
            '进度': progress,
            '采访分组': group_details,
            '缺失配对': missing_pairs,
            '问题清单': errors,
            'dashboard': dashboard,
            'unconfirmed_list': unconfirmed_list,
        }

        if daily:
            daily_report = self.generate_daily_report(result)
            report_data['daily_report'] = daily_report

        if weekly:
            weekly_report = self.generate_weekly_report(result)
            report_data['weekly_report'] = weekly_report

        if format == 'json':
            report_content = json.dumps(report_data, ensure_ascii=False, indent=2)
        else:
            report_content = self._format_text_report(report_data, daily=daily, weekly=weekly)

        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)

        return report_content

    def _format_text_report(self, data, daily=False, weekly=False):
        lines = []
        lines.append("=" * 70)
        lines.append("采访素材整理报告")
        lines.append("=" * 70)
        lines.append("")

        dashboard = data.get('dashboard', {})

        lines.append("╔══════════════════════════════════════╗")
        lines.append("║          【项目看板】                ║")
        lines.append("╚══════════════════════════════════════╝")
        pairing_rate_display = dashboard.get('pairing_rate_display', '0.0%')
        unconfirmed_count = dashboard.get('unconfirmed_count', 0)
        merged_but_incomplete = dashboard.get('merged_but_incomplete', [])
        merged_but_incomplete_count = dashboard.get('merged_but_incomplete_count', 0)
        today_activity = dashboard.get('today_activity', {})
        step_statuses = dashboard.get('step_statuses', {})

        lines.append(f"  配对完成率: {pairing_rate_display}")
        lines.append(f"  待确认素材: {unconfirmed_count} 件")
        lines.append(f"  已合并仍缺件: {merged_but_incomplete_count} 组")
        if merged_but_incomplete:
            for item in merged_but_incomplete:
                interviewee = item.get('interviewee', '未知')
                date = item.get('date', '未知')
                missing = item.get('missing', '')
                lines.append(f"    - {interviewee} ({date}): 缺{missing}")
        lines.append(f"  今日动态: 重命名 {today_activity.get('renamed_count', 0)} 件 / 合并 {today_activity.get('merged_count', 0)} 组 / 确认 {today_activity.get('confirmed_count', 0)} 件")
        lines.append("")

        lines.append("【基本信息】")
        for k, v in data['摘要']['基本信息'].items():
            lines.append(f"  {k}: {v}")
        lines.append("")

        lines.append("【采访分组统计】")
        for k, v in data['摘要']['采访分组统计'].items():
            lines.append(f"  {k}: {v}")
        lines.append("")

        lines.append("【文件分类统计】")
        for k, v in data['摘要']['文件分类'].items():
            lines.append(f"  {k}: {v}")
        lines.append("")

        lines.append("【音频统计】")
        for k, v in data['摘要']['音频统计'].items():
            lines.append(f"  {k}: {v}")
        lines.append("")

        lines.append("【内容统计】")
        content_stats = data['摘要']['内容统计']
        lines.append(f"  受访者人数: {content_stats['受访者人数']}")
        lines.append(f"  受访者列表: {', '.join(content_stats['受访者列表'])}")
        lines.append(f"  涉及日期数: {content_stats['涉及日期数']}")
        lines.append(f"  日期列表: {', '.join(content_stats['日期列表'])}")
        lines.append("")

        lines.append("【整理进度】")
        lines.append(f"  整体进度: {data['进度']['整体进度']['百分比']}")
        lines.append(f"  命名规范化: {data['进度']['命名规范化进度']['百分比']} ({data['进度']['命名规范化进度']['已重命名文件']}/{data['进度']['命名规范化进度']['总文件数']} 文件)")
        lines.append(f"  分组合并: {data['进度']['合并进度']['百分比']} ({data['进度']['合并进度']['已合并分组']}/{data['进度']['合并进度']['总分组数']} 分组)")
        for step, status in data['进度']['步骤状态'].items():
            icon = "✓" if '已完成' in status else ("○" if '待处理' in status else "●")
            lines.append(f"    {icon} {step}: {status}")
        lines.append("")

        if '各采访分组状态' in data['进度'] and data['进度']['各采访分组状态']:
            lines.append("【各采访分组整理状态】")
            for state in data['进度']['各采访分组状态']:
                status_parts = []
                if state.get('已重命名'):
                    status_parts.append('已命名')
                if state.get('已合并'):
                    status_parts.append('已合并')
                status_str = ", ".join(status_parts) if status_parts else "未处理"
                lines.append(f"  {state['受访者']} ({state['日期']}): {status_str}")
            lines.append("")

        lines.append("【采访分组详情】")
        for i, group in enumerate(data['采访分组'], 1):
            status_icon = "✓" if group['状态'] == '完整' else "!"
            lines.append(f"  {i:>3}. {status_icon} {group['受访者']} - {group['日期']} - {group['主题']}")
            lines.append(f"       状态: {group['状态']} | 音频: {group['音频文件数']} 个 | 文字稿: {group['文字稿文件数']} 个")
            lines.append(f"       时长: {group['总时长']} | 大小: {group['总大小']}")
            lines.append(f"       整理状态: {'已命名' if group['已重命名'] else '未命名'} | {'已合并' if group['已合并'] else '未合并'}")
            if group['音频文件']:
                lines.append(f"       音频: {', '.join(group['音频文件'])}")
            if group['文字稿文件']:
                lines.append(f"       文字稿: {', '.join(group['文字稿文件'])}")
            if group.get('合并输出'):
                lines.append(f"       合并稿: {os.path.basename(group['合并输出'])}")
        lines.append("")

        lines.append("【缺失配对】")
        missing = data['缺失配对']
        lines.append(f"  有音频无文字稿: {len(missing['有音频无文字稿'])} 组")
        for name, path, files in missing['有音频无文字稿'][:5]:
            files_str = ", ".join(files)
            lines.append(f"    - {name}: {files_str}")
        if len(missing['有音频无文字稿']) > 5:
            lines.append(f"    ... 还有 {len(missing['有音频无文字稿']) - 5} 组")

        lines.append(f"  有文字稿无音频: {len(missing['有文字稿无音频'])} 组")
        for name, path, files in missing['有文字稿无音频'][:5]:
            files_str = ", ".join(files)
            lines.append(f"    - {name}: {files_str}")
        if len(missing['有文字稿无音频']) > 5:
            lines.append(f"    ... 还有 {len(missing['有文字稿无音频']) - 5} 组")
        lines.append("")

        unconfirmed_list = data.get('unconfirmed_list', [])
        lines.append("【待确认素材】")
        lines.append(f"  共 {len(unconfirmed_list)} 件待确认")
        for item in unconfirmed_list[:10]:
            filename = item.get('filename', '')
            interviewee = item.get('interviewee') or '(未识别)'
            date = item.get('date') or '(未识别)'
            topic = item.get('topic') or '采访'
            reasons = []
            if item.get('interviewee') is None:
                reasons.append('受访者未识别')
            if item.get('date') is None:
                reasons.append('日期未识别')
            if topic == '采访':
                reasons.append('主题为默认')
            reason_str = '、'.join(reasons) if reasons else ''
            lines.append(f"    - {filename} | 受访者: {interviewee} | 日期: {date} | {reason_str}")
        if len(unconfirmed_list) > 10:
            lines.append(f"    ... 还有 {len(unconfirmed_list) - 10} 件")
        lines.append("")

        if daily and 'daily_report' in data:
            dr = data['daily_report']
            lines.append("【日报】")
            lines.append(f"  日期: {dr['date']}")
            lines.append("")

            lines.append(f"  今日新处理素材 ({dr['renamed_count']} 件)")
            for item in dr.get('renamed_files', [])[:10]:
                old_name = os.path.basename(item.get('old_path', ''))
                new_name = os.path.basename(item.get('new_path', ''))
                interviewee = item.get('interviewee', '')
                lines.append(f"    - {old_name} → {new_name}" + (f" ({interviewee})" if interviewee else ""))
            if dr['renamed_count'] > 10:
                lines.append(f"    ... 还有 {dr['renamed_count'] - 10} 件")
            lines.append("")

            lines.append(f"  今日合并完成 ({dr['merged_count']} 组)")
            for item in dr.get('merged_groups', [])[:10]:
                group_name = item.get('group_name', '')
                file_count = item.get('file_count', 0)
                lines.append(f"    - {group_name} ({file_count} 个文件)")
            if dr['merged_count'] > 10:
                lines.append(f"    ... 还有 {dr['merged_count'] - 10} 组")
            lines.append("")

            lines.append(f"  今日确认补录 ({dr['confirmed_count']} 件)")
            for item in dr.get('confirmed_files', [])[:10]:
                filename = item.get('filename', '')
                field = item.get('field', '')
                value = item.get('value', '')
                lines.append(f"    - {filename}: {field} → {value}")
            if dr['confirmed_count'] > 10:
                lines.append(f"    ... 还有 {dr['confirmed_count'] - 10} 件")
            lines.append("")

            lines.append(f"  仍缺件分组 ({dr['missing_count']} 组)")
            for item in dr.get('missing_groups', [])[:10]:
                group_name = item.get('group_name', '')
                missing_desc = item.get('missing', '')
                lines.append(f"    - {group_name}: 缺{missing_desc}")
            if dr['missing_count'] > 10:
                lines.append(f"    ... 还有 {dr['missing_count'] - 10} 组")
            lines.append("")

            lines.append(f"  待确认素材 ({dr['unconfirmed_count']} 件)")
            for item in dr.get('unconfirmed_list', [])[:10]:
                filename = item.get('filename', '')
                interviewee = item.get('interviewee') or '(未识别)'
                date = item.get('date') or '(未识别)'
                lines.append(f"    - {filename} | 受访者: {interviewee} | 日期: {date}")
            if dr['unconfirmed_count'] > 10:
                lines.append(f"    ... 还有 {dr['unconfirmed_count'] - 10} 件")
            lines.append("")

        if weekly and 'weekly_report' in data:
            wr = data['weekly_report']
            lines.append("【周报】")
            lines.append(f"  周期: {wr.get('week_start', '')} ~ {wr.get('week_end', '')}")
            lines.append(f"  周号: {wr.get('week_key', '')}")
            lines.append("")

            lines.append(f"  本周新处理: 重命名 {wr.get('renamed_count', 0)} 件 / 合并 {wr.get('merged_count', 0)} 组 / 确认 {wr.get('confirmed_count', 0)} 个字段")
            lines.append("")

            lines.append(f"  本周新确认补录 ({wr.get('confirmed_count', 0)} 个字段)")
            for item in wr.get('confirmed_files', [])[:10]:
                filename = item.get('filename', '')
                field = item.get('field', '')
                value = item.get('value', '')
                field_cn = {'interviewee': '受访者', 'date': '日期', 'topic': '主题'}.get(field, field)
                lines.append(f"    - {filename}: {field_cn} → {value}")
            if wr.get('confirmed_count', 0) > 10:
                lines.append(f"    ... 还有 {wr['confirmed_count'] - 10} 条")
            lines.append("")

            lines.append(f"  本周新变完整 ({wr.get('newly_complete_count', 0)} 组)")
            if wr.get('newly_complete'):
                for item in wr['newly_complete'][:10]:
                    interviewee = item.get('interviewee', '未知')
                    date = item.get('date', '未知')
                    topic = item.get('topic', '采访')
                    lines.append(f"    - {interviewee} | {date} | {topic}")
                if len(wr['newly_complete']) > 10:
                    lines.append(f"    ... 还有 {len(wr['newly_complete']) - 10} 组")
            else:
                lines.append("    (本周暂无新增完整分组)")
            lines.append("")

            lines.append(f"  反复卡壳分组 ({wr.get('stuck_count', 0)} 组)")
            if wr.get('stuck_groups'):
                for item in wr['stuck_groups'][:10]:
                    interviewee = item.get('interviewee', '未知')
                    stuck_days = item.get('stuck_days', 0)
                    missing = []
                    if not item.get('has_audio'):
                        missing.append('音频')
                    if not item.get('has_text'):
                        missing.append('文字稿')
                    if item.get('unconfirmed'):
                        missing.append('待确认')
                    missing_str = '、'.join(missing) if missing else '未知'
                    lines.append(f"    - {interviewee}: 卡壳 {stuck_days} 天 (缺{missing_str})")
                if len(wr['stuck_groups']) > 10:
                    lines.append(f"    ... 还有 {len(wr['stuck_groups']) - 10} 组")
            else:
                lines.append("    (暂无反复卡壳的分组)")
            lines.append("")

            lines.append(f"  当前仍缺件分组 ({wr.get('missing_count', 0)} 组)")
            for item in wr.get('missing_groups', [])[:10]:
                group_name = item.get('group_name', '')
                missing_desc = item.get('missing', '')
                lines.append(f"    - {group_name}: 缺{missing_desc}")
            if wr.get('missing_count', 0) > 10:
                lines.append(f"    ... 还有 {wr['missing_count'] - 10} 组")
            lines.append("")

            lines.append(f"  当前待确认素材: {wr.get('unconfirmed_count', 0)} 件")
            lines.append("")

        lines.append("【问题清单】")
        errors = data['问题清单']

        lines.append(f"  空文件: {len(errors['空文件'])} 个")
        for item in errors['空文件'][:5]:
            lines.append(f"    - {item['文件']}")
        if len(errors['空文件']) > 5:
            lines.append(f"    ... 还有 {len(errors['空文件']) - 5} 个")

        lines.append(f"  重复文件组: {len(errors['重复文件'])} 组")
        for group in errors['重复文件'][:3]:
            lines.append(f"    - {group['文件数']} 个重复文件，大小: {group['大小']}")
            for fp in group['文件列表']:
                lines.append(f"      * {fp}")
        if len(errors['重复文件']) > 3:
            lines.append(f"    ... 还有 {len(errors['重复文件']) - 3} 组")

        if errors.get('跳过文件'):
            lines.append(f"  跳过文件: {len(errors['跳过文件'])} 个")
            for item in errors['跳过文件']:
                reason = f" - {item['原因']}" if item['原因'] else ""
                conflict = f" (冲突: {os.path.basename(item['冲突文件'])})" if item.get('冲突文件') else ""
                lines.append(f"    - {os.path.basename(item['原文件'])}{reason}{conflict}")

        if errors.get('重命名失败'):
            lines.append(f"  重命名失败: {len(errors['重命名失败'])} 个")
            for item in errors['重命名失败']:
                lines.append(f"    - {os.path.basename(item['原文件'])} -> {os.path.basename(item['目标文件'])}: {item['错误']}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)
