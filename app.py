#!/usr/bin/env python3
"""
Open Whisper - Click menubar icon to record
Pastes transcribed text into the active app
"""

import os
import sys
import site

sys.path.insert(0, site.getusersitepackages())
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")

import wave
import tempfile
import subprocess
import threading
import time
import json
import sqlite3
import logging
from pathlib import Path

import rumps
import pyaudio
from ApplicationServices import AXIsProcessTrustedWithOptions
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventSetFlags,
    CGEventPost,
    CGEventSourceCreate,
    kCGEventSourceStateHIDSystemState,
    kCGAnnotatedSessionEventTap,
    kCGEventFlagMaskCommand,
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventGetIntegerValueField,
    CGEventGetFlags,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventKeyDown,
    kCGKeyboardEventKeycode,
)
from Quartz import CFMachPortCreateRunLoopSource, CFRunLoopAddSource, CFRunLoopGetMain, kCFRunLoopCommonModes
from AppKit import (
    NSWindow, NSBackingStoreBuffered, NSMakeRect,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable, NSWindowStyleMaskResizable,
    NSApp, NSWorkspace,
)
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController
from Foundation import NSObject
import objc

HOTKEY_KEYCODE = 15  # R key
HOTKEY_FN_FLAG = 0x800000  # kCGEventFlagMaskSecondaryFn (Fn/Globe key)

DEFAULT_MODEL = "mlx-community/distil-whisper-large-v3"

MODELS = [
    ("mlx-community/distil-whisper-large-v3",       "Distil Large V3 — fastest, uses ~1.4 GB RAM (default)"),
    ("LibraxisAI/whisper-large-v3-turbo-mlx-q8",    "Turbo Q8 — 15% slower, uses ~880 MB RAM (save ~560 MB)"),
    ("mlx-community/whisper-large-v3-turbo",         "Large V3 Turbo — multilingual, uses ~1.6 GB RAM"),
    ("mlx-community/whisper-tiny",                   "Tiny — ultra fast, uses ~100 MB RAM (lower quality)"),
]

DATA_DIR = Path.home() / ".open-whisper"
DB_PATH = DATA_DIR / "history.db"
LOG_PATH = DATA_DIR / "app.log"
_OLD_DATA_DIR = Path.home() / ".voice-transcriber"

# Logging to file (stdout is swallowed by .app bundle)
DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("voice")

# Python path for subprocess transcription (avoids MLX/rumps thread deadlock)
PYTHON = "/usr/bin/python3"

WORKER_SCRIPT = '''
import sys, os, time, json
sys.path.insert(0, "__USER_SITE__")
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")'''.replace("__USER_SITE__", site.getusersitepackages()) + '''

# Redirect stderr so download progress bars don't corrupt stdout
sys.stderr = open(os.devnull, "w")

import mlx.core as mx

# Cap MLX Metal cache at 200MB between transcriptions
mx.metal.set_cache_limit(200 * 1024 * 1024)

# Read model from first stdin line
model = sys.stdin.readline().strip()

t0 = time.time()
import mlx_whisper
import_time = time.time() - t0

# Signal ready
print(json.dumps({"status": "ready", "import_time": round(import_time, 3), "model": model}), flush=True)

# Process requests forever
for line in sys.stdin:
    wav_path = line.strip()
    if not wav_path:
        continue
    t0 = time.time()
    try:
        result = mlx_whisper.transcribe(
            wav_path,
            path_or_hf_repo=model,
            language="en",
            verbose=False
        )
        text = result.get("text", "").strip()
        elapsed = time.time() - t0
        active_mb = mx.metal.get_active_memory() / 1024 / 1024
        cache_mb  = mx.metal.get_cache_memory()  / 1024 / 1024
        peak_mb   = mx.metal.get_peak_memory()   / 1024 / 1024
        mx.metal.clear_cache()
        after_mb  = mx.metal.get_active_memory() / 1024 / 1024
        print(json.dumps({
            "text": text,
            "transcribe_time": round(elapsed, 3),
            "mem_active_mb": round(active_mb, 1),
            "mem_cache_mb":  round(cache_mb,  1),
            "mem_peak_mb":   round(peak_mb,   1),
            "mem_after_mb":  round(after_mb,  1),
        }), flush=True)
        mx.metal.reset_peak_memory()
    except Exception as e:
        mx.metal.clear_cache()
        print(json.dumps({"text": "", "error": str(e), "transcribe_time": round(time.time() - t0, 3)}), flush=True)
'''


class TranscribeWorker:
    """Persistent subprocess that keeps mlx_whisper loaded in memory."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self.model = DEFAULT_MODEL

    def start(self, model=None):
        if model:
            self.model = model
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LANG": "en_US.UTF-8"}
        self._proc = subprocess.Popen(
            [PYTHON, "-c", WORKER_SCRIPT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", env=env
        )
        # Send model name, then wait for "ready" signal
        self._proc.stdin.write(self.model + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        info = json.loads(line)
        log.info(f"worker: started, model={self.model}, import_time={info.get('import_time')}s")
        # Warm up: transcribe a tiny silent WAV to page model weights into memory
        self._warmup()

    def transcribe(self, wav_path):
        with self._lock:
            if not self._proc or self._proc.poll() is not None:
                log.warning("worker: process dead, restarting")
                self.start()
            self._proc.stdin.write(wav_path + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("worker: no response")
            result = json.loads(line)
            if "error" in result:
                log.error(f"worker: error={result['error']}")
            log.info(
                f"worker: transcribe_time={result.get('transcribe_time')}s | "
                f"mem active={result.get('mem_active_mb')}MB "
                f"cache={result.get('mem_cache_mb')}MB "
                f"peak={result.get('mem_peak_mb')}MB "
                f"after_clear={result.get('mem_after_mb')}MB"
            )
            return result.get("text", ""), result.get("transcribe_time", 0)

    def _warmup(self):
        """Transcribe 0.5s of silence to page model weights into memory."""
        try:
            import wave, tempfile, struct
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
            samples = b'\x00\x00' * 8000  # 0.5s of silence at 16kHz, 16-bit
            with wave.open(path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(samples)
            t0 = time.time()
            self._proc.stdin.write(path + "\n")
            self._proc.stdin.flush()
            self._proc.stdout.readline()  # discard result
            os.unlink(path)
            log.info(f"worker: warmup done in {time.time()-t0:.2f}s")
        except Exception as e:
            log.warning(f"worker: warmup failed: {e}")

    def restart(self, model):
        log.info(f"worker: restarting with model={model}")
        self.stop()
        self.start(model)

    def stop(self):
        if self._proc:
            self._proc.stdin.close()
            self._proc.wait(timeout=5)
            self._proc = None


worker = TranscribeWorker()


HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #faf7f2 0%, #f5f0e8 100%);
    color: #3d3529;
    padding: 24px 24px 16px;
    -webkit-user-select: none;
  }
  .header { text-align: center; margin-bottom: 20px; }
  .status-icon { font-size: 38px; margin-bottom: 4px; }
  .status-text { font-size: 16px; font-weight: 600; color: #5a4e3c; }
  .status-hint { font-size: 11px; color: #9a8e7c; margin-top: 3px; }
  .toolbar {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px; gap: 8px;
  }
  .toolbar-left { display: flex; align-items: center; gap: 8px; }
  .toolbar-right { display: flex; align-items: center; gap: 6px; }
  .filter-select {
    font-size: 12px; padding: 4px 8px; border-radius: 6px;
    border: 1px solid rgba(0,0,0,0.1); background: rgba(255,255,255,0.7);
    color: #5a4e3c; font-family: inherit; cursor: pointer;
  }
  .section-title {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: #b0a48f;
  }
  .export-btn {
    background: none; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px;
    padding: 4px 10px; font-size: 11px; color: #8a7e6c; cursor: pointer;
    font-family: inherit; transition: all 0.15s;
  }
  .export-btn:hover { background: rgba(0,0,0,0.05); color: #5a4e3c; }
  .date-group {
    font-size: 12px; font-weight: 600; color: #8a7e6c;
    margin-top: 16px; margin-bottom: 6px; padding-left: 2px;
  }
  .date-group:first-child { margin-top: 0; }
  .entries { display: flex; flex-direction: column; gap: 8px; }
  .entry {
    background: rgba(255,255,255,0.75); border-radius: 10px;
    padding: 12px 14px; transition: background 0.15s;
    border: 1px solid rgba(0,0,0,0.04);
  }
  .entry:hover { background: rgba(255,255,255,0.95); }
  .entry.hidden { display: none; }
  .entry-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 4px;
  }
  .entry-meta {
    font-size: 11px; color: #b0a48f; font-weight: 500;
    display: flex; align-items: center; gap: 6px;
  }
  .entry-app {
    background: rgba(0,0,0,0.05); padding: 1px 6px;
    border-radius: 4px; font-size: 10px;
  }
  .copy-btn {
    background: none; border: none; padding: 4px; cursor: pointer;
    color: #b0a48f; transition: color 0.15s; line-height: 1;
  }
  .copy-btn:hover { color: #5a4e3c; }
  .copy-btn.copied svg { display: none; }
  .copy-btn .check { display: none; color: #5a9a5a; font-size: 14px; }
  .copy-btn.copied .check { display: inline; }
  .entry-text {
    font-size: 14px; line-height: 1.45; color: #3d3529;
    -webkit-user-select: text;
  }
  .empty {
    text-align: center; padding: 48px 20px; color: #b0a48f;
    font-size: 14px; line-height: 1.6;
  }
  .model-bar {
    margin-top: 16px; padding-top: 12px;
    border-top: 1px solid rgba(0,0,0,0.06);
    display: flex; align-items: center; gap: 8px;
  }
  .model-label {
    font-size: 11px; font-weight: 600; color: #b0a48f;
    text-transform: uppercase; letter-spacing: 0.6px; white-space: nowrap;
  }
  .model-select {
    font-size: 12px; padding: 4px 8px; border-radius: 6px;
    border: 1px solid rgba(0,0,0,0.1); background: rgba(255,255,255,0.7);
    color: #5a4e3c; font-family: inherit; cursor: pointer; flex: 1;
  }
  .recording .status-icon { animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
</style>
</head>
<body class="STATUS_CLASS">
  <div class="header">
    <div class="status-icon">STATUS_ICON</div>
    <div class="status-text">STATUS_TEXT</div>
    <div class="status-hint">Fn+R to record</div>
  </div>
  <div class="toolbar">
    <div class="toolbar-left">
      <span class="section-title">Transcriptions</span>
      <select class="filter-select" id="appFilter" onchange="filterByApp(this.value)">
        <option value="all">All Apps</option>
        APP_OPTIONS
      </select>
    </div>
    <div class="toolbar-right">
      <button class="export-btn" onclick="doExport('md')">Export .md</button>
      <button class="export-btn" onclick="doExport('txt')">Export .txt</button>
    </div>
  </div>
  <div class="entries" id="entries">
    ENTRIES_HTML
  </div>
  <div class="model-bar">
    <span class="model-label">Model</span>
    <select class="model-select" id="modelSelect" onchange="changeModel(this.value)">
      MODEL_OPTIONS
    </select>
  </div>
  <script>
    var COPY_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';

    function copyText(btn, id) {
      var el = document.getElementById(id);
      var ta = document.createElement('textarea');
      ta.value = el.innerText;
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      btn.classList.add('copied');
      setTimeout(function() { btn.classList.remove('copied'); }, 1200);
    }

    function filterByApp(app) {
      document.querySelectorAll('.entry').forEach(function(el) {
        if (app === 'all') { el.classList.remove('hidden'); }
        else { el.classList.toggle('hidden', el.dataset.app !== app); }
      });
    }

    function doExport(fmt) {
      window.webkit.messageHandlers.action.postMessage({type: 'export', format: fmt});
    }

    function changeModel(model) {
      window.webkit.messageHandlers.action.postMessage({type: 'model', model: model});
    }
  </script>
</body>
</html>'''


WKScriptMessageHandlerProto = objc.protocolNamed('WKScriptMessageHandler')

class ScriptMessageHandler(NSObject, protocols=[WKScriptMessageHandlerProto]):
    """Bridge JS messages to Python callbacks."""

    def initWithCallback_(self, callback):
        self = objc.super(ScriptMessageHandler, self).init()
        if self:
            self._callback = callback
        return self

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        self._callback(message.body())


class HistoryPanel:
    """Native macOS window with warm WebView GUI."""

    def __init__(self):
        self.window = None
        self.webview = None
        self._handler = None
        self.on_model_change = None

    def show(self, rows, status="ready"):
        html = self._render(rows, status)

        if self.window and self.window.isVisible():
            self.webview.loadHTMLString_baseURL_(html, None)
            self.window.makeKeyAndOrderFront_(None)
            NSApp.activateIgnoringOtherApps_(True)
            return

        w, h = 520, 620
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, w, h), style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("Open Whisper")
        self.window.center()
        self.window.setMinSize_(NSMakeRect(0, 0, 360, 400).size)
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setBackgroundColor_(None)

        config = WKWebViewConfiguration.alloc().init()
        self._handler = ScriptMessageHandler.alloc().initWithCallback_(self._on_message)
        config.userContentController().addScriptMessageHandler_name_(self._handler, "action")

        self.webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, w, h), config
        )
        self.webview.setAutoresizingMask_(0b010010)
        self.webview.setValue_forKey_(True, "drawsTransparentBackground")
        self.window.setContentView_(self.webview)
        self.webview.loadHTMLString_baseURL_(html, None)

        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def _on_message(self, body):
        if not isinstance(body, dict):
            return
        if body.get("type") == "export":
            fmt = body.get("format", "txt")
            self._export(fmt)
        elif body.get("type") == "model":
            if self.on_model_change:
                self.on_model_change(body.get("model"))

    def _export(self, fmt):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT text, created_at, app_name FROM transcriptions ORDER BY created_at DESC"
        ).fetchall()
        conn.close()

        if not rows:
            rumps.notification("Open Whisper", "", "No transcriptions to export")
            return

        if fmt == "md":
            lines = ["# Open Whisper — History\n"]
            for txt, ts, app in rows:
                app_str = f" ({app})" if app else ""
                lines.append(f"### {ts}{app_str}\n\n{txt}\n")
            content = "\n".join(lines)
            ext = "md"
        else:
            lines = []
            for txt, ts, app in rows:
                app_str = f" [{app}]" if app else ""
                lines.append(f"[{ts}]{app_str}\n{txt}")
            content = "\n\n".join(lines)
            ext = "txt"

        out_path = Path.home() / "Desktop" / f"open-whisper-history.{ext}"
        out_path.write_text(content, encoding="utf-8")
        log.info(f"export: saved {len(rows)} entries to {out_path}")
        subprocess.run(["open", "-R", str(out_path)], capture_output=True)
        rumps.notification("Open Whisper", "", f"{len(rows)} transcriptions saved to Desktop")

    def _render(self, rows, status, current_model=None):
        if not current_model:
            current_model = worker.model
        if status == "recording":
            icon, text, css_class = "🔴", "Recording...", "recording"
        elif status == "processing":
            icon, text, css_class = "⏳", "Transcribing...", "processing"
        else:
            icon, text, css_class = "🎤", "Ready", ""

        # Model options
        model_options = "\n".join(
            f'<option value="{repo}" {"selected" if repo == current_model else ""}>{name}</option>'
            for repo, name in MODELS
        )

        # Collect unique app names for filter
        apps = sorted(set(row[2] for row in rows if len(row) > 2 and row[2]))
        app_options = "\n".join(f'<option value="{a}">{a}</option>' for a in apps)

        if rows:
            from datetime import datetime, date, timedelta
            today = date.today()
            yesterday = today - timedelta(days=1)

            def date_label(ts_str):
                try:
                    d = datetime.strptime(ts_str.split(" ")[0], "%Y-%m-%d").date()
                except (ValueError, IndexError):
                    return "Other"
                if d == today: return "Today"
                if d == yesterday: return "Yesterday"
                return d.strftime("%b %d")

            entries = []
            current_label = None
            for i, row in enumerate(rows):
                txt, ts = row[0], row[1]
                app_name = row[2] if len(row) > 2 and row[2] else ""
                label = date_label(ts)
                if label != current_label:
                    current_label = label
                    entries.append(f'<div class="date-group">{label}</div>')
                t = ts.split(" ")[-1][:5] if " " in ts else ts[:5]
                safe = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                app_tag = f'<span class="entry-app">{app_name}</span>' if app_name else ""
                entries.append(
                    f'<div class="entry" data-app="{app_name}" data-date="{label}">'
                    f'<div class="entry-header">'
                    f'<div class="entry-meta"><span>{t}</span>{app_tag}</div>'
                    f'<button class="copy-btn" onclick="copyText(this,\'t{i}\')">'
                    f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>'
                    f'<span class="check">✓</span>'
                    f'</button>'
                    f'</div>'
                    f'<div class="entry-text" id="t{i}">{safe}</div>'
                    f'</div>'
                )
            entries_html = "\n".join(entries)
        else:
            entries_html = '<div class="empty">No transcriptions yet.<br>Press Fn+R to start recording.</div>'

        return (HTML_TEMPLATE
                .replace("STATUS_ICON", icon)
                .replace("STATUS_TEXT", text)
                .replace("STATUS_CLASS", css_class)
                .replace("APP_OPTIONS", app_options)
                .replace("MODEL_OPTIONS", model_options)
                .replace("ENTRIES_HTML", entries_html))


history_panel = HistoryPanel()


def play_sound(sound_name):
    subprocess.run(['afplay', f'/System/Library/Sounds/{sound_name}.aiff'],
                   capture_output=True)

def paste_text():
    """Paste using CGEvent (Cmd+V)."""
    try:
        source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
        event_down = CGEventCreateKeyboardEvent(source, 9, True)
        CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
        CGEventPost(kCGAnnotatedSessionEventTap, event_down)

        event_up = CGEventCreateKeyboardEvent(source, 9, False)
        CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
        CGEventPost(kCGAnnotatedSessionEventTap, event_up)
        log.info("paste_text: CGEvent posted successfully")
        return True
    except Exception as e:
        log.error(f"paste_text: failed: {e}")
        return False

def get_frontmost_app():
    """Get the name of the currently active app."""
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return app.localizedName() if app else None
    except Exception:
        return None

def check_accessibility():
    return AXIsProcessTrustedWithOptions(None)

def request_accessibility():
    options = {"AXTrustedCheckOptionPrompt": True}
    return AXIsProcessTrustedWithOptions(options)

def get_setting(key, default=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


class VoiceApp(rumps.App):
    def __init__(self):
        super().__init__("", quit_button=None)
        self.title = "🎤"
        self.recording = False
        self.processing = False
        self.frames = []
        self.stream = None
        self.pa = None
        self.model_ready = False
        self._lock = threading.Lock()

        self._setup_db()
        self._build_menu()
        self._setup_hotkey()
        history_panel.on_model_change = self._change_model

        threading.Thread(target=self._startup, daemon=True).start()
        threading.Thread(target=self._keepalive_loop, daemon=True).start()

    @rumps.timer(0.2)
    def _sync_icon(self, _):
        """Sync menu bar icon to recording state on the main thread."""
        if self.recording:
            expected = "🔴"
        elif self.processing:
            expected = "⏳"
        elif self.model_ready:
            expected = "🎤"
        else:
            expected = "⏳"
        if self.title != expected:
            self.title = expected

    def _build_menu(self):
        self.menu = [
            rumps.MenuItem("⏺ Record  [Fn+R]", callback=self._toggle),
            None,
            rumps.MenuItem("📋 History", callback=self._show_history),
            None,
            rumps.MenuItem("⚙️ Settings", callback=self._open_accessibility),
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

    def _setup_hotkey(self):
        """Register Fn+R as global hotkey to toggle recording."""
        # macOS disables event taps it considers unresponsive; these type values signal that
        kCGEventTapDisabledByTimeout   = 0xFFFFFFFE
        kCGEventTapDisabledByUserInput = 0xFFFFFFFF

        def hotkey_callback(proxy, event_type, event, refcon):
            # Re-enable tap if macOS disabled it
            if event_type in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput):
                log.warning("hotkey: event tap disabled by macOS, re-enabling")
                CGEventTapEnable(self._event_tap, True)
                return event
            try:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                flags = CGEventGetFlags(event)
                if keycode == HOTKEY_KEYCODE and (flags & HOTKEY_FN_FLAG):
                    log.info("hotkey: Fn+R pressed")
                    self._toggle(None)
                    return None  # Suppress the keystroke
            except Exception as e:
                log.error(f"hotkey: callback error: {e}")
            return event

        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            0,  # active tap
            (1 << kCGEventKeyDown),
            hotkey_callback,
            None
        )
        if tap:
            source = CFMachPortCreateRunLoopSource(None, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetMain(), source, kCFRunLoopCommonModes)
            CGEventTapEnable(tap, True)
            self._event_tap = tap  # prevent GC
            self._tap_source = source
            log.info("hotkey: Fn+R registered")
        else:
            log.warning("hotkey: failed to create event tap (Accessibility permission needed)")

    def _startup(self):
        self.title = "⏳"
        log.info(f"startup: begin, executable={sys.executable}, pid={os.getpid()}")

        ax = check_accessibility()
        log.info(f"startup: accessibility={ax}")
        if not ax:
            log.info("startup: requesting accessibility permission")
            request_accessibility()
            # Open System Settings directly to the right page
            subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'],
                          capture_output=True)
            rumps.notification("Open Whisper", "Accessibility Required",
                             "Toggle ON Open Whisper in the System Settings window that just opened. If already ON, toggle OFF then ON.")

        saved_model = get_setting("model", DEFAULT_MODEL)
        t0 = time.time()
        worker.start(saved_model)
        log.info(f"startup: worker started in {time.time()-t0:.2f}s, model={saved_model}")

        self.title = "🎤"
        self.model_ready = True
        log.info("startup: ready")

    def _keepalive_loop(self):
        """Periodically ping the worker with silence to keep model weights in RAM."""
        INTERVAL = 3 * 60  # every 3 minutes
        time.sleep(INTERVAL)  # first ping after initial warmup
        while True:
            if not self.recording and not self.processing and self.model_ready:
                log.info("keepalive: pinging worker")
                worker._warmup()
            time.sleep(INTERVAL)

    def _setup_db(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Migrate from old data directory if needed
        old_db = _OLD_DATA_DIR / "history.db"
        if old_db.exists() and not DB_PATH.exists():
            import shutil
            shutil.copy(old_db, DB_PATH)
            log.info("setup_db: migrated history from .voice-transcriber")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                app_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Migration: add app_name column if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(transcriptions)")]
        if "app_name" not in cols:
            conn.execute("ALTER TABLE transcriptions ADD COLUMN app_name TEXT")
        conn.commit()
        conn.close()

    def _open_accessibility(self, _):
        if check_accessibility():
            rumps.alert("Permissions OK", "Accessibility permission is already granted.")
        else:
            request_accessibility()
            rumps.notification("Open Whisper", "",
                             "Flip the toggle in System Settings, then you're all set.")

    def _change_model(self, model):
        if model == worker.model:
            return
        log.info(f"change_model: switching to {model}")
        set_setting("model", model)
        self.model_ready = False
        self.title = "⏳"
        model_name = dict(MODELS).get(model, model.split("/")[-1])
        rumps.notification("Open Whisper", "", f"Loading {model_name}...")
        def do_switch():
            try:
                # Pre-download model if not cached
                self._ensure_model_downloaded(model)
                worker.restart(model)
                self.model_ready = True
                self.title = "🎤"
                rumps.notification("Open Whisper", "", f"{model_name} ready")
            except Exception as e:
                log.error(f"change_model: error: {e}")
                self.model_ready = True
                self.title = "🎤"
                rumps.notification("Open Whisper", "Error", f"Failed to load model: {e}")
        threading.Thread(target=do_switch, daemon=True).start()

    def _ensure_model_downloaded(self, model):
        """Pre-download model weights from HuggingFace if not cached."""
        try:
            from huggingface_hub import snapshot_download
            log.info(f"ensure_model: downloading {model} if needed...")
            snapshot_download(model)
            log.info(f"ensure_model: {model} ready")
        except Exception as e:
            log.warning(f"ensure_model: download check failed: {e}")

    @rumps.clicked("🎤")
    def _icon_click(self, _):
        self._toggle(None)

    def _toggle(self, _):
        if not self.model_ready:
            rumps.notification("Open Whisper", "", "Still loading, please wait...")
            return
        if self.processing:
            rumps.notification("Open Whisper", "", "Still transcribing, please wait...")
            return
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.target_app = get_frontmost_app()
        log.info(f"recording: START, target_app={self.target_app}")
        self.recording = True
        self.frames = []
        self.title = "🔴"
        self.menu["⏺ Record  [Fn+R]"].title = "⏹ Stop  [Fn+R]"

        threading.Thread(target=lambda: play_sound("Blow"), daemon=True).start()

        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        threading.Thread(target=self._record_loop, daemon=True).start()

    def _record_loop(self):
        start_time = time.time()

        while self.recording and (time.time() - start_time) < 1800:  # 30 min hard limit
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
            except Exception as e:
                log.error(f"record_loop: exception: {e}")
                break

        duration = time.time() - start_time
        log.info(f"record_loop: ended, duration={duration:.1f}s, frames={len(self.frames)}")

        # Check if we hit max duration (user didn't click Stop)
        with self._lock:
            was_recording = self.recording
            self.recording = False

        if was_recording:
            log.info("record_loop: 30min limit reached")
            threading.Thread(target=lambda: play_sound("Pop"), daemon=True).start()

        # Always cleanup from THIS thread (the one doing stream.read)
        self._cleanup_stream()
        self._do_transcription()

    def _cleanup_stream(self):
        log.info("cleanup_stream: cleaning up")
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        except Exception as e:
            log.error(f"cleanup_stream: stream error: {e}")
        try:
            if self.pa:
                self.pa.terminate()
        except Exception as e:
            log.error(f"cleanup_stream: pa error: {e}")
        self.stream = None
        self.pa = None

    def _stop_recording(self):
        with self._lock:
            if not self.recording:
                log.info("stop_recording: already stopped")
                return
            self.recording = False
            log.info(f"stop_recording: manual stop, frames={len(self.frames)}")
        # Don't touch the stream here — _record_loop will clean up safely
        threading.Thread(target=lambda: play_sound("Pop"), daemon=True).start()

    def _do_transcription(self):
        """Start transcription if we have enough audio."""
        frame_count = len(self.frames)
        log.info(f"do_transcription: frame_count={frame_count}")

        if frame_count < 10:
            self.title = "🎤"
            self._reset_menu_title()
            rumps.notification("Open Whisper", "", "No audio captured")
            return

        self.processing = True
        self.title = "⏳"
        self._reset_menu_title()
        threading.Thread(target=self._transcribe, daemon=True).start()

    def _reset_menu_title(self):
        try:
            for key in ["⏹ Stop  [Fn+R]", "⏺ Record  [Fn+R]"]:
                if key in self.menu:
                    self.menu[key].title = "⏺ Record  [Fn+R]"
                    return
        except:
            pass

    def _transcribe(self):
        log.info("transcribe: START")
        pipeline_start = time.time()
        try:
            # Save audio to temp WAV
            t0 = time.time()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
                wf = wave.open(path, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b''.join(self.frames))
                wf.close()

            file_size = os.path.getsize(path)
            audio_duration = len(self.frames) * 1024 / 16000
            log.info(f"transcribe: wav saved in {time.time()-t0:.3f}s, size={file_size} bytes, audio={audio_duration:.1f}s")

            # Transcribe via persistent worker
            t0 = time.time()
            text, whisper_time = worker.transcribe(path)
            total_rpc = time.time() - t0
            os.unlink(path)

            log.info(f"transcribe: worker responded in {total_rpc:.2f}s (whisper={whisper_time:.2f}s), result: {text!r}")

            if text:
                app_name = getattr(self, 'target_app', None)
                self._save_history(text, app_name)
                log.info(f"transcribe: saved to history, app={app_name}")

                # Copy to clipboard
                t0 = time.time()
                p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                p.communicate(text.encode())
                log.info(f"transcribe: clipboard copy took {time.time()-t0:.3f}s")

                # Paste into active app (requires Accessibility)
                ax = check_accessibility()
                log.info(f"transcribe: accessibility={ax} before paste")
                pasted = False
                if ax:
                    time.sleep(0.1)
                    t0 = time.time()
                    pasted = paste_text()
                    log.info(f"transcribe: paste took {time.time()-t0:.3f}s, result={pasted}")

                threading.Thread(target=lambda: play_sound("Glass"), daemon=True).start()
                total = time.time() - pipeline_start
                log.info(f"transcribe: PIPELINE TOTAL {total:.2f}s (whisper={whisper_time:.2f}s)")

                if pasted:
                    rumps.notification("Pasted", f"{total:.1f}s", text[:60])
                elif not ax:
                    subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'],
                                  capture_output=True)
                    rumps.notification("Open Whisper", "Accessibility OFF — Grant in Settings",
                                     text[:60])
                else:
                    rumps.notification("Copied - Press Cmd+V", f"{total:.1f}s", text[:60])
            else:
                log.warning("transcribe: empty text")
                rumps.notification("Open Whisper", "", "No speech detected")

        except Exception as e:
            log.error(f"transcribe: ERROR: {e}", exc_info=True)
            rumps.notification("Error", "", str(e)[:50])
        finally:
            self.title = "🎤"
            self.processing = False
            self.frames = []
            log.info("transcribe: DONE, reset to ready")

    def _save_history(self, text, app_name=None):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO transcriptions (text, app_name) VALUES (?, ?)", (text, app_name))
        conn.commit()
        conn.close()

    def _get_status(self):
        if self.recording:
            return "recording"
        elif self.processing:
            return "processing"
        return "ready"

    def _show_history(self, _):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT text, created_at, app_name FROM transcriptions ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        history_panel.show(rows, self._get_status())

if __name__ == "__main__":
    log.info("=== APP LAUNCH ===")
    VoiceApp().run()
