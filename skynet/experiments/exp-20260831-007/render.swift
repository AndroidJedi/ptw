import AppKit
import CoreText
import Foundation

let canvasWidth: CGFloat = 1080
let canvasHeight: CGFloat = 1080

guard CommandLine.arguments.count == 2 else {
    fatalError("usage: render.swift OUTPUT_PNG")
}

let outputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let scriptURL = URL(fileURLWithPath: #filePath)
let experimentRoot = scriptURL.deletingLastPathComponent()
let skynetRoot = experimentRoot.deletingLastPathComponent().deletingLastPathComponent()
let mediaURL = experimentRoot.appendingPathComponent("assets/return-loop-still-life-v1.png")
let fontURL = skynetRoot.appendingPathComponent("assets/natal/inter.ttf")
let logoURL = skynetRoot.appendingPathComponent("assets/natal/logo-natal.png")

func copyValue(_ name: String) -> String {
    let url = experimentRoot.appendingPathComponent("copy/\(name).txt")
    guard let value = try? String(contentsOf: url, encoding: .utf8)
        .trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
        fatalError("unable to read copy binding \(name)")
    }
    return value
}

let headline = copyValue("headline")
let primary = copyValue("primary")
let offer = copyValue("offer")
let cta = copyValue("cta")

var fontError: Unmanaged<CFError>?
if !CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, &fontError) {
    let description = fontError.map {
        CFErrorCopyDescription($0.takeRetainedValue()) as String
    } ?? "unknown font error"
    fatalError("font registration failed: \(description)")
}

guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: Int(canvasWidth),
    pixelsHigh: Int(canvasHeight),
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
), let graphics = NSGraphicsContext(bitmapImageRep: bitmap) else {
    fatalError("unable to create bitmap context")
}

func hex(_ value: String, alpha: CGFloat = 1) -> NSColor {
    let clean = value.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
    guard clean.count == 6, let rgb = Int(clean, radix: 16) else {
        fatalError("invalid color \(value)")
    }
    return NSColor(
        calibratedRed: CGFloat((rgb >> 16) & 0xff) / 255,
        green: CGFloat((rgb >> 8) & 0xff) / 255,
        blue: CGFloat(rgb & 0xff) / 255,
        alpha: alpha
    )
}

func rect(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat) -> NSRect {
    NSRect(x: x, y: canvasHeight - y - height, width: width, height: height)
}

func fillRect(_ frame: NSRect, color: NSColor) {
    color.setFill()
    NSBezierPath(rect: frame).fill()
}

func fillRounded(_ frame: NSRect, radius: CGFloat, color: NSColor) {
    color.setFill()
    NSBezierPath(roundedRect: frame, xRadius: radius, yRadius: radius).fill()
}

func inter(_ size: CGFloat, bold: Bool = false) -> NSFont {
    let names = ["Inter", "Inter-Regular", "InterVariable"]
    let base = names.compactMap { NSFont(name: $0, size: size) }.first
        ?? NSFont.systemFont(ofSize: size)
    return bold ? NSFontManager.shared.convert(base, toHaveTrait: .boldFontMask) : base
}

func textAttributes(
    size: CGFloat,
    bold: Bool,
    color: NSColor,
    lineHeight: CGFloat = 1,
    alignment: NSTextAlignment = .left,
    kern: CGFloat = 0
) -> [NSAttributedString.Key: Any] {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = alignment
    paragraph.minimumLineHeight = size * lineHeight
    paragraph.maximumLineHeight = size * lineHeight
    paragraph.lineBreakMode = .byWordWrapping
    return [
        .font: inter(size, bold: bold),
        .foregroundColor: color,
        .paragraphStyle: paragraph,
        .kern: kern
    ]
}

func drawText(
    _ value: String,
    x: CGFloat,
    y: CGFloat,
    width: CGFloat,
    height: CGFloat,
    size: CGFloat,
    bold: Bool,
    color: NSColor,
    lineHeight: CGFloat = 1,
    alignment: NSTextAlignment = .left,
    kern: CGFloat = 0,
    verticalBottom: Bool = false
) {
    let attributes = textAttributes(
        size: size,
        bold: bold,
        color: color,
        lineHeight: lineHeight,
        alignment: alignment,
        kern: kern
    )
    var top = y
    if verticalBottom {
        let measured = (value as NSString).boundingRect(
            with: NSSize(width: width, height: height),
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: attributes
        )
        top = y + max(0, height - ceil(measured.height))
    }
    (value as NSString).draw(
        with: rect(x, top, width, height - (top - y)),
        options: [.usesLineFragmentOrigin, .usesFontLeading],
        attributes: attributes
    )
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = graphics
graphics.imageInterpolation = .high

let dark = hex("#0C0E12")
let ink = hex("#181C25")
let light = hex("#F4F6FA")
let accent = hex("#43BDD3")

fillRect(rect(0, 0, 1080, 1080), color: light)

guard let media = NSImage(contentsOf: mediaURL) else {
    fatalError("unable to load generated still life")
}
media.draw(
    in: rect(0, 0, 1080, 1080),
    from: NSRect(origin: .zero, size: media.size),
    operation: .sourceOver,
    fraction: 1,
    respectFlipped: false,
    hints: [.interpolation: NSImageInterpolation.high]
)

// Exact 58%-wide readability scrim: nearly opaque at the left edge and
// progressively transparent toward the physical return loop.
let scrimWidth = 626
for column in 0..<scrimWidth {
    let progress = CGFloat(column) / CGFloat(scrimWidth - 1)
    let alpha = 0.94 - (0.74 * progress)
    fillRect(rect(CGFloat(column), 0, 1, 1080), color: hex("#F4F6FA", alpha: alpha))
}

guard let logo = NSImage(contentsOf: logoURL) else {
    fatalError("unable to load Natal logo")
}
logo.draw(
    in: rect(65, 70, 191, 65),
    from: NSRect(origin: .zero, size: logo.size),
    operation: .sourceOver,
    fraction: 1,
    respectFlipped: false,
    hints: [.interpolation: NSImageInterpolation.high]
)

drawText(
    headline,
    x: 65, y: 216, width: 518, height: 259,
    size: 66, bold: true, color: dark,
    lineHeight: 0.98, kern: -1.8, verticalBottom: true
)

drawText(
    primary,
    x: 70, y: 529, width: 432, height: 162,
    size: 27, bold: false, color: ink,
    lineHeight: 1.13, kern: -0.3
)

fillRounded(rect(65, 745, 432, 86), radius: 14, color: dark)
drawText(
    offer,
    x: 81, y: 771, width: 400, height: 35,
    size: 27, bold: true, color: light,
    lineHeight: 1, kern: -0.5
)

fillRounded(rect(65, 886, 410, 97), radius: 16, color: accent)
drawText(
    cta,
    x: 76, y: 922, width: 388, height: 32,
    size: 24, bold: true, color: dark,
    lineHeight: 1, alignment: .center, kern: -0.4
)

graphics.flushGraphics()
NSGraphicsContext.restoreGraphicsState()

guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("unable to encode PNG")
}
try png.write(to: outputURL, options: .atomic)
