"""测试数据生成脚本

生成模拟的采访素材文件，用于测试工具功能
"""

import os
import sys
import struct
import wave
import random
from pathlib import Path

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'test_samples')


def create_wav_file(filepath, duration_seconds=5, sample_rate=44100):
    """创建一个简单的 WAV 音频文件"""
    num_samples = int(duration_seconds * sample_rate)
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        samples = []
        for i in range(num_samples):
            sample = int(32767 * 0.3 * (i % 1000 < 500))
            samples.append(struct.pack('<h', sample))
        
        wav_file.writeframes(b''.join(samples))
    
    return filepath


def create_text_file(filepath, content):
    """创建文本文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


def create_empty_file(filepath):
    """创建空文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        pass
    return filepath


def generate_test_data():
    """生成测试数据"""
    
    sample_dir = SAMPLE_DIR
    
    if os.path.exists(sample_dir):
        import shutil
        shutil.rmtree(sample_dir)
    
    os.makedirs(sample_dir, exist_ok=True)
    
    print("正在生成测试数据...")
    
    # 张三 - 完整的采访素材（有日期）
    create_wav_file(os.path.join(sample_dir, '20240115_张三访谈录音.wav'), duration_seconds=30)
    create_text_file(os.path.join(sample_dir, '20240115_张三访谈文字稿.txt'), """
【采访时间】2024年1月15日
【受访者】张三
【采访者】李四

问：请您先做个自我介绍吧。
答：大家好，我是张三，从事互联网行业已经有十年了。

问：您对行业发展有什么看法？
答：我认为未来几年人工智能会深刻改变我们的工作方式...

问：您有什么建议给年轻人？
答：我觉得最重要的是保持学习的热情，不断充实自己...
""".strip())
    
    # 李四 - 多个片段
    create_wav_file(os.path.join(sample_dir, '李四_片段1.wav'), duration_seconds=20)
    create_wav_file(os.path.join(sample_dir, '李四_片段2.wav'), duration_seconds=25)
    create_wav_file(os.path.join(sample_dir, '李四_片段3.wav'), duration_seconds=15)
    
    create_text_file(os.path.join(sample_dir, '李四_片段1.txt'), """
【片段1】开场介绍
受访者：李四
采访者：王五

问：李老师您好，感谢您接受我们的采访。
答：不客气，很高兴能有这个机会。
""".strip())
    
    create_text_file(os.path.join(sample_dir, '李四_片段2.txt'), """
【片段2】行业见解
问：您怎么看待当前的市场环境？
答：整体来说机遇与挑战并存，我们需要...

问：公司未来的发展方向是什么？
答：我们会继续深耕技术研发，同时拓展新的业务领域...
""".strip())
    
    create_text_file(os.path.join(sample_dir, '李四_片段3.txt'), """
【片段3】总结与展望
问：最后想对观众说些什么？
答：希望大家都能找到自己热爱的事业，坚持走下去。谢谢！

【采访结束】
""".strip())
    
    # 王五 - 只有音频，没有文字稿
    create_wav_file(os.path.join(sample_dir, '2024-02-20_王五专访.wav'), duration_seconds=40)
    
    # 赵六 - 只有文字稿，没有音频
    create_text_file(os.path.join(sample_dir, '赵六访谈记录.txt'), """
受访者：赵六
时间：2024年3月1日

问：请谈谈您的创业经历。
答：我是2015年开始创业的，那时候...
""".strip())
    
    # 杂乱命名的文件
    create_wav_file(os.path.join(sample_dir, '录音_001.wav'), duration_seconds=10)
    create_wav_file(os.path.join(sample_dir, 'audio_002.wav'), duration_seconds=12)
    create_text_file(os.path.join(sample_dir, '新建文本文档.txt'), '一些零散的笔记内容...')
    
    # 空文件
    create_empty_file(os.path.join(sample_dir, '空文件.wav'))
    create_empty_file(os.path.join(sample_dir, '空文字稿.txt'))
    
    # 重复文件
    create_text_file(os.path.join(sample_dir, '重复文件_副本1.txt'), '这是一个测试文件，用于检测重复。')
    create_text_file(os.path.join(sample_dir, '重复文件_副本2.txt'), '这是一个测试文件，用于检测重复。')
    
    # 子目录
    sub_dir = os.path.join(sample_dir, '旧采访')
    create_wav_file(os.path.join(sub_dir, '20231201_陈七访谈.wav'), duration_seconds=35)
    create_text_file(os.path.join(sub_dir, '20231201_陈七访谈.txt'), """
【采访记录】
时间：2023年12月1日
受访者：陈七
""".strip())
    
    # 带日期的其他格式
    create_wav_file(os.path.join(sample_dir, '周八_2024-03-15_采访.wav'), duration_seconds=28)
    
    print(f"测试数据已生成到: {sample_dir}")
    print()
    
    # 统计
    total_files = 0
    for root, dirs, files in os.walk(sample_dir):
        total_files += len(files)
    
    print(f"共生成 {total_files} 个测试文件")
    print()
    print("文件列表:")
    for root, dirs, files in os.walk(sample_dir):
        rel_path = os.path.relpath(root, sample_dir)
        if rel_path != '.':
            print(f"  {rel_path}/")
        for f in sorted(files):
            size = os.path.getsize(os.path.join(root, f))
            prefix = "  " if rel_path == '.' else "    "
            print(f"{prefix}{f} ({size} bytes)")
    
    return sample_dir


if __name__ == '__main__':
    generate_test_data()
