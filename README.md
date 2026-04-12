# Open Wisper

> Local voice transcription for macOS. Press a key, speak, done.

Built because Wispr Flow was too slow — sometimes taking 5–10 seconds to fill in a transcription, occasionally failing silently. We live in an age where Apple Silicon can run a state-of-the-art speech model in under a second, entirely on your device. Open Wisper is that: a small, fast, transparent app that does one thing well.

**No subscription. No cloud. No clipboard pollution. Just your voice, pasted.**

---

## How it works

Press **Fn+R** → speak → press **Fn+R** again. Your words appear in whatever app you were using, as if you typed them. The full pipeline runs locally on your Mac in ~1 second.

---

## Features

| | |
|---|---|
| **Global hotkey** | Fn+R starts and stops recording from any app (customizable in Settings) |
| **Auto-paste** | Text is pasted directly into your active window — no Cmd+V needed |
| **Clipboard-safe** | Your clipboard is not overwritten. The old content is restored within 300ms |
| **Everything local** | Audio never leaves your Mac. No account, no API key, no internet after setup |
| **Model selection** | 4 models to choose from: trade off speed vs. RAM vs. accuracy |
| **Microphone selection** | Pick any input device — built-in mic, AirPods, USB interface |
| **Custom hotkey** | Change the trigger key from the Settings panel — no code editing needed |
| **Transcription history** | Every recording saved to a local SQLite database |
| **Filter by app** | See transcriptions grouped by which app was active when you recorded |
| **Export** | Save your full history as `.md` or `.txt` in one click |
| **Apple Silicon optimized** | Uses MLX — the same framework Apple uses for on-device AI |
| **Model stays in RAM** | Model is loaded once and kept warm. No cold-start delay per recording |
| **Menu bar app** | Lives in your menu bar. No dock icon, no window clutter |
| **Sound feedback** | Audio cues for start, stop, and transcription complete |
| **Open source** | ~1600 lines of Python. Read it, fork it, change anything |

---

## Requirements

- macOS 12 or later
- Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.9+
- Homebrew (for PortAudio)

---

## Getting started

### Step 1 — Clone and install

Open Terminal and run:

```bash
git clone https://github.com/YOUR_USERNAME/open-wisper.git
cd open-wisper
bash install.sh
```

`install.sh` checks your system, installs PortAudio via Homebrew, and installs all Python dependencies. It takes about a minute. You'll see a summary when it's done.

---

### Step 2 — Launch the app

```bash
python3 app.py
```

The app starts in your menu bar. You'll see a **setup wizard** appear automatically — it walks you through the two things needed before the app can work.

---

### Step 3 — Download the AI model (wizard: step 1)

The wizard's first step downloads the speech model. The default model is **Distil-Whisper Large v3** (~750 MB). A progress bar shows download status. This happens once — the model is cached and reused on every future launch.

> If the download fails, check your internet connection and relaunch. The wizard will re-appear.

---

### Step 4 — Grant Microphone access (wizard: step 2)

The wizard will prompt macOS to ask for microphone access. Click **Allow** in the dialog that appears.

If you missed it or clicked Deny:

1. Open **System Settings**
2. Go to **Privacy & Security → Microphone**
3. Find **Python** (or **OpenWisper** if using the app bundle) and toggle it **ON**

---

### Step 5 — Grant Accessibility access (wizard: step 3)

This is what lets the app paste text into other apps automatically. macOS requires you to grant this manually — it cannot be granted via a dialog.

The wizard opens System Settings to the right page automatically. Here is what to do:

1. System Settings will open to **Privacy & Security → Accessibility**
2. Click the **+** button at the bottom of the list
3. Navigate to and select `python3` (or `OpenWisper.app` if using the app bundle)
4. Make sure the toggle next to it is **ON**
5. Switch back to the app — it will detect the permission automatically

> Without Accessibility, the app still works: transcriptions are saved and copied to your clipboard. You just press Cmd+V manually instead of having it auto-paste.

---

### Step 6 — You're ready

The wizard closes. The **microphone icon (🎤)** appears in your menu bar. The model loads in the background — this takes 5–15 seconds on first launch.

Once the icon is visible and the model is loaded, you're done with setup. Every future launch is instant.

---

## Using the app

| Action | How |
|--------|-----|
| Start recording | Press **Fn+R** (or your custom hotkey) |
| Stop and transcribe | Press **Fn+R** again |
| View history / change settings | Click 🎤 in the menu bar → **History** |
| Change microphone | History panel → Settings → Microphone |
| Change model | History panel → Settings → Model |
| Change hotkey | History panel → Settings → Hotkey → click **Record** → press your new key combo |
| Launch at login | History panel → Settings → At Login |
| Export history | History panel → Export .md or Export .txt |

Menu bar icon states: 🎤 ready · 🔴 recording · ⏳ loading / transcribing

---

## Changing your hotkey

Open the History panel (click 🎤 → History). In the **Settings** section:

1. Find the **Hotkey** row — it shows your current hotkey (default: `Fn+R`)
2. Click **Record**
3. Press the key combination you want (e.g. Fn+T, or ⌃Space, or ⌥R)
4. The new hotkey is saved immediately and works right away

The hotkey requires at least one modifier key (Fn, Control, Option, or Command). Bare letter keys are ignored to avoid interfering with typing.

---

## Models

Choose your model based on your Mac's RAM and what languages you speak. Change it any time in the Settings panel without restarting.

### Distil Large V3 — default, recommended for English

```
RAM: ~1.4 GB   Speed: fastest   Language: English only
```

The best choice for most people. Near-Large quality at a fraction of the size. Language detection is skipped entirely, making it noticeably faster. **If you speak English, use this.**

### Turbo Q8 — best for low-RAM Macs

```
RAM: ~880 MB   Speed: fast (~15% slower)   Language: English + multilingual
```

8-bit quantized version of Whisper Large v3 Turbo. Saves ~560 MB of RAM. **Use this if you have 8 GB RAM and run other memory-heavy apps** (Xcode, Chrome, etc.).

### Large V3 Turbo — multilingual

```
RAM: ~1.6 GB   Speed: fast   Language: all languages
```

Full-precision multilingual model. Language detection runs (~0.4s overhead), then transcribes in whatever language you spoke. **Use this if you switch between languages** or speak a non-English language.

### Tiny — for constrained environments

```
RAM: ~100 MB   Speed: ultra fast   Language: multilingual (lower accuracy)
```

Extremely small model. Noticeable errors on proper nouns, technical terms, and accents. **Use this only if RAM is very constrained.**

---

## How we made it fast

Whisper is accurate but not inherently fast. Getting to sub-second transcription on an everyday Mac took several deliberate choices:

**1. Skip language detection (the biggest win)**

Whisper normally runs a language detection pass before transcribing — this adds ~0.3–0.5 seconds per recording. Setting `language="en"` skips detection entirely and goes straight to transcribing. The tradeoff: English only. For other languages, use Large V3 Turbo with detection enabled.

**2. Model loaded once, stays in memory**

Most tools load the AI model fresh on every transcription — 3–5 seconds of overhead every time. Open Wisper loads the model once at startup in a persistent background subprocess and keeps it there. You pay the loading cost once; subsequent transcriptions start immediately.

**3. Warmup run**

When the model first loads, its weights are in memory but not yet paged in to the GPU. The first transcription would be slow. A 0.5-second silent audio clip runs through the model immediately after loading, forcing the GPU to page in all the weights before your first real recording.

**4. Keepalive every 3 minutes**

macOS can evict GPU memory from idle processes. A silent ping runs every 3 minutes to keep model weights resident. Fast transcription even after a long break.

**5. Metal cache capped at 200 MB**

MLX maintains a GPU memory cache between operations. By default it can grow to 400 MB+. We cap it at 200 MB to reduce memory pressure, especially on 8 GB Macs.

**6. 16 kHz mono audio**

Whisper was trained on 16 kHz mono. We record at exactly this format — no resampling step before inference.

**7. Distillation (default model)**

Distil-Whisper Large v3 is 6x smaller than full Whisper Large v3 but retains ~98% of the accuracy for English — the best quality-to-speed ratio for the common case.

---

## Data

All data lives in `~/.open-wisper/`:

| File | Contents |
|------|----------|
| `history.db` | SQLite database of all transcriptions and settings |
| `app.log` | Application logs (useful for debugging) |

Model weights are cached in `~/.cache/huggingface/` by HuggingFace Hub.

To fully reset: `rm -rf ~/.open-wisper/`

---

## Troubleshooting

**Icon shows ⏳ and stays there**
→ The model is loading. Wait 5–15 seconds. If it stays for more than 30 seconds, check `~/.open-wisper/app.log` for errors.

**Hotkey does nothing**
→ Accessibility permission is missing. Open System Settings → Privacy & Security → Accessibility → add and enable Python (or OpenWisper.app).

**Text not auto-pasting**
→ Same as above. The app opens System Settings automatically when permission is missing.

**App opens System Settings on every launch**
→ Accessibility permission was revoked (this happens when you rebuild the `.app` bundle or reinstall Python). Re-grant it in System Settings → Privacy & Security → Accessibility.

**Recording cuts out or sounds wrong**
→ Try a different microphone in History panel → Settings → Microphone.

**Transcription is inaccurate**
→ Try a larger model. If you're using Tiny, switch to Distil Large V3.

**Model download fails or is slow**
→ Check `~/.open-wisper/app.log`. Run `python3 app.py` in Terminal to see live output.

**Setup wizard doesn't appear on launch**
→ The wizard only shows on first launch. To reset: `rm -rf ~/.open-wisper/ && python3 app.py`

---

## Building a standalone .app (optional)

If you want to double-click to launch instead of using Terminal:

```bash
make install-bundle   # installs py2app (one-time)
make rebuild          # builds dist/OpenWisper.app
open dist/OpenWisper.app
```

After rebuilding, re-grant Accessibility permission in System Settings — the bundle identity changes with each build.

---

## Project structure

```
app.py           — the entire application (~1600 lines)
install.sh       — one-command setup for new users
setup.py         — py2app config for building the .app bundle
Makefile         — install / build / dev shortcuts
requirements.txt — Python dependencies
LICENSE
```

Everything is in `app.py`. No framework, no build step to run the script. Read it top to bottom in 20 minutes.

---

## License

MIT
