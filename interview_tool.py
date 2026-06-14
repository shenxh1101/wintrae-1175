"""采访素材整理工具 - 入口脚本

可以直接运行: python interview_tool.py
或者安装为命令后运行: interview-tool
"""

import sys
from interview_tool.cli import main

if __name__ == '__main__':
    sys.exit(main())
