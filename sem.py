# VS Code PowerShell 终端输入（先切换项目目录）：
# Set-Location -LiteralPath 'D:\sem自动化'
# & '.\.venv\Scripts\python.exe' '.\sem.py' --help
from sem_automation.cli.main import main

if __name__ == '__main__':
    raise SystemExit(main())
