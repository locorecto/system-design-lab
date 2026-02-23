from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any
from typing import Protocol


@dataclass
class SandboxHandle:
    run_id: str
    backend: str
    profile: str
    limits: dict
    target_process: subprocess.Popen | None = None
    load_process: subprocess.Popen | None = None
    target_container_id: str | None = None
    load_container_id: str | None = None
    metadata: dict[str, Any] | None = None


class SandboxBackend(Protocol):
    name: str

    def provision(self, run_id: str, profile: str) -> SandboxHandle: ...
    def start_target(self, handle: SandboxHandle) -> None: ...
    def start_load_generator(self, handle: SandboxHandle) -> None: ...
    def stop(self, handle: SandboxHandle, reason: str) -> None: ...
    def cleanup(self, handle: SandboxHandle) -> None: ...


class ProcessSandboxBackend:
    name = "process"
    _profiles = {
        "low": {"cpu_cores": 1, "memory_mb": 512, "nominal_rps_capacity": 120},
        "medium": {"cpu_cores": 2, "memory_mb": 1024, "nominal_rps_capacity": 500},
        "high": {"cpu_cores": 4, "memory_mb": 2048, "nominal_rps_capacity": 1500},
    }

    def provision(self, run_id: str, profile: str) -> SandboxHandle:
        return SandboxHandle(run_id, self.name, profile, self._profiles.get(profile, self._profiles["medium"]).copy())

    def start_target(self, handle: SandboxHandle) -> None:
        handle.target_process = self._spawn_placeholder()

    def start_load_generator(self, handle: SandboxHandle) -> None:
        handle.load_process = self._spawn_placeholder()

    def stop(self, handle: SandboxHandle, reason: str) -> None:
        _ = reason
        self.cleanup(handle)

    def cleanup(self, handle: SandboxHandle) -> None:
        for proc in (handle.target_process, handle.load_process):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def _spawn_placeholder(self) -> subprocess.Popen:
        return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ContainerSandboxBackend:
    name = "container"
    _profiles = {
        "low": {"cpu_cores": 1, "memory_mb": 512, "nominal_rps_capacity": 100},
        "medium": {"cpu_cores": 2, "memory_mb": 1024, "nominal_rps_capacity": 420},
        "high": {"cpu_cores": 4, "memory_mb": 2048, "nominal_rps_capacity": 1300},
    }
    _python_image = "python:3.11-alpine"

    def provision(self, run_id: str, profile: str) -> SandboxHandle:
        client = self._client()
        client.ping()
        limits = self._profiles.get(profile, self._profiles["medium"]).copy()
        network_name = f"sdl-net-{run_id}"
        self._remove_network_if_exists(client, network_name)
        client.networks.create(network_name, driver="bridge", labels={"system-design-lab": "true", "sdl.run_id": run_id})
        return SandboxHandle(
            run_id,
            self.name,
            profile,
            limits,
            metadata={
                "engine": "docker",
                "network_name": network_name,
                "target_name": f"sdl-target-{run_id}",
                "loadgen_name": f"sdl-loadgen-{run_id}",
            },
        )

    def start_target(self, handle: SandboxHandle) -> None:
        target_profile = (handle.metadata or {}).get("target_spec") or {}
        container = self._run_target_service(handle, target_profile)
        handle.target_container_id = container.id

    def start_load_generator(self, handle: SandboxHandle) -> None:
        load_spec = (handle.metadata or {}).get("load_spec") or {}
        container = self._run_load_generator(handle, load_spec)
        handle.load_container_id = container.id

    def stop(self, handle: SandboxHandle, reason: str) -> None:
        _ = reason
        self.cleanup(handle)

    def cleanup(self, handle: SandboxHandle) -> None:
        try:
            client = self._client()
        except RuntimeError:
            return
        for cid in (handle.target_container_id, handle.load_container_id):
            if not cid:
                continue
            try:
                container = client.containers.get(cid)
                container.remove(force=True)
            except Exception:
                continue
        network_name = (handle.metadata or {}).get("network_name")
        if network_name:
            try:
                network = client.networks.get(network_name)
                network.remove()
            except Exception:
                pass
        handle.target_container_id = None
        handle.load_container_id = None
    def attach_specs(self, handle: SandboxHandle, *, target_spec: dict[str, Any] | None, load_spec: dict[str, Any] | None) -> None:
        handle.metadata = handle.metadata or {}
        handle.metadata["target_spec"] = target_spec or {}
        handle.metadata["load_spec"] = load_spec or {}

    def _run_target_service(self, handle: SandboxHandle, target_spec: dict[str, Any]):
        client = self._client()
        names = handle.metadata or {}
        name = str(names.get("target_name") or f"sdl-target-{handle.run_id}")
        network_name = str(names.get("network_name"))
        self._remove_if_exists(client, name)
        cpu_cores = float(handle.limits.get("cpu_cores", 2))
        memory_mb = int(handle.limits.get("memory_mb", 1024))
        workload = (target_spec.get("workload") or {}) if isinstance(target_spec, dict) else {}
        tuning = (target_spec.get("simulation_tuning") or {}) if isinstance(target_spec, dict) else {}
        env = {
            "PORT": "8080",
            "READ_RATIO": str(workload.get("read_ratio", 0.8)),
            "WRITE_RATIO": str(workload.get("write_ratio", 0.2)),
            "SEARCH_RATIO": str(workload.get("search_ratio", 0.0)),
            "CPU_BIAS": str(tuning.get("cpu_bias", 1.0)),
            "MEMORY_BIAS": str(tuning.get("memory_bias", 1.0)),
            "QUEUE_SENSITIVITY": str(tuning.get("queue_sensitivity", 1.0)),
            "ERROR_SENSITIVITY": str(tuning.get("error_sensitivity", 1.0)),
        }
        cmd = ["python", "-u", "-c", self._target_service_script()]
        return self._run_container(
            client=client,
            handle=handle,
            name=name,
            role="target",
            command=cmd,
            environment=env,
            network_name=network_name,
            cpu_cores=max(0.25, cpu_cores / 2),
            memory_mb=max(128, int(memory_mb / 2)),
        )

    def _run_load_generator(self, handle: SandboxHandle, load_spec: dict[str, Any]):
        client = self._client()
        names = handle.metadata or {}
        name = str(names.get("loadgen_name") or f"sdl-loadgen-{handle.run_id}")
        target_name = str(names.get("target_name") or f"sdl-target-{handle.run_id}")
        network_name = str(names.get("network_name"))
        self._remove_if_exists(client, name)
        cpu_cores = float(handle.limits.get("cpu_cores", 2))
        memory_mb = int(handle.limits.get("memory_mb", 1024))
        load_profile = (load_spec.get("load_profile") or {}) if isinstance(load_spec, dict) else {}
        duration_sec = int(load_profile.get("duration_sec", 20) or 20)
        target_rps = int(load_profile.get("target_rps") or load_profile.get("start_rps") or 50)
        request_mix = (load_profile.get("request_mix") or {}) if isinstance(load_profile, dict) else {}
        env = {
            "TARGET_URL": f"http://{target_name}:8080/work",
            "DURATION_SEC": str(max(3, min(duration_sec, 120))),
            "TARGET_RPS": str(max(1, target_rps)),
            "REQUEST_TIMEOUT_SEC": "2",
            "READ_RATIO": str(request_mix.get("read", 0.8)),
            "WRITE_RATIO": str(request_mix.get("write", 0.2)),
            "SEARCH_RATIO": str(request_mix.get("search", 0.0)),
        }
        cmd = ["python", "-u", "-c", self._loadgen_script()]
        return self._run_container(
            client=client,
            handle=handle,
            name=name,
            role="loadgen",
            command=cmd,
            environment=env,
            network_name=network_name,
            cpu_cores=max(0.25, cpu_cores / 2),
            memory_mb=max(128, int(memory_mb / 2)),
        )

    def _run_container(
        self,
        *,
        client,
        handle: SandboxHandle,
        name: str,
        role: str,
        command: list[str],
        environment: dict[str, str],
        network_name: str,
        cpu_cores: float,
        memory_mb: int,
    ):
        labels = {"system-design-lab": "true", "sdl.run_id": handle.run_id, "sdl.role": role}
        self._ensure_image(client, self._python_image)
        return client.containers.run(
            self._python_image,
            command=command,
            detach=True,
            name=name,
            labels=labels,
            environment=environment,
            network=network_name,
            mem_limit=f"{memory_mb}m",
            nano_cpus=int(cpu_cores * 1_000_000_000),
        )

    def _remove_if_exists(self, client, name: str) -> None:
        try:
            container = client.containers.get(name)
            container.remove(force=True)
        except Exception:
            return

    def _client(self):
        try:
            import docker  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Docker SDK is not installed in the backend runtime") from exc
        try:
            return docker.from_env()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to connect to Docker engine: {exc}") from exc

    def _ensure_image(self, client, image: str) -> None:
        try:
            client.images.get(image)
            return
        except Exception:
            client.images.pull(image)

    def _remove_network_if_exists(self, client, name: str) -> None:
        try:
            net = client.networks.get(name)
            net.remove()
        except Exception:
            return

    def _target_service_script(self) -> str:
        return r"""
import json, os, random, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
READ_RATIO = float(os.environ.get("READ_RATIO", "0.8"))
WRITE_RATIO = float(os.environ.get("WRITE_RATIO", "0.2"))
SEARCH_RATIO = float(os.environ.get("SEARCH_RATIO", "0.0"))
CPU_BIAS = float(os.environ.get("CPU_BIAS", "1.0"))
MEMORY_BIAS = float(os.environ.get("MEMORY_BIAS", "1.0"))
QUEUE_SENSITIVITY = float(os.environ.get("QUEUE_SENSITIVITY", "1.0"))
ERROR_SENSITIVITY = float(os.environ.get("ERROR_SENSITIVITY", "1.0"))

def _response_profile(kind: str):
    if kind == "write":
        base = 0.020
    elif kind == "search":
        base = 0.030
    else:
        base = 0.008
    base *= CPU_BIAS
    jitter = random.uniform(0.0, 0.015 * QUEUE_SENSITIVITY)
    error_p = min(0.35, 0.003 * ERROR_SENSITIVITY + (0.01 if kind == "search" else 0))
    return base + jitter, error_p

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return
    def _write_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path.startswith("/healthz"):
            self._write_json(200, {"status": "ok"})
            return
        if self.path.startswith("/config"):
            self._write_json(200, {"read_ratio": READ_RATIO, "write_ratio": WRITE_RATIO, "search_ratio": SEARCH_RATIO, "memory_bias": MEMORY_BIAS})
            return
        if self.path.startswith("/work"):
            r = random.random()
            if r < READ_RATIO:
                kind = "read"
            elif r < READ_RATIO + WRITE_RATIO:
                kind = "write"
            else:
                kind = "search"
            delay, error_p = _response_profile(kind)
            time.sleep(delay)
            if random.random() < error_p:
                self._write_json(503, {"ok": False, "kind": kind, "delay_ms": round(delay*1000, 2)})
                return
            self._write_json(200, {"ok": True, "kind": kind, "delay_ms": round(delay*1000, 2)})
            return
        self._write_json(404, {"error": "not_found"})

ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
"""

    def _loadgen_script(self) -> str:
        return r"""
import json, os, time, urllib.error, urllib.request

TARGET_URL = os.environ["TARGET_URL"]
DURATION_SEC = int(os.environ.get("DURATION_SEC", "20"))
TARGET_RPS = max(1, int(os.environ.get("TARGET_RPS", "50")))
TIMEOUT_SEC = float(os.environ.get("REQUEST_TIMEOUT_SEC", "2"))

start_ts = time.time()
window_start = start_ts
submitted = 0
latencies = []
success = 0
errors = 0

def pct(values, q):
    if not values:
        return 0.0
    idx = min(len(values)-1, max(0, int(round((q/100.0) * (len(values)-1)))))
    return sorted(values)[idx]
interval = 1.0 / float(TARGET_RPS)
next_emit = time.time() + 1.0
while time.time() - start_ts < DURATION_SEC:
    st = time.perf_counter()
    try:
        with urllib.request.urlopen(TARGET_URL, timeout=TIMEOUT_SEC) as resp:
            _ = resp.read()
            code = getattr(resp, "status", 200)
            ok = 200 <= code < 500
    except Exception:
        ok = False
    ms = (time.perf_counter() - st) * 1000.0
    latencies.append(ms)
    if ok:
        success += 1
    else:
        errors += 1
    submitted += 1

    now = time.time()
    if now >= next_emit:
        lats = latencies[:]
        s = success
        e = errors
        latencies = []
        success = 0
        errors = 0
        total = s + e
        out = {
            "type": "loadgen.sample",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "metrics": {
                "rps": total / max(0.001, now - window_start),
                "success": s,
                "errors": e,
                "error_rate": (e / total) if total else 0.0,
                "latency_ms": {
                    "p50": pct(lats, 50),
                    "p95": pct(lats, 95),
                    "p99": pct(lats, 99),
                }
            }
        }
        print(json.dumps(out), flush=True)
        window_start = now
        next_emit = now + 1.0

    elapsed = time.perf_counter() - st
    sleep_for = interval - elapsed
    if sleep_for > 0:
        time.sleep(sleep_for)
print(json.dumps({"type":"loadgen.completed","submitted":submitted}), flush=True)
"""


class SandboxRuntimeManager:
    def __init__(self) -> None:
        self._backends: dict[str, SandboxBackend] = {"process": ProcessSandboxBackend(), "container": ContainerSandboxBackend()}
        self._handles: dict[str, SandboxHandle] = {}
        self._lock = threading.Lock()

    def provision(self, run_id: str, profile: str, backend_name: str = "process") -> dict:
        backend = self._backends.get(backend_name, self._backends["process"])
        handle = backend.provision(run_id, profile)
        with self._lock:
            self._handles[run_id] = handle
        return {"backend": handle.backend, "profile": handle.profile, "limits": handle.limits}

    def start_target(self, run_id: str, target_spec: dict[str, Any] | None = None) -> None:
        handle, backend = self._resolve(run_id)
        if handle.backend == "container":
            container_backend = backend  # runtime protocol impl
            if hasattr(container_backend, "attach_specs"):
                container_backend.attach_specs(handle, target_spec=target_spec, load_spec=None)
        backend.start_target(handle)

    def start_load_generator(self, run_id: str, load_spec: dict[str, Any] | None = None) -> None:
        handle, backend = self._resolve(run_id)
        if handle.backend == "container":
            container_backend = backend
            if hasattr(container_backend, "attach_specs"):
                existing_target_spec = ((handle.metadata or {}).get("target_spec") if handle.metadata else None)
                container_backend.attach_specs(handle, target_spec=existing_target_spec, load_spec=load_spec)
        backend.start_load_generator(handle)

    def stop(self, run_id: str, reason: str) -> dict:
        handle, backend = self._resolve(run_id)
        backend.stop(handle, reason)
        return {"run_id": run_id, "status": "stopped", "reason": reason}

    def cleanup(self, run_id: str) -> None:
        with self._lock:
            handle = self._handles.pop(run_id, None)
        if not handle:
            return
        self._backends[handle.backend].cleanup(handle)

    def _resolve(self, run_id: str) -> tuple[SandboxHandle, SandboxBackend]:
        with self._lock:
            handle = self._handles.get(run_id)
        if handle is None:
            raise KeyError(f"Sandbox handle not found for {run_id}")
        return handle, self._backends[handle.backend]
