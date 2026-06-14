"""文件命名规则模块"""

import re
import os
from pathlib import Path
from datetime import datetime

from .utils import safe_filename, parse_date_from_filename, extract_interviewee_from_filename

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
            topic_val = topic or "采访"
        
        name = self.pattern.format(
            date=date_str,
            interviewee=interviewee_val,
            topic=topic_val,
            index=str(index).zfill(self.index_padding),
            original=stem
        )
        
        return safe_filename(name) + ext

class Renamer:
    """批量重命名执行器"""
    
    def __init__(self, rule=None):
        self.rule = rule or NamingRule()
        self.rename_plan = []
        self.conflicts = []
    
    def plan_rename(self, files, group_by=None):
        """
        制定重命名计划
        
        Args:
            files: 文件路径列表或 FileInfo 对象列表
            group_by: 分组方式，可选 'interviewee', 'date', 'extension'
        
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
                else:
                    key = 'default'
                groups.setdefault(key, []).append(f)
            
            self.rename_plan = []
            for key, group_files in groups.items():
                group_files.sort(key=lambda x: x.filename)
                for idx, f in enumerate(group_files, 1):
                    new_name = self.rule.generate_name(
                        f.filename,
                        index=idx,
                        date=f.date,
                        interviewee=f.interviewee
                    )
                    old_path = f.filepath
                    new_path = os.path.join(os.path.dirname(old_path), new_name)
                    self.rename_plan.append((old_path, new_name, new_path))
        else:
            file_list.sort(key=lambda x: x.filename)
            self.rename_plan = []
            for idx, f in enumerate(file_list, 1):
                new_name = self.rule.generate_name(
                    f.filename,
                    index=idx,
                    date=f.date,
                    interviewee=f.interviewee
                )
                old_path = f.filepath
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                self.rename_plan.append((old_path, new_name, new_path))
        
        self._check_conflicts()
        return self.rename_plan
    
    def _check_conflicts(self):
        """检查命名冲突"""
        self.conflicts = []
        target_paths = {}
        for old_path, new_name, new_path in self.rename_plan:
            if new_path in target_paths:
                self.conflicts.append((target_paths[new_path], old_path, new_path))
            else:
                target_paths[new_path] = old_path
            
            if os.path.exists(new_path) and new_path != old_path:
                if new_path not in [c[2] for c in self.conflicts]:
                    self.conflicts.append((old_path, new_path, "目标文件已存在"))
    
    def execute(self, dry_run=False):
        """
        执行重命名
        
        Args:
            dry_run: 是否为试运行（只打印不执行）
        
        Returns:
            执行结果列表 [(old_path, new_path, success, error_message), ...]
        """
        results = []
        for old_path, new_name, new_path in self.rename_plan:
            if old_path == new_path:
                results.append((old_path, new_path, True, "文件名未变化"))
                continue
            
            if dry_run:
                results.append((old_path, new_path, True, "[试运行] 将重命名"))
                continue
            
            try:
                if os.path.exists(new_path):
                    results.append((old_path, new_path, False, "目标文件已存在"))
                    continue
                
                os.rename(old_path, new_path)
                results.append((old_path, new_path, True, ""))
            except Exception as e:
                results.append((old_path, new_path, False, str(e)))
        
        return results
