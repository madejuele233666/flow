"""Git 账本 — VersionControl 的 Git 实现.

设计要点：
- 通过 subprocess 调用 git，避免 GitPython 的重量级依赖（可选）。
- 所有 Git 操作静默执行，不干扰用户终端输出。
- 初始化时自动 git init（如果不存在）。
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from flow_engine.storage.base import VersionControl

logger = logging.getLogger(__name__)


class GitLedger(VersionControl):
    """基于 Git 的版本控制实现."""

    def __init__(self, repo_dir: Path, *, enabled: bool = True) -> None:
        self._dir = repo_dir
        self._enabled = enabled
        if self._enabled:
            self._ensure_repo()

    def _run(self, *args: str) -> str:
        """执行 git 命令，返回 stdout."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self._dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.warning("git %s failed: %s", " ".join(args), e.stderr.strip())
            return ""
        except FileNotFoundError:
            logger.warning("git not found on PATH, disabling version control")
            self._enabled = False
            return ""

    def _ensure_repo(self) -> None:
        """如果目录下没有 .git，则初始化."""
        git_dir = self._dir / ".git"
        if not git_dir.exists():
            self._dir.mkdir(parents=True, exist_ok=True)
            self._run("init")
            logger.info("initialized git repo at %s", self._dir)

    def commit(self, message: str) -> None:
        """暂存并提交全部变更."""
        if not self._enabled:
            return
        self._run("add", ".")
        output = self._run("commit", "-m", message, "--allow-empty-message")
        if output:
            logger.debug("git commit: %s", output.split("\n")[0])

    def log(self, count: int = 10) -> list[str]:
        """返回最近 N 条提交信息."""
        if not self._enabled:
            return []
        output = self._run("log", f"--oneline", f"-{count}")
        return output.splitlines() if output else []
