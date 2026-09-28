"""Real Docker execution, artifact accuracy, and resource ownership for chapter 10."""
from copy import deepcopy
from pathlib import Path
import subprocess

import nbformat
import pytest


@pytest.fixture
def chapter(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    notebook = nbformat.read(
        Path(__file__).parents[1] / "ch10/01-sandbox-execution-and-files.ipynb", as_version=4,
    )
    namespace = {}
    cells = {tag: cell.source for cell in notebook.cells
             for tag in cell.metadata.get("tags", [])}
    for tag in ("ch10-imports", "ch10-inputs", "ch10-agent"):
        exec(cells[tag], namespace)
    exec(cells["ch10-check"].split("\nreplies =", 1)[0], namespace)
    return namespace, cells


def test_notebook_pipeline_and_failure_preserve_real_exit_codes(chapter):
    namespace, cells = chapter
    exec(cells["ch10-run"], namespace)
    exec(cells["ch10-check"], namespace)
    assert namespace["report"] == {"orders": 3, "total": 75}
    exec(cells["ch10-failure"], namespace)
    reply = namespace["failed_replies"][0]
    assert reply.status == "success" and reply.artifact["exit_code"] == 7


def test_changed_input_returns_new_total_before_business_check_fails(chapter):
    namespace, cells = chapter
    changed = cells["ch10-inputs"].replace('"price": 10', '"price": 12', 1)
    exec(changed, namespace)
    exec(cells["ch10-run"], namespace)
    assert namespace["report"] == {"orders": 3, "total": 79}
    assert not namespace["container_exists"](namespace["container_name"])
    with pytest.raises(AssertionError, match="总额 75"):
        exec(cells["ch10-check"], namespace)


def test_success_status_cannot_hide_unrelated_tool_result(chapter):
    namespace, cells = chapter
    exec(cells["ch10-run"], namespace)
    result = deepcopy(namespace["result"])
    reply = next(m for m in result["messages"] if isinstance(m, namespace["ToolMessage"]))
    reply.tool_call_id = "unrelated-call"
    with pytest.raises(AssertionError):
        namespace["check_loop"](result, namespace["CALLS"])


def test_file_transfers_report_partial_errors_and_preserve_bytes(chapter):
    namespace, _ = chapter
    with namespace["DockerSandbox"]() as backend:
        name = backend.id
        uploads = backend.upload_files([
            ("/workspace/input.bin", b"\x00\xff\n"),
            ("relative-path", b"bad"),
            ("/blocked.txt", b"bad"),
        ])
        assert [r.error for r in uploads] == [None, "invalid_path", "permission_denied"]
        downloads = backend.download_files([
            "/workspace/missing.bin", "/workspace/input.bin", "/workspace",
        ])
        assert [r.error for r in downloads] == ["file_not_found", None, "is_directory"]
        assert downloads[1].content == b"\x00\xff\n"
    assert not namespace["container_exists"](name)


def test_container_restrictions_and_cleanup_on_python_exception(chapter, monkeypatch):
    namespace, _ = chapter
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-host-only-marker")
    with pytest.raises(ValueError, match="planned exception"):
        with namespace["DockerSandbox"]() as backend:
            name = backend.id
            info = backend.inspect()
            limits = info["HostConfig"]
            assert limits["NetworkMode"] == "none" and limits["ReadonlyRootfs"]
            assert limits["Memory"] == 256 * 1024 * 1024 and limits["PidsLimit"] == 64
            assert limits["NanoCpus"] == 1_000_000_000
            assert info["Config"]["User"] == "65534:65534" and info["Mounts"] == []
            assert not any(item.startswith("MODEL_API_KEY=") for item in info["Config"]["Env"])
            raise ValueError("planned exception")
    assert not namespace["container_exists"](name)


def test_timeout_and_truncation_are_not_reported_as_complete_success(chapter):
    namespace, _ = chapter
    with namespace["DockerSandbox"]() as backend:
        name = backend.id
        long_output = backend.execute("python -c 'print(\"x\" * 40000)'")
        assert long_output.exit_code == 0 and long_output.truncated
        assert len(long_output.output.encode()) == 32768
        timed_out = backend.execute("python -c 'import time; time.sleep(20)'", timeout=1)
        assert timed_out.exit_code == 124
        assert backend.execute("python -c 'print(123)'").output.strip() == "123"
    assert not namespace["container_exists"](name)


def test_transport_timeout_removes_environment_before_raising(chapter, monkeypatch):
    namespace, _ = chapter
    import docker_sandbox
    original = docker_sandbox.docker
    with namespace["DockerSandbox"]() as backend:
        name = backend.id

        def stalled(*args, **kwargs):
            if args[0] == "exec":
                raise subprocess.TimeoutExpired("docker exec", 40)
            return original(*args, **kwargs)

        monkeypatch.setattr(docker_sandbox, "docker", stalled)
        with pytest.raises(TimeoutError, match="容器已回收"):
            backend.execute("python -c 'print(1)'")
        assert not namespace["container_exists"](name)


def test_startup_failure_after_creation_does_not_leak_container(chapter, monkeypatch):
    namespace, _ = chapter
    import docker_sandbox
    original = docker_sandbox.docker
    backend = namespace["DockerSandbox"]()

    def lost_acknowledgement(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0] == "run":
            raise RuntimeError("planned startup failure")
        return result

    monkeypatch.setattr(docker_sandbox, "docker", lost_acknowledgement)
    with pytest.raises(RuntimeError, match="planned startup failure"):
        with backend:
            raise AssertionError("启动失败时不应进入实验主体")
    assert not namespace["container_exists"](backend.name)
