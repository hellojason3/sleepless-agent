"""
Sleepless Agent - 程序入口模块

本模块是 Python 包的主入口点，当使用 `python -m sleepless_agent` 运行时执行。

执行流程:
    1. 导入 CLI 主函数
    2. 调用 main() 并传递退出码到 sys.exit()

使用方式:
    python -m sleepless_agent start -w ./workspace
    python -m sleepless_agent prompt "任务描述"
"""

import sys

from sleepless_agent.cli import main


if __name__ == "__main__":
    # 执行 CLI 主函数并返回退出码
    sys.exit(main())
