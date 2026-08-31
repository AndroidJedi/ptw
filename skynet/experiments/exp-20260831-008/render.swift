import AppKit
import CoreText
import Foundation

let finalWidth: CGFloat = 1080
let finalHeight: CGFloat = 1080
let assetWidth: CGFloat = 540
let assetHeight: CGFloat = 1000

guard CommandLine.arguments.count == 3 else {
    fatalError("usage: render.swift ASSET_PNG OUTPUT_PNG")
}

let assetOutputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let finalOutputURL = URL(fileURLWithPath: CommandLine.arguments[2])
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

func topRect(
    _ x: CGFloat,
    _ y: CGFloat,
    _ width: CGFloat,
    _ height: CGFloat,
    canvasHeight: CGFloat
) -> NSRect {
    NSRect(x: x, y: canvasHeight - y - height, width: width, height: height)
}

func topPoint(_ x: CGFloat, _ y: CGFloat, canvasHeight: CGFloat) -> NSPoint {
    NSPoint(x: x, y: canvasHeight - y)
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
    vertical: String = "top"
) {
    let attributes = textAttributes(
        size: size,
        bold: bold,
        color: color,
        lineHeight: lineHeight,
        alignment: alignment,
        kern: kern
    )
    let measured = (value as NSString).boundingRect(
        with: NSSize(width: width, height: height),
        options: [.usesLineFragmentOrigin, .usesFontLeading],
        attributes: attributes
    )
    let measuredHeight = min(height, ceil(measured.height))
    let top: CGFloat
    switch vertical {
    case "bottom":
        top = y + max(0, height - measuredHeight)
    case "center":
        top = y + max(0, (height - measuredHeight) / 2)
    default:
        top = y
    }
    (value as NSString).draw(
        with: topRect(x, top, width, height - (top - y), canvasHeight: finalHeight),
        options: [.usesLineFragmentOrigin, .usesFontLeading],
        attributes: attributes
    )
}

func makeBitmap(width: CGFloat, height: CGFloat) -> (NSBitmapImageRep, NSGraphicsContext) {
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: Int(width),
        pixelsHigh: Int(height),
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
    return (bitmap, graphics)
}

func writePNG(_ bitmap: NSBitmapImageRep, to outputURL: URL) {
    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        fatalError("unable to encode PNG")
    }
    do {
        try png.write(to: outputURL, options: .atomic)
    } catch {
        fatalError("unable to write PNG: \(error)")
    }
}

func drawSignalArc(centerX: CGFloat, centerY: CGFloat, radius: CGFloat, alpha: CGFloat) {
    let arc = NSBezierPath()
    arc.appendArc(
        withCenter: topPoint(centerX, centerY, canvasHeight: assetHeight),
        radius: radius,
        startAngle: 205,
        endAngle: 335
    )
    arc.lineWidth = 3
    arc.lineCapStyle = .round
    hex("#657787", alpha: alpha).setStroke()
    arc.stroke()
}

func renderAsset() {
    let (bitmap, graphics) = makeBitmap(width: assetWidth, height: assetHeight)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = graphics
    graphics.imageInterpolation = .high

    let assetBounds = NSRect(x: 0, y: 0, width: assetWidth, height: assetHeight)
    guard let gradient = NSGradient(
        starting: hex("#EEF3F5"),
        ending: hex("#C5D0D6")
    ) else {
        fatalError("unable to create asset gradient")
    }
    gradient.draw(in: assetBounds, angle: -90)

    for x in stride(from: CGFloat(24), through: CGFloat(528), by: 42) {
        fillRect(
            topRect(x, 0, 1, assetHeight, canvasHeight: assetHeight),
            color: hex("#0C0E12", alpha: 0.035)
        )
    }
    for y in stride(from: CGFloat(24), through: CGFloat(984), by: 42) {
        fillRect(
            topRect(0, y, assetWidth, 1, canvasHeight: assetHeight),
            color: hex("#0C0E12", alpha: 0.035)
        )
    }

    let mutedNodes: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [
        (72, 102, 17, 0.42), (156, 78, 12, 0.26), (256, 116, 22, 0.38),
        (378, 72, 15, 0.30), (472, 132, 19, 0.40), (112, 212, 24, 0.35),
        (214, 188, 14, 0.28), (330, 230, 18, 0.42), (442, 210, 11, 0.30),
        (66, 318, 13, 0.30), (170, 294, 19, 0.42), (286, 338, 12, 0.28),
        (420, 304, 24, 0.36), (492, 366, 13, 0.32)
    ]
    for (x, y, radius, alpha) in mutedNodes {
        fillRounded(
            topRect(x - radius, y - radius, radius * 2, radius * 2, canvasHeight: assetHeight),
            radius: radius,
            color: hex("#405260", alpha: alpha)
        )
        drawSignalArc(centerX: x, centerY: y, radius: radius + 13, alpha: alpha * 0.55)
    }

    let noisyLinks: [((CGFloat, CGFloat), (CGFloat, CGFloat))] = [
        ((72, 102), (156, 78)), ((156, 78), (256, 116)), ((256, 116), (378, 72)),
        ((112, 212), (214, 188)), ((214, 188), (330, 230)), ((330, 230), (442, 210)),
        ((66, 318), (170, 294)), ((170, 294), (286, 338)), ((286, 338), (420, 304))
    ]
    for link in noisyLinks {
        let path = NSBezierPath()
        path.move(to: topPoint(link.0.0, link.0.1, canvasHeight: assetHeight))
        path.line(to: topPoint(link.1.0, link.1.1, canvasHeight: assetHeight))
        path.lineWidth = 2
        path.lineCapStyle = .round
        hex("#405260", alpha: 0.17).setStroke()
        path.stroke()
    }

    fillRounded(
        topRect(232, 408, 76, 76, canvasHeight: assetHeight),
        radius: 38,
        color: hex("#43BDD3")
    )
    fillRounded(
        topRect(254, 430, 32, 32, canvasHeight: assetHeight),
        radius: 16,
        color: hex("#0C0E12")
    )

    let route = NSBezierPath()
    route.move(to: topPoint(270, 484, canvasHeight: assetHeight))
    route.curve(
        to: topPoint(348, 650, canvasHeight: assetHeight),
        controlPoint1: topPoint(270, 560, canvasHeight: assetHeight),
        controlPoint2: topPoint(348, 558, canvasHeight: assetHeight)
    )
    route.curve(
        to: topPoint(270, 914, canvasHeight: assetHeight),
        controlPoint1: topPoint(486, 712, canvasHeight: assetHeight),
        controlPoint2: topPoint(474, 914, canvasHeight: assetHeight)
    )
    route.curve(
        to: topPoint(116, 810, canvasHeight: assetHeight),
        controlPoint1: topPoint(186, 914, canvasHeight: assetHeight),
        controlPoint2: topPoint(116, 874, canvasHeight: assetHeight)
    )
    route.lineWidth = 18
    route.lineCapStyle = .round
    route.lineJoinStyle = .round
    hex("#43BDD3").setStroke()
    route.stroke()

    fillRounded(
        topRect(108, 626, 316, 244, canvasHeight: assetHeight),
        radius: 30,
        color: hex("#F4F6FA", alpha: 0.96)
    )
    strokeRounded(
        topRect(108.5, 626.5, 315, 243, canvasHeight: assetHeight),
        radius: 30,
        color: hex("#181C25", alpha: 0.26),
        width: 2
    )
    fillRounded(
        topRect(108, 626, 316, 58, canvasHeight: assetHeight),
        radius: 30,
        color: hex("#181C25")
    )
    fillRect(
        topRect(108, 656, 316, 28, canvasHeight: assetHeight),
        color: hex("#181C25")
    )

    for x in [172 as CGFloat, 360 as CGFloat] {
        fillRounded(
            topRect(x, 600, 22, 56, canvasHeight: assetHeight),
            radius: 11,
            color: hex("#43BDD3")
        )
        fillRounded(
            topRect(x + 5, 608, 12, 38, canvasHeight: assetHeight),
            radius: 6,
            color: hex("#0C0E12")
        )
    }

    let cellXs = [136 as CGFloat, 226 as CGFloat, 316 as CGFloat]
    let cellYs = [716 as CGFloat, 790 as CGFloat]
    for y in cellYs {
        for x in cellXs {
            fillRounded(
                topRect(x, y, 64, 46, canvasHeight: assetHeight),
                radius: 9,
                color: hex("#A3ADBD", alpha: 0.23)
            )
        }
    }
    fillRounded(
        topRect(316, 790, 64, 46, canvasHeight: assetHeight),
        radius: 9,
        color: hex("#43BDD3")
    )

    let arrow = NSBezierPath()
    arrow.move(to: topPoint(105, 798, canvasHeight: assetHeight))
    arrow.line(to: topPoint(84, 834, canvasHeight: assetHeight))
    arrow.line(to: topPoint(126, 832, canvasHeight: assetHeight))
    arrow.close()
    hex("#43BDD3").setFill()
    arrow.fill()

    fillRounded(
        topRect(446, 888, 38, 38, canvasHeight: assetHeight),
        radius: 19,
        color: hex("#181C25", alpha: 0.76)
    )
    fillRounded(
        topRect(459, 901, 12, 12, canvasHeight: assetHeight),
        radius: 6,
        color: hex("#43BDD3")
    )

    graphics.flushGraphics()
    NSGraphicsContext.restoreGraphicsState()
    writePNG(bitmap, to: assetOutputURL)
}

func renderFinal() {
    let (bitmap, graphics) = makeBitmap(width: finalWidth, height: finalHeight)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = graphics
    graphics.imageInterpolation = .high

    let dark = hex("#0C0E12")
    let light = hex("#F4F6FA")
    let muted = hex("#A3ADBD")
    let accent = hex("#43BDD3")
    let accentSoft = hex("#87D0DD")

    fillRect(topRect(0, 0, 1080, 1080, canvasHeight: finalHeight), color: light)
    fillRect(topRect(0, 0, 572, 1080, canvasHeight: finalHeight), color: hex("#0C0E12", alpha: 0.94))

    guard let asset = NSImage(contentsOf: assetOutputURL) else {
        fatalError("unable to load deterministic route asset")
    }
    let heroFrame = topRect(575, 0, 497, 998, canvasHeight: finalHeight)
    NSGraphicsContext.saveGraphicsState()
    NSBezierPath(roundedRect: heroFrame, xRadius: 36, yRadius: 36).addClip()
    asset.draw(
        in: heroFrame,
        from: NSRect(origin: .zero, size: asset.size),
        operation: .sourceOver,
        fraction: 0.88,
        respectFlipped: false,
        hints: [.interpolation: NSImageInterpolation.high]
    )
    NSGraphicsContext.restoreGraphicsState()

    fillRect(topRect(556, 0, 23, 1080, canvasHeight: finalHeight), color: hex("#43BDD3", alpha: 0.91))

    drawText(
        "НЕ ВСІМ.\nТИМ, ХТО\nОХОЛОВ.",
        x: 65, y: 194, width: 421, height: 216,
        size: 58, bold: true, color: light, lineHeight: 0.98, kern: -1.2, vertical: "bottom"
    )
    drawText(
        "Після візиту Natal оновлює статус.\nДля клієнта в «Ризику» запускайте\nнагадування, пропозицію або повторний запис.",
        x: 65, y: 454, width: 421, height: 140,
        size: 22, bold: false, color: light, lineHeight: 1.1
    )
    drawText(
        "90 ДНІВ БЕЗКОШТОВНО",
        x: 65, y: 691, width: 421, height: 76,
        size: 25, bold: true, color: accentSoft, vertical: "center"
    )

    fillRounded(topRect(65, 853, 367, 97, canvasHeight: finalHeight), radius: 12, color: accent)
    drawText(
        "СПРОБУВАТИ NATAL",
        x: 76, y: 869, width: 346, height: 65,
        size: 23, bold: true, color: dark, alignment: .center, vertical: "center"
    )

    fillRounded(topRect(49, 43, 270, 97, canvasHeight: finalHeight), radius: 16, color: hex("#F4F6FA", alpha: 0.94))
    guard let logo = NSImage(contentsOf: logoURL) else {
        fatalError("unable to load Natal logo")
    }
    logo.draw(
        in: topRect(65, 65, 238, 54, canvasHeight: finalHeight),
        from: NSRect(origin: .zero, size: logo.size),
        operation: .sourceOver,
        fraction: 1,
        respectFlipped: false,
        hints: [.interpolation: NSImageInterpolation.high]
    )

    fillRounded(topRect(734, 76, 259, 81, canvasHeight: finalHeight), radius: 16, color: hex("#0C0E12", alpha: 0.88))
    drawText(
        "↗",
        x: 745, y: 86, width: 238, height: 59,
        size: 18, bold: true, color: light, alignment: .center, vertical: "center"
    )

    fillRounded(topRect(500, 1019, 9, 9, canvasHeight: finalHeight), radius: 4.5, color: muted)
    fillRounded(topRect(521, 1019, 9, 9, canvasHeight: finalHeight), radius: 4.5, color: accent)

    graphics.flushGraphics()
    NSGraphicsContext.restoreGraphicsState()
    writePNG(bitmap, to: finalOutputURL)
}

renderAsset()
renderFinal()
