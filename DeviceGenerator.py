import binascii
import json
import os
import platform
import queue
import random
import re
import shutil
import subprocess
import threading
import time
import webbrowser
import tkinter as tk
from concurrent.futures import FIRST_COMPLETED, CancelledError, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests
from tkinter import filedialog, messagebox, scrolledtext, ttk


def getrandommc():
    mcrandom = ["a", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
    mc = "{}:{}:{}:{}:{}:{}".format(
        "".join(random.choices(mcrandom, k=2)),
        "".join(random.choices(mcrandom, k=2)),
        "".join(random.choices(mcrandom, k=2)),
        "".join(random.choices(mcrandom, k=2)),
        "".join(random.choices(mcrandom, k=2)),
        "".join(random.choices(mcrandom, k=2)),
    )
    return mc


def getsystem():
    system = platform.system()
    if system.startswith("Win"):
        return "win" + platform.machine()[-2:]
    if system.startswith("Lin"):
        return "linux" + platform.machine()[-2:]
    return "osx64"


def get_java_exe():
    """Resolve java.exe; on Windows prefer 64-bit (win64 DLLs need a 64-bit JVM)."""
    win = platform.system().startswith("Win")
    java_name = "java.exe" if win else "java"
    candidates = []

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.append(Path(java_home) / "bin" / java_name)

    if win:
        candidates.append(Path(r"C:\Java\jdk-17-temurin-x64\bin\java.exe"))

    which = shutil.which("java")
    if which:
        candidates.append(Path(which))

    def jvm_is_64bit(exe: Path) -> bool:
        if not exe.is_file():
            return False
        try:
            p = subprocess.run(
                [str(exe), "-version"],
                capture_output=True,
                timeout=20,
            )
            text = (p.stderr or b"").decode("utf-8", errors="replace")
            text += (p.stdout or b"").decode("utf-8", errors="replace")
            return "64-Bit" in text
        except (OSError, subprocess.TimeoutExpired):
            return False

    if win and getsystem().endswith("64"):
        for c in candidates:
            if jvm_is_64bit(c):
                return str(c.resolve())

    for c in candidates:
        if c.is_file():
            return str(c.resolve())

    return which or "java"


def jvm_os_arch(java_exe: str) -> str | None:
    """Return JVM os.arch from `java -XshowSettings:properties -version` (e.g. aarch64, x86_64)."""
    try:
        p = subprocess.run(
            [java_exe, "-XshowSettings:properties", "-version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (p.stderr or "") + "\n" + (p.stdout or "")
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("os.arch") and "=" in line:
                return line.split("=", 1)[1].strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def apple_silicon_unidbg_java_warning(java_exe: str) -> str | None:
    """
    unidbg.jar ships old JNA whose darwin libjnidispatch is x86_64/i386 only.
    An arm64 JVM on Apple Silicon cannot dlopen it → UnsatisfiedLinkError on extracted jna*.tmp.
    """
    if platform.system() != "Darwin":
        return None
    if platform.machine() != "arm64":
        return None
    arch = jvm_os_arch(java_exe)
    if arch is None:
        return None
    if arch in ("x86_64", "amd64", "i386"):
        return None
    if arch in ("aarch64", "arm64"):
        return (
            "Apple Silicon + arm64 Java: the bundled unidbg JNA native library is x86_64-only.\n\n"
            "Install an Intel (x64) JDK 11 or 17 (e.g. Eclipse Temurin macOS x64 from adoptium.net), "
            "set JAVA_HOME to that JDK, restart this app, and verify:\n"
            "  java -XshowSettings:properties -version\n"
            "shows  os.arch = x86_64\n\n"
            "OK = try anyway (usually still fails). Cancel = stop."
        )
    return None


def default_output_dir():
    return Path(__file__).resolve().parent / "generated_devices"


APP_DISPLAY_TITLE = "TikTok Device Generator"
DEVELOPER_NAME_EN = "Mostafa Al-Bagouri"
COMPANY_NAME = "Storage TE"
COMPANY_URL = "http://storage-te.com/"
CONTACT_PHONE = "+201001995914"
CONTACT_WHATSAPP_URL = "https://wa.me/201001995914"


def mask_proxy_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    p = urlparse(raw)
    host = p.hostname or ""
    port_part = f":{p.port}" if p.port else ""
    if p.username is not None:
        user = p.username or ""
        netloc = f"{user}:***@{host}{port_part}"
    else:
        netloc = f"{host}{port_part}" if host else (p.netloc or "")
    return urlunparse((p.scheme, netloc, "", "", "", ""))


def parse_proxy_url(proxy_url: str | None) -> tuple[dict | None, dict]:
    """
    Build requests proxies dict and JSON-safe network metadata.
    Supports http, https, socks5, socks5h (needs PySocks — requests[socks]).
    """
    if not proxy_url or not str(proxy_url).strip():
        return None, {"proxy_enabled": False}

    u = proxy_url.strip()
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https", "socks5", "socks5h"):
        raise ValueError(
            f"Unsupported proxy scheme: {parsed.scheme!r}. Use http, https, socks5, or socks5h."
        )
    if not parsed.hostname:
        raise ValueError("Proxy URL must include a host (e.g. http://127.0.0.1:8080).")

    proxies = {"http": u, "https": u}
    meta = {
        "proxy_enabled": True,
        "proxy_url_masked": mask_proxy_url(u),
        "proxy_scheme": parsed.scheme,
    }
    return proxies, meta


DEVICE_REGISTER_URL = "https://log-va.tiktokv.com/service/2/device_register/"


def format_register_request_log(
    device_index: int,
    url: str,
    headers: dict,
    body: bytes,
    body_hex_preview_bytes: int = 512,
    hex_line_width: int = 64,
) -> str:
    """Human-readable log of POST headers + body (hex preview) for the UI Log panel."""
    n = min(len(body), body_hex_preview_bytes)
    hx = binascii.hexlify(body[:n]).decode("ascii")
    if len(body) > body_hex_preview_bytes:
        hx += " …[truncated]"
    if hex_line_width > 0 and hx:
        hx = "\n".join(
            hx[i : i + hex_line_width] for i in range(0, len(hx), hex_line_width)
        )
    lines = [
        f"========== Device #{device_index} ==========",
        f"POST {url}",
        "",
        "Headers:",
        json.dumps(headers, ensure_ascii=False, indent=2),
        "",
        f"Body: {len(body)} bytes (application/octet-stream)",
        f"Body (hex, first {n} bytes):",
        hx,
        "",
    ]
    return "\n".join(lines)


def generate_one_device(
    libs_path: Path,
    jni_path: Path,
    java_exe: str,
    proxy_url: str | None = None,
    device_batch_index: int = 0,
):
    """
    Run unidbg + device_register. Returns (ok: bool, payload: dict).
    payload includes network/proxy info, inputs, API body or error (same flow as original tool).
    """
    try:
        proxies, network_meta = parse_proxy_url(proxy_url)
    except ValueError as e:
        return False, {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "step": "proxy_config",
            "error": str(e),
            "network": {"proxy_enabled": bool(proxy_url and str(proxy_url).strip())},
        }

    headers = {
        "user-agent": "com.zhiliaoapp.musically/2023105030",
        "content-type": "application/octet-stream;tt-data=a",
    }

    gentime = str(int(time.time() * 1000))
    ud_id = str(random.randint(221480502743165, 821480502743165))
    openu_did = "".join(random.choice("0123456789abcdef") for _ in range(16))
    mc = getrandommc()
    message = " ".join([gentime, ud_id, openu_did, mc])

    jp = str(jni_path.resolve())
    # JVM options (-D…) must come *before* -jar; otherwise native paths may be ignored.
    command = (
        '"{2}" -Djna.library.path="{0}" -Djava.library.path="{0}" -jar unidbg.jar {1}'
    ).format(jp, message, java_exe)

    base = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "network": network_meta,
        "input": {
            "gentime_ms": gentime,
            "ud_id": ud_id,
            "openudid": openu_did,
            "mac_pattern": mc,
            "unidbg_message": message,
        },
    }

    completed = subprocess.run(
        command,
        cwd=str(libs_path),
        shell=True,
        capture_output=True,
    )
    out = completed.stdout.decode("utf-8", errors="replace")
    err = completed.stderr.decode("utf-8", errors="replace")
    combined = f"{out}\n{err}"
    # unidbg prints a hex block then a line starting with "size" (CRLF or extra spaces possible).
    match = re.search(r"(?is)hex\s*=\s*([\s\S]*?)\r?\n\s*size\b", combined)
    if not match:
        match = re.search(r"(?is)hex\s*=\s*([0-9a-fA-F\s]+)", combined)
    if not match:
        detail = (combined.strip() or "(no output)")
        return False, {
            **base,
            "status": "failed",
            "step": "unidbg",
            "java_returncode": completed.returncode,
            "error": "Could not parse unidbg output (expected hex=… then a line starting with size).",
            "stderr": detail[:4000],
            "unidbg_stdout": out[:2000],
            "unidbg_stderr": err[:2000],
        }

    hex_str = re.sub(r"\s+", "", match.group(1))
    try:
        astr = binascii.unhexlify(hex_str.encode("ascii"))
    except (binascii.Error, ValueError) as e:
        return False, {
            **base,
            "status": "failed",
            "step": "hex_decode",
            "error": str(e),
        }

    register = DEVICE_REGISTER_URL
    base["request_log"] = format_register_request_log(
        device_batch_index, register, headers, astr
    )

    try:
        with requests.Session() as sess:
            sess.trust_env = proxies is None
            r = sess.post(
                register,
                data=astr,
                headers=headers,
                timeout=30,
                proxies=proxies,
            )
        http_status = r.status_code
        r.raise_for_status()
        response = r.json()
    except requests.RequestException as e:
        extra = f"\n--- HTTP error ---\n{type(e).__name__}: {e}\n"
        return False, {
            **base,
            "status": "failed",
            "step": "http",
            "error": str(e),
            "request_log": base["request_log"] + extra,
        }
    except ValueError:
        extra = (
            f"\n--- Invalid JSON response ---\nHTTP {r.status_code}\n"
            f"Body (first 2000 chars):\n{r.text[:2000]}\n"
        )
        return False, {
            **base,
            "status": "failed",
            "step": "json",
            "http_status": r.status_code,
            "error": "Server did not return JSON.",
            "raw_text_preview": r.text[:2000],
            "request_log": base["request_log"] + extra,
        }

    if "device_id" not in response or "install_id" not in response:
        extra = (
            "\n--- Unexpected JSON (missing ids) ---\n"
            f"{json.dumps(response, ensure_ascii=False, indent=2)[:4000]}\n"
        )
        return False, {
            **base,
            "status": "failed",
            "step": "api_body",
            "http_status": http_status,
            "error": "Missing device_id or install_id in response.",
            "register_response": response,
            "request_log": base["request_log"] + extra,
        }

    resp_body = json.dumps(response, ensure_ascii=False, indent=2)
    tail = f"\n--- Response ---\nHTTP {http_status}\n{resp_body}\n"
    rec = {
        **base,
        "status": "ok",
        "http_status": http_status,
        "register_response": response,
        "device_id": response.get("device_id"),
        "install_id": response.get("install_id"),
        "device_id_str": str(response.get("device_id_str", response.get("device_id", ""))),
        "install_id_str": str(response.get("install_id_str", response.get("install_id", ""))),
        "server_time": response.get("server_time"),
        "new_user": response.get("new_user"),
        "request_log": base["request_log"] + tail,
    }
    return True, rec


DEVICES_PER_JSON_FILE = 50
DEVICE_SUBDIR_NAME = "Device"


def project_generated_devices_dir() -> Path:
    """Always `<project>/generated_devices/`."""
    return Path(__file__).resolve().parent / "generated_devices"


def flat_device_export_dir() -> Path:
    """`<project>/Device/` — device chunk JSON files (not under generated_devices)."""
    return Path(__file__).resolve().parent / DEVICE_SUBDIR_NAME


class DeviceChunkWriter:
    """Writes `devices_001.json`, … under project `Device/` (continues part numbers across runs)."""

    @staticmethod
    def _next_part_number(device_dir: Path) -> int:
        device_dir.mkdir(parents=True, exist_ok=True)
        highest = 0
        for p in device_dir.glob("devices_*.json"):
            core = p.stem
            if core.startswith("devices_"):
                suffix = core[8:]
                if suffix.isdigit():
                    highest = max(highest, int(suffix))
        return highest + 1

    def __init__(self, device_dir: Path, per_file: int = DEVICES_PER_JSON_FILE):
        self.device_dir = device_dir
        self.per_file = per_file
        self._part = self._next_part_number(device_dir)
        self._buffer: list[dict] = []

    def add(self, batch_index: int, payload: dict) -> None:
        self._buffer.append({"batch_index": batch_index, "record": payload})
        self.device_dir.mkdir(parents=True, exist_ok=True)
        if len(self._buffer) >= self.per_file:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        path = self.device_dir / f"devices_{self._part:03d}.json"
        self._buffer.sort(key=lambda x: x["batch_index"])
        doc = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "part": self._part,
            "devices_per_file": self.per_file,
            "count": len(self._buffer),
            "devices": self._buffer,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        self._part += 1
        self._buffer = []

    def close(self) -> None:
        self._flush()

    def status_hint(self) -> str:
        n = len(self._buffer)
        proj = Path(__file__).resolve().parent
        try:
            rel = self.device_dir.relative_to(proj)
            prefix = str(rel).replace("\\", "/")
        except ValueError:
            prefix = str(self.device_dir)
        return f"{prefix}/devices_{self._part:03d}.json · {n}/{self.per_file}"


def copy_to_clipboard(content):
    root.clipboard_clear()
    root.clipboard_append(content)
    messagebox.showinfo("Copied", "Content copied to clipboard!")


def main():
    global root, openudid, device_id, iid

    C = {
        "bg": "#eceff3",
        "header": "#0b1220",
        "header_line": "#6366f1",
        "header_sub": "#a5b4fc",
        "card": "#ffffff",
        "text": "#0f172a",
        "muted": "#64748b",
        "accent": "#4f46e5",
        "accent_dark": "#4338ca",
        "stop": "#e11d48",
        "stop_dark": "#be123c",
        "footer_bg": "#f8fafc",
        "footer_border": "#e2e8f0",
        "field_bg": "#f1f5f9",
        "ring": "#c7d2fe",
        "prog_trough": "#e2e8f0",
        "prog_fill": "#6366f1",
        "secondary_btn": "#e0e7ff",
        "secondary_btn_active": "#c7d2fe",
    }

    root = tk.Tk()
    root.title(f"{APP_DISPLAY_TITLE} · {COMPANY_NAME}")
    root.configure(bg=C["bg"])
    root.minsize(600, 680)
    root.geometry("640x760")

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Card.TLabelframe", background=C["card"])
    style.configure(
        "Card.TLabelframe.Label",
        background=C["card"],
        foreground=C["text"],
        font=("Segoe UI", 10, "bold"),
    )
    style.configure("App.TLabel", background=C["card"], foreground=C["text"], font=("Segoe UI", 10))
    style.configure("AppMuted.TLabel", background=C["card"], foreground=C["muted"], font=("Segoe UI", 9))
    style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(8, 5))
    style.configure(
        "App.Horizontal.TProgressbar",
        troughcolor=C["prog_trough"],
        background=C["prog_fill"],
        troughrelief=tk.FLAT,
        borderwidth=0,
        lightcolor=C["prog_fill"],
        darkcolor=C["prog_fill"],
        thickness=12,
    )
    style.map(
        "App.Horizontal.TProgressbar",
        background=[("!disabled", C["prog_fill"])],
        troughcolor=[("!disabled", C["prog_trough"])],
    )

    openudid = tk.StringVar()
    device_id = tk.StringVar()
    iid = tk.StringVar()
    out_dir_var = tk.StringVar(value=str(default_output_dir()))
    count_var = tk.StringVar(value="1")
    threads_var = tk.StringVar(value="4")
    proxy_var = tk.StringVar(value="")

    ui_queue: queue.Queue = queue.Queue()
    running = {"active": False, "cancel_event": None, "progress_indeterminate": False}

    header = tk.Frame(root, bg=C["header"], height=86)
    header.pack(side=tk.TOP, fill=tk.X)
    header.pack_propagate(False)
    accent_bar = tk.Frame(header, bg=C["header_line"], height=3)
    accent_bar.pack(side=tk.TOP, fill=tk.X)
    head_inner = tk.Frame(header, bg=C["header"])
    head_inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=(12, 14))
    tk.Label(
        head_inner,
        text=APP_DISPLAY_TITLE,
        bg=C["header"],
        fg="#f8fafc",
        font=("Segoe UI", 17, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(
        head_inner,
        text="Batch device register · JSON export · proxy support",
        bg=C["header"],
        fg=C["header_sub"],
        font=("Segoe UI", 9),
    ).pack(anchor=tk.W, pady=(2, 0))

    footer = tk.Frame(root, bg=C["footer_bg"], highlightthickness=1, highlightbackground=C["footer_border"])
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    fu = tk.Frame(footer, bg=C["footer_bg"])
    fu.pack(fill=tk.X, padx=12, pady=6)

    def foot_sep(parent):
        tk.Label(parent, text="·", bg=C["footer_bg"], fg=C["muted"], font=("Segoe UI", 9)).pack(
            side=tk.LEFT, padx=8
        )

    tk.Label(
        fu,
        text=f"Developer · {DEVELOPER_NAME_EN}",
        bg=C["footer_bg"],
        fg=C["text"],
        font=("Segoe UI", 8, "bold"),
    ).pack(side=tk.LEFT)
    foot_sep(fu)
    tk.Label(
        fu,
        text=f"Company · {COMPANY_NAME}",
        bg=C["footer_bg"],
        fg=C["muted"],
        font=("Segoe UI", 8),
    ).pack(side=tk.LEFT)
    foot_sep(fu)
    link_lbl = tk.Label(
        fu,
        text=COMPANY_URL,
        bg=C["footer_bg"],
        fg=C["accent"],
        font=("Segoe UI", 8, "underline"),
        cursor="hand2",
    )
    link_lbl.pack(side=tk.LEFT)
    link_lbl.bind("<Button-1>", lambda e: webbrowser.open(COMPANY_URL))
    foot_sep(fu)
    phone_lbl = tk.Label(
        fu,
        text=f"Contact · {CONTACT_PHONE}",
        bg=C["footer_bg"],
        fg=C["accent"],
        font=("Segoe UI", 8, "underline"),
        cursor="hand2",
    )
    phone_lbl.pack(side=tk.LEFT)
    phone_lbl.bind("<Button-1>", lambda e: webbrowser.open(CONTACT_WHATSAPP_URL))

    body = tk.Frame(root, bg=C["bg"])
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def open_output_folder():
        p = out_dir_var.get().strip()
        if not p:
            return
        path = Path(p)
        path.mkdir(parents=True, exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except OSError:
            messagebox.showerror("Open folder", f"Could not open:\n{path}")

    action_bar = tk.Frame(
        body,
        bg=C["card"],
        highlightthickness=1,
        highlightbackground=C["ring"],
    )
    action_bar.pack(fill=tk.X, padx=12, pady=(8, 6))
    btn_inner = tk.Frame(action_bar, bg=C["card"])
    btn_inner.pack(fill=tk.X, padx=12, pady=8)

    run_btns = tk.Frame(btn_inner, bg=C["card"])
    run_btns.pack(side=tk.LEFT)

    btn_run_w = 11
    btn_run_py = 7
    btn_run_px = 0

    start_btn = tk.Button(
        run_btns,
        text="Start",
        font=("Segoe UI", 10, "bold"),
        bg=C["accent"],
        fg="#ffffff",
        activebackground=C["accent_dark"],
        activeforeground="#ffffff",
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=0,
        cursor="hand2",
        width=btn_run_w,
        padx=btn_run_px,
        pady=btn_run_py,
    )
    start_btn.pack(side=tk.LEFT)

    stop_btn = tk.Button(
        run_btns,
        text="Stop",
        state=tk.DISABLED,
        font=("Segoe UI", 10, "bold"),
        bg=C["stop"],
        fg="#ffffff",
        activebackground=C["stop_dark"],
        activeforeground="#ffffff",
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=0,
        cursor="hand2",
        width=btn_run_w,
        padx=btn_run_px,
        pady=btn_run_py,
    )
    stop_btn.pack(side=tk.LEFT, padx=(8, 0))

    open_out_btn = tk.Button(
        btn_inner,
        text="Open output folder",
        command=open_output_folder,
        font=("Segoe UI", 9),
        bg=C["secondary_btn"],
        fg=C["text"],
        activebackground=C["secondary_btn_active"],
        activeforeground=C["text"],
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=C["ring"],
        cursor="hand2",
        padx=14,
        pady=btn_run_py,
    )
    open_out_btn.pack(side=tk.RIGHT)

    opts = ttk.LabelFrame(body, text="  Batch options  ", style="Card.TLabelframe", padding=(10, 8))
    opts.pack(fill=tk.X, padx=12, pady=(2, 6))

    row0 = tk.Frame(opts, bg=C["card"])
    row0.pack(fill=tk.X)
    ttk.Label(row0, text="Number of devices", style="App.TLabel").pack(side=tk.LEFT)
    count_sb = tk.Spinbox(
        row0,
        from_=1,
        to=9999,
        width=10,
        textvariable=count_var,
        font=("Segoe UI", 10),
        buttoncursor="hand2",
        relief=tk.FLAT,
        bg=C["field_bg"],
        highlightthickness=1,
        highlightbackground=C["ring"],
    )
    count_sb.pack(side=tk.LEFT, padx=(10, 28))
    ttk.Label(row0, text="Threads", style="App.TLabel").pack(side=tk.LEFT)
    threads_sb = tk.Spinbox(
        row0,
        from_=1,
        to=64,
        width=6,
        textvariable=threads_var,
        font=("Segoe UI", 10),
        buttoncursor="hand2",
        relief=tk.FLAT,
        bg=C["field_bg"],
        highlightthickness=1,
        highlightbackground=C["ring"],
    )
    threads_sb.pack(side=tk.LEFT, padx=(10, 0))

    row_storage_proxy = tk.Frame(opts, bg=C["card"])
    row_storage_proxy.pack(fill=tk.X, pady=(8, 0))
    row_storage_proxy.columnconfigure(0, weight=1, uniform="opt_col")
    row_storage_proxy.columnconfigure(1, weight=1, uniform="opt_col")

    col_out = tk.Frame(row_storage_proxy, bg=C["card"])
    col_out.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
    ttk.Label(col_out, text="Output folder", style="App.TLabel").pack(anchor=tk.W)
    row1e = tk.Frame(col_out, bg=C["card"])
    row1e.pack(fill=tk.X, pady=(4, 0))
    out_entry = tk.Entry(
        row1e,
        textvariable=out_dir_var,
        font=("Segoe UI", 9),
        relief=tk.FLAT,
        bg=C["field_bg"],
        highlightthickness=1,
        highlightbackground=C["ring"],
    )
    out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

    def browse_out():
        p = filedialog.askdirectory(initialdir=out_dir_var.get() or str(default_output_dir()))
        if p:
            out_dir_var.set(p)

    ttk.Button(row1e, text="Browse…", style="Secondary.TButton", command=browse_out).pack(
        side=tk.LEFT, padx=(6, 0)
    )

    col_proxy = tk.Frame(row_storage_proxy, bg=C["card"])
    col_proxy.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0))
    ttk.Label(col_proxy, text="Proxy URL (optional)", style="App.TLabel").pack(anchor=tk.W)
    proxy_entry = tk.Entry(
        col_proxy,
        textvariable=proxy_var,
        font=("Segoe UI", 9),
        relief=tk.FLAT,
        bg=C["field_bg"],
        highlightthickness=1,
        highlightbackground=C["ring"],
    )
    proxy_entry.pack(fill=tk.X, pady=(4, 2), ipady=4)
    ttk.Label(
        col_proxy,
        text="http://host:port · user:pass@host · socks5h://127.0.0.1:1080",
        style="AppMuted.TLabel",
    ).pack(anchor=tk.W)

    output_frame = ttk.LabelFrame(body, text="  Last device (preview)  ", style="Card.TLabelframe", padding=(10, 8))
    output_frame.pack(fill=tk.X, padx=12, pady=4)

    preview_inner = tk.Frame(output_frame, bg=C["card"])
    preview_inner.pack(fill=tk.X)
    for col in range(3):
        preview_inner.columnconfigure(col, weight=1, uniform="preview_col")

    def preview_cell(parent, col, label, var, copy_cmd, pad_l):
        px = (pad_l, 6) if col else (0, 6)
        ttk.Label(parent, text=label, style="AppMuted.TLabel").grid(
            row=0, column=col, sticky=tk.W, padx=px, pady=(0, 2)
        )
        ent = tk.Entry(
            parent,
            textvariable=var,
            font=("Consolas", 8),
            state="readonly",
            readonlybackground=C["field_bg"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["ring"],
        )
        ent.grid(row=1, column=col, sticky=tk.EW, padx=px, pady=(0, 4), ipady=2)
        ttk.Button(parent, text="Copy", style="Secondary.TButton", command=copy_cmd).grid(
            row=2, column=col, sticky=tk.W, padx=px, pady=(0, 0)
        )

    preview_cell(preview_inner, 0, "OpenUDID", openudid, lambda: copy_to_clipboard(openudid.get()), 0)
    preview_cell(preview_inner, 1, "Device ID", device_id, lambda: copy_to_clipboard(device_id.get()), 4)
    preview_cell(preview_inner, 2, "IID", iid, lambda: copy_to_clipboard(iid.get()), 4)

    prog_frame = tk.Frame(body, bg=C["bg"])
    prog_frame.pack(fill=tk.X, padx=12, pady=(4, 2))
    tk.Label(
        prog_frame,
        text="Batch progress",
        anchor=tk.W,
        bg=C["bg"],
        fg=C["muted"],
        font=("Segoe UI", 9, "bold"),
    ).pack(fill=tk.X)
    progress = ttk.Progressbar(
        prog_frame,
        mode="determinate",
        maximum=100,
        style="App.Horizontal.TProgressbar",
    )
    progress.pack(fill=tk.X, pady=(2, 0))
    prog_line = tk.Frame(prog_frame, bg=C["bg"])
    prog_line.pack(fill=tk.X, pady=(4, 0))
    progress_pct_var = tk.StringVar(value="")
    tk.Label(
        prog_line,
        textvariable=progress_pct_var,
        anchor=tk.W,
        bg=C["bg"],
        fg=C["accent"],
        font=("Segoe UI", 9, "bold"),
    ).pack(side=tk.LEFT)
    status_var = tk.StringVar(value="Ready.")
    tk.Label(
        prog_line,
        textvariable=status_var,
        anchor=tk.W,
        bg=C["bg"],
        fg=C["muted"],
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT, padx=(12, 0))

    log_frame = ttk.LabelFrame(body, text="  Log  ", style="Card.TLabelframe", padding=(8, 6))
    log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2, 8))
    log_text = scrolledtext.ScrolledText(
        log_frame,
        height=9,
        width=78,
        wrap=tk.CHAR,
        font=("Consolas", 8),
        bg=C["field_bg"],
        fg=C["text"],
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=C["ring"],
        state=tk.DISABLED,
    )
    log_text.pack(fill=tk.BOTH, expand=True)

    def halt_progress_loading():
        if running.get("progress_indeterminate"):
            try:
                progress.stop()
            except tk.TclError:
                pass
            running["progress_indeterminate"] = False
        try:
            progress.config(mode="determinate")
        except tk.TclError:
            pass

    def request_stop():
        ev = running.get("cancel_event")
        if ev is not None:
            ev.set()
        status_var.set("Stopping…")

    stop_btn.config(command=request_stop)

    def process_ui_queue():
        try:
            while True:
                kind, data = ui_queue.get_nowait()
                if kind == "progress":
                    done, total, msg = data
                    if running.get("progress_indeterminate"):
                        halt_progress_loading()
                    progress["maximum"] = max(total, 1)
                    progress["value"] = done
                    pct = (100 * done) // max(total, 1)
                    progress_pct_var.set(f"{done} / {total}  ·  {pct}% complete")
                    status_var.set(msg)
                elif kind == "log":
                    try:
                        log_text.config(state=tk.NORMAL)
                        chunk = str(data)
                        log_text.insert(tk.END, chunk)
                        if not chunk.endswith("\n"):
                            log_text.insert(tk.END, "\n")
                        log_text.see(tk.END)
                        log_text.config(state=tk.DISABLED)
                        root.update_idletasks()
                    except tk.TclError:
                        pass
                elif kind == "last_ok":
                    o, d, i = data
                    openudid.set(o)
                    device_id.set(d)
                    iid.set(i)
                elif kind == "done":
                    ok_n, fail_n, devices_path, summary_path = data
                    running["active"] = False
                    running["cancel_event"] = None
                    halt_progress_loading()
                    start_btn.config(state=tk.NORMAL)
                    stop_btn.config(state=tk.DISABLED)
                    count_sb.config(state=tk.NORMAL)
                    threads_sb.config(state=tk.NORMAL)
                    proxy_entry.config(state=tk.NORMAL)
                    progress["value"] = progress["maximum"]
                    progress_pct_var.set(f"Done  ·  {ok_n} OK / {fail_n} failed  ·  100%")
                    status_var.set(f"Finished. OK: {ok_n}  Failed: {fail_n}  → {devices_path}")
                    messagebox.showinfo(
                        "Batch complete",
                        f"Success: {ok_n}\nFailed: {fail_n}\n\n"
                        f"Devices folder:\n{devices_path}\n\nBatch summary:\n{summary_path}",
                    )
                elif kind == "cancelled":
                    ok_n, fail_n, devices_path, summary_path, n_req, done_partial = data
                    running["active"] = False
                    running["cancel_event"] = None
                    halt_progress_loading()
                    start_btn.config(state=tk.NORMAL)
                    stop_btn.config(state=tk.DISABLED)
                    count_sb.config(state=tk.NORMAL)
                    threads_sb.config(state=tk.NORMAL)
                    proxy_entry.config(state=tk.NORMAL)
                    progress["maximum"] = max(n_req, 1)
                    progress["value"] = done_partial
                    pstop = (100 * done_partial) // max(n_req, 1)
                    progress_pct_var.set(
                        f"Stopped  ·  {done_partial}/{n_req}  ·  {pstop}%  ·  OK {ok_n} / Fail {fail_n}"
                    )
                    status_var.set(
                        f"Stopped. Done {done_partial}/{n_req}  OK: {ok_n}  Fail: {fail_n}"
                    )
                    messagebox.showinfo(
                        "Stopped",
                        f"Generation stopped.\nCompleted: {done_partial} / {n_req}\n"
                        f"OK: {ok_n}  Failed: {fail_n}\n\n"
                        f"Devices folder:\n{devices_path}\n\nBatch summary:\n{summary_path}",
                    )
                elif kind == "error":
                    running["active"] = False
                    running["cancel_event"] = None
                    halt_progress_loading()
                    start_btn.config(state=tk.NORMAL)
                    stop_btn.config(state=tk.DISABLED)
                    count_sb.config(state=tk.NORMAL)
                    threads_sb.config(state=tk.NORMAL)
                    proxy_entry.config(state=tk.NORMAL)
                    progress["maximum"] = 100
                    progress["value"] = 0
                    progress_pct_var.set("")
                    status_var.set("Error — see message.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass
        root.after(40, process_ui_queue)

    def start_batch():
        if running["active"]:
            return

        libs_path = Path(__file__).resolve().parent / "Libs"
        jni_path = libs_path / "prebuilt" / getsystem()
        jar_path = libs_path / "unidbg.jar"

        if not jar_path.is_file():
            messagebox.showerror(
                "Missing unidbg.jar",
                f"Expected file not found:\n{jar_path}",
            )
            return
        if not jni_path.is_dir():
            messagebox.showerror(
                "Missing native libraries",
                f"Folder not found:\n{jni_path}",
            )
            return

        try:
            n = int(count_var.get().strip())
            w = int(threads_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Device count and threads must be integers.")
            return

        if n < 1:
            messagebox.showerror("Invalid input", "Device count must be at least 1.")
            return
        if w < 1:
            messagebox.showerror("Invalid input", "Threads must be at least 1.")
            return
        w = min(w, n, 64)

        proxy_line = proxy_var.get().strip()
        if proxy_line:
            try:
                parse_proxy_url(proxy_line)
            except ValueError as e:
                messagebox.showerror("Invalid proxy", str(e))
                return

        java_exe = get_java_exe()
        _as_warn = apple_silicon_unidbg_java_warning(java_exe)
        if _as_warn:
            if not messagebox.askokcancel(
                "Java / unidbg on Apple Silicon",
                _as_warn,
                default=messagebox.CANCEL,
            ):
                return

        batch_root = project_generated_devices_dir()
        batch_root.mkdir(parents=True, exist_ok=True)
        devices_dir = flat_device_export_dir()
        devices_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = batch_root / f"_batch_summary_{stamp}.json"

        running["active"] = True
        cancel_event = threading.Event()
        running["cancel_event"] = cancel_event
        start_btn.config(state=tk.DISABLED)
        stop_btn.config(state=tk.NORMAL)
        count_sb.config(state=tk.DISABLED)
        threads_sb.config(state=tk.DISABLED)
        proxy_entry.config(state=tk.DISABLED)
        halt_progress_loading()
        progress["maximum"] = 100
        progress["value"] = 0
        log_text.config(state=tk.NORMAL)
        log_text.delete("1.0", tk.END)
        log_text.config(state=tk.DISABLED)
        progress_pct_var.set("Loading… preparing batch")
        running["progress_indeterminate"] = True
        progress.config(mode="indeterminate")
        progress.start(10)
        status_var.set(f"Loading… preparing {n} device(s) · {w} thread(s)")

        proxy_for_jobs = proxy_line or None
        _, batch_network_meta = parse_proxy_url(proxy_for_jobs)

        def worker():
            ok_count = 0
            fail_count = 0
            done = 0
            cancelled = False
            device_writer = DeviceChunkWriter(devices_dir)
            ui_queue.put(
                (
                    "log",
                    f"=== Batch started · {n} device(s) · {w} thread(s) ===\n",
                )
            )

            def one_job(idx: int):
                return idx, *generate_one_device(
                    libs_path,
                    jni_path,
                    java_exe,
                    proxy_for_jobs,
                    device_batch_index=idx,
                )

            ex = ThreadPoolExecutor(max_workers=w)
            try:
                future_list = [ex.submit(one_job, i) for i in range(1, n + 1)]
                pending = set(future_list)
                while pending:
                    if cancel_event.is_set():
                        cancelled = True
                        break
                    done_now, pending = wait(pending, timeout=0.25, return_when=FIRST_COMPLETED)
                    for fut in done_now:
                        try:
                            idx, ok, payload = fut.result()
                        except CancelledError:
                            continue
                        rl = payload.pop("request_log", None)
                        if rl:
                            ui_queue.put(("log", rl))
                        elif not ok:
                            tail = ""
                            je = payload.get("stderr") or payload.get("unidbg_stderr")
                            if payload.get("step") == "unidbg" and je:
                                tail = f"\n--- Java / unidbg output ---\n{str(je)[:3500]}\n"
                            elif payload.get("step") == "unidbg":
                                uo = payload.get("unidbg_stdout")
                                if uo:
                                    tail = f"\n--- unidbg stdout ---\n{str(uo)[:2000]}\n"
                            ui_queue.put(
                                (
                                    "log",
                                    f"========== Device #{idx} ==========\n"
                                    f"Failed step: {payload.get('step', '?')}\n"
                                    f"{payload.get('error', '')}\n"
                                    f"java_returncode={payload.get('java_returncode', '')}\n"
                                    f"{tail}",
                                )
                            )
                        device_writer.add(idx, payload)
                        if ok:
                            ok_count += 1
                            ui_queue.put(
                                (
                                    "last_ok",
                                    (
                                        str(payload["input"]["openudid"]),
                                        str(payload.get("device_id_str", "")),
                                        str(payload.get("install_id_str", "")),
                                    ),
                                )
                            )
                        else:
                            fail_count += 1
                        done += 1
                        ui_queue.put(
                            (
                                "progress",
                                (
                                    done,
                                    n,
                                    f"{done}/{n}  {device_writer.status_hint()}  OK={ok_count} Fail={fail_count}",
                                ),
                            )
                        )
            except Exception as e:
                ui_queue.put(("error", str(e)))
                return
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
                device_writer.close()

            try:
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "requested_devices": n,
                            "threads": w,
                            "success": ok_count,
                            "failed": fail_count,
                            "completed_tasks": done,
                            "cancelled": cancelled,
                            "batch_root": str(batch_root.resolve()),
                            "summary_file": str(summary_path.resolve()),
                            "devices_folder": DEVICE_SUBDIR_NAME,
                            "devices_directory": str(devices_dir.resolve()),
                            "devices_json_chunk_size": DEVICES_PER_JSON_FILE,
                            "network": batch_network_meta,
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            except OSError:
                pass

            dev_p = str(devices_dir.resolve())
            sum_p = str(summary_path.resolve())
            if cancelled:
                ui_queue.put(
                    ("cancelled", (ok_count, fail_count, dev_p, sum_p, n, done))
                )
            else:
                ui_queue.put(("done", (ok_count, fail_count, dev_p, sum_p)))

        threading.Thread(target=worker, daemon=True).start()

    start_btn.config(command=start_batch)
    root.after(30, process_ui_queue)
    root.mainloop()


root = None
openudid = device_id = iid = None

if __name__ == "__main__":
    main()
