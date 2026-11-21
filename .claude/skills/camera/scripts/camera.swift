// Command-line camera capture for macOS (AVFoundation, no dependencies).
//
//   camera list
//   camera photo [-o out.jpg]
//   camera burst [-o dir] [--count 5] [--interval 1.0]
//   camera video [-o out.mov] [--duration 5] [--frames 0]
//
// Common options:
//   --device <name|id>   pick a camera (default: system default)
//   --warmup <sec>       let auto-exposure/white-balance settle (default 1.5)
//   --max-width <px>     downscale saved stills (default 1280, 0 = full size)
//   --roi x,y,w,h        normalized region (top-left origin) used for color stats
//
// Every saved still prints one JSON line to stdout with its path and the mean
// RGB / luma of the ROI (or whole frame), so changes can be compared numerically.

import AVFoundation
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers

// MARK: - Options

struct Options {
    var mode = "photo"
    var output: String?
    var device: String?
    var warmup = 1.5
    var maxWidth = 1280
    var count = 5
    var interval = 1.0
    var duration = 5.0
    var frames = 0
    var roi: CGRect?
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("error: \(message)\n".utf8))
    exit(1)
}

func parseOptions() -> Options {
    var opts = Options()
    var args = Array(CommandLine.arguments.dropFirst())
    if let first = args.first, !first.hasPrefix("-") {
        opts.mode = first
        args.removeFirst()
    }
    func value(_ i: inout Int) -> String {
        i += 1
        guard i < args.count else { fail("missing value for \(args[i - 1])") }
        return args[i]
    }
    var i = 0
    while i < args.count {
        switch args[i] {
        case "-o", "--output": opts.output = value(&i)
        case "--device": opts.device = value(&i)
        case "--warmup": opts.warmup = Double(value(&i)) ?? opts.warmup
        case "--max-width": opts.maxWidth = Int(value(&i)) ?? opts.maxWidth
        case "--count": opts.count = Int(value(&i)) ?? opts.count
        case "--interval": opts.interval = Double(value(&i)) ?? opts.interval
        case "--duration": opts.duration = Double(value(&i)) ?? opts.duration
        case "--frames": opts.frames = Int(value(&i)) ?? opts.frames
        case "--roi":
            let parts = value(&i).split(separator: ",").compactMap { Double($0) }
            guard parts.count == 4 else { fail("--roi expects x,y,w,h (normalized 0-1)") }
            opts.roi = CGRect(x: parts[0], y: parts[1], width: parts[2], height: parts[3])
        case "-h", "--help":
            print("usage: camera [list|photo|burst|video] [-o path] [--device name] [--warmup s] "
                + "[--max-width px] [--count n] [--interval s] [--duration s] [--frames n] [--roi x,y,w,h]")
            exit(0)
        default: fail("unknown argument \(args[i])")
        }
        i += 1
    }
    return opts
}

// MARK: - Devices & permission

func allDevices() -> [AVCaptureDevice] {
    AVCaptureDevice.DiscoverySession(
        deviceTypes: [.builtInWideAngleCamera, .external],
        mediaType: .video, position: .unspecified
    ).devices
}

func pickDevice(_ query: String?) -> AVCaptureDevice {
    guard let query else {
        guard let device = AVCaptureDevice.default(for: .video) else { fail("no camera found") }
        return device
    }
    let match = allDevices().first {
        $0.uniqueID == query || $0.localizedName.localizedCaseInsensitiveContains(query)
    }
    guard let match else { fail("no camera matching '\(query)' (try: camera list)") }
    return match
}

func ensureCameraAccess() {
    switch AVCaptureDevice.authorizationStatus(for: .video) {
    case .authorized:
        return
    case .notDetermined:
        let sem = DispatchSemaphore(value: 0)
        var granted = false
        AVCaptureDevice.requestAccess(for: .video) { ok in
            granted = ok
            sem.signal()
        }
        sem.wait()
        if !granted { fail("camera access was not granted") }
    default:
        fail("camera access denied - enable your terminal app under System Settings > "
            + "Privacy & Security > Camera, then restart the terminal")
    }
}

/// Wait while spinning the main run loop so AVFoundation callbacks can be delivered.
/// (RunLoop.run returns immediately when it has no sources, so sleep in that case.)
func pump(_ seconds: Double) {
    let end = Date().addingTimeInterval(seconds)
    while Date() < end {
        if !RunLoop.current.run(mode: .default, before: min(end, Date().addingTimeInterval(0.05))) {
            Thread.sleep(forTimeInterval: 0.01)
        }
    }
}

// MARK: - Still capture

final class FrameGrabber: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    private let lock = NSLock()
    private var latest: CVPixelBuffer?

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lock.lock()
        latest = buffer
        lock.unlock()
    }

    func snapshot() -> CIImage? {
        lock.lock()
        defer { lock.unlock() }
        return latest.map { CIImage(cvPixelBuffer: $0) }
    }
}

let ciContext = CIContext()

/// Mean RGB (0-255) over a normalized top-left-origin ROI, plus Rec.601 luma.
func colorStats(_ image: CIImage, roi: CGRect?) -> (r: Double, g: Double, b: Double, luma: Double) {
    let extent = image.extent
    var rect = extent
    if let roi {
        rect = CGRect(x: extent.minX + roi.minX * extent.width,
                      y: extent.minY + (1 - roi.minY - roi.height) * extent.height,
                      width: roi.width * extent.width,
                      height: roi.height * extent.height).intersection(extent)
    }
    let filter = CIFilter(name: "CIAreaAverage",
                          parameters: [kCIInputImageKey: image, kCIInputExtentKey: CIVector(cgRect: rect)])!
    var pixel = [UInt8](repeating: 0, count: 4)
    ciContext.render(filter.outputImage!, toBitmap: &pixel, rowBytes: 4,
                     bounds: CGRect(x: 0, y: 0, width: 1, height: 1),
                     format: .RGBA8, colorSpace: CGColorSpaceCreateDeviceRGB())
    let (r, g, b) = (Double(pixel[0]), Double(pixel[1]), Double(pixel[2]))
    return (r, g, b, 0.299 * r + 0.587 * g + 0.114 * b)
}

func saveJPEG(_ image: CIImage, to path: String, maxWidth: Int) {
    var image = image
    if maxWidth > 0, image.extent.width > CGFloat(maxWidth) {
        let scale = CGFloat(maxWidth) / image.extent.width
        image = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
    }
    guard let cgImage = ciContext.createCGImage(image, from: image.extent) else { fail("could not render frame") }
    let url = URL(fileURLWithPath: path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else {
        fail("could not write \(path)")
    }
    CGImageDestinationAddImage(dest, cgImage, [kCGImageDestinationLossyCompressionQuality: 0.85] as CFDictionary)
    guard CGImageDestinationFinalize(dest) else { fail("could not write \(path)") }
}

/// One-decimal number that serializes cleanly (no 153.69999999999999).
func round1(_ x: Double) -> NSDecimalNumber {
    NSDecimalNumber(string: String(format: "%.1f", x))
}

func printJSON(_ obj: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes])
    print(String(data: data, encoding: .utf8)!)
    fflush(stdout)
}

func report(_ image: CIImage, path: String, opts: Options, extra: [String: Any] = [:]) {
    let stats = colorStats(image, roi: opts.roi)
    var obj: [String: Any] = [
        "path": path,
        "width": Int(image.extent.width),
        "height": Int(image.extent.height),
        "mean_rgb": [stats.r, stats.g, stats.b].map(round1),
        "luma": round1(stats.luma),
        "time": ISO8601DateFormatter().string(from: Date()),
    ]
    if let roi = opts.roi { obj["roi"] = [roi.minX, roi.minY, roi.width, roi.height].map { NSDecimalNumber(string: String(format: "%.3f", Double($0))) } }
    obj.merge(extra) { _, new in new }
    printJSON(obj)
}

func defaultDir() -> String {
    let dir = (NSTemporaryDirectory() as NSString).appendingPathComponent("claude-camera")
    try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
    return dir
}

func timestamp() -> String {
    let f = DateFormatter()
    f.dateFormat = "yyyyMMdd-HHmmss-SSS"
    return f.string(from: Date())
}

func makeSession(_ device: AVCaptureDevice) -> AVCaptureSession {
    let session = AVCaptureSession()
    session.sessionPreset = .high
    guard let input = try? AVCaptureDeviceInput(device: device), session.canAddInput(input) else {
        fail("could not open \(device.localizedName) (in use by another app?)")
    }
    session.addInput(input)
    return session
}

func captureStills(_ opts: Options) {
    let device = pickDevice(opts.device)
    let session = makeSession(device)
    let output = AVCaptureVideoDataOutput()
    output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
    output.alwaysDiscardsLateVideoFrames = true
    let grabber = FrameGrabber()
    output.setSampleBufferDelegate(grabber, queue: DispatchQueue(label: "camera.frames"))
    guard session.canAddOutput(output) else { fail("could not attach video output") }
    session.addOutput(output)
    session.startRunning()
    defer { session.stopRunning() }

    pump(opts.warmup)
    let count = opts.mode == "burst" ? max(1, opts.count) : 1
    for n in 0..<count {
        if n > 0 { pump(opts.interval) }
        var frame = grabber.snapshot()
        var waited = 0.0
        while frame == nil, waited < 5 {
            pump(0.1)
            waited += 0.1
            frame = grabber.snapshot()
        }
        guard let frame else { fail("no frames received from \(device.localizedName)") }
        let path: String
        if opts.mode == "burst" {
            let dir = opts.output ?? (defaultDir() as NSString).appendingPathComponent("burst-\(timestamp())")
            path = (dir as NSString).appendingPathComponent(String(format: "frame-%03d.jpg", n))
        } else {
            path = opts.output ?? (defaultDir() as NSString).appendingPathComponent("photo-\(timestamp()).jpg")
        }
        saveJPEG(frame, to: path, maxWidth: opts.maxWidth)
        report(frame, path: path, opts: opts, extra: opts.mode == "burst" ? ["index": n] : [:])
    }
}

// MARK: - Video capture

final class Recorder: NSObject, AVCaptureFileOutputRecordingDelegate {
    var started = false
    var finished = false
    var error: Error?

    func fileOutput(_ output: AVCaptureFileOutput, didStartRecordingTo fileURL: URL,
                    from connections: [AVCaptureConnection]) {
        started = true
    }

    func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL,
                    from connections: [AVCaptureConnection], error: Error?) {
        // AVFoundation reports an "error" even on success; check the success flag.
        if let error = error as NSError?,
           (error.userInfo[AVErrorRecordingSuccessfullyFinishedKey] as? Bool) != true {
            self.error = error
        }
        finished = true
    }
}

func extractFrames(from path: String, count: Int, opts: Options) {
    let asset = AVURLAsset(url: URL(fileURLWithPath: path))
    // The recorded clip is usually a bit shorter than requested, so use its real length.
    let duration = asset.duration.seconds
    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    generator.requestedTimeToleranceBefore = .zero
    generator.requestedTimeToleranceAfter = .zero
    let base = (path as NSString).deletingPathExtension
    for n in 0..<count {
        let seconds = duration * (Double(n) + 0.5) / Double(count)
        guard let cgImage = try? generator.copyCGImage(at: CMTime(seconds: seconds, preferredTimescale: 600),
                                                       actualTime: nil) else { continue }
        let image = CIImage(cgImage: cgImage)
        let framePath = String(format: "%@-frame-%03d.jpg", base, n)
        saveJPEG(image, to: framePath, maxWidth: opts.maxWidth)
        report(image, path: framePath, opts: opts, extra: ["index": n, "video_time": round1(seconds)])
    }
}

func captureVideo(_ opts: Options) {
    let device = pickDevice(opts.device)
    let session = makeSession(device)
    let output = AVCaptureMovieFileOutput()
    guard session.canAddOutput(output) else { fail("could not attach movie output") }
    session.addOutput(output)
    session.startRunning()
    defer { session.stopRunning() }

    pump(opts.warmup)
    let path = opts.output ?? (defaultDir() as NSString).appendingPathComponent("video-\(timestamp()).mov")
    let url = URL(fileURLWithPath: path)
    try? FileManager.default.removeItem(at: url)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)

    let recorder = Recorder()
    output.startRecording(to: url, recordingDelegate: recorder)
    // Recording starts asynchronously; only count time once the file has started.
    var waitedForStart = 0.0
    while !recorder.started, waitedForStart < 5 {
        pump(0.05)
        waitedForStart += 0.05
    }
    pump(opts.duration)
    output.stopRecording()
    var waited = 0.0
    while !recorder.finished, waited < 10 {
        pump(0.1)
        waited += 0.1
    }
    if let error = recorder.error { fail("recording failed: \(error.localizedDescription)") }
    guard recorder.finished else { fail("recording did not finish") }

    let actual = AVURLAsset(url: url).duration.seconds
    printJSON(["path": path, "requested_duration": opts.duration, "duration": round1(actual)])
    if opts.frames > 0 { extractFrames(from: path, count: opts.frames, opts: opts) }
}

// MARK: - Main

let opts = parseOptions()
switch opts.mode {
case "list":
    let defaultID = AVCaptureDevice.default(for: .video)?.uniqueID
    for device in allDevices() {
        print("\(device.uniqueID == defaultID ? "*" : " ") \(device.localizedName)  [\(device.uniqueID)]")
    }
case "photo", "burst":
    ensureCameraAccess()
    captureStills(opts)
case "video":
    ensureCameraAccess()
    captureVideo(opts)
default:
    fail("unknown mode '\(opts.mode)' (expected list, photo, burst, video)")
}
