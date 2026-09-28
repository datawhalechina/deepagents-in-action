"""Chapter-only Docker adapter; commands and file transfers run inside a container."""
import json
from pathlib import PurePosixPath
import shutil
import subprocess
from textwrap import dedent
from uuid import uuid4

from deepagents.backends.protocol import (
    ExecuteResponse, FileDownloadResponse, FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox


# Multi-platform manifest for the Python 3.12 slim-bookworm image used in this chapter.
IMAGE = "python@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e"

EXECUTE_SCRIPT = dedent("""
    import json, os, signal, subprocess, sys, tempfile
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(sys.argv[1], shell=True, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=int(sys.argv[2]))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            code = 124
        log.seek(0)
        data = log.read(32769)
        print(json.dumps({"output": data[:32768].decode("utf-8", errors="replace"),
                          "exit_code": code, "truncated": len(data) > 32768}))
""")

TRANSFER_SCRIPT = dedent("""
    import base64, errno, json, pathlib, sys
    path = pathlib.Path(sys.argv[2])
    try:
        if sys.argv[1] == "upload":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(sys.stdin.buffer.read())
            result = {"error": None}
        else:
            result = {"error": None, "content": base64.b64encode(path.read_bytes()).decode()}
    except FileNotFoundError:
        result = {"error": "file_not_found"}
    except PermissionError:
        result = {"error": "permission_denied"}
    except IsADirectoryError:
        result = {"error": "is_directory"}
    except OSError as error:
        result = {"error": "permission_denied" if error.errno == errno.EROFS else str(error)}
    print(json.dumps(result))
""")


def docker(*arguments, timeout=30, content=None):
    """Use argument arrays: the host never interprets commands as shell code."""
    result = subprocess.run(
        ["docker", *arguments], input=content, capture_output=True, timeout=timeout,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Docker 调用失败：{detail}")
    return result.stdout


def container_exists(name):
    """Connection failures raise, rather than being reported as successful cleanup."""
    names = docker("ps", "--all", "--filter", f"name=^/{name}$", "--format", "{{.Names}}")
    return name in names.decode().splitlines()


class DockerSandbox(BaseSandbox):
    """Small teaching adapter with a five-minute container lifetime, not a provider SDK."""

    def __init__(self):
        self.name = f"deepagents-ch10-{uuid4().hex}"
        self.active = False

    @property
    def id(self):
        if not self.active:
            raise RuntimeError("容器尚未启动或已经回收；请重新创建实验。")
        return self.name

    def __enter__(self):
        if not shutil.which("docker"):
            raise RuntimeError("请安装并启动 Docker Desktop / Docker Engine，再运行本章。")
        docker("info", "--format", "{{.ServerVersion}}")
        # Download the pinned image before creating a resource; subsequent runs use the cache.
        cached = subprocess.run(["docker", "image", "inspect", IMAGE],
                                capture_output=True, timeout=30)
        if cached.returncode:
            docker("pull", "--quiet", IMAGE, timeout=300)
        try:
            docker(
                "run", "--detach", "--rm", "--pull=never", "--name", self.name,
                "--label", "deepagents.course=ch10", "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
                "--user", "65534:65534", "--workdir", "/workspace",
                "--tmpfs", "/workspace:rw,size=16m,mode=1777",
                "--tmpfs", "/tmp:rw,size=16m,mode=1777", IMAGE,
                "python", "-c", "import time; time.sleep(300)",
            )
        except BaseException:
            self.close()
            raise
        self.active = True
        return self

    def __exit__(self, *exception):
        self.close()

    def close(self):
        if container_exists(self.name):
            docker("rm", "--force", self.name)
        self.active = False

    def inspect(self):
        return json.loads(docker("inspect", self.id))[0]

    def execute(self, command, *, timeout=None):
        seconds = 30 if timeout is None else timeout
        if not isinstance(seconds, int) or not 1 <= seconds <= 30:
            raise ValueError("教学后端仅支持 1～30 秒的命令超时。")
        try:
            data = docker("exec", self.id, "python", "-c", EXECUTE_SCRIPT,
                          command, str(seconds), timeout=seconds + 10)
        except subprocess.TimeoutExpired:
            # If even the Docker transport stalls, remove the environment and fail loudly.
            self.close()
            raise TimeoutError("Docker 传输超时，容器已回收；本次实验终止。") from None
        return ExecuteResponse(**json.loads(data))

    def _transfer(self, operation, path, content=None):
        target = PurePosixPath(path)
        if not target.is_absolute() or ".." in target.parts or "\x00" in path:
            return {"error": "invalid_path"}
        try:
            return json.loads(docker("exec", "-i", self.id, "python", "-c",
                                     TRANSFER_SCRIPT, operation, path, content=content))
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            return {"error": str(error)}

    def upload_files(self, files):
        return [FileUploadResponse(path=path, error=self._transfer("upload", path, data)["error"])
                for path, data in files]

    def download_files(self, paths):
        import base64
        results = []
        for path in paths:
            result = self._transfer("download", path)
            data = base64.b64decode(result["content"]) if result["error"] is None else None
            results.append(FileDownloadResponse(path=path, content=data, error=result["error"]))
        return results
