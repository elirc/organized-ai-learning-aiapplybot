# chrome.py — Browser Lifecycle Manager

**File:** `src/applypilot/apply/chrome.py` (322 lines)
**Role:** Launches, manages, and cleans up Chrome browser instances for each worker.

---

## What This File Does

Each auto-apply worker needs its own Chrome browser. This file handles:
1. Creating isolated Chrome profiles (with session cookies)
2. Launching Chrome with remote debugging enabled
3. Cross-platform process tree killing
4. Port cleanup for zombie processes
5. Graceful shutdown

---

## Why Chrome Needs Special Handling

Chrome is not a simple process. When you launch Chrome:
- It spawns **10+ child processes** (GPU renderer, network service, extension host, etc.)
- It binds to a **network port** (CDP/remote debugging)
- It locks **profile files** (cookies, history, preferences)
- It writes **crash recovery data** that triggers restore prompts

Each of these needs specific handling. If you just `kill` the main Chrome PID, child processes become orphans. If you don't clean up ports, the next launch fails.

---

## Cross-Platform Process Tree Killing

```python
def _kill_process_tree(pid):
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10,
            )
        else:
            import os
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)
    except Exception:
        logger.debug("Failed to kill process tree for PID %d", pid)
```

### Windows: `taskkill /F /T /PID`

- `/F` — Force kill (don't ask nicely)
- `/T` — Kill the entire process **tree** (parent + all children)
- `/PID` — Target a specific process ID

Without `/T`, killing Chrome's main process leaves 10+ orphan processes consuming RAM.

### Unix: `os.killpg()`

On Linux/macOS, `os.killpg()` sends a signal to the entire **process group**. Chrome's child processes inherit the same process group ID as the parent, so one call kills them all.

The fallback to `os.kill()` handles the case where `getpgid()` fails (process already dead or different user).

### Why Swallow Exceptions?

```python
except Exception:
    logger.debug("Failed to kill process tree", exc_info=True)
```

Process killing can fail for many reasons (process already dead, permissions, race conditions). None of these are worth crashing over — the worst case is a stale Chrome process that the user can kill manually. So we log the failure and move on.

---

## Port Cleanup

```python
def _kill_on_port(port):
    if platform.system() == "Windows":
        result = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid.isdigit():
                    _kill_process_tree(int(pid))
    else:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        for pid_str in result.stdout.strip().splitlines():
            _kill_process_tree(int(pid_str))
```

### Why Kill by Port?

If ApplyPilot crashes, Chrome might still be running on port 9222. When the user restarts, `launch_chrome()` tries to use port 9222 again — but it's already taken. By killing whatever is on the port first, we ensure a clean start.

### Windows vs. Unix

- **Windows:** Uses `netstat -ano` to list connections, then parses the PID from the last column
- **Unix:** Uses `lsof -ti :9222` which directly outputs the PID

---

## Worker Profile Setup

```python
def setup_worker_profile(worker_id):
    profile_dir = config.CHROME_WORKER_DIR / f"worker-{worker_id}"
    if (profile_dir / "Default").exists():
        return profile_dir  # already set up

    # Find a source to clone from
    source = None
    for wid in range(10):
        if wid == worker_id:
            continue
        candidate = config.CHROME_WORKER_DIR / f"worker-{wid}"
        if (candidate / "Default").exists():
            source = candidate
            break
    if source is None:
        source = config.get_chrome_user_data()  # user's actual Chrome profile
```

### Why Clone Profiles?

A fresh Chrome profile has no cookies, no saved logins, nothing. The AI agent would need to log in to every job site from scratch. By cloning from:

1. **Another worker profile** (preferred) — already has session cookies from previous applications
2. **The user's real Chrome profile** (fallback) — has all the user's saved sessions

The agent inherits authenticated sessions, saving time and avoiding login walls.

### Selective Copying

```python
skip = {
    "ShaderCache", "GrShaderCache", "Service Worker", "Cache",
    "Code Cache", "GPUCache", "CacheStorage", "Crashpad",
    "BrowserMetrics", "SafeBrowsing", ...
}

for item in source.iterdir():
    if item.name in skip:
        continue
    # copy...
```

Chrome profiles are large (often 1GB+). Most of that is caches, compiled shaders, and telemetry data. We skip these to:
1. Save disk space
2. Speed up copying
3. Avoid locking issues (cache files are often locked by running Chrome)

We only copy the essentials: cookies, preferences, local storage, extensions.

---

## Suppress Restore Nag

```python
def _suppress_restore_nag(profile_dir):
    prefs = json.loads(prefs_file.read_text())
    prefs.setdefault("profile", {})["exit_type"] = "Normal"
    prefs.setdefault("session", {})["restore_on_startup"] = 4  # open blank
    prefs["credentials_enable_service"] = False
    prefs.setdefault("password_manager", {})["saving_enabled"] = False
    prefs.setdefault("autofill", {})["profile_enabled"] = False
```

### Why Patch Preferences?

When Chrome is killed (not closed gracefully), it writes `exit_type: "Crashed"` to the preferences file. On next launch, it shows a "Restore pages?" dialog. For automated workers, this dialog blocks the agent.

We patch the preferences to:
- Set `exit_type` to `"Normal"` (no restore prompt)
- Set `restore_on_startup` to `4` (open blank page)
- Disable credential saving (agents shouldn't save passwords)
- Disable autofill (we fill forms ourselves)

---

## Chrome Launch

```python
def launch_chrome(worker_id, port=None, headless=False):
    port = port or BASE_CDP_PORT + worker_id

    _kill_on_port(port)  # clean up zombies
    _suppress_restore_nag(profile_dir)

    cmd = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1024,768",
        "--deny-permission-prompts",
        "--disable-notifications",
        "--use-fake-device-for-media-stream",
        ...
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)  # wait for Chrome to start
    return proc
```

### Key Chrome Flags

**`--remote-debugging-port`:** Enables Chrome DevTools Protocol (CDP). The Playwright MCP server connects to this port to control the browser.

**`--deny-permission-prompts`:** Automatically deny all permission requests (camera, microphone, location, notifications). This is a security measure — the agent should NEVER grant permissions.

**`--use-fake-device-for-media-stream`:** If a site requests camera/mic access (even after denial), provide a fake device instead of real hardware.

**`--disable-popup-blocking`:** Job application sites often open popups for OAuth login or file upload. Blocking these would break the flow.

### Why `time.sleep(3)`?

Chrome takes 1-3 seconds to fully start and open the debugging port. Without the wait, the MCP server might try to connect before Chrome is ready.

**Is there a better way?** Yes — poll the CDP endpoint until it responds. But `sleep(3)` is simpler and works reliably enough for this use case.

### Unix Process Groups

```python
if platform.system() != "Windows":
    import os
    kwargs["preexec_fn"] = os.setsid
```

`os.setsid` starts Chrome in a **new session**. This creates a process group that we can kill with `os.killpg()` later. Without this, Chrome's children might not be in the same process group.

---

## Worker Directory Reset

```python
def reset_worker_dir(worker_id):
    worker_dir = config.APPLY_WORKER_DIR / f"worker-{worker_id}"
    if worker_dir.exists():
        shutil.rmtree(str(worker_dir), ignore_errors=True)
    worker_dir.mkdir(parents=True, exist_ok=True)
    return worker_dir
```

Each job gets a **fresh working directory**. This prevents:
- Resume PDFs from a previous job being picked up
- MCP config files from pointing to wrong ports
- Codex config files from conflicting

`ignore_errors=True` handles the case where files are locked (Windows) or have weird permissions.

---

## Design Patterns to Notice

### 1. Resource Management
Chrome is a resource (process, port, disk space). This file manages the full lifecycle: acquire → use → release. The `finally` blocks in the launcher ensure cleanup happens even on errors.

### 2. Platform Abstraction
Every operation has Windows and Unix code paths. The file hides platform differences behind clean function signatures. Callers never need to know the OS.

### 3. Defensive Cleanup
Multiple layers prevent resource leaks:
- `cleanup_worker()` — per-worker cleanup after each job
- `kill_all_chrome()` — kill everything during shutdown
- `cleanup_on_exit()` — atexit handler as final safety net
- `_kill_on_port()` — cleanup zombies from previous runs
