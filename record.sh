#!/bin/bash
# Quick voice transcription - bind this to a hotkey in macOS Shortcuts
# Records for up to 30 seconds, stops on silence or Ctrl+C

cd "$(dirname "$0")"

# Record audio (press Ctrl+C to stop, or wait for silence)
TEMP_FILE=$(mktemp /tmp/voice_XXXXXX.wav)

echo "🎤 Recording... (Ctrl+C to stop)"

# Record with sox if available, otherwise use rec
if command -v rec &> /dev/null; then
    rec -q -r 16000 -c 1 "$TEMP_FILE" silence 1 0.1 1% 1 2.0 3% &
    REC_PID=$!
    sleep 30 &
    SLEEP_PID=$!
    wait -n $REC_PID $SLEEP_PID 2>/dev/null
    kill $REC_PID $SLEEP_PID 2>/dev/null
else
    # Fallback to Python recording
    python3 -c "
import pyaudio
import wave
import sys

RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 10

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
frames = []
print('Recording for 10s max...')
try:
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        frames.append(stream.read(CHUNK))
except KeyboardInterrupt:
    pass
stream.stop_stream()
stream.close()
p.terminate()
wf = wave.open('$TEMP_FILE', 'wb')
wf.setnchannels(1)
wf.setsampwidth(2)
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()
"
fi

echo "⏳ Transcribing..."

# Transcribe
TEXT=$(python3 -c "
import mlx_whisper
result = mlx_whisper.transcribe('$TEMP_FILE', path_or_hf_repo='mlx-community/whisper-tiny', verbose=False)
print(result.get('text', '').strip())
")

rm -f "$TEMP_FILE"

if [ -n "$TEXT" ]; then
    # Copy to clipboard
    echo "$TEXT" | pbcopy

    # Paste
    osascript -e 'tell application "System Events" to keystroke "v" using command down'

    # Notify
    osascript -e "display notification \"$TEXT\" with title \"✓ Transcribed\""
    echo "✓ $TEXT"
else
    osascript -e 'display notification "No speech detected" with title "Voice Transcriber"'
    echo "No speech detected"
fi
