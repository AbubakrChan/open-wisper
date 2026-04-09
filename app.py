#!/usr/bin/env python3
"""
Voice Transcriber - Click menubar icon to record
Auto-stops on silence, pastes result
"""

import os
import sys
sys.path.insert(0, "/Users/chan/Library/Python/3.9/lib/python/site-packages")
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")

import wave
import tempfile
import subprocess
import threading
import time
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
)

DATA_DIR = Path.home() / ".voice-transcriber"
DB_PATH = DATA_DIR / "history.db"
SETUP_DONE = DATA_DIR / ".setup_done"
LOG_PATH = DATA_DIR / "app.log"

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

TRANSCRIBE_SCRIPT = '''
import sys, os
sys.path.insert(0, "/Users/chan/Library/Python/3.9/lib/python/site-packages")
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")
import mlx_whisper
result = mlx_whisper.transcribe(
    sys.argv[1],
    path_or_hf_repo="mlx-community/whisper-tiny",
    language="en",
    verbose=False
)
print(result.get("text", "").strip())
'''

def transcribe_audio(wav_path):
    """Run mlx_whisper in a subprocess to avoid MLX/rumps thread deadlock."""
    log.info(f"transcribe_audio: starting subprocess for {wav_path}")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LANG": "en_US.UTF-8"}
    result = subprocess.run(
        [PYTHON, "-c", TRANSCRIBE_SCRIPT, wav_path],
        capture_output=True, text=True, encoding="utf-8",
        timeout=60, env=env
    )
    log.info(f"transcribe_audio: rc={result.returncode} stdout={result.stdout.strip()!r}")
    if result.returncode != 0:
        log.error(f"transcribe_audio: stderr={result.stderr.strip()[:300]}")
    return result.stdout.strip()

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

def check_accessibility():
    return AXIsProcessTrustedWithOptions(None)

def request_accessibility():
    options = {"AXTrustedCheckOptionPrompt": True}
    return AXIsProcessTrustedWithOptions(options)

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

        threading.Thread(target=self._startup, daemon=True).start()

    def _build_menu(self):
        self.menu = [
            rumps.MenuItem("⏺ Record", callback=self._toggle),
            None,
            rumps.MenuItem("📋 View History", callback=self._show_history),
            rumps.MenuItem("🗑 Clear History", callback=self._clear_history),
            None,
            rumps.MenuItem("⚙️ Permissions", callback=self._open_accessibility),
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

    def _startup(self):
        self.title = "⏳"
        log.info("startup: begin")

        ax = check_accessibility()
        log.info(f"startup: accessibility={ax}")
        if not ax and not SETUP_DONE.exists():
            request_accessibility()
            SETUP_DONE.touch()

        self._preload_model()

        self.title = "🎤"
        self.model_ready = True
        log.info("startup: ready")

    def _preload_model(self):
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
                wf = wave.open(path, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b'\x00' * 32000)
                wf.close()
            transcribe_audio(path)
            os.unlink(path)
            log.info("preload: model cached")
        except Exception as e:
            log.error(f"preload: error: {e}")

    def _setup_db(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _open_accessibility(self, _):
        if check_accessibility():
            rumps.alert("Permissions OK", "Accessibility permission is already granted.")
        else:
            request_accessibility()
            rumps.notification("Voice Transcriber", "",
                             "Flip the toggle in System Settings, then you're all set.")

    @rumps.clicked("🎤")
    def _icon_click(self, _):
        self._toggle(None)

    def _toggle(self, _):
        if not self.model_ready:
            rumps.notification("Voice", "", "Still loading, please wait...")
            return
        if self.processing:
            rumps.notification("Voice", "", "Still transcribing, please wait...")
            return
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        log.info("recording: START")
        self.recording = True
        self.frames = []
        self.title = "🔴"
        self.menu["⏺ Record"].title = "⏹ Stop"

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

        while self.recording and (time.time() - start_time) < 120:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
            except Exception as e:
                log.error(f"record_loop: exception: {e}")
                break

        duration = time.time() - start_time
        log.info(f"record_loop: ended, duration={duration:.1f}s, frames={len(self.frames)}")

        # Only handle stop if we hit the 120s max (user didn't click Stop)
        with self._lock:
            if self.recording:
                self.recording = False
                log.info("record_loop: max duration reached")
                threading.Thread(target=lambda: play_sound("Pop"), daemon=True).start()
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

        threading.Thread(target=lambda: play_sound("Pop"), daemon=True).start()
        self._cleanup_stream()
        self._do_transcription()

    def _do_transcription(self):
        """Start transcription if we have enough audio."""
        frame_count = len(self.frames)
        log.info(f"do_transcription: frame_count={frame_count}")

        if frame_count < 10:
            self.title = "🎤"
            self._reset_menu_title()
            rumps.notification("Voice", "", "No audio captured")
            return

        self.processing = True
        self.title = "⏳"
        self._reset_menu_title()
        threading.Thread(target=self._transcribe, daemon=True).start()

    def _reset_menu_title(self):
        try:
            for key in ["⏹ Stop", "⏺ Record"]:
                if key in self.menu:
                    self.menu[key].title = "⏺ Record"
                    return
        except:
            pass

    def _transcribe(self):
        log.info("transcribe: START")
        try:
            # Save audio to temp WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
                wf = wave.open(path, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b''.join(self.frames))
                wf.close()

            file_size = os.path.getsize(path)
            log.info(f"transcribe: wav saved, size={file_size} bytes")

            # Transcribe in subprocess
            t0 = time.time()
            text = transcribe_audio(path)
            elapsed = time.time() - t0
            os.unlink(path)

            log.info(f"transcribe: result in {elapsed:.1f}s: {text!r}")

            if text:
                self._save_history(text)
                log.info("transcribe: saved to history")

                # Copy to clipboard
                p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                p.communicate(text.encode())
                log.info("transcribe: copied to clipboard")

                # Paste into active app (requires Accessibility)
                ax = check_accessibility()
                log.info(f"transcribe: accessibility={ax} before paste")
                pasted = False
                if ax:
                    time.sleep(0.1)
                    pasted = paste_text()
                    log.info(f"transcribe: paste result={pasted}")

                threading.Thread(target=lambda: play_sound("Glass"), daemon=True).start()

                if pasted:
                    rumps.notification("Pasted", f"{elapsed:.1f}s", text[:60])
                elif not ax:
                    rumps.notification("Copied (paste needs Accessibility)",
                                     "Click Permissions in menu to fix",
                                     text[:60])
                else:
                    rumps.notification("Copied - Press Cmd+V", f"{elapsed:.1f}s", text[:60])
            else:
                log.warning("transcribe: empty text")
                rumps.notification("Voice", "", "No speech detected")

        except Exception as e:
            log.error(f"transcribe: ERROR: {e}", exc_info=True)
            rumps.notification("Error", "", str(e)[:50])
        finally:
            self.title = "🎤"
            self.processing = False
            self.frames = []
            log.info("transcribe: DONE, reset to ready")

    def _save_history(self, text):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO transcriptions (text) VALUES (?)", (text,))
        conn.commit()
        conn.close()

    def _show_history(self, _):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT text, created_at FROM transcriptions ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        conn.close()

        if not rows:
            rumps.alert("History", "No transcriptions yet")
            return

        history = "\n\n".join([f"[{r[1]}]\n{r[0][:150]}" for r in rows])
        rumps.alert("Recent Transcriptions", history[:2000])

    def _clear_history(self, _):
        if rumps.alert("Clear all history?", ok="Delete", cancel="Cancel") == 1:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM transcriptions")
            conn.commit()
            conn.close()
            rumps.notification("Voice", "", "History cleared")

if __name__ == "__main__":
    log.info("=== APP LAUNCH ===")
    VoiceApp().run()
