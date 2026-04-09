# Voice Transcriber

A free, local, privacy-focused voice transcription app for macOS. Click the menubar icon, speak, and your transcribed text is automatically pasted into the active window.

## Features

- **Menubar app** - Lives in your menubar, no dock icon
- **Click to record** - Simple one-click recording
- **Auto-stop on silence** - Stops recording after 1.5 seconds of silence
- **Auto-paste** - Transcribed text is pasted into the active window
- **Clipboard fallback** - Text is always copied to clipboard
- **Local history** - All transcriptions saved locally in SQLite
- **Sound feedback** - Audio cues for start, stop, and completion
- **100% local** - No internet required, all processing on-device
- **Fast** - Uses mlx-whisper optimized for Apple Silicon

## Requirements

- macOS 10.15+ (Catalina or later)
- Apple Silicon Mac (M1/M2/M3)
- Python 3.9+
- Microphone access permission
- Accessibility permission (for auto-paste)

## Installation

### 1. Install system dependencies

```bash
brew install portaudio ffmpeg
```

### 2. Install Python packages

```bash
pip3 install --user rumps pyaudio mlx-whisper
```

### 3. Run the app

**Option A: Run directly**
```bash
python3 app.py
```

**Option B: Use the built app bundle**
```bash
open dist/VoiceTranscriber.app
```

## Usage

1. Look for the microphone icon in your menubar
2. Click the icon and select "Record" (or click the icon itself)
3. Speak - the icon turns red while recording
4. Stop speaking - recording auto-stops after 1.5s of silence
5. Text is transcribed, copied to clipboard, and pasted

### Menu Options

| Option | Description |
|--------|-------------|
| Record | Start/stop recording |
| View History | Show recent transcriptions |
| Clear History | Delete all saved transcriptions |
| Grant Paste Permission | Opens System Settings for Accessibility |
| Quit | Exit the app |

## Permissions

### Microphone Access
The app will prompt for microphone access on first use. Grant it in:
**System Settings → Privacy & Security → Microphone**

### Accessibility (for auto-paste)
To automatically paste transcribed text, grant accessibility access:
1. Click "Grant Paste Permission" in the app menu
2. In System Settings → Privacy & Security → Accessibility
3. Click + and add VoiceTranscriber.app (or Python.app if running directly)
4. Make sure it's checked

Without this permission, text is still copied to clipboard - just press Cmd+V to paste.

## Project Structure

```
voice-transcriber/
├── app.py              # Main application
├── setup.py            # py2app build configuration
├── run-voice.sh        # Shell wrapper for Shortcuts
├── dist/
│   └── VoiceTranscriber.app/  # Built macOS app bundle
└── README.md
```

## Configuration

Settings are hardcoded for speed. To modify:

| Setting | Location | Default |
|---------|----------|---------|
| Language | app.py line 257 | `"en"` (English only) |
| Model | app.py line 256 | `whisper-tiny` |
| Silence threshold | app.py line 197 | RMS > 500 |
| Silence duration | app.py line 204 | 1.5s (~23 chunks) |
| Max recording | app.py line 188 | 30 seconds |

### Using a different model

For better accuracy (slower):
```python
# In app.py, change whisper-tiny to:
path_or_hf_repo="mlx-community/whisper-small"   # or
path_or_hf_repo="mlx-community/whisper-base"    # or
path_or_hf_repo="mlx-community/whisper-medium"
```

## Data Storage

- **History database**: `~/.voice-transcriber/history.db`
- **Model cache**: `~/.cache/huggingface/` (downloaded on first run)

## Building the App

To rebuild the .app bundle:

```bash
pip3 install py2app
python3 setup.py py2app -A
```

The `-A` flag creates an alias build (faster, for development).

For a standalone build:
```bash
python3 setup.py py2app
```

## Troubleshooting

### App shows "Still loading, please wait..."
The model is being loaded. First launch takes longer as it may download the model.

### No audio captured
Check microphone permissions in System Settings.

### Text not auto-pasting
Grant Accessibility permission (see Permissions section above).

### ffmpeg not found
Install with: `brew install ffmpeg`

### pyaudio installation fails
Install portaudio first: `brew install portaudio`

## How It Works

1. **Recording**: Uses PyAudio to capture 16kHz mono audio
2. **Silence detection**: Monitors RMS amplitude, stops after sustained silence
3. **Transcription**: mlx-whisper processes audio locally using Apple's MLX framework
4. **Output**: Text copied to clipboard via `pbcopy`, pasted via AppleScript

## Performance

| Optimization | Benefit |
|--------------|---------|
| `language="en"` | Skips language detection (~1-2s) |
| `whisper-tiny` | Smallest/fastest model |
| Model preloading | No load time per transcription |
| MLX framework | Hardware acceleration on Apple Silicon |
| 16kHz audio | Minimum sample rate, less data |

## Privacy

- All processing happens locally on your Mac
- No data is sent to any server
- History is stored only in your home directory
- You can clear history anytime from the menu

## License

Personal use. Do whatever you want with it.

## Credits

- [mlx-whisper](https://github.com/ml-explore/mlx-examples) - Apple's MLX implementation of Whisper
- [rumps](https://github.com/jaredks/rumps) - macOS menubar apps in Python
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) - Audio I/O
