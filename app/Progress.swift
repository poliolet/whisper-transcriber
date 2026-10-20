import AppKit
import Foundation
import Darwin

struct JobState: Decodable {
    let filename: String
    let started: Double
    let pid: Int32
    let phase: String
    let percent: Double?
    let detail: String
    let status: String
    let output_path: String?
    let finished: Double?
}

final class ProgressApp: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let stateURL: URL
    var window: NSWindow!
    var timer: Timer?
    var state: JobState?
    let filename = NSTextField(labelWithString: "")
    let phase = NSTextField(labelWithString: "Starting…")
    let detail = NSTextField(wrappingLabelWithString: "")
    let elapsed = NSTextField(labelWithString: "")
    let fraction = NSTextField(labelWithString: "")
    let bar = NSProgressIndicator()
    let openButton = NSButton(title: "Open transcript", target: nil, action: nil)

    init(path: String) { stateURL = URL(fileURLWithPath: path) }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let item = NSMenuItem()
        let submenu = NSMenu()
        submenu.addItem(withTitle: "Close progress window", action: #selector(closeWindow), keyEquivalent: "q").target = self
        item.submenu = submenu
        menu.addItem(item)
        NSApp.mainMenu = menu

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 500, height: 285),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Whisper Transcriber"
        window.isReleasedWhenClosed = false
        window.delegate = self
        let content = window.contentView!

        filename.font = .systemFont(ofSize: 13)
        filename.textColor = .secondaryLabelColor
        filename.lineBreakMode = .byTruncatingMiddle
        phase.font = .systemFont(ofSize: 20, weight: .semibold)
        detail.font = .systemFont(ofSize: 13)
        detail.textColor = .secondaryLabelColor
        elapsed.font = .monospacedDigitSystemFont(ofSize: 12, weight: .regular)
        elapsed.textColor = .secondaryLabelColor
        fraction.font = .monospacedDigitSystemFont(ofSize: 12, weight: .regular)
        fraction.alignment = .right
        bar.style = .bar
        bar.minValue = 0
        bar.maxValue = 100

        let footer = NSTextField(wrappingLabelWithString: "You can close this window. Processing will continue in the background.")
        footer.font = .systemFont(ofSize: 11)
        footer.textColor = .secondaryLabelColor
        openButton.target = self
        openButton.action = #selector(openTranscript)
        openButton.bezelStyle = .rounded
        openButton.isEnabled = false

        let frames: [(NSView, NSRect)] = [
            (filename, NSRect(x: 24, y: 238, width: 452, height: 20)),
            (phase, NSRect(x: 24, y: 198, width: 452, height: 30)),
            (detail, NSRect(x: 24, y: 151, width: 452, height: 38)),
            (bar, NSRect(x: 24, y: 125, width: 452, height: 16)),
            (elapsed, NSRect(x: 24, y: 99, width: 215, height: 18)),
            (fraction, NSRect(x: 245, y: 99, width: 231, height: 18)),
            (footer, NSRect(x: 24, y: 20, width: 280, height: 42)),
            (openButton, NSRect(x: 324, y: 26, width: 152, height: 32))
        ]
        for (view, frame) in frames { view.frame = frame; content.addSubview(view) }
        refresh()
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        timer = Timer.scheduledTimer(timeInterval: 0.5, target: self, selector: #selector(refresh), userInfo: nil, repeats: true)
    }

    @objc func refresh() {
        if let data = try? Data(contentsOf: stateURL),
           let decoded = try? JSONDecoder().decode(JobState.self, from: data) { state = decoded }
        guard let state else { return }
        filename.stringValue = state.filename
        phase.stringValue = state.phase
        detail.stringValue = state.detail
        let seconds = max(0, Int((state.finished ?? Date().timeIntervalSince1970) - state.started))
        elapsed.stringValue = String(format: "Elapsed  %02d:%02d", seconds / 60, seconds % 60)
        openButton.isEnabled = state.status == "done" && state.output_path != nil
        if state.status == "running" && kill(state.pid, 0) != 0 && errno == ESRCH {
            phase.stringValue = "Processing stopped"
            detail.stringValue = "The worker is no longer running. Check ~/Library/Logs/Whisper Transcriber."
            bar.stopAnimation(nil)
            bar.isIndeterminate = false
            bar.doubleValue = 0
            fraction.stringValue = ""
            timer?.invalidate()
            return
        }
        if let percent = state.percent {
            bar.stopAnimation(nil)
            bar.isIndeterminate = false
            bar.doubleValue = percent
            fraction.stringValue = state.status == "running" ? String(format: "%.0f%% of this step", percent) : ""
        } else {
            bar.isIndeterminate = state.status == "running"
            if bar.isIndeterminate { bar.startAnimation(nil) } else { bar.stopAnimation(nil); bar.doubleValue = 0 }
            fraction.stringValue = ""
        }
        if state.status != "running" { timer?.invalidate() }
    }

    @objc func openTranscript() {
        if let path = state?.output_path { NSWorkspace.shared.open(URL(fileURLWithPath: path)) }
    }
    @objc func closeWindow() { window.close() }
    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }
    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
        try? FileManager.default.removeItem(at: stateURL)
    }
}

guard CommandLine.arguments.count == 2 else { exit(2) }
let app = NSApplication.shared
let delegate = ProgressApp(path: CommandLine.arguments[1])
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
