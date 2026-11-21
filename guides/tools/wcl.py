#!/usr/bin/env python3
"""Warcraft Logs 大秘境数据查询工具（职业攻略制作的数据层）。

用法：python3 guides/tools/wcl.py <命令> [参数]
      python3 guides/tools/wcl.py --help
只依赖 Python 3.9+ 标准库。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wclr.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
