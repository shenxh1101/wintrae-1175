"""验证脚本 - 测试所有命令是否正常工作"""

import os
import sys
import subprocess
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_SCRIPT = os.path.join(SCRIPT_DIR, 'interview_tool.py')
TEST_DATA_SCRIPT = os.path.join(SCRIPT_DIR, 'generate_test_data.py')
TEST_DIR = os.path.join(SCRIPT_DIR, 'test_samples')


def run_command(args):
    """运行命令并返回结果"""
    cmd = [sys.executable, TOOL_SCRIPT] + args
    print(f"\n$ {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)
    
    print("-" * 60)
    print(f"返回码: {result.returncode}")
    
    return result


def main():
    print("=" * 60)
    print("采访素材整理工具 - 功能验证")
    print("=" * 60)
    
    # 生成测试数据
    print("\n【步骤1】生成测试数据")
    result = subprocess.run(
        [sys.executable, TEST_DATA_SCRIPT],
        capture_output=True, text=True, cwd=SCRIPT_DIR
    )
    if result.returncode != 0:
        print("生成测试数据失败")
        print(result.stderr)
        return 1
    print(result.stdout)
    
    # 测试 scan 命令
    print("\n【步骤2】测试 scan 命令 - 基础扫描")
    run_command(['scan', 'test_samples'])
    
    print("\n【步骤3】测试 scan 命令 - 详细模式")
    run_command(['scan', 'test_samples', '--detail'])
    
    # 测试 merge 命令
    print("\n【步骤4】测试 merge 命令 - 合并李四的片段")
    lisi_dir = os.path.join('test_samples')
    run_command(['merge', 'test_samples', '--output', 'test_samples/李四_合并测试.txt', '--no-recursive'])
    
    print("\n【步骤5】测试 merge 命令 - 分组合并")
    run_command(['merge', 'test_samples', '--group-by', 'interviewee', '--output', 'test_samples/merged'])
    
    # 测试 rename 命令（试运行）
    print("\n【步骤6】测试 rename 命令 - 试运行")
    run_command(['rename', 'test_samples', '--dry-run', '--date', '2024-01-01', '--pattern', '{date}_{interviewee}_采访_{index}'])
    
    print("\n【步骤7】测试 rename 命令 - 按受访者分组")
    run_command(['rename', 'test_samples', '--dry-run', '--group-by', 'interviewee'])
    
    # 测试 report 命令
    print("\n【步骤8】测试 report 命令 - 文本格式")
    run_command(['report', 'test_samples'])
    
    print("\n【步骤9】测试 report 命令 - JSON 格式")
    run_command(['report', 'test_samples', '--format', 'json', '--output', 'test_samples/report.json'])
    
    # 测试帮助
    print("\n【步骤10】测试帮助信息")
    run_command(['--help'])
    
    print("\n【步骤11】测试 scan 命令帮助")
    run_command(['scan', '--help'])
    
    print("\n" + "=" * 60)
    print("验证完成！")
    print("=" * 60)
    
    # 清理
    print("\n是否保留测试数据？(Y/n): ", end='')
    try:
        response = input().strip().lower()
    except EOFError:
        response = 'y'
    
    if response == 'n':
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
        print("测试数据已清理")
    else:
        print(f"测试数据保存在: {TEST_DIR}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
