# Open Whisper

A free, local, privacy-focused voice transcription app for macOS. Press Fn+R, speak, and your words are instantly transcribed and pasted — no cloud, no subscription.

## Features

- **Menu bar app** — lives in your menu bar, no dock icon
- **Global hotkey** — Fn+R to start/stop recording from any app
- **Auto-paste** — transcribed text is pasted directly into the active window
- **Clipboard-safe** — does not overwrite your clipboard
- **Microphone selection** — pick any input device from the Settings panel
- **Model selection** — choose between speed and accuracy (4 models)
- **Transcription history** — filterable by app, exportable as .md or .txt
- **100% local** — no internet required after first model download
- **Apple Silicon optimized** — uses MLX for fast on-device inference

## Requirements

- macOS 12+ (Monterey or later recommended)
- Apple Silicon Mac (M1/M2/M3/M4)
- Python 3.9+
- Microphone permission
- Accessibility permission (for auto-paste)

## Installation

### 1. Install system dependencies

```bash
brew install portaudio
```

### 2. Install Python packages

```bash
pip3 install --user rumps pyaudio mlx-whisper huggingface-hub \
  pyobjc-framework-ApplicationServices pyobjc-framework-WebKit
```

### 3. Run

```bash
python3 app.py
```

Or build the app bundle:

```bash
pip3 install --user py2app
make rebuild
open dist/OpenWhisper.app
```

## Permissions

### Microphone
The app will prompt for microphone access on first use.

### Accessibility (for auto-paste)
Required for the app to paste text into other apps:

1. Open **System Settings → Privacy & Security → Accessibility**
2. Click **+** and add `OpenWhisper.app` (or `Python` if running directly)
3. Toggle it **ON**

Without this, transcriptions are still saved to history and copied to clipboard for manual Cmd+V.

## Usage

1. Launch the app — look for 🎤 in your menu bar
2. Press **Fn+R** (or click icon → Record) to start
3. Speak — icon turns 🔴 while recording
4. Press **Fn+R** again to stop and transcribe
5. Text is pasted into your active app

Click **📋 History** to view past transcriptions, change the microphone, or switch models.

## Models

| Model | RAM | Notes |
|-------|-----|-------|
| Distil Large V3 | ~1.4 GB | Fastest, English only (default) |
| Turbo Q8 | ~880 MB | 15% slower, saves ~560 MB RAM |
| Large V3 Turbo | ~1.6 GB | Multilingual |
| Tiny | ~100 MB | Ultra fast, lower accuracy |

Models download from HuggingFace on first use (~75 MB – 900 MB).

## Data

- History: `~/.open-whisper/history.db`
- Logs: `~/.open-whisper/app.log`
- Model cache: `~/.cache/huggingface/`

## Troubleshooting

**Hotkey not working / icon missing**
Grant Accessibility permission — System Settings → Privacy & Security → Accessibility.

**Text not pasting**
Same as above. The app opens System Settings automatically when permission is missing.

**Recording stops unexpectedly**
Check `~/.open-whisper/app.log` for errors. Try switching microphone in the Settings panel.

**Model not loading**
Check the log for download errors. Ensure you have internet for the first download.

## License

MIT
