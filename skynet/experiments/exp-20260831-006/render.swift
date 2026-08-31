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
let fontURL = skynetRoot.appendingPathComponent("assets/natal/inter.ttf")
let logoURL = skynetRoot.appendingPathComponent("assets/natal/logo-natal.png")

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

func strokeRounded(_ frame: NSRect, radius: CGFloat, color: NSColor, width: CGFloat) {
    color.setStroke()
    let path = NSBezierPath(roundedRect: frame, xRadius: radius, yRadius: radius)
    path.lineWidth = width
    path.stroke()
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
    lineHeight: CGFloat = 1.0,
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
    lineHeight: CGFloat = 1.0,
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
let muted = hex("#A3ADBD")
let accent = hex("#43BDD3")
let accentSoft = hex("#87D0DD")

fillRect(rect(0, 0, 1080, 1080), color: light)
fillRounded(rect(54, 76, 454, 562), radius: 28, color: ink)

let heroFrame = rect(76, 97, 410, 456)
NSGraphicsContext.saveGraphicsState()
NSBezierPath(roundedRect: heroFrame, xRadius: 22, yRadius: 22).addClip()
graphics.cgContext.setAlpha(0.84)
fillRounded(heroFrame, radius: 22, color: dark)
for position in stride(from: CGFloat(108), through: CGFloat(544), by: 32) {
    fillRect(rect(76, position, 410, 1), color: hex("#87D0DD", alpha: 0.08))
}
for position in stride(from: CGFloat(76), through: CGFloat(486), by: 32) {
    fillRect(rect(position, 97, 1, 456), color: hex("#87D0DD", alpha: 0.08))
}

drawText("СТАТУС ПІСЛЯ ВІЗИТУ", x: 106, y: 127, width: 350, height: 22, size: 16, bold: true, color: muted, kern: 2.4)

let statusRows: [(String, CGFloat, CGFloat, Bool)] = [
    ("АКТИВНИЙ", 173, 55, false),
    ("РИЗИК", 239, 66, true),
    ("ВІДТІК", 316, 55, false)
]
for (label, top, height, isRisk) in statusRows {
    let rowFrame = rect(106, top, 350, height)
    if isRisk {
        fillRounded(rowFrame, radius: 13, color: accent)
    } else {
        fillRounded(rowFrame, radius: 13, color: hex("#F4F6FA", alpha: 0.035))
        strokeRounded(rowFrame.insetBy(dx: 0.5, dy: 0.5), radius: 13, color: hex("#A3ADBD", alpha: 0.24), width: 1)
    }
    fillRounded(rect(123, top + (height - 10) / 2, 10, 10), radius: 5, color: isRisk ? dark : hex("#A3ADBD", alpha: 0.5))
    drawText(label, x: 146, y: top + (isRisk ? 19 : 17), width: 180, height: 28, size: isRisk ? 22 : 18, bold: true, color: isRisk ? dark : muted, kern: 0.8)
    if isRisk {
        fillRounded(rect(381, top + 17, 58, 31), radius: 7, color: hex("#0C0E12", alpha: 0.16))
        drawText("ДІЯ", x: 386, y: top + 26, width: 48, height: 14, size: 11, bold: true, color: dark, alignment: .center, kern: 1.2)
    }
}

fillRect(rect(280, 382, 2, 22), color: accent)
let arrow = NSBezierPath()
arrow.move(to: NSPoint(x: 276, y: canvasHeight - 400))
arrow.line(to: NSPoint(x: 281, y: canvasHeight - 405))
arrow.line(to: NSPoint(x: 286, y: canvasHeight - 400))
accent.setStroke()
arrow.lineWidth = 2
arrow.stroke()
drawText("ДОРЕЧНИЙ СЦЕНАРІЙ", x: 106, y: 414, width: 350, height: 18, size: 12, bold: true, color: accentSoft, alignment: .center, kern: 1.5)

let actionFrames: [(String, CGFloat, CGFloat, CGFloat)] = [
    ("НАГАДУВАННЯ", 106, 442, 171),
    ("ПРОПОЗИЦІЯ", 285, 442, 171),
    ("ПОВТОРНИЙ ЗАПИС", 106, 484, 350)
]
for (label, x, top, width) in actionFrames {
    let actionFrame = rect(x, top, width, 34)
    strokeRounded(actionFrame.insetBy(dx: 0.5, dy: 0.5), radius: 9, color: hex("#87D0DD", alpha: 0.38), width: 1)
    drawText(label, x: x + 4, y: top + 10, width: width - 8, height: 16, size: 12, bold: true, color: light, alignment: .center)
}
NSGraphicsContext.restoreGraphicsState()

fillRounded(rect(521, 292, 497, 335), radius: 24, color: hex("#87D0DD", alpha: 0.22))
drawText(
    "Ризик видно\nдо порожнього\nкалендаря",
    x: 562, y: 97, width: 454, height: 162,
    size: 53, bold: true, color: dark, lineHeight: 1, kern: -1.7, verticalBottom: true
)
drawText(
    "Після кожного візиту Natal оновлює статус:\nАктивний, Ризик або Відтік.\n\nДля «Ризику» запускайте доречний\nсценарій повернення.",
    x: 572, y: 335, width: 410, height: 226,
    size: 21, bold: false, color: ink, lineHeight: 1.12
)

fillRounded(rect(562, 715, 42, 5), radius: 2.5, color: accent)
drawText("90 ДНІВ БЕЗКОШТОВНО", x: 619, y: 700, width: 375, height: 40, size: 25, bold: true, color: dark)

fillRounded(rect(562, 821, 410, 97), radius: 18, color: dark)
drawText("СПРОБУВАТИ NATAL", x: 572, y: 858, width: 389, height: 32, size: 23, bold: true, color: light, alignment: .center)

guard let logo = NSImage(contentsOf: logoURL) else {
    fatalError("unable to load Natal logo")
}
logo.draw(
    in: rect(76, 929, 238, 59),
    from: NSRect(origin: .zero, size: logo.size),
    operation: .sourceOver,
    fraction: 1,
    respectFlipped: false,
    hints: [.interpolation: NSImageInterpolation.high]
)

fillRounded(rect(38, 59, 59, 59), radius: 29.5, color: light)
fillRounded(rect(48, 69, 39, 39), radius: 19.5, color: hex("#43BDD3", alpha: 0.86))

graphics.flushGraphics()
NSGraphicsContext.restoreGraphicsState()

guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("unable to encode PNG")
}
try png.write(to: outputURL, options: .atomic)
