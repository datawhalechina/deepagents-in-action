"""Real Docker execution, artifact accuracy, and resource ownership for chapter 10."""
import asyncio
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
        command = "python -c 'print(\"x\" * 40000)'"
        for offload in [
            backend.execute_with_offload(command, "/workspace/unused-log", max_inline_bytes=32768),
            asyncio.run(backend.aexecute_with_offload(
                command, "/workspace/unused-log", max_inline_bytes=32768,
            )),
        ]:
            assert not offload.offloaded
            assert offload.response.exit_code == 0 and offload.response.truncated
            assert len(offload.response.output.encode()) == 32768
        calls = [{"name": "execute", "args": {"command": command}, "id": "long-log"}]
        result = namespace["make_agent"](backend, calls).invoke(namespace["task_input"](calls))
        reply = namespace["check_loop"](result, calls)[0]
        assert reply.artifact["exit_code"] == 0
        assert "Output was truncated due to size limits" in reply.text
        timed_out = backend.execute("python -c 'import time; time.sleep(20)'", timeout=1)
        assert timed_out.exit_code == 124
        assert backend.execute("python -c 'print(123)'").output.strip() == "123"
    assert not namespace["container_exists"](name)


def test_large_file_and_directory_protocols_survive_command_display_limit(chapter):
    namespace, _ = chapter
    lines = [f"{index:04d} " + "x" * 35 for index in range(1000)]
    content = "\n".join(lines) + "\n"
    assert len(content.encode()) == 41000
    directory = "/workspace/many"
    paths = {f"{directory}/{index:04d}-" + "n" * 100 for index in range(400)}
    with namespace["DockerSandbox"]() as backend:
        name = backend.id
        upload = backend.upload_files([("/workspace/large.txt", content.encode())])[0]
        assert upload.error is None
        created = backend.execute(
            "python - <<'PY'\nfrom pathlib import Path\n"
            f"root = Path({directory!r})\nroot.mkdir()\n"
            "for index in range(400):\n"
            "    (root / (f'{index:04d}-' + 'n' * 100)).touch()\nPY"
        )
        assert created.exit_code == 0
        for read in [backend.read("/workspace/large.txt"),
                     asyncio.run(backend.aread("/workspace/large.txt"))]:
            assert read.error is None and read.file_data["content"] == "\n".join(lines)
            assert (read.start_line, read.end_line, read.total_lines, read.next_offset) == (1, 1000, 1000, None)
        pages, offset = [], 0
        while True:
            page = backend.read("/workspace/large.txt", offset=offset, limit=100)
            assert page.error is None and page.start_line == offset + 1
            pages.extend(page.file_data["content"].splitlines())
            if page.next_offset is None:
                break
            assert page.next_offset > offset
            offset = page.next_offset
        assert pages == lines
        for listing in [backend.ls(directory), asyncio.run(backend.als(directory))]:
            assert listing.error is None
            assert len(listing.entries) == 400
            assert {entry["path"] for entry in listing.entries} == paths
        # Sibling file helpers share raw execute(), so their protocols must also stay complete.
        matches = backend.glob("*", directory)
        assert matches.error is None and not matches.truncated
        assert {entry["path"] for entry in matches.matches} == paths
        grep = backend.grep("x", "/workspace/large.txt")
        assert grep.error is None and not grep.truncated
        assert [match["text"] for match in grep.matches] == lines
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
