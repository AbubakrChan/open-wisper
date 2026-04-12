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
| **Open source** | ~1600 lines of Python. Read it, fork it, change anything |

---

## How we made it fast

Whisper is accurate but not inherently fast. Getting to sub-second transcription on an everyday Mac took several deliberate choices:

**1. Skip language detection (the biggest win)**

Whisper normally runs a language detection pass before transcribing — it listens to the audio and tries to figure out what language you're speaking. This adds ~0.3–0.5 seconds of overhead on every recording.

If you set `language="en"`, Whisper skips detection entirely and goes straight to transcribing. No guessing, no delay. The tradeoff is that it only works well for English. If you speak another language, switch to a multilingual model (Large V3 Turbo) and remove the language setting — detection will run but accuracy will be better.

**2. Model loaded once, stays in memory**

Most tools load the AI model fresh on every transcription. That's 3–5 seconds of overhead every time.

Open Wisper loads the model once at startup (in a persistent background subprocess) and keeps it there. Each transcription goes directly to an already-loaded model. The loading time you pay once; subsequent transcriptions start immediately.

**3. Warmup run**

When the model first loads, its weights are in memory but not yet "paged in" to the GPU. The first transcription would be slow.

To fix this, we run a 0.5-second silent audio clip through the model immediately after loading. This forces the GPU to page in all the weights before your first real recording.

**4. Keepalive every 3 minutes**

macOS can evict GPU memory from idle processes. If you haven't recorded in a while, the model weights might get paged out — and your next recording would be slow again.

We send a silent ping to the model every 3 minutes to keep the weights resident. You always get fast transcription, even after a long break.

**5. Metal cache capped at 200 MB**

MLX (Apple's ML framework) maintains a GPU memory cache between operations. By default it can grow to 400 MB+ of idle cache. We cap it at 200 MB. Less memory pressure on the system, especially relevant on 8 GB Macs.

**6. 16 kHz mono audio**

Whisper was trained on 16 kHz mono audio. We record at exactly this format, so there's no resampling step before inference. Less data, no conversion overhead.

**7. Distillation (default model)**

The default model (Distil-Whisper Large v3) was built using knowledge distillation — a technique where a smaller model is trained to behave like a much larger one. It's 6x smaller than the full Whisper Large v3 but retains ~98% of the accuracy for English. That's why it's the default: the best quality-to-speed ratio for English speakers.

---

## Models

Choose your model based on your Mac's RAM and what languages you speak. Change it any time in the Settings panel without restarting the app.

### Distil Large V3 — default, recommended for English

```
RAM: ~1.4 GB   Speed: fastest   Language: English only
```

The best choice for most people. Uses distillation to hit near-Large quality at a fraction of the size. Language detection is skipped entirely (see above), making it noticeably faster than the multilingual alternatives. **If you speak English, use this.**

### Turbo Q8 — best for low-RAM Macs

```
RAM: ~880 MB   Speed: fast (~15% slower than Distil)   Language: English + multilingual
```

8-bit quantized version of Whisper Large v3 Turbo. Saves ~560 MB of RAM compared to the default with only a small quality and speed hit. **Use this if you have 8 GB RAM and are running other memory-heavy apps** (Xcode, Chrome, etc.).

### Large V3 Turbo — multilingual

```
RAM: ~1.6 GB   Speed: fast   Language: all languages
```

Full-precision multilingual model. Whisper's language detection runs (adds ~0.4s), then transcribes in whatever language you spoke. **Use this if you switch between languages** or primarily speak a non-English language.

### Tiny — for constrained environments

```
RAM: ~100 MB   Speed: ultra fast   Language: multilingual (lower accuracy)
```

Extremely small model. Noticeably more errors, especially on proper nouns, technical terms, and accents. **Use this only if RAM is extremely constrained** (8 GB Mac running many apps) or if you need maximum speed and accuracy doesn't matter.

---

## Requirements

- macOS 12 or later
- Apple Silicon (M1/M2/M3/M4)
- Python 3.9+

---

## Install

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/open-wisper.git
cd open-wisper

# 2. Install
bash install.sh

# 3. Run
python3 app.py
```

That's it. On first launch a setup wizard guides you through downloading the AI model (~750 MB) and granting permissions. Subsequent launches are instant.

---

## Permissions

Two macOS permissions are required:

**Microphone** — prompted automatically on first recording.

**Accessibility** — required for auto-paste (so the app can simulate Cmd+V in other apps):
1. Open **System Settings → Privacy & Security → Accessibility**
2. Click **+** → add `Python` (or `OpenWisper.app` if using the built bundle)
3. Toggle it **ON**

Without Accessibility permission the app still works — transcriptions are saved to history and copied to your clipboard. You just press Cmd+V manually.

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

## Customization

Open `app.py`. The top has a `CONFIGURATION` section:

```python
# Hotkey: Fn+R by default. Change HOTKEY_KEYCODE to use a different key.
# Key codes: A=0 S=1 D=2 F=3 H=4 G=5 Z=6 X=7 C=8 V=9 R=15 ...
HOTKEY_KEYCODE = 15
HOTKEY_FN_FLAG = 0x800000

# Default model on first launch
DEFAULT_MODEL = "mlx-community/distil-whisper-large-v3"

# Models shown in the Settings panel — add any mlx-community Whisper model here
MODELS = [...]
```

To switch to multilingual or change the target language, find `language="en"` inside `WORKER_SCRIPT` (~line 115) and change it to any Whisper language code (`"fr"`, `"de"`, `"ar"`, etc.), or remove the argument entirely for auto-detection.

---

## Data

All data lives in `~/.open-wisper/`:

| File | Contents |
|------|----------|
| `history.db` | SQLite database of all transcriptions |
| `app.log` | Application logs (useful for debugging) |

Model weights are cached in `~/.cache/huggingface/` by HuggingFace Hub.

To fully reset: `rm -rf ~/.open-wisper/`

---

## Building the app bundle (optional)

If you want a standalone `.app`:

```bash
make install-bundle   # installs py2app (one-time)
make rebuild          # builds dist/OpenWisper.app
open dist/OpenWisper.app
```

After rebuilding you'll need to re-grant Accessibility permission since the bundle identity changes.

---

## Troubleshooting

**Hotkey does nothing / icon missing from menu bar**
→ Grant Accessibility permission — System Settings → Privacy & Security → Accessibility

**Text not auto-pasting**
→ Same. The app opens System Settings automatically when permission is missing.

**Recording cuts out or sounds wrong**
→ Try a different microphone in History panel → Settings → Microphone

**Transcription is inaccurate**
→ Try a larger model. If you're using Tiny, switch to Distil Large V3.

**Model download fails or is slow**
→ Check `~/.open-wisper/app.log`. Run `python3 app.py` in Terminal to see errors live.

**Want a different hotkey**
→ Edit `HOTKEY_KEYCODE` at the top of `app.py`

---

## Project structure

```
app.py           — the entire application (~1600 lines)
setup.py         — py2app config for building the .app bundle
Makefile         — install / build / dev shortcuts
requirements.txt — Python dependencies
LICENSE
```

Everything is in `app.py`. No framework, no build step to run. Read it top to bottom in 20 minutes.

---

## License

MIT
