#!/usr/bin/env python3
"""
Voice transcriber with auto-stop on silence
Bind to hotkey via macOS Shortcuts
"""

import os
import sys
sys.path.insert(0, "/Users/chan/Library/Python/3.9/lib/python/site-packages")

import wave
import tempfile
import subprocess
import time
import struct

import pyaudio
import mlx_whisper

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024
MAX_SECONDS = 30
SILENCE_THRESHOLD = 500  # Amplitude threshold for silence
SILENCE_DURATION = 1.5   # Seconds of silence to stop recording
MODEL = "mlx-community/whisper-tiny"

def notify(title, message, sound=True):
    sound_part = 'sound name "default"' if sound else ""
    subprocess.run([
        'osascript', '-e',
        f'display notification "{message}" with title "{title}" {sound_part}'
    ], capture_output=True)

def paste():
    time.sleep(0.1)
    subprocess.run([
        'osascript', '-e',
        'tell application "System Events" to keystroke "v" using command down'
    ], capture_output=True)

def get_rms(data):
    """Calculate RMS amplitude of audio chunk."""
    shorts = struct.unpack(f"{len(data)//2}h", data)
    return (sum(s**2 for s in shorts) / len(shorts)) ** 0.5

def main():
    notify("Voice", "Listening... (stops on silence)", sound=False)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    frames = []
    silent_chunks = 0
    chunks_for_silence = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK)
    started_speaking = False
    start_time = time.time()

    while (time.time() - start_time) < MAX_SECONDS:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

            rms = get_rms(data)

            if rms > SILENCE_THRESHOLD:
                started_speaking = True
                silent_chunks = 0
            else:
                silent_chunks += 1

            # Stop after silence (only if we've spoken)
            if started_speaking and silent_chunks > chunks_for_silence:
                break

        except Exception as e:
            break

    duration = time.time() - start_time
    stream.stop_stream()
    stream.close()
    p.terminate()

    if not started_speaking or duration < 0.5:
        notify("Voice", "No speech detected")
        return

    notify("Voice", "Transcribing...", sound=False)

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name
        wf = wave.open(temp_path, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

    # Transcribe
    try:
        result = mlx_whisper.transcribe(temp_path, path_or_hf_repo=MODEL, language="en", verbose=False)
        text = result.get("text", "").strip()
    except Exception as e:
        notify("Error", str(e)[:50])
        return
    finally:
        os.unlink(temp_path)

    if text:
        # Copy to clipboard
        proc = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        proc.communicate(text.encode('utf-8'))

        # Paste
        paste()

        notify("Done", text[:50])
    else:
        notify("Voice", "No speech detected")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify("Error", str(e)[:50])
