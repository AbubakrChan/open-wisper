#!/usr/bin/env python3
"""
Voice Transcriber - Local, fast, free voice-to-text for macOS
Click menubar icon or use hotkey to record. Auto-pastes result.
"""

import os
import sys
import wave
import tempfile
import sqlite3
import threading
import subprocess
import time
from datetime import datetime
from pathlib import Path

import rumps
import pyaudio
import numpy as np

# Config
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16
DATA_DIR = Path.home() / ".voice-transcriber"
DB_PATH = DATA_DIR / "history.db"
MODEL_NAME = "mlx-community/whisper-tiny"


def run_applescript(script):
    """Run AppleScript and return output."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"AppleScript error: {e}")
        return None


def paste_text():
    """Simulate Cmd+V using AppleScript - works without accessibility permissions."""
    script = '''
    tell application "System Events"
        keystroke "v" using command down
    end tell
    '''
    run_applescript(script)


def copy_to_clipboard(text):
    """Copy text to clipboard using pbcopy."""
    process = subprocess.Popen(
        ['pbcopy'],
        stdin=subprocess.PIPE,
        env={**os.environ, 'LANG': 'en_US.UTF-8'}
    )
    process.communicate(text.encode('utf-8'))


class VoiceTranscriber(rumps.App):
    def __init__(self):
        super().__init__("🎤", quit_button=None)

        # State
        self.is_recording = False
        self.audio_frames = []
        self.audio_stream = None
        self.audio_interface = None
        self.model_loaded = False

        # Setup
        self._setup_data_dir()
        self._setup_db()
        self._setup_menu()

        # Preload model in background
        threading.Thread(target=self._preload_model, daemon=True).start()

    def _preload_model(self):
        """Preload whisper model at startup."""
        self.title = "⏳"
        try:
            import mlx_whisper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                wf = wave.open(f.name, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b'\x00' * 3200)
                wf.close()
                mlx_whisper.transcribe(f.name, path_or_hf_repo=MODEL_NAME, verbose=False)
            self.model_loaded = True
            print("Model ready!")
        except Exception as e:
            print(f"Model preload failed: {e}")
        self.title = "🎤"

    def _setup_data_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _setup_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _setup_menu(self):
        self.menu = [
            rumps.MenuItem("⏺ Start Recording", callback=self._toggle_recording),
            None,
            rumps.MenuItem("View History", callback=self._show_history),
            rumps.MenuItem("Clear History", callback=self._clear_history),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

    @rumps.clicked("🎤")
    def on_icon_click(self, _):
        """Toggle recording when menubar icon is clicked."""
        self._toggle_recording(None)

    def _toggle_recording(self, sender):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self.is_recording:
            return

        self.is_recording = True
        self.audio_frames = []
        self.title = "🔴"
        self.menu["⏺ Start Recording"].title = "⏹ Stop Recording"

        self.audio_interface = pyaudio.PyAudio()
        self.audio_stream = self.audio_interface.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=self._audio_callback
        )
        self.audio_stream.start_stream()

        rumps.notification("Voice Transcriber", "Recording...", "Click 🔴 to stop")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_recording:
            self.audio_frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    def _stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        self.title = "⏳"
        self.menu["⏹ Stop Recording"].title = "⏺ Start Recording"

        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        if self.audio_interface:
            self.audio_interface.terminate()

        threading.Thread(target=self._transcribe_audio, daemon=True).start()

    def _transcribe_audio(self):
        if not self.audio_frames:
            self.title = "🎤"
            rumps.notification("Voice Transcriber", "No audio", "Nothing recorded")
            return

        start_time = time.time()

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                wf = wave.open(f.name, 'wb')
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(b''.join(self.audio_frames))
                wf.close()

            duration = len(self.audio_frames) * CHUNK / SAMPLE_RATE

            import mlx_whisper
            result = mlx_whisper.transcribe(
                temp_path,
                path_or_hf_repo=MODEL_NAME,
                verbose=False
            )
            text = result.get("text", "").strip()

            os.unlink(temp_path)
            elapsed = time.time() - start_time

            if text:
                # Copy and paste
                copy_to_clipboard(text)
                time.sleep(0.1)
                paste_text()

                # Save history
                self._save_to_history(text, duration)

                preview = text[:60] + "..." if len(text) > 60 else text
                rumps.notification("✓ Pasted", f"{elapsed:.1f}s", preview)
            else:
                rumps.notification("Voice Transcriber", "No speech", "Try again")

        except Exception as e:
            rumps.notification("Error", "", str(e)[:80])
            print(f"Error: {e}")
        finally:
            self.title = "🎤"
            self.audio_frames = []

    def _save_to_history(self, text, duration):
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO transcriptions (text, duration_seconds) VALUES (?, ?)",
            (text, duration)
        )
        conn.commit()
        conn.close()

    def _show_history(self, sender):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT text, created_at FROM transcriptions ORDER BY created_at DESC LIMIT 10"
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            rumps.alert("History", "No transcriptions yet")
            return

        history = "\n\n".join([f"[{r[1]}]\n{r[0][:150]}" for r in rows])
        rumps.alert("Recent Transcriptions", history[:1500])

    def _clear_history(self, sender):
        if rumps.alert("Clear all history?", ok="Delete", cancel="Cancel") == 1:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM transcriptions")
            conn.commit()
            conn.close()


if __name__ == "__main__":
    print("Voice Transcriber")
    print("-" * 40)
    print("Click the 🎤 icon in menubar to record")
    print("Click 🔴 again to stop and transcribe")
    print("-" * 40)
    VoiceTranscriber().run()
