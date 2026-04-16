// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "OpenWisperLauncher",
    platforms: [.macOS(.v12)],
    targets: [
        .executableTarget(
            name: "OpenWisperLauncher",
            path: "OpenWisperLauncher"
        )
    ]
)
