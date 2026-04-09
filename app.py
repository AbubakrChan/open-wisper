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
import struct
import time
import sqlite3
from pathlib import Path

import rumps
import pyaudio
import mlx_whisper
from ApplicationServices import AXIsProcessTrustedWithOptions

DATA_DIR = Path.home() / ".voice-transcriber"
DB_PATH = DATA_DIR / "history.db"

def play_sound(sound_name):
    """Play system sound."""
    subprocess.run(['afplay', f'/System/Library/Sounds/{sound_name}.aiff'],
                   capture_output=True)

def paste_text():
    """Paste using AppleScript - requires Accessibility permission."""
    script = '''
    tell application "System Events"
        keystroke "v" using command down
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.returncode == 0

def check_accessibility():
    """Check if we have accessibility permissions."""
    return AXIsProcessTrustedWithOptions(None)

def request_accessibility():
    """Trigger native macOS accessibility permission dialog.
    Shows 'VoiceTranscriber would like to control this computer' dialog."""
    options = {"AXTrustedCheckOptionPrompt": True}
    return AXIsProcessTrustedWithOptions(options)

class VoiceApp(rumps.App):
    def __init__(self):
        super().__init__("", quit_button=None)
        self.title = "🎤"
        self.recording = False
        self.frames = []
        self.stream = None
        self.pa = None
        self.model_ready = False

        self._setup_db()
        self._build_menu()

        # Check permissions on startup
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

        # Request accessibility if not granted — shows native macOS dialog
        if not check_accessibility():
            request_accessibility()

        # Preload model
        self._preload_model()

        self.title = "🎤"
        self.model_ready = True
        print("Ready!")

    def _preload_model(self):
        """Warm up the model."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            wf = wave.open(f.name, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b'\x00' * 3200)
            wf.close()
            mlx_whisper.transcribe(f.name, path_or_hf_repo="mlx-community/whisper-tiny",
                                   language="en", verbose=False)

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
        """Request accessibility permission via native macOS dialog."""
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
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.recording = True
        self.frames = []
        self.title = "🔴"
        self.menu["⏺ Record"].title = "⏹ Stop"

        # Play start sound
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
        silent_chunks = 0
        started_speaking = False
        start_time = time.time()

        while self.recording and (time.time() - start_time) < 30:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)

                # Check volume (RMS)
                shorts = struct.unpack(f"{len(data)//2}h", data)
                rms = (sum(s**2 for s in shorts) / len(shorts)) ** 0.5

                if rms > 500:
                    started_speaking = True
                    silent_chunks = 0
                else:
                    silent_chunks += 1

                # Auto-stop after 1.5s silence (only after speaking started)
                if started_speaking and silent_chunks > 23:
                    break

            except:
                break

        # Auto-stop
        if self.recording:
            rumps.App.getApplication().performSelectorOnMainThread_withObject_waitUntilDone_(
                '_stop_recording_from_thread:', None, False
            ) if hasattr(rumps.App, 'getApplication') else self._stop_recording()

    def _stop_recording(self):
        if not self.recording:
            return

        self.recording = False
        self.title = "⏳"
        self.menu["⏹ Stop"].title = "⏺ Record"

        # Play stop sound
        threading.Thread(target=lambda: play_sound("Pop"), daemon=True).start()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pa:
            self.pa.terminate()

        if len(self.frames) < 10:
            self.title = "🎤"
            rumps.notification("Voice", "", "No audio captured")
            return

        threading.Thread(target=self._transcribe, daemon=True).start()

    def _transcribe(self):
        try:
            # Save audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
                wf = wave.open(path, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b''.join(self.frames))
                wf.close()

            # Transcribe
            t0 = time.time()
            result = mlx_whisper.transcribe(
                path,
                path_or_hf_repo="mlx-community/whisper-tiny",
                language="en",
                verbose=False
            )
            text = result.get("text", "").strip()
            elapsed = time.time() - t0
            os.unlink(path)

            if text:
                # Save to history
                self._save_history(text)

                # Copy to clipboard
                p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                p.communicate(text.encode())

                # Try to paste, fallback to just notification
                time.sleep(0.1)
                pasted = paste_text()

                # Success sound
                threading.Thread(target=lambda: play_sound("Glass"), daemon=True).start()

                if pasted:
                    rumps.notification("✓ Pasted", f"{elapsed:.1f}s", text[:60])
                else:
                    rumps.notification("✓ Copied - Press ⌘V", f"{elapsed:.1f}s", text[:60])
            else:
                rumps.notification("Voice", "", "No speech detected")

        except Exception as e:
            rumps.notification("Error", "", str(e)[:50])
            print(f"Error: {e}")
        finally:
            self.title = "🎤"
            self.frames = []

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
    print("Voice Transcriber starting...")
    VoiceApp().run()
