"""Chapter-local process lifecycle. Async task experiments stay in the notebook."""
import asyncio
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import psutil
from langgraph_sdk import get_client

from course_notebooks.model_config import selected_mode


class LocalAgentServer:
    """Own one temporary deployment and its threads; always close them on exit."""

    def __init__(self, chapter_dir, root, *, mode=None):
        self.chapter_dir = Path(chapter_dir)
        self.root = Path(root)
        self.mode = selected_mode(mode)
        self.process = None
        self.parent_id = None
        self.task_ids = set()
        self.cleaned_task_ids = set()
        self.client = None
        self._directory = None
        self._log = None

    async def __aenter__(self):
        self._directory = tempfile.TemporaryDirectory(prefix="ch06-demo-")
        self.workdir = Path(self._directory.name)
        self._log = tempfile.NamedTemporaryFile(mode="w", prefix="ch06-agent-server-", suffix=".log", delete=False)
        self.log_path = Path(self._log.name)
        try:
            cli = Path(sys.executable).with_name("langgraph.exe" if os.name == "nt" else "langgraph")
            if not cli.is_file():
                raise FileNotFoundError("请先 uv sync --project notebooks --locked --extra server")
            shutil.copytree(self.chapter_dir / "graphs", self.workdir / "graphs", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(self.chapter_dir / "langgraph.json", self.workdir / "langgraph.json")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                self.port = sock.getsockname()[1]
            env = os.environ.copy()
            env.update(COURSE_MODE=self.mode, COURSE_REPO_ROOT=str(self.root))
            if self.mode == "offline":
                env["LANGSMITH_TRACING"] = "false"
                env["LANGCHAIN_TRACING_V2"] = "false"
            self.client = get_client(url=f"http://127.0.0.1:{self.port}")
            self.process = subprocess.Popen(
                [str(cli), "dev", "--host", "127.0.0.1", "--no-browser", "--no-reload",
                 "--port", str(self.port), "--n-jobs-per-worker", "4", "--config", "langgraph.json"],
                cwd=self.workdir, env=env, stdout=self._log, stderr=subprocess.STDOUT,
            )
            await self._wait_ready()
            self.parent_id = (await asyncio.wait_for(self.client.threads.create(), 10))["thread_id"]
            print("Agent Server 已就绪（仅本机访问）；已创建本次主 thread。")
            return self
        except BaseException:
            await self._close(successful=False)
            raise

    async def _wait_ready(self, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Agent Server 提前退出；诊断日志：{self.log_path}")
            try:
                assistants = await asyncio.wait_for(self.client.assistants.search(), 2)
                if {"supervisor", "researcher"} <= {item["graph_id"] for item in assistants}:
                    return
            except Exception:
                pass  # Connection failure is expected only within this bounded startup window.
            await asyncio.sleep(0.3)
        raise TimeoutError(f"Agent Server 未在 {timeout}s 内就绪；日志：{self.log_path}")

    async def _delete_threads(self, errors):
        tracked = {}
        if self.parent_id is None:
            return
        try:
            state = await self.client.threads.get_state(self.parent_id)
            tracked = state.get("values", {}).get("async_tasks", {})
            self.task_ids.update(tracked)
        except Exception as error:
            errors.append(f"读取主 thread: {type(error).__name__}")
        for task_id in self.task_ids:
            try:
                task = tracked.get(task_id)
                if task:
                    run = await self.client.runs.get(task_id, task["run_id"])
                    if run["status"] in {"pending", "running"}:
                        await self.client.runs.cancel(task_id, task["run_id"])
                await self.client.threads.delete(task_id)
                self.cleaned_task_ids.add(task_id)
            except Exception as error:
                errors.append(f"子 thread: {type(error).__name__}")
        try:
            await self.client.threads.delete(self.parent_id)
        except Exception as error:
            errors.append(f"主 thread: {type(error).__name__}")

    def _stop_windows_process_tree(self):
        """Wait for the CLI launchers and their service interpreter to exit."""
        try:
            launcher = psutil.Process(self.process.pid)
            processes = [*reversed(launcher.children(recursive=True)), launcher]
        except psutil.NoSuchProcess:
            return
        for process in processes:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(processes, timeout=10)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(alive, timeout=5)
        if alive:
            raise TimeoutError("Agent Server 进程树未完全退出")

    async def _close(self, *, successful):
        errors = []
        try:
            if self.process is not None and self.process.poll() is None:
                try:
                    await asyncio.wait_for(self._delete_threads(errors), timeout=20)
                except Exception as error:
                    errors.append(f"清理请求: {type(error).__name__}")
        finally:
            try:
                if self.process is not None and self.process.poll() is None:
                    if os.name == "nt":
                        await asyncio.to_thread(self._stop_windows_process_tree)
                    else:
                        self.process.terminate()
                    try:
                        await asyncio.to_thread(self.process.wait, timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        await asyncio.to_thread(self.process.wait, timeout=5)
            finally:
                self._directory.cleanup()
                self._log.close()
        if successful and not errors:
            self.log_path.unlink(missing_ok=True)
        else:
            print("失败诊断日志：", self.log_path)
        if errors:
            raise RuntimeError("清理未完成：" + "; ".join(errors) + f"；日志：{self.log_path}")
        print("本次创建的任务、thread、服务进程与临时状态已清理。")

    async def __aexit__(self, exc_type, exc, traceback):
        await self._close(successful=exc_type is None)
        return False
