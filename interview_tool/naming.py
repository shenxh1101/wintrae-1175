"""文件命名规则模块"""

import re
import os
import json
from pathlib import Path
from datetime import datetime

from .utils import safe_filename, parse_date_from_filename, extract_interviewee_from_filename, extract_topic_from_filename
from .state import StateManager


class NamingRule:
    """命名规则配置"""
    
    DEFAULT_PATTERN = "{date}_{interviewee}_{topic}_{index}"
    
    def __init__(self, pattern=None, date_format="%Y%m%d", index_padding=2):
        """
        初始化命名规则
        
        Args:
            pattern: 文件名模板，支持占位符：{date}, {interviewee}, {topic}, {index}, {original}
            date_format: 日期格式
            index_padding: 序号补零位数
        """
        self.pattern = pattern or self.DEFAULT_PATTERN
        self.date_format = date_format
        self.index_padding = index_padding
        self.date_override = None
        self.interviewee_override = None
        self.topic_override = None
    
    def set_date(self, date_str):
        """设置强制日期"""
        if isinstance(date_str, str):
            self.date_override = datetime.strptime(date_str, "%Y-%m-%d")
        elif isinstance(date_str, datetime):
            self.date_override = date_str
    
    def set_interviewee(self, interviewee):
        """设置强制受访者"""
        self.interviewee_override = interviewee
    
    def set_topic(self, topic):
        """设置强制主题"""
        self.topic_override = topic
    
    def generate_name(self, original_filename, index=1, date=None, interviewee=None, topic=None):
        """
        生成新文件名
        
        Args:
            original_filename: 原文件名
            index: 序号
            date: 日期（datetime 对象或字符串）
            interviewee: 受访者
            topic: 主题
        
        Returns:
            新文件名（含扩展名）
        """
        ext = Path(original_filename).suffix
        stem = Path(original_filename).stem
        
        date_obj = self.date_override
        if date_obj is None:
            if isinstance(date, datetime):
                date_obj = date
            elif isinstance(date, str):
                date_obj = parse_date_from_filename(date)
            else:
                date_obj = parse_date_from_filename(stem)
        
        date_str = date_obj.strftime(self.date_format) if date_obj else "未知日期"
        
        interviewee_val = self.interviewee_override
        if interviewee_val is None:
            interviewee_val = interviewee or extract_interviewee_from_filename(stem) or "未知受访者"
        
        topic_val = self.topic_override
        if topic_val is None:
            topic_val = topic or extract_topic_from_filename(original_filename)
        
        name = self.pattern.format(
            date=date_str,
            interviewee=interviewee_val,
            topic=topic_val,
            index=str(index).zfill(self.index_padding),
            original=stem
        )
        
        return safe_filename(name) + ext
    
    def to_dict(self):
        """导出规则配置为字典"""
        return {
            'pattern': self.pattern,
            'date_format': self.date_format,
            'index_padding': self.index_padding,
            'date_override': self.date_override.isoformat() if self.date_override else None,
            'interviewee_override': self.interviewee_override,
            'topic_override': self.topic_override,
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建规则配置"""
        rule = cls(
            pattern=data.get('pattern'),
            date_format=data.get('date_format', '%Y%m%d'),
            index_padding=data.get('index_padding', 2)
        )
        if data.get('date_override'):
            rule.date_override = datetime.fromisoformat(data['date_override'])
        rule.interviewee_override = data.get('interviewee_override')
        rule.topic_override = data.get('topic_override')
        return rule


class Renamer:
    """批量重命名执行器"""
    
    def __init__(self, rule=None, state_manager=None):
        self.rule = rule or NamingRule()
        self.state_manager = state_manager
        self.rename_plan = []
        self.conflicts = []
        self.skipped = []
        self.executed_results = []
    
    def plan_rename(self, files, group_by=None):
        """
        制定重命名计划
        
        Args:
            files: 文件路径列表或 FileInfo 对象列表
            group_by: 分组方式，可选 'interviewee', 'date', 'extension', 'topic'
        
        Returns:
            重命名计划列表 [(old_path, new_name, new_path), ...]
        """
        from .scanner import FileInfo
        
        file_list = []
        for f in files:
            if isinstance(f, FileInfo):
                file_list.append(f)
            else:
                file_list.append(FileInfo(f))
        
        if group_by:
            groups = {}
            for f in file_list:
                if group_by == 'interviewee':
                    key = f.interviewee or '未知受访者'
                elif group_by == 'date':
                    key = f.date.isoformat() if f.date else '未知日期'
                elif group_by == 'extension':
                    key = f.extension
                elif group_by == 'topic':
                    key = extract_topic_from_filename(f.filename)
                else:
                    key = 'default'
                groups.setdefault(key, []).append(f)
            
            self.rename_plan = []
            for key, group_files in groups.items():
                group_files.sort(key=lambda x: x.filename)
                for idx, f in enumerate(group_files, 1):
                    topic = extract_topic_from_filename(f.filename)
                    new_name = self.rule.generate_name(
                        f.filename,
                        index=idx,
                        date=f.date,
                        interviewee=f.interviewee,
                        topic=topic
                    )
                    old_path = f.filepath
                    new_path = os.path.join(os.path.dirname(old_path), new_name)
                    self.rename_plan.append({
                        'old_path': old_path,
                        'new_name': new_name,
                        'new_path': new_path,
                        'interviewee': f.interviewee,
                        'date': f.date.isoformat() if f.date else None,
                        'topic': topic,
                        'group': key,
                        'index': idx,
                        'file_size': f.size,
                        'is_audio': f.is_audio,
                        'is_text': f.is_text,
                    })
        else:
            file_list.sort(key=lambda x: x.filename)
            self.rename_plan = []
            for idx, f in enumerate(file_list, 1):
                topic = extract_topic_from_filename(f.filename)
                new_name = self.rule.generate_name(
                    f.filename,
                    index=idx,
                    date=f.date,
                    interviewee=f.interviewee,
                    topic=topic
                )
                old_path = f.filepath
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                self.rename_plan.append({
                    'old_path': old_path,
                    'new_name': new_name,
                    'new_path': new_path,
                    'interviewee': f.interviewee,
                    'date': f.date.isoformat() if f.date else None,
                    'topic': topic,
                    'group': 'default',
                    'index': idx,
                    'file_size': f.size,
                    'is_audio': f.is_audio,
                    'is_text': f.is_text,
                })
        
        self._check_conflicts()
        return self.rename_plan
    
    def _check_conflicts(self):
        """检查命名冲突"""
        self.conflicts = []
        target_paths = {}
        
        for item in self.rename_plan:
            old_path = item['old_path']
            new_path = item['new_path']
            
            if new_path in target_paths:
                conflict = {
                    'type': 'plan_conflict',
                    'files': [target_paths[new_path], old_path],
                    'target_path': new_path,
                    'message': '计划内重名冲突'
                }
                self.conflicts.append(conflict)
            else:
                target_paths[new_path] = old_path
            
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
                existing_conflict = next((c for c in self.conflicts if c['target_path'] == new_path), None)
                if not existing_conflict:
                    conflict = {
                        'type': 'exists_conflict',
                        'old_path': old_path,
                        'target_path': new_path,
                        'message': '目标文件已存在'
                    }
                    self.conflicts.append(conflict)
    
    def export_plan(self, output_path):
        """
        导出重命名清单为 JSON 文件，供团队确认
        
        Args:
            output_path: 输出文件路径
        
        Returns:
            导出的清单字典
        """
        plan_data = {
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'rule': self.rule.to_dict(),
            'summary': {
                'total_files': len(self.rename_plan),
                'conflicts': len(self.conflicts),
                'to_rename': sum(1 for p in self.rename_plan if p['old_path'] != p['new_path']),
                'unchanged': sum(1 for p in self.rename_plan if p['old_path'] == p['new_path']),
            },
            'conflicts': self.conflicts,
            'plan': self.rename_plan,
        }
        
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)
        
        return plan_data
    
    def load_plan(self, plan_path):
        """
        从 JSON 文件加载重命名清单
        
        Args:
            plan_path: 清单文件路径
        
        Returns:
            加载的计划列表
        """
        with open(plan_path, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        self.rule = NamingRule.from_dict(plan_data.get('rule', {}))
        self.rename_plan = plan_data.get('plan', [])
        self.conflicts = plan_data.get('conflicts', [])
        
        return self.rename_plan
    
    def execute(self, dry_run=False, skip_on_conflict=True):
        """
        执行重命名
        
        Args:
            dry_run: 是否为试运行（只打印不执行）
            skip_on_conflict: 遇到冲突时是否跳过（否则报错）
        
        Returns:
            执行结果字典，包含成功、失败、跳过列表
        """
        if self.state_manager and not dry_run:
            self.state_manager.mark_rename_started()
        
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'unchanged': [],
        }
        
        conflict_targets = set()
        for c in self.conflicts:
            if c['type'] == 'exists_conflict':
                conflict_targets.add(c['target_path'])
            elif c['type'] == 'plan_conflict':
                for fp in c['files']:
                    conflict_targets.add(fp)
        
        for item in self.rename_plan:
            old_path = item['old_path']
            new_path = item['new_path']
            new_name = item['new_name']
            
            if old_path == new_path:
                results['unchanged'].append({
                    'old_path': old_path,
                    'new_path': new_path,
                    'reason': '文件名未变化'
                })
                continue
            
            if skip_on_conflict and (new_path in conflict_targets or old_path in conflict_targets):
                conflict = next((c for c in self.conflicts 
                               if c.get('target_path') == new_path 
                               or (c.get('type') == 'plan_conflict' and old_path in c.get('files', []))), 
                              None)
                reason = conflict['message'] if conflict else '命名冲突'
                conflict_with = conflict.get('target_path') if conflict else None
                
                skip_record = {
                    'old_path': old_path,
                    'new_path': new_path,
                    'reason': reason,
                    'conflict_with': conflict_with,
                }
                results['skipped'].append(skip_record)
                
                if self.state_manager and not dry_run:
                    self.state_manager.add_skipped_file(old_path, reason, conflict_with)
                
                continue
            
            if dry_run:
                results['success'].append({
                    'old_path': old_path,
                    'new_path': new_path,
                    'dry_run': True
                })
                continue
            
            try:
                if os.path.exists(new_path):
                    results['failed'].append({
                        'old_path': old_path,
                        'new_path': new_path,
                        'error': '目标文件已存在'
                    })
                    if self.state_manager:
                        self.state_manager.add_failed_file(old_path, new_path, '目标文件已存在')
                    continue
                
                os.rename(old_path, new_path)
                
                results['success'].append({
                    'old_path': old_path,
                    'new_path': new_path,
                    'dry_run': False
                })
                
                if self.state_manager:
                    date_obj = datetime.fromisoformat(item['date']) if item.get('date') else None
                    self.state_manager.add_renamed_file(
                        old_path, new_path,
                        interviewee=item.get('interviewee'),
                        date=date_obj
                    )
                
            except Exception as e:
                results['failed'].append({
                    'old_path': old_path,
                    'new_path': new_path,
                    'error': str(e)
                })
                if self.state_manager:
                    self.state_manager.add_failed_file(old_path, new_path, str(e))
        
        if self.state_manager and not dry_run:
            self.state_manager.mark_rename_completed()
        
        self.executed_results = results
        return results
    
    def export_execution_report(self, output_path):
        """
        导出执行结果报告
        
        Args:
            output_path: 输出文件路径
        """
        if not self.executed_results:
            raise ValueError("尚未执行重命名操作")
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                '总计': len(self.rename_plan),
                '成功': len(self.executed_results['success']),
                '失败': len(self.executed_results['failed']),
                '跳过': len(self.executed_results['skipped']),
                '未变化': len(self.executed_results['unchanged']),
            },
            '成功列表': self.executed_results['success'],
            '失败列表': self.executed_results['failed'],
            '跳过列表': self.executed_results['skipped'],
            '未变化列表': self.executed_results['unchanged'],
        }
        
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report
    
    def format_plan_for_preview(self):
        """
        格式化计划为易读的预览文本，用于打印或导出确认
        
        Returns:
            格式化的预览文本
        """
        lines = []
        lines.append("=" * 80)
        lines.append("重命名清单预览")
        lines.append("=" * 80)
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"文件总数: {len(self.rename_plan)}")
        lines.append(f"冲突数: {len(self.conflicts)}")
        lines.append("")
        
        current_group = None
        for i, item in enumerate(self.rename_plan, 1):
            if item['group'] != current_group:
                current_group = item['group']
                lines.append(f"\n【分组: {current_group}】")
                lines.append("-" * 80)
            
            old_name = os.path.basename(item['old_path'])
            new_name = item['new_name']
            status = " [不变]" if old_name == new_name else ""
            
            has_conflict = any(c.get('target_path') == item['new_path'] or 
                             (c.get('type') == 'plan_conflict' and item['old_path'] in c.get('files', []))
                             for c in self.conflicts)
            conflict_mark = " [冲突]" if has_conflict else ""
            
            file_type = "音频" if item.get('is_audio') else ("文字稿" if item.get('is_text') else "其他")
            
            lines.append(f"{i:>3}. {old_name}")
            lines.append(f"     -> {new_name}{status}{conflict_mark}")
            lines.append(f"     类型: {file_type} | 受访者: {item.get('interviewee', '未知')} | 日期: {item.get('date', '未知')}")
        
        if self.conflicts:
            lines.append("\n")
            lines.append("【冲突详情】")
            lines.append("-" * 80)
            for i, c in enumerate(self.conflicts, 1):
                if c['type'] == 'exists_conflict':
                    lines.append(f"{i}. 目标文件已存在:")
                    lines.append(f"   源文件: {os.path.basename(c['old_path'])}")
                    lines.append(f"   目标: {c['target_path']}")
                else:
                    lines.append(f"{i}. 计划内重名冲突:")
                    lines.append(f"   冲突文件: {', '.join(os.path.basename(f) for f in c['files'])}")
                    lines.append(f"   目标: {c['target_path']}")
        
        lines.append("\n" + "=" * 80)
        return "\n".join(lines)
