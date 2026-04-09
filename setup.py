from setuptools import setup

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'VoiceTranscriber',
        'CFBundleDisplayName': 'Voice Transcriber',
        'CFBundleIdentifier': 'com.local.voicetranscriber',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.15',
        'LSUIElement': True,  # Menu bar app, no dock icon
        'NSMicrophoneUsageDescription': 'Voice Transcriber needs microphone access to record your voice for transcription.',
        'NSAppleEventsUsageDescription': 'Voice Transcriber needs automation access to paste transcribed text into other apps.',
    },
    'packages': ['rumps', 'pyaudio', 'mlx_whisper', 'mlx'],
    'includes': ['sqlite3', 'wave', 'struct', 'ApplicationServices'],
    'iconfile': None,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
