# Open Whisper

> Local voice transcription for macOS. Press a key, speak, done.

Built because Wispr Flow was slow — sometimes taking 5–10 seconds to fill in a transcription, occasionally failing silently. We live in an age where Apple Silicon can run a state-of-the-art speech model in under a second, entirely on your device. Open Whisper is that: a small, fast, transparent app that does one thing well.

**No subscription. No cloud. No clipboard pollution. Just your voice, pasted.**

---

## How it works

Press **Fn+R** → speak → press **Fn+R** again. Your words appear in whatever app you were using, as if you typed them. The full pipeline runs locally on your Mac in ~1 second.

---

## Features

| | |
|---|---|
| **Global hotkey** | Fn+R starts and stops recording from any app |
| **Auto-paste** | Text is pasted directly into your active window — no Cmd+V needed |
| **Clipboard-safe** | Your clipboard is not overwritten. The old content is restored within 300ms |
| **Everything local** | Audio never leaves your Mac. No account, no API key, no internet after setup |
| **Model selection** | 4 models to choose from: trade off speed vs. RAM vs. accuracy |
| **Microphone selection** | Pick any input device — built-in mic, AirPods, USB interface |
| **Transcription history** | Every recording saved to a local SQLite database |
| **Filter by app** | See transcriptions grouped by which app was active when you recorded |
| **Export** | Save your full history as `.md` or `.txt` in one click |
| **Apple Silicon optimized** | Uses MLX — the same framework Apple uses for on-device AI |
| **Model stays in RAM** | Model is loaded once and kept warm. No cold-start delay per recording |
| **Menu bar app** | Lives in your menu bar. No dock icon, no window clutter |
| **Sound feedback** | Audio cues for start, stop, and transcription complete |
| **Open source** | ~1000 lines of Python. Read it, fork it, change anything |

---

## Requirements

- macOS 12 or later
- Apple Silicon (M1/M2/M3/M4)
- Python 3.9+

---

## Install

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/open-whisper.git
cd open-whisper

# 2. Install dependencies
make install

# 3. Run
python3 app.py
```

That's it. The first run downloads the default model (~750 MB) from HuggingFace.

---

## Permissions

Two macOS permissions are required:

**Microphone** — prompted automatically on first recording.

**Accessibility** — required for auto-paste (so the app can simulate Cmd+V in other apps):
1. Open **System Settings → Privacy & Security → Accessibility**
2. Click **+** → add `Python` (or `OpenWhisper.app` if using the built bundle)
3. Toggle it **ON**

Without Accessibility permission the app still works — transcriptions are saved and copied to your clipboard. You just press Cmd+V manually.

---

## Usage

| Action | How |
|--------|-----|
| Start recording | Press **Fn+R** |
| Stop and transcribe | Press **Fn+R** again |
| View history / change settings | Click 🎤 in menu bar → **History** |
| Change microphone | History panel → Settings → Microphone |
| Change model | History panel → Settings → Model |
| Export history | History panel → Export .md or Export .txt |

Menu bar icon states: 🎤 ready · 🔴 recording · ⏳ transcribing

---

## Models

| Model | RAM | Speed | Notes |
|-------|-----|-------|-------|
| Distil Large V3 | ~1.4 GB | Fastest | English only — **default** |
| Turbo Q8 (8-bit) | ~880 MB | Fast | ~15% slower, saves 560 MB RAM |
| Large V3 Turbo | ~1.6 GB | Fast | Multilingual |
| Tiny | ~100 MB | Ultra fast | Lower accuracy |

Change the default in `app.py` by editing `DEFAULT_MODEL`. Any `mlx-community` Whisper model on HuggingFace works — just add it to the `MODELS` list.

---

## Customization

Open `app.py`. The top of the file has a `CONFIGURATION` section with everything you'd want to change:

```python
# Change the hotkey (default: Fn+R)
HOTKEY_KEYCODE = 15   # R key (see comments for other key codes)
HOTKEY_FN_FLAG = 0x800000

# Change the default model
DEFAULT_MODEL = "mlx-community/distil-whisper-large-v3"

# Add or remove models from the Settings panel
MODELS = [
    ("mlx-community/distil-whisper-large-v3", "..."),
    ...
]
```

To change the transcription language (default: English), find `language="en"` inside `WORKER_SCRIPT` and change it to any Whisper-supported language code, or remove it entirely for auto-detection.

---

## Data

All data lives in `~/.open-whisper/`:

| File | Contents |
|------|----------|
| `history.db` | SQLite database of all transcriptions |
| `app.log` | Application logs (useful for debugging) |

Model weights are cached in `~/.cache/huggingface/` by HuggingFace Hub.

To fully reset: `rm -rf ~/.open-whisper/`

---

## Building the app bundle (optional)

If you want a standalone `.app` that lives in your Applications folder:

```bash
make install-bundle   # installs py2app (one-time)
make rebuild          # builds dist/OpenWhisper.app
open dist/OpenWhisper.app
```

After rebuilding you'll need to re-grant Accessibility permission since the bundle identity changes.

---

## Troubleshooting

**Hotkey does nothing / icon missing from menu bar**
→ Grant Accessibility permission (System Settings → Privacy & Security → Accessibility)

**Text not auto-pasting**
→ Same — the app opens System Settings automatically when permission is missing

**Recording cuts out or sounds wrong**
→ Try a different microphone in History panel → Settings → Microphone

**Model download fails**
→ Check `~/.open-whisper/app.log`. Try running `python3 app.py` in Terminal to see errors directly.

**Want to use a different key than Fn+R**
→ Edit `HOTKEY_KEYCODE` at the top of `app.py`

---

## Project structure

```
app.py           — the entire application (~1000 lines)
setup.py         — py2app config for building the .app bundle
Makefile         — install / build / dev shortcuts
requirements.txt — Python dependencies
LICENSE
```

Everything is in `app.py`. No framework, no build step to run it. Read it top to bottom in 20 minutes.

---

## License

MIT
