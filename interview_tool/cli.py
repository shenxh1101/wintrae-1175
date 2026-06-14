"""命令行接口 (CLI)"""

import argparse
import sys
import os

from . import __version__
from .commands import cmd_scan, cmd_rename, cmd_merge, cmd_report


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='interview-tool',
        description='采访素材整理工具 - 批量整理采访录音和文字稿',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流程:
  1. scan   查看素材概况
  2. rename 先 --export-plan 导出清单确认，再 --from-plan 执行
  3. merge  按受访者/日期/主题分组合并，生成采访提要
  4. report 查看整理进度和缺失项

示例:
  interview-tool scan ./素材目录
  interview-tool scan ./素材目录 --detail
  
  # 重命名流程
  interview-tool rename ./素材目录 --export-plan rename_plan.json
  interview-tool rename ./素材目录 --from-plan rename_plan.json
  interview-tool rename ./素材目录 --date 2024-01-15 --interviewee 张三 --group-by interviewee
  interview-tool rename ./素材目录 --pattern "{date}_{interviewee}_采访_{index}" --dry-run
  
  # 合并流程
  interview-tool merge ./素材目录 --group-by interviewee
  interview-tool merge ./素材目录 --group-by topic
  interview-tool merge ./素材目录 --output 合并稿.txt
  
  # 报告
  interview-tool report ./素材目录
  interview-tool report ./素材目录 --output 报告.txt --format json
        """
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    
    subparsers = parser.add_subparsers(
        dest='command',
        title='命令',
        description='可用的命令'
    )
    
    _add_scan_parser(subparsers)
    _add_rename_parser(subparsers)
    _add_merge_parser(subparsers)
    _add_report_parser(subparsers)
    
    return parser


def _add_scan_parser(subparsers):
    """添加 scan 命令解析器"""
    scan_parser = subparsers.add_parser(
        'scan',
        help='扫描目录，查看素材概况',
        description='扫描目录中的采访相关文件，显示文件列表、音频时长、空文件、重复文件等信息'
    )
    
    scan_parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='要扫描的目录路径（默认当前目录）'
    )
    
    scan_parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归扫描子目录'
    )
    
    scan_parser.add_argument(
        '--no-hash',
        action='store_true',
        help='不计算文件哈希（跳过重复文件检测，速度更快）'
    )
    
    scan_parser.add_argument(
        '--detail',
        action='store_true',
        help='显示详细文件列表'
    )
    
    scan_parser.set_defaults(func=cmd_scan)


def _add_rename_parser(subparsers):
    """添加 rename 命令解析器"""
    rename_parser = subparsers.add_parser(
        'rename',
        help='按规则批量重命名文件',
        description='按规则批量重命名采访文件，支持清单导出/导入、日期补全、受访者标签、分组序号',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 1. 导出重命名清单供团队确认
  interview-tool rename ./素材 --export-plan plan.json
  
  # 2. 根据确认后的清单执行
  interview-tool rename ./素材 --from-plan plan.json
  
  # 3. 直接指定规则执行
  interview-tool rename ./素材 --date 2024-01-15 --interviewee 张三
  interview-tool rename ./素材 --group-by interviewee --dry-run
        """
    )
    
    rename_parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='要处理的目录路径（默认当前目录）'
    )
    
    rename_parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归处理子目录'
    )
    
    rename_parser.add_argument(
        '--pattern',
        default=None,
        help='''命名模板，支持占位符：
{date} - 日期
{interviewee} - 受访者
{topic} - 主题
{index} - 序号
{original} - 原文件名
默认: "{date}_{interviewee}_{topic}_{index}"'''
    )
    
    rename_parser.add_argument(
        '--date',
        default=None,
        help='强制设置日期（格式：YYYY-MM-DD），用于批量补全日期'
    )
    
    rename_parser.add_argument(
        '--interviewee',
        default=None,
        help='强制设置受访者姓名，用于批量补全受访者标签'
    )
    
    rename_parser.add_argument(
        '--topic',
        default=None,
        help='强制设置主题（默认从文件名提取或"采访"）'
    )
    
    rename_parser.add_argument(
        '--group-by',
        default=None,
        choices=['interviewee', 'date', 'extension', 'topic'],
        help='分组方式，每组单独编号'
    )
    
    rename_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行，只显示计划不实际执行'
    )
    
    rename_parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='自动确认，不提示'
    )
    
    rename_parser.add_argument(
        '--export-plan',
        default=None,
        metavar='JSON_FILE',
        help='导出重命名清单到 JSON 文件（不执行），供团队确认'
    )
    
    rename_parser.add_argument(
        '--from-plan',
        default=None,
        metavar='JSON_FILE',
        help='从导出的 JSON 清单中加载计划并执行'
    )
    
    rename_parser.add_argument(
        '--export-report',
        default=None,
        metavar='JSON_FILE',
        help='导出执行结果报告到 JSON 文件'
    )
    
    rename_parser.add_argument(
        '--no-skip-on-conflict',
        action='store_true',
        help='遇到命名冲突时报错而非跳过'
    )
    
    rename_parser.set_defaults(func=cmd_rename)


def _add_merge_parser(subparsers):
    """添加 merge 命令解析器"""
    merge_parser = subparsers.add_parser(
        'merge',
        help='合并零散的文字稿',
        description='将多个零散的文字稿片段合并为完整文件，支持片段排序、采访提要、按主题分组',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 按受访者分组合并，生成采访提要
  interview-tool merge ./素材 --group-by interviewee
  
  # 按主题分组合并
  interview-tool merge ./素材 --group-by topic
  
  # 按日期分组合并
  interview-tool merge ./素材 --group-by date
  
  # 手动合并所有文字稿
  interview-tool merge ./素材 --output 合并稿.txt
        """
    )
    
    merge_parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='要处理的目录路径（默认当前目录）'
    )
    
    merge_parser.add_argument(
        '-o', '--output',
        default=None,
        help='输出文件路径（默认在输入目录生成）'
    )
    
    merge_parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归处理子目录'
    )
    
    merge_parser.add_argument(
        '--no-separator',
        action='store_true',
        help='不在片段间添加分隔线'
    )
    
    merge_parser.add_argument(
        '--no-filename',
        action='store_true',
        help='不在每个片段前添加文件名标题'
    )
    
    merge_parser.add_argument(
        '--group-by',
        default=None,
        choices=['interviewee', 'date', 'topic'],
        help='按受访者/日期/主题分组合并'
    )
    
    merge_parser.add_argument(
        '--summary-length',
        type=int,
        default=200,
        help='摘要长度（字符数），设为0禁用摘要'
    )
    
    merge_parser.add_argument(
        '--no-brief',
        action='store_true',
        help='不在合并稿开头添加采访提要'
    )
    
    merge_parser.set_defaults(func=cmd_merge)


def _add_report_parser(subparsers):
    """添加 report 命令解析器"""
    report_parser = subparsers.add_parser(
        'report',
        help='生成统计报告',
        description='生成素材整理统计报告，包括缺失项、重复项、整理进度等'
    )
    
    report_parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='要分析的目录路径（默认当前目录）'
    )
    
    report_parser.add_argument(
        '-o', '--output',
        default=None,
        help='输出报告文件路径'
    )
    
    report_parser.add_argument(
        '-f', '--format',
        default='text',
        choices=['text', 'json'],
        help='报告格式（默认 text）'
    )
    
    report_parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归处理子目录'
    )
    
    report_parser.set_defaults(func=cmd_report)


def main(args=None):
    """主入口函数"""
    parser = create_parser()
    
    if args is None:
        args = sys.argv[1:]
    
    if not args:
        parser.print_help()
        return 0
    
    parsed_args = parser.parse_args(args)
    
    if hasattr(parsed_args, 'func'):
        try:
            return parsed_args.func(parsed_args)
        except KeyboardInterrupt:
            print("\n操作已取消")
            return 130
        except Exception as e:
            print(f"错误: {e}")
            return 1
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
