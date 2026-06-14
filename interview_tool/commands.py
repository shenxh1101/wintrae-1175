"""命令实现模块"""

import os
import sys
from pathlib import Path

from .scanner import scan_directory
from .naming import NamingRule, Renamer
from .merger import merge_text_files, merge_by_group, sort_segments, extract_summary
from .reporter import ReportGenerator
from .utils import format_duration, format_file_size, is_text_file


def cmd_scan(args):
    """
    执行 scan 命令
    
    扫描目录，显示素材概况：文件列表、音频时长、空文件、重复文件等
    """
    directory = args.directory
    recursive = not args.no_recursive
    compute_hash = not args.no_hash
    
    print(f"正在扫描目录: {directory}")
    if recursive:
        print("模式: 递归扫描")
    else:
        print("模式: 仅当前目录")
    print("-" * 50)
    
    try:
        result = scan_directory(directory, recursive=recursive, compute_hash=compute_hash)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"错误: {e}")
        return 1
    
    print(f"扫描完成，共发现 {result.total_files} 个文件")
    print()
    
    print("【文件分类】")
    print(f"  音频文件: {len(result.audio_files)} 个")
    print(f"  文字稿文件: {len(result.text_files)} 个")
    print(f"  字幕文件: {len(result.subtitle_files)} 个")
    print()
    
    print("【音频总览】")
    print(f"  总时长: {format_duration(result.total_audio_duration)}")
    print(f"  总大小: {format_file_size(sum(f.size for f in result.audio_files))}")
    print()
    
    if args.detail:
        print("【文件详情】")
        all_files = sorted(result.files, key=lambda x: x.filename)
        for i, f in enumerate(all_files, 1):
            file_type = "音频" if f.is_audio else ("文字稿" if f.is_text else "字幕")
            duration_str = f" - {format_duration(f.duration)}" if f.duration else ""
            size_str = format_file_size(f.size)
            empty_str = " [空文件]" if f.is_empty else ""
            
            date_str = f.date.strftime("%Y-%m-%d") if f.date else "未知日期"
            interviewee_str = f.interviewee or "未知受访者"
            
            print(f"  {i:>3}. {f.filename}")
            print(f"       类型: {file_type}{duration_str} | 大小: {size_str}{empty_str}")
            print(f"       日期: {date_str} | 受访者: {interviewee_str}")
        print()
    
    if result.empty_files:
        print("【空文件警告】")
        print(f"  发现 {len(result.empty_files)} 个空文件:")
        for f in result.empty_files:
            print(f"    - {f.filepath}")
        print()
    
    if result.duplicates:
        print("【重复文件警告】")
        dup_count = sum(len(files) for files in result.duplicates.values())
        print(f"  发现 {len(result.duplicates)} 组重复文件，共 {dup_count} 个文件:")
        for h, files in result.duplicates.items():
            print(f"    组 ({h[:8]}...): {len(files)} 个文件")
            for f in files:
                print(f"      - {f.filepath}")
        print()
    
    interviewees = set()
    for f in result.files:
        if f.interviewee:
            interviewees.add(f.interviewee)
    
    if interviewees:
        print("【受访者列表】")
        for name in sorted(interviewees):
            count = sum(1 for f in result.files if f.interviewee == name)
            print(f"  - {name}: {count} 个文件")
        print()
    
    dates = set()
    for f in result.files:
        if f.date:
            dates.add(f.date.date().isoformat())
    
    if dates:
        print("【涉及日期】")
        for d in sorted(dates):
            count = sum(1 for f in result.files if f.date and f.date.date().isoformat() == d)
            print(f"  - {d}: {count} 个文件")
        print()
    
    return 0


def cmd_rename(args):
    """
    执行 rename 命令
    
    按规则批量重命名文件，支持日期补全、受访者标签、分组序号
    """
    directory = args.directory
    recursive = not args.no_recursive
    dry_run = args.dry_run
    pattern = args.pattern
    date_str = args.date
    interviewee = args.interviewee
    topic = args.topic
    group_by = args.group_by
    
    print(f"准备重命名目录: {directory}")
    if dry_run:
        print("模式: 试运行（不会实际修改文件）")
    else:
        print("模式: 执行重命名")
    print("-" * 50)
    
    try:
        result = scan_directory(directory, recursive=recursive, compute_hash=False)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"错误: {e}")
        return 1
    
    print(f"扫描到 {result.total_files} 个文件")
    
    rule = NamingRule(pattern=pattern) if pattern else NamingRule()
    
    if date_str:
        rule.set_date(date_str)
        print(f"强制日期: {date_str}")
    
    if interviewee:
        rule.set_interviewee(interviewee)
        print(f"强制受访者: {interviewee}")
    
    if topic:
        rule.set_topic(topic)
        print(f"强制主题: {topic}")
    
    if group_by:
        print(f"分组方式: {group_by}")
    
    print()
    
    renamer = Renamer(rule)
    
    files_to_rename = result.audio_files + result.text_files + result.subtitle_files
    plan = renamer.plan_rename(files_to_rename, group_by=group_by)
    
    if renamer.conflicts:
        print(f"警告: 发现 {len(renamer.conflicts)} 个命名冲突")
        for conflict in renamer.conflicts:
            print(f"  - {conflict}")
        print()
    
    print("【重命名计划】")
    changed_count = 0
    for i, (old_path, new_name, new_path) in enumerate(plan, 1):
        old_name = os.path.basename(old_path)
        if old_name == new_name:
            status = " [不变]"
        else:
            status = ""
            changed_count += 1
        print(f"  {i:>3}. {old_name} -> {new_name}{status}")
    
    print()
    print(f"共 {len(plan)} 个文件，其中 {changed_count} 个需要重命名")
    
    if changed_count == 0:
        print("没有需要重命名的文件")
        return 0
    
    if not dry_run and not args.yes:
        print()
        response = input("确认执行重命名？(y/N): ")
        if response.lower() != 'y':
            print("已取消")
            return 0
    
    print()
    print("执行中...")
    results = renamer.execute(dry_run=dry_run)
    
    success_count = sum(1 for _, _, success, _ in results if success)
    fail_count = sum(1 for _, _, success, _ in results if not success)
    
    print()
    print("【执行结果】")
    print(f"  成功: {success_count} 个")
    print(f"  失败: {fail_count} 个")
    
    if fail_count > 0:
        print()
        print("【失败详情】")
        for old_path, new_path, success, error in results:
            if not success:
                print(f"  - {os.path.basename(old_path)}: {error}")
    
    return 0 if fail_count == 0 else 1


def cmd_merge(args):
    """
    执行 merge 命令
    
    合并零散的文字稿，支持片段排序、摘要提取
    """
    directory = args.directory
    output = args.output
    recursive = not args.no_recursive
    no_separator = args.no_separator
    no_filename = args.no_filename
    group_by = args.group_by
    summary_length = args.summary_length
    
    print(f"准备合并文字稿，目录: {directory}")
    print("-" * 50)
    
    try:
        result = scan_directory(directory, recursive=recursive, compute_hash=False)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"错误: {e}")
        return 1
    
    text_files = [f.filepath for f in result.text_files]
    
    if not text_files:
        print("未找到文字稿文件")
        return 0
    
    print(f"找到 {len(text_files)} 个文字稿文件")
    
    if group_by:
        print(f"分组方式: {group_by}")
        
        if not output:
            output = directory
        print(f"输出目录: {output}")
        
        if not os.path.exists(output):
            os.makedirs(output, exist_ok=True)
        
        results = merge_by_group(
            text_files,
            output,
            group_by=group_by,
            add_separator=not no_separator,
            add_filename=not no_filename
        )
        
        print()
        print("【合并结果】")
        if results:
            for group_name, output_path, file_count in results:
                print(f"  - {group_name}: 合并了 {file_count} 个文件 -> {os.path.basename(output_path)}")
                
                if summary_length > 0:
                    from .merger import read_text_file
                    content = read_text_file(output_path)
                    summary = extract_summary(content, summary_length)
                    print(f"    摘要: {summary}")
        else:
            print("  没有可合并的分组（每个分组少于2个文件）")
    else:
        sorted_files = sort_segments(text_files)
        
        print()
        print("【合并顺序】")
        for i, f in enumerate(sorted_files, 1):
            print(f"  {i:>3}. {os.path.basename(f)}")
        
        if not output:
            first_file = sorted_files[0]
            base = os.path.splitext(os.path.basename(first_file))[0]
            output = os.path.join(directory, f"{base}_合并.txt")
        
        print()
        print(f"输出文件: {output}")
        
        merged_text = merge_text_files(
            sorted_files,
            output_path=output,
            add_separator=not no_separator,
            add_filename=not no_filename
        )
        
        print(f"合并完成，共 {len(sorted_files)} 个文件")
        
        if summary_length > 0:
            summary = extract_summary(merged_text, summary_length)
            print()
            print("【内容摘要】")
            print(f"  {summary}")
    
    return 0


def cmd_report(args):
    """
    执行 report 命令
    
    生成统计报告，包括缺失项、重复项、整理进度等
    """
    directory = args.directory
    output = args.output
    format_type = args.format
    recursive = not args.no_recursive
    
    print(f"生成报告，目录: {directory}")
    print("-" * 50)
    
    try:
        result = scan_directory(directory, recursive=recursive, compute_hash=True)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"错误: {e}")
        return 1
    
    reporter = ReportGenerator(result)
    
    report_content = reporter.generate_full_report(
        output_path=output,
        format=format_type
    )
    
    print(report_content)
    
    if output:
        print()
        print(f"报告已保存到: {output}")
    
    return 0
