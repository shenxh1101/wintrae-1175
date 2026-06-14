"""报告生成模块 - 生成统计报告、错误清单等"""

import os
import json
from datetime import datetime
from collections import defaultdict

from .utils import format_duration, format_file_size


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, scan_result=None):
        self.scan_result = scan_result
        self.errors = []
        self.warnings = []
    
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
        
        total_duration = result.total_audio_duration
        
        interviewees = set()
        for f in result.files:
            if f.interviewee:
                interviewees.add(f.interviewee)
        
        dates = set()
        for f in result.files:
            if f.date:
                dates.add(f.date.date().isoformat())
        
        duplicate_count = sum(len(files) for files in result.duplicates.values())
        duplicate_group_count = len(result.duplicates)
        
        summary = {
            '基本信息': {
                '扫描目录数': len(result.directories),
                '总文件数': result.total_files,
                '总大小': format_file_size(result.total_size),
                '扫描时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
        
        基于文件名匹配
        """
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")
        
        audio_basenames = {}
        text_basenames = {}
        
        for f in result.audio_files:
            base = os.path.splitext(f.filename)[0]
            audio_basenames[base] = f.filepath
        
        for f in result.text_files:
            base = os.path.splitext(f.filename)[0]
            text_basenames[base] = f.filepath
        
        missing_text = []
        missing_audio = []
        
        for base, path in audio_basenames.items():
            if base not in text_basenames:
                missing_text.append((base, path))
        
        for base, path in text_basenames.items():
            if base not in audio_basenames:
                missing_audio.append((base, path))
        
        return {
            '有音频无文字稿': missing_text,
            '有文字稿无音频': missing_audio,
        }
    
    def generate_progress_report(self, scan_result=None, rename_completed=False, merge_completed=False):
        """
        生成整理进度报告
        
        Args:
            scan_result: 扫描结果
            rename_completed: 重命名是否完成
            merge_completed: 合并是否完成
        
        Returns:
            进度报告字典
        """
        result = scan_result or self.scan_result
        if result is None:
            raise ValueError("未提供扫描结果")
        
        named_files = 0
        total_files = result.total_files
        
        for f in result.files:
            if f.date and f.interviewee:
                named_files += 1
        
        naming_progress = (named_files / total_files * 100) if total_files > 0 else 0
        
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
                '已规范文件': named_files,
                '总文件数': total_files,
            },
            '步骤状态': {
                '扫描': '已完成',
                '重命名': '已完成' if rename_completed else '待处理',
                '合并': '已完成' if merge_completed else '待处理',
            }
        }
        
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
            '无法识别的文件': [],
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
        
        return errors
    
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
        
        report_data = {
            '摘要': summary,
            '进度': progress,
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
        lines.append("=" * 60)
        lines.append("采访素材整理报告")
        lines.append("=" * 60)
        lines.append("")
        
        lines.append("【基本信息】")
        for k, v in data['摘要']['基本信息'].items():
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
        lines.append(f"  命名规范化: {data['进度']['命名规范化进度']['百分比']}")
        for step, status in data['进度']['步骤状态'].items():
            lines.append(f"    {step}: {status}")
        lines.append("")
        
        lines.append("【缺失配对】")
        missing = data['缺失配对']
        lines.append(f"  有音频无文字稿: {len(missing['有音频无文字稿'])} 个")
        for name, path in missing['有音频无文字稿'][:5]:
            lines.append(f"    - {name}")
        if len(missing['有音频无文字稿']) > 5:
            lines.append(f"    ... 还有 {len(missing['有音频无文字稿']) - 5} 个")
        
        lines.append(f"  有文字稿无音频: {len(missing['有文字稿无音频'])} 个")
        for name, path in missing['有文字稿无音频'][:5]:
            lines.append(f"    - {name}")
        if len(missing['有文字稿无音频']) > 5:
            lines.append(f"    ... 还有 {len(missing['有文字稿无音频']) - 5} 个")
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
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
