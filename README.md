<div align="center">
  <img src="assets/banner.svg" alt="Open Wisper" width="820"/>

  <br/>
  <br/>

  <a href="https://github.com/AbubakrChan/open-wisper/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License"/>
  </a>
  <img src="https://img.shields.io/badge/macOS-12%2B-lightgrey?style=flat-square&logo=apple&logoColor=white" alt="macOS 12+"/>
  <img src="https://img.shields.io/badge/Apple%20Silicon-M1%20·%20M2%20·%20M3%20·%20M4-blue?style=flat-square&logo=apple&logoColor=white" alt="Apple Silicon"/>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+"/>
  <img src="https://img.shields.io/badge/powered%20by-MLX-ff6b35?style=flat-square" alt="Powered by MLX"/>

  <br/>
  <br/>

  <p>
    Built because Wispr Flow was too slow — sometimes 5–10 seconds per transcription, occasionally failing silently.<br/>
    Apple Silicon can run a state-of-the-art speech model in under a second, entirely on your device.<br/>
    Open Wisper does exactly that.
  </p>

  <strong>No subscription. No cloud. Highly customizable. Just your voice, pasted.</strong>

</div>

---

## What it does

Press your hotkey → speak → press it again. (**Fn+R** by default — set your own in Settings.)

Your words appear in whatever app you were using, as if you typed them. The full pipeline — recording, transcription, paste — completes in ~1 second. Everything runs locally on your Mac. Nothing is sent anywhere.

---

## Features

| | |
|---|---|
| **Custom hotkey** | Set any key combo in Settings — Fn+R by default |
| **Auto-paste** | Text is pasted directly into your active window. No Cmd+V needed |
| **Clipboard-safe** | Your clipboard is preserved. Old content is restored within 300ms |
| **100% local** | Audio never leaves your Mac. No account, no API key, no internet after setup |
| **Bring your own model** | Plug in any Whisper model from HuggingFace — appears in Settings instantly |
| **Language selection** | 16 languages + auto-detect, switchable in Settings |
| **Microphone selection** | Built-in mic, AirPods, USB interface — switch any time |
| **Transcription history** | Every recording saved to a local SQLite database |
| **Filter by app** | Transcriptions grouped by which app was active when you recorded |
| **Export** | Save full history as `.md` or `.txt` in one click |
| **Launch at login** | Start automatically with macOS — toggle in Settings |
| **Apple Silicon optimized** | Uses MLX, Apple's own ML framework for on-device inference |
| **Model stays warm** | Loaded once at startup, kept in memory. No cold-start delay per recording |
| **Menu bar app** | Lives in your menu bar. No dock icon, no window clutter |
| **Sound feedback** | Audio cues for start, stop, and transcription complete |
| **Highly customizable** | ~1600 lines of Python, one file. Read it, fork it, change anything |

---

## Fully local. Fully private.

Everything runs on your Mac. Nothing leaves your device.

- **No account** — there is no sign-up, no login, no profile
- **No API key** — the AI model runs directly on your Apple Silicon chip via MLX
- **No internet after setup** — the model is downloaded once (~750 MB), then works offline forever
- **No audio storage** — recordings are processed and immediately discarded; only the final text is saved
- **No telemetry** — no analytics, no crash reporting, no phone-home of any kind
- **Verifiable** — every line of code is in `app.py`. Read it and confirm it yourself

The only network request the app ever makes is the one-time model download from HuggingFace.

---

## Requirements

- macOS 12 or later
- Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.9+ and Homebrew (the installer handles both)

---

## Getting started

**One command installs everything:**

```bash
curl -fsSL https://raw.githubusercontent.com/AbubakrChan/open-wisper/master/install.sh | bash
```

### What happens

1. **Dependencies install** — Homebrew, Python, and required packages (automatic)
2. **App launches** — Open Wisper opens with a simple permission dialog
3. **One toggle** — Click "Open Settings", find "Open Wisper" in the list, toggle it **ON**
4. **Done** — The app auto-detects when you've enabled it and starts working

That's it. The 🎤 icon appears in your menu bar. Press **Fn+R** to record.

### First recording

On your first recording, the AI model downloads (~750 MB). This takes 30–60 seconds depending on your connection. After that, it's cached forever and works offline.

### Launch at login

Enable **Settings → At Login** to have Open Wisper start automatically with your Mac. You'll never think about launching it again.

### Manual launch

```bash
open-wisper
```

Or double-click `~/Applications/OpenWisper.app`.

---

## Using the app

| Action | How |
|--------|-----|
| Start recording | Press **Fn+R** (or your custom hotkey) |
| Stop and transcribe | Press **Fn+R** again |
| View history / settings | Click 🎤 in the menu bar → **History** |
| Change microphone | History → Settings → Microphone |
| Change model | History → Settings → Model |
| Change language | History → Settings → Language |
| Change hotkey | History → Settings → Hotkey → **Record** → press new combo |
| Launch at login | History → Settings → At Login |
| Export history | History → Export .md or Export .txt |

Menu bar icon states: 🎤 ready · 🔴 recording · ⏳ loading / transcribing

---

## Models

| Model | Speed | Languages |
|-------|-------|-----------|
| **Large V3 Turbo** ← default | fast | All languages |
| **Distil Large V3** | fastest | English only |
| **Turbo Q8** | fast | Multilingual |
| **Tiny** | ultra fast | All (lower accuracy) |

**Large V3 Turbo** is the default — best quality, handles all languages, ~1–1.5s pipeline.

**Distil Large V3** is the fastest option if you only speak English and want the lowest latency (~1s).

**Tiny** works on any language with minimal resource usage. Accuracy is lower on technical terms and proper nouns.

Change models any time in Settings — no restart needed.

**Bring your own model** — any Whisper model from `mlx-community` on HuggingFace works. Add it to the `MODELS` list in `app.py` and it appears in Settings immediately.

---

## How we made it fast

Whisper is accurate but not inherently fast. Getting to ~1s on an everyday Mac took several deliberate choices:

**Skip language detection** — Whisper normally runs a detection pass before transcribing, adding 0.3–0.5s. Setting `language="en"` skips it entirely. This is the biggest single win.

**Model stays in memory** — most tools load the model fresh on every transcription (3–5s overhead). Open Wisper loads the model once at startup in a persistent subprocess and keeps it there.

**Warmup run** — immediately after loading, a 0.5s silent clip runs through the model to page weights into GPU memory. Your first real recording is as fast as every other.

**Keepalive every 3 minutes** — macOS can evict GPU memory from idle processes. A silent ping every 3 minutes keeps model weights resident, so you get fast transcription even after a long break.

**Metal cache cap at 200 MB** — MLX's GPU memory cache is capped at 200 MB instead of the default 400 MB+. Less memory pressure on 8 GB Macs.

**16 kHz mono audio** — Whisper was trained on 16 kHz mono. We record at exactly this format, skipping any resampling step before inference.

**Distillation** — Distil-Whisper Large v3 is 6× smaller than full Whisper Large v3 but retains ~98% of English accuracy. It's the default for a reason.

---

## Built for customization

Open Wisper is designed to be yours. Every common setting lives in the **Settings panel** — no code editing required for any of it:

| What | Where |
|------|-------|
| Hotkey | Settings → Hotkey → Record (press any combo) |
| Model | Settings → Model |
| Language | Settings → Language |
| Microphone | Settings → Microphone |
| Launch at login | Settings → At Login |

Want to go deeper? The entire app is ~1600 lines of Python in one file (`app.py`) with a clear configuration block at the top. Fork it, read it, make it yours.

**Add any Whisper model from HuggingFace**

Find the `MODELS` list near the top of `app.py` and add a line:

```python
MODELS = [
    ("mlx-community/distil-whisper-large-v3", "Distil Large V3 — fastest, English"),
    ("your-org/your-model",                   "My custom model"),  # ← add here
]
```

Any `mlx-community` Whisper model on HuggingFace works. It appears in Settings immediately and downloads on demand.

**Change the default hotkey**

Set `DEFAULT_HOTKEY_KEYCODE` and `DEFAULT_HOTKEY_FLAGS` at the top of `app.py` to change what hotkey new users get on first launch. Existing users can always change it without touching code via Settings → Hotkey.

---

## Data

All data lives in `~/.open-wisper/`:

| File | Contents |
|------|----------|
| `history.db` | SQLite database of all transcriptions and settings |
| `app.log` | Application logs |

Model weights are cached in `~/.cache/huggingface/` by HuggingFace Hub.

To fully reset: `rm -rf ~/.open-wisper/`

---

## Troubleshooting

**Icon shows ⏳ and stays there**
→ Model is loading — wait 5–15 seconds on first launch. If it stays longer, check `~/.open-wisper/app.log`.

**Hotkey does nothing**
→ Accessibility permission is missing. System Settings → Privacy & Security → Accessibility → find "Open Wisper" and toggle it **ON**.

**Text not auto-pasting**
→ Same as above. Without Accessibility, text is copied to your clipboard — press Cmd+V manually.

**"Open Wisper" not in Accessibility list**
→ Relaunch the app. It will prompt you to add it.

**Recording sounds wrong or cuts out**
→ Try a different microphone in History → Settings → Microphone.

**Transcription is inaccurate**
→ Switch to a larger model. If you're on Tiny, try Distil Large V3.

**Model download fails**
→ Check your connection and relaunch. Check `~/.open-wisper/app.log` for details.

---

## Architecture

Open Wisper uses a two-process architecture for a seamless permission experience:

```
OpenWisper.app (Swift)          Python backend
┌─────────────────────┐         ┌─────────────────────┐
│ • Global hotkey     │ ──IPC── │ • Audio recording   │
│ • Paste simulation  │         │ • Whisper inference │
│ • Menu bar icon     │         │ • History database  │
│ • Accessibility UI  │         │ • Settings panel    │
└─────────────────────┘         └─────────────────────┘
```

**Why?** macOS requires Accessibility permission for global hotkeys (CGEventTap). By handling the hotkey in a native Swift app, users grant permission to "Open Wisper" — not "Python", which is confusing and buried in a deep system path.

The Python backend handles everything else: recording, transcription, history, and settings. The two processes communicate via simple file-based IPC.

---

## Project structure

```
app.py              — Python backend (~1600 lines)
OpenWisper.app/     — Pre-built Swift launcher for hotkey + paste
launcher/           — Swift source code for the launcher
install.sh          — One-command setup script
requirements.txt    — Python dependencies
assets/             — Banner and static assets
LICENSE
```

---

## Building from source

The Swift launcher is pre-built and included in the repo. If you want to modify it:

```bash
cd launcher
swift build -c release
./build.sh
```

This creates `OpenWisper.app`. Copy it to `~/Applications/` and re-grant Accessibility permission.

---

## License

MIT — do whatever you want with it.
