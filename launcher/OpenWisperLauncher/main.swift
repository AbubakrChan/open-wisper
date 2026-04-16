import Cocoa
import Carbon

// IPC paths for communication with Python backend
let triggerFile = "/tmp/openwisper-trigger"
let resultFile = "/tmp/openwisper-result"
let statusFile = "/tmp/openwisper-status"
let hotkeyFile = "/tmp/openwisper-hotkey"

// Default hotkey: Fn+R (keycode 15, Fn flag 0x800000)
let defaultKeycode: Int64 = 15
let defaultFlags: UInt64 = 0x800000

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var eventTap: CFMachPort?
    var pythonProcess: Process?
    var isRecording = false
    var isReady = false
    var accessibilityCheckTimer: Timer?

    // Current hotkey (can be changed via Settings)
    var hotkeyKeycode: Int64 = defaultKeycode
    var hotkeyFlags: UInt64 = defaultFlags

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupMenuBar()

        // Check accessibility and show wizard if needed
        if !checkAccessibility() {
            showAccessibilityWizard()
        } else {
            startApp()
        }
    }

    func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "⏳"

        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Wisper", action: nil, keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q"))
        statusItem.menu = menu
    }

    func checkAccessibility() -> Bool {
        return AXIsProcessTrustedWithOptions(nil)
    }

    func showAccessibilityWizard() {
        let alert = NSAlert()
        alert.messageText = "One Quick Step"
        alert.informativeText = """
        Open Wisper needs Accessibility permission to use the global hotkey.

        Click "Open Settings" and then:
        1. Find "Open Wisper" in the list
        2. Toggle it ON

        The app will start automatically once enabled.
        """
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Open Settings")
        alert.addButton(withTitle: "Quit")

        if let appIcon = NSImage(named: NSImage.applicationIconName) {
            alert.icon = appIcon
        }

        let response = alert.runModal()

        if response == .alertFirstButtonReturn {
            openAccessibilitySettings()
            startAccessibilityPolling()
        } else {
            NSApplication.shared.terminate(nil)
        }
    }

    func openAccessibilitySettings() {
        AXIsProcessTrustedWithOptions(
            [kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary
        )

        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }

    func startAccessibilityPolling() {
        statusItem.button?.title = "⏳"

        accessibilityCheckTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] timer in
            if self?.checkAccessibility() == true {
                timer.invalidate()
                self?.accessibilityCheckTimer = nil

                DispatchQueue.main.async {
                    self?.showSuccessAndStart()
                }
            }
        }
    }

    func showSuccessAndStart() {
        startApp()
    }

    func startApp() {
        try? "loading".write(toFile: statusFile, atomically: true, encoding: .utf8)

        loadHotkey()
        setupHotkey()
        startPythonBackend()
        watchResultFile()
        watchStatusFile()
        watchHotkeyFile()

        statusItem.button?.title = "⏳"
    }

    func loadHotkey() {
        // Read hotkey from file (written by Python)
        guard let content = try? String(contentsOfFile: hotkeyFile, encoding: .utf8) else {
            return
        }
        let parts = content.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: ",")
        if parts.count == 2,
           let keycode = Int64(parts[0]),
           let flags = UInt64(parts[1]) {
            hotkeyKeycode = keycode
            hotkeyFlags = flags
        }
    }

    func setupHotkey() {
        let eventMask = (1 << CGEventType.keyDown.rawValue)

        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: CGEventMask(eventMask),
            callback: { (proxy, type, event, refcon) -> Unmanaged<CGEvent>? in
                let delegate = Unmanaged<AppDelegate>.fromOpaque(refcon!).takeUnretainedValue()
                let keycode = event.getIntegerValueField(.keyboardEventKeycode)
                let flags = event.flags.rawValue

                // Check if pressed key matches configured hotkey
                if keycode == delegate.hotkeyKeycode && (flags & delegate.hotkeyFlags) == delegate.hotkeyFlags {
                    delegate.toggleRecording()
                    return nil
                }
                return Unmanaged.passRetained(event)
            },
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        )

        if let tap = eventTap {
            let runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
            CGEvent.tapEnable(tap: tap, enable: true)
        }
    }

    func toggleRecording() {
        if !isReady {
            DispatchQueue.main.async {
                let notification = NSUserNotification()
                notification.title = "Open Wisper"
                notification.informativeText = "Still loading AI model, please wait..."
                NSUserNotificationCenter.default.deliver(notification)
            }
            return
        }

        isRecording = !isRecording
        let command = isRecording ? "start" : "stop"
        try? command.write(toFile: triggerFile, atomically: true, encoding: .utf8)

        DispatchQueue.main.async {
            self.statusItem.button?.title = self.isRecording ? "🔴" : "🎤"
        }
    }

    func startPythonBackend() {
        let pythonPaths = [
            "/opt/homebrew/bin/python3.13",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3"
        ]

        var pythonPath: String?
        for path in pythonPaths {
            if FileManager.default.fileExists(atPath: path) {
                pythonPath = path
                break
            }
        }

        guard let python = pythonPath else {
            showError("Python not found", "Please install Python 3 via Homebrew:\nbrew install python")
            return
        }

        let scriptDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Applications/OpenWisper")
        let scriptPath = scriptDir.appendingPathComponent("app.py").path

        guard FileManager.default.fileExists(atPath: scriptPath) else {
            showError("App not found", "OpenWisper is not installed correctly.\nExpected: \(scriptPath)")
            return
        }

        pythonProcess = Process()
        pythonProcess?.executableURL = URL(fileURLWithPath: python)
        pythonProcess?.arguments = [scriptPath, "--backend-mode"]
        pythonProcess?.currentDirectoryURL = scriptDir
        pythonProcess?.standardOutput = FileHandle.nullDevice
        pythonProcess?.standardError = FileHandle.nullDevice

        do {
            try pythonProcess?.run()
        } catch {
            showError("Failed to start", "Could not start Python backend: \(error.localizedDescription)")
        }
    }

    func watchResultFile() {
        FileManager.default.createFile(atPath: resultFile, contents: nil)

        Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            guard let content = try? String(contentsOfFile: resultFile, encoding: .utf8),
                  content.trimmingCharacters(in: .whitespacesAndNewlines) == "paste" else {
                return
            }
            try? "".write(toFile: resultFile, atomically: true, encoding: .utf8)
            self?.simulatePaste()
        }
    }

    func watchStatusFile() {
        Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { [weak self] timer in
            guard let content = try? String(contentsOfFile: statusFile, encoding: .utf8) else {
                return
            }

            let status = content.trimmingCharacters(in: .whitespacesAndNewlines)

            if status == "ready" && self?.isReady == false {
                self?.isReady = true
                DispatchQueue.main.async {
                    self?.statusItem.button?.title = "🎤"

                    let notification = NSUserNotification()
                    notification.title = "Open Wisper"
                    notification.informativeText = "Ready! Press Fn+R to record."
                    NSUserNotificationCenter.default.deliver(notification)
                }
                timer.invalidate()
            }
        }
    }

    func watchHotkeyFile() {
        // Watch for hotkey changes from Python Settings
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.loadHotkey()
        }
    }

    func simulatePaste() {
        let source = CGEventSource(stateID: .hidSystemState)

        let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true)
        keyDown?.flags = .maskCommand
        keyDown?.post(tap: .cgAnnotatedSessionEventTap)

        let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false)
        keyUp?.flags = .maskCommand
        keyUp?.post(tap: .cgAnnotatedSessionEventTap)
    }

    func showError(_ title: String, _ message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.runModal()
    }

    @objc func quit() {
        pythonProcess?.terminate()
        NSApplication.shared.terminate(nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
