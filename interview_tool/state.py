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
            'interviews': {}
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
        
        self._save()
    
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
