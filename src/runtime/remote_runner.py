import base64
import ctypes
import hashlib
import json
import os
import pathlib
import resource
import selectors
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

PINS = {
    "data-manifest.json": "99810e57a77cd3bc8b107287037e54fb2521795a96ec71d431fd585c03289f91",
    "source-records.json": "5c31dcd20478c1644b50eff7a7286b9c568094dd1e26427843afd23fc9dfe57c",
    "caldova-research.duckdb": "f12f3e239f7b439b5c4fde1b405bd4e2346fa49fba79b1c1b198f42874ef9559",
}
MAX_OUTPUT = 131072
WALL_SECONDS = 30


def identity_endpoint_status():
    endpoint = os.environ.get("IDENTITY_ENDPOINT")
    if not endpoint:
        return "not_exposed"
    query = urllib.parse.urlencode({
        "api-version": "2019-08-01", "resource": "https://management.azure.com/",
    })
    request = urllib.request.Request(
        endpoint + ("&" if "?" in endpoint else "?") + query,
        headers={"X-IDENTITY-HEADER": os.environ.get("IDENTITY_HEADER", "")},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            value = json.loads(response.read(16384))
            if value.get("access_token"):
                raise PermissionError("The platform endpoint still exposes an Azure identity token.")
            raise RuntimeError("The identity endpoint returned an unexpected successful response.")
    except urllib.error.HTTPError as error:
        if error.code not in {400, 401, 403, 404}:
            raise
        return error.code


def frozen_files():
    root = pathlib.Path("/opt/lab722-data")
    actual = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in PINS}
    if actual != PINS or any((root / name).stat().st_mode & 0o222 for name in PINS):
        raise RuntimeError("Frozen dataset bytes or read-only permissions changed.")
    return actual


def drop_privileges():
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot enable no-new-privileges.")
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16777216, 16777216))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def stop_analysis(child):
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    # A child can start a detached session. This serial, dedicated Sandbox
    # has no other analysis user; reap that UID too, not only the process group.
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
            uid = next(line.split()[1] for line in status.splitlines() if line.startswith("Uid:"))
            if uid == "65534":
                os.kill(int(entry.name), signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass
    child.wait(timeout=5)
    deadline = time.monotonic() + 5
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid:
            continue
        if time.monotonic() >= deadline:
            raise RuntimeError("Analysis descendants were not reaped within five seconds.")
        time.sleep(0.01)


def prepare_customer_note(payload):
    if "customer_note" in payload:
        note = payload["customer_note"]
        if not isinstance(note, str) or len(note.encode()) > 1024:
            raise ValueError("The server-owned customer note is outside the lab contract.")
        path = pathlib.Path("/workspace/customer-note.txt")
        if path.is_symlink():
            raise PermissionError("Customer note path must not be a symbolic link.")
        path.write_text(note)
        path.chmod(0o600)
        os.chown(path, 65534, 65534)


def run(payload):
    if os.getuid() != 0:
        raise RuntimeError("The trusted execution supervisor must start as root.")
    code = payload["code"]
    if not isinstance(code, str) or not code.strip() or len(code.encode()) > 16384 or "\0" in code:
        raise ValueError("Code must be nonempty Python, at most 16 KiB, without NUL bytes.")
    pins = frozen_files()
    identity_status = identity_endpoint_status()
    prepare_customer_note(payload)
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot enable analysis descendant reaping.")
    started = time.monotonic()
    child = subprocess.Popen(
        ["/opt/python/3/bin/python3", "-I", "-c", code],
        cwd="/workspace",
        env={"PATH": "/opt/python/3/bin:/usr/bin:/bin", "HOME": "/workspace"},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True, preexec_fn=drop_privileges,
    )
    output = {"stdout": bytearray(), "stderr": bytearray()}
    captured = 0
    reason = None
    selector = selectors.DefaultSelector()
    for name in output:
        pipe = getattr(child, name)
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ, name)
    try:
        while selector.get_map():
            if time.monotonic() - started >= WALL_SECONDS:
                reason = "timed_out"
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = MAX_OUTPUT - captured
                output[key.data].extend(chunk[:remaining])
                captured += min(len(chunk), remaining)
                if len(chunk) > remaining:
                    reason = "output_limit"
                    break
            if reason:
                break
        # Closing both output pipes is not evidence that the process exited.
        if reason is None:
            try:
                child.wait(timeout=max(0.01, WALL_SECONDS - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                reason = "timed_out"
    finally:
        selector.close()
        stop_analysis(child)
        child.stdout.close()
        child.stderr.close()
    if frozen_files() != pins:
        raise RuntimeError("Frozen dataset changed during execution.")
    return {
        "schema_version": "1.0",
        "run_id": payload["run_id"],
        "execution_marker": payload["marker"],
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "status": reason or ("completed" if child.returncode == 0 else "failed"),
        "exit_code": child.returncode,
        "stdout": output["stdout"].decode("utf-8", errors="replace"),
        "stderr": output["stderr"].decode("utf-8", errors="replace"),
        "captured_bytes": captured,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "execution_uid": 65534,
        "environment_cleared": True,
        "no_new_privileges": True,
        "identity_endpoint_status": identity_status,
        "dataset_version": "caldova-public-lab-use-v2",
        "files_sha256": pins,
    }


if __name__ == "__main__":
    print(json.dumps(run(json.loads(base64.b64decode(os.environ["LAB722_PAYLOAD"])))))
