.PHONY: install install-bundle build rebuild run dev clean

# Install dependencies for running directly with python3
install:
	brew install portaudio
	pip3 install --user -r requirements.txt

# Install additional dependency for building the .app bundle
install-bundle: install
	pip3 install --user py2app

PYTHON_BIN = /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3

build:
	@if [ ! -d dist/OpenWhisper.app ]; then \
		rm -rf build dist; \
		python3 setup.py py2app -A; \
		rm dist/OpenWhisper.app/Contents/MacOS/python; \
		ln -s $(PYTHON_BIN) dist/OpenWhisper.app/Contents/MacOS/python; \
		codesign -s - -f --deep dist/OpenWhisper.app; \
		echo "\n✓ Built and signed: dist/OpenWhisper.app"; \
	else \
		echo "✓ App already built (alias build picks up code changes automatically)"; \
	fi

rebuild:
	rm -rf build dist
	python3 setup.py py2app -A
	rm dist/OpenWhisper.app/Contents/MacOS/python
	ln -s $(PYTHON_BIN) dist/OpenWhisper.app/Contents/MacOS/python
	codesign -s - -f --deep dist/OpenWhisper.app
	@echo "\n✓ Rebuilt and signed: dist/OpenWhisper.app"
	@echo "⚠️  You will need to re-grant Accessibility permission in System Settings"

run: build
	open dist/OpenWhisper.app

# Run directly without building the app bundle (easiest for development)
dev:
	python3 app.py

clean:
	rm -rf build dist .eggs
