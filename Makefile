.PHONY: install build run dev clean

install:
	brew install portaudio ffmpeg
	pip3 install --user -r requirements.txt
	pip3 install --user py2app

build:
	rm -rf build dist
	python3 setup.py py2app -A
	@echo "\n✓ Built: dist/VoiceTranscriber.app"

run: build
	open dist/VoiceTranscriber.app

dev:
	python3 app.py

clean:
	rm -rf build dist .eggs
