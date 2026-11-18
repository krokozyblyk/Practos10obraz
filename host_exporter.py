import ctypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_uint32),
        ("dwHighDateTime", ctypes.c_uint32),
    ]


kernel32 = ctypes.windll.kernel32
kernel32.GetSystemTimes.argtypes = [
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
]
kernel32.GetSystemTimes.restype = ctypes.c_bool

state = {"value": 0.0}


def filetime_value(value):
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def read_times():
    idle = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    if not kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        raise ctypes.WinError()
    return filetime_value(idle), filetime_value(kernel), filetime_value(user)


def sampler():
    prev_idle, prev_kernel, prev_user = read_times()
    while True:
        time.sleep(1)
        idle, kernel, user = read_times()
        idle_delta = idle - prev_idle
        total = (kernel - prev_kernel) + (user - prev_user)
        busy = total - idle_delta
        state["value"] = max(0.0, min(100.0, busy / total * 100.0)) if total > 0 else 0.0
        prev_idle, prev_kernel, prev_user = idle, kernel, user


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = f"pc_cpu_usage_percent {state['value']:.2f}\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


threading.Thread(target=sampler, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 9273), Handler).serve_forever()
