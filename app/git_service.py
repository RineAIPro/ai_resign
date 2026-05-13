# Git服务
# 修改时间：2026/05/08
# 功能：Git操作（读取提交记录、执行命令序列、流式执行）

import os
import subprocess


class GitService:
    @staticmethod
    def get_recent_commits(project_path: str, count: int = 5) -> list[dict]:
        """获取最近N条提交记录"""
        if not os.path.exists(os.path.join(project_path, ".git")):
            return []
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--pretty=format:%h|%s|%cr"],
                cwd=project_path, capture_output=True,
                encoding='utf-8', errors='replace', timeout=10
            )
            if result.returncode != 0:
                return []
            commits = []
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 2)
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1] if len(parts) > 1 else "",
                        "time": parts[2] if len(parts) > 2 else "",
                    })
            return commits
        except Exception:
            return []

    @staticmethod
    def execute_command(project_path: str, command: str) -> tuple[bool, str]:
        """执行单条Git命令"""
        try:
            result = subprocess.run(
                command, cwd=project_path, capture_output=True,
                encoding='utf-8', errors='replace',
                timeout=60, shell=True
            )
            output = result.stdout or result.stderr
            return result.returncode == 0, output
        except Exception as e:
            return False, str(e)

    @staticmethod
    def execute_commands(project_path: str, commands: list[str]) -> list[tuple[bool, str]]:
        """逐步执行命令序列"""
        results = []
        for cmd in commands:
            ok, output = GitService.execute_command(project_path, cmd)
            results.append((ok, output))
            if not ok:
                break
        return results

    # 修改时间：2026/05/08 - 流式执行，实时返回输出
    @staticmethod
    def execute_command_stream(project_path: str, command: str):
        """流式执行Git命令，逐行yield输出内容"""
        try:
            process = subprocess.Popen(
                command,
                cwd=project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8', errors='replace',
                shell=True,
                bufsize=0  # 无缓冲
            )
            for line in iter(process.stdout.readline, ''):
                if line:
                    yield line.rstrip('\n')
            process.wait()
            yield f"__EXIT__:{process.returncode}"
        except Exception as e:
            yield f"__ERROR__:{str(e)}"

    # 修改时间：2026/05/08 - 流式执行多条命令
    @staticmethod
    def execute_commands_stream(project_path: str, commands: list[str]):
        """流式执行多条Git命令，逐行yield输出内容"""
        try:
            for i, cmd in enumerate(commands):
                yield f"__CMD__:▶ {cmd}"
                process = subprocess.Popen(
                    cmd,
                    cwd=project_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8', errors='replace',
                    shell=True,
                    bufsize=0
                )
                for line in iter(process.stdout.readline, ''):
                    if line:
                        yield line.rstrip('\n')
                process.wait()
                yield f"__EXIT__:{process.returncode}"
                if process.returncode != 0:
                    yield "__BREAK__:命令执行失败，已中断后续命令"
                    break
        except Exception as e:
            yield f"__ERROR__:{str(e)}"