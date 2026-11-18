from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import datetime
import html
import json
from pathlib import Path

LOG = Path(__file__).with_name("alerts.log")


def load_entries(limit=100):
    if not LOG.exists():
        return []
    lines = LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    entries = []
    for line in reversed(lines):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def render_page():
    rows = []
    for data in load_entries():
        status = data.get("status", "")
        receiver = data.get("receiver", "")
        for alert in data.get("alerts", []):
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            rows.append(
                "<tr class='%s'><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (
                    html.escape(status),
                    html.escape(status),
                    html.escape(str(data.get("receivedAt") or alert.get("startsAt", ""))[:19]),
                    html.escape(labels.get("alertname", "")),
                    html.escape(labels.get("source", "")),
                    html.escape(receiver),
                    html.escape(annotations.get("description", "")),
                )
            )
    body = "\n".join(rows) or "<tr><td colspan='6'>Нет событий</td></tr>"
    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>Alertmanager webhook</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:24px; }}
h1 {{ font-size:20px; margin:0 0 6px; }}
p {{ color:#94a3b8; }}
table {{ border-collapse:collapse; width:100%; }}
th, td {{ border:1px solid #334155; padding:8px 10px; text-align:left; }}
th {{ background:#1e293b; }}
tr.firing td {{ background:#3f1d1d; }}
tr.resolved td {{ background:#14321f; }}
td:first-child {{ font-weight:600; text-transform:uppercase; }}
</style></head><body>
<h1>Alertmanager → webhook</h1>
<p>События: {len(rows)}</p>
<table><thead><tr><th>Статус</th><th>Время</th><th>Алерт</th><th>Группа</th><th>Receiver</th><th>Описание</th></tr></thead>
<tbody>{body}</tbody></table>
</body></html>"""
    return page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {"raw": raw.decode("utf-8", "replace")}
        status = data.get("status")
        alerts = data.get("alerts", [])
        receiver = data.get("receiver", "")
        print(
            "%s receiver=%s status=%s alerts=%d"
            % (datetime.datetime.now().isoformat(timespec="seconds"), receiver, status, len(alerts)),
            flush=True,
        )
        for alert in alerts:
            labels = alert.get("labels", {})
            summary = alert.get("annotations", {}).get("summary", "")
            print(
                "  %s source=%s status=%s %s"
                % (labels.get("alertname"), labels.get("source"), alert.get("status"), summary),
                flush=True,
            )
        data["receivedAt"] = datetime.datetime.now().isoformat(timespec="seconds")
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):
        if self.path in ("/", "/webhook", "/webhook/app", "/webhook/pc"):
            body = render_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
