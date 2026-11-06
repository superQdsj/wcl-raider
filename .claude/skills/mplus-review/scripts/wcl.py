#!/usr/bin/env python3
"""Warcraft Logs 大秘境数据工具 —— mplus-review skill 的数据层。

用法：python3 wcl.py <命令> <报告链接或代码> [选项]
      python3 wcl.py --help
只依赖 Python 3.9+ 标准库。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wclr.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
