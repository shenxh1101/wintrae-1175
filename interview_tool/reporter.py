"""报告生成模块 - 生成统计报告、错误清单等"""

import os
import json
from datetime import datetime
from collections import defaultdict

from .utils import format_duration, format_file_size, normalize_basename_for_pairing, get_pairing_key, extract_topic_from_filename
from .state import StateManager


class InterviewGroup:
    """同一场采访的分组信息"""
    
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
    """报告生成器"""
    
    def __init__(self, scan_result=None, state_manager=None):
        self.scan_result = scan_result
        self.state_manager = state_manager
        self.errors = []
        self.warnings = []
        self._interview_groups = None
    
    def add_error(self, message, filepath=None, error_type="error"):
        """添加错误记录"""
        self.errors.append({
            'type': error_type,
            'message': message,
            'filepath': filepath,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_warning(self, message, filepath=None):
        """添加警告记录"""
        self.warnings.append({
            'message': message,
            'filepath': filepath,
            'timestamp': datetime.now().isoformat()
        })
    
    def _build_interview_groups(self, scan_result=None):
        """
        构建采访分组，将同一场采访的音频和文字稿归为一组
        
        基于配对键（日期+受访者+主题）进行分组
        """
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
                groups[key] = InterviewGroup(
                    pairing_key=key,
                    interviewee=f.interviewee,
                    date=f.date,
                    topic=extract_topic_from_filename(f.filename)
                )
            
            group = groups[key]
            
            # 更新组信息（确保有值的信息覆盖空值）
            if f.interviewee and not group.interviewee:
                group.interviewee = f.interviewee
            if f.date and not group.date:
                group.date = f.date
            
            if f.is_audio:
                group.audio_files.append(f)
            elif f.is_text:
                group.text_files.append(f)
            elif f.is_subtitle:
                group.subtitle_files.append(f)
        
        self._interview_groups = groups
        return groups
    
    def get_interview_groups(self, scan_result=None):
        """获取采访分组列表"""
        if self._interview_groups is None:
            self._build_interview_groups(scan_result)
        return self._interview_groups
    
    def generate_summary(self, scan_result=None):
        """
        生成摘要统计
        
        Args:
            scan_result: 扫描结果，可选
        
        Returns:
            摘要字典
        """
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
        """
        查找缺失的配对文件（有音频无文字稿，或有文字稿无音频）
        
        基于采访分组进行智能匹配，避免后缀差异导致的误报
        """
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
        """格式化分组名称用于显示"""
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
        """
        生成整理进度报告
        
        从持久化状态文件读取真实进度
        """
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
            }
        }
        
        if interview_states:
            progress['各采访分组状态'] = interview_states
        
        return progress
    
    def generate_error_list(self, scan_result=None):
        """
        生成错误/问题清单
        
        Returns:
            问题清单字典
        """
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
        """生成采访分组详情"""
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
    
    def generate_full_report(self, scan_result=None, output_path=None, format='text'):
        """
        生成完整报告
        
        Args:
            scan_result: 扫描结果
            output_path: 输出文件路径（可选）
            format: 输出格式 'text' 或 'json'
        
        Returns:
            报告内容
        """
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")
        
        summary = self.generate_summary(result)
        missing_pairs = self.find_missing_pairs(result)
        errors = self.generate_error_list(result)
        progress = self.generate_progress_report(result)
        group_details = self.generate_interview_groups_detail(result)
        
        report_data = {
            '摘要': summary,
            '进度': progress,
            '采访分组': group_details,
            '缺失配对': missing_pairs,
            '问题清单': errors,
        }
        
        if format == 'json':
            report_content = json.dumps(report_data, ensure_ascii=False, indent=2)
        else:
            report_content = self._format_text_report(report_data)
        
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
        
        return report_content
    
    def _format_text_report(self, data):
        """将报告数据格式化为文本"""
        lines = []
        lines.append("=" * 70)
        lines.append("采访素材整理报告")
        lines.append("=" * 70)
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
