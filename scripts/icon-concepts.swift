// Icon concepts for the Maine app (2026-10-08), flat (no gloss, no gradients), drawn in code, food only, no text.
// A: lobster roll in a split-top bun with a claw on top · B: whoopie pie · C: a whole cooked lobster.
// (A red snapper hot dog was left out: Chicago's icon is a hot dog, and each state app must look like its own.)
// Ground: deep ocean teal with one low, lighter wave (Nick, 2026-10-08: "ocean vibes", "cozy").
// Usage: swift scripts/icon-concepts.swift   (run from me-eats/) -> playbook/brand/concepts.png and concept-<x>-1024.png
import AppKit
import CoreGraphics

let root = FileManager.default.currentDirectoryPath
func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: a)
}
let ocean = rgb(0x0E4D5C), ocean2 = rgb(0x1B6673), white = rgb(0xFFFFFF), ink = rgb(0x10262E)
let red = rgb(0xD8402A), red2 = rgb(0xB02E1E)

func canvas(_ w: Int, _ h: Int, _ draw: (CGContext) -> Void) -> CGImage {
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.setShouldAntialias(true); ctx.interpolationQuality = .high
    draw(ctx)
    return ctx.makeImage()!
}
func save(_ img: CGImage, _ path: String) {
    let url = URL(fileURLWithPath: root + "/" + path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try! NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])!.write(to: url)
    print("wrote", path)
}
func P(_ s: CGFloat, _ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * s, y: y * s) }
func R(_ s: CGFloat, _ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> CGRect { CGRect(x: x * s, y: y * s, width: w * s, height: h * s) }
func ellipse(_ c: CGContext, _ s: CGFloat, _ cx: CGFloat, _ cy: CGFloat, _ rx: CGFloat, _ ry: CGFloat, _ col: CGColor) {
    c.setFillColor(col); c.fillEllipse(in: R(s, cx - rx, cy - ry, 2 * rx, 2 * ry))
}

/// The ground: deep ocean teal with one low, lighter wave along the bottom.
func ground(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(ocean); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    let w = CGMutablePath()
    w.move(to: P(s, 0, 0)); w.addLine(to: P(s, 0, 0.13))
    w.addCurve(to: P(s, 0.5, 0.13), control1: P(s, 0.16, 0.20), control2: P(s, 0.34, 0.20))
    w.addCurve(to: P(s, 1.0, 0.13), control1: P(s, 0.66, 0.06), control2: P(s, 0.84, 0.06))
    w.addLine(to: P(s, 1, 0)); w.closeSubpath()
    c.setFillColor(ocean2); c.addPath(w); c.fillPath()
}

/// One cooked claw in local units: palm along +x from the origin, two pincers at the end with a gap between them.
func claw(_ c: CGContext, at x: CGFloat, _ y: CGFloat, angle: CGFloat, scale k: CGFloat, _ s: CGFloat) {
    c.saveGState()
    c.translateBy(x: x * s, y: y * s); c.rotate(by: angle); c.scaleBy(x: k * s, y: k * s)
    c.setFillColor(red); c.fillEllipse(in: CGRect(x: -0.05, y: -0.22, width: 0.66, height: 0.44))   // the palm
    let upper = CGMutablePath()   // the moving finger
    upper.move(to: CGPoint(x: 0.36, y: 0.20)); upper.addCurve(to: CGPoint(x: 1.02, y: 0.07), control1: CGPoint(x: 0.62, y: 0.32), control2: CGPoint(x: 0.94, y: 0.24))
    upper.addCurve(to: CGPoint(x: 0.50, y: 0.025), control1: CGPoint(x: 0.88, y: 0.05), control2: CGPoint(x: 0.66, y: 0.02)); upper.closeSubpath()
    let lower = CGMutablePath()   // the fixed finger
    lower.move(to: CGPoint(x: 0.36, y: -0.20)); lower.addCurve(to: CGPoint(x: 0.96, y: -0.07), control1: CGPoint(x: 0.60, y: -0.30), control2: CGPoint(x: 0.90, y: -0.22))
    lower.addCurve(to: CGPoint(x: 0.50, y: -0.045), control1: CGPoint(x: 0.84, y: -0.08), control2: CGPoint(x: 0.64, y: -0.05)); lower.closeSubpath()
    c.setFillColor(red); c.addPath(upper); c.fillPath(); c.addPath(lower); c.fillPath()
    c.setFillColor(red2)   // a few bumps on the shell, one tone darker
    for (bx, by, r) in [(0.18, 0.08, 0.035), (0.30, -0.06, 0.03), (0.08, -0.07, 0.028)] as [(CGFloat, CGFloat, CGFloat)] {
        c.fillEllipse(in: CGRect(x: bx - r, y: by - r, width: 2 * r, height: 2 * r))
    }
    c.restoreGState()
}

/// A: a New England split-top bun, toasted flat side out, heaped with lobster meat, a little lettuce, and one claw on top.
func roll(_ c: CGContext, _ s: CGFloat) {
    let bun = rgb(0xF0C47E), toast = rgb(0xD38B39), lettuce = rgb(0x7DB548), meat = rgb(0xF8E0D0), meatRed = rgb(0xE0533A), meatRed2 = rgb(0xC9422C)
    // the bun: a rounded block with a toasted flat side
    c.setFillColor(bun); c.addPath(CGPath(roundedRect: R(s, 0.08, 0.20, 0.84, 0.30), cornerWidth: 0.11 * s, cornerHeight: 0.11 * s, transform: nil)); c.fillPath()
    c.setFillColor(toast); c.addPath(CGPath(roundedRect: R(s, 0.14, 0.25, 0.72, 0.20), cornerWidth: 0.07 * s, cornerHeight: 0.07 * s, transform: nil)); c.fillPath()
    // lettuce peeking over the bun's top edge
    let l = CGMutablePath(); l.move(to: P(s, 0.12, 0.48))
    for i in 0..<10 { let x = 0.12 + CGFloat(i) * 0.076; l.addQuadCurve(to: P(s, x + 0.076, 0.48), control: P(s, x + 0.038, 0.55)) }
    l.addLine(to: P(s, 0.88, 0.46)); l.addLine(to: P(s, 0.12, 0.46)); l.closeSubpath()
    c.setFillColor(lettuce); c.addPath(l); c.fillPath()
    // the meat: one heap of chunks, red outside with pale meat showing underneath
    let chunks: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [(0.22, 0.54, 0.10, 0.07), (0.37, 0.58, 0.11, 0.08), (0.53, 0.585, 0.11, 0.08), (0.68, 0.565, 0.10, 0.075),
                                                          (0.80, 0.535, 0.075, 0.055), (0.30, 0.51, 0.09, 0.05), (0.62, 0.515, 0.10, 0.05)]
    for (cx, cy, rx, ry) in chunks { ellipse(c, s, cx, cy - 0.012, rx, ry, meat) }
    for (i, (cx, cy, rx, ry)) in chunks.enumerated() { ellipse(c, s, cx, cy + 0.008, rx * 0.94, ry * 0.86, i % 3 == 1 ? meatRed2 : meatRed) }
    claw(c, at: 0.34, 0.60, angle: 0.50, scale: 0.46, s)   // the claw on top, pointing up and right
}

/// B: a whoopie pie from the side: two dark chocolate domes and a thick, scalloped white filling.
func whoopie(_ c: CGContext, _ s: CGFloat) {
    let cake = rgb(0x4B2A1D), cake2 = rgb(0x3A1F15), crack = rgb(0x6E4130), cream = rgb(0xFFF7EA)
    // bottom cake: flat top, rounded underside
    let bot = CGMutablePath(); bot.move(to: P(s, 0.13, 0.43))
    bot.addCurve(to: P(s, 0.87, 0.43), control1: P(s, 0.15, 0.19), control2: P(s, 0.85, 0.19)); bot.closeSubpath()
    c.setFillColor(cake2); c.addPath(bot); c.fillPath()
    // filling: a band wider than the cakes, with a scalloped edge on both sides
    let f = CGMutablePath(); f.move(to: P(s, 0.11, 0.41))
    for i in 0..<9 { let x = 0.11 + CGFloat(i) * 0.0867; f.addQuadCurve(to: P(s, x + 0.0867, 0.41), control: P(s, x + 0.0433, 0.37)) }
    f.addLine(to: P(s, 0.89, 0.55))
    for i in 0..<9 { let x = 0.89 - CGFloat(i) * 0.0867; f.addQuadCurve(to: P(s, x - 0.0867, 0.55), control: P(s, x - 0.0433, 0.59)) }
    f.closeSubpath()
    c.setFillColor(cream); c.addPath(f); c.fillPath()
    // top cake: a dome
    let top = CGMutablePath(); top.move(to: P(s, 0.12, 0.54))
    top.addCurve(to: P(s, 0.88, 0.54), control1: P(s, 0.14, 0.88), control2: P(s, 0.86, 0.88)); top.closeSubpath()
    c.setFillColor(cake); c.addPath(top); c.fillPath()
    // a few crackles on the dome
    c.setStrokeColor(crack); c.setLineWidth(0.018 * s); c.setLineCap(.round)
    for (a, b, d) in [((0.33, 0.70), (0.42, 0.73), (0.47, 0.69)), ((0.55, 0.75), (0.62, 0.72), (0.68, 0.74)), ((0.40, 0.62), (0.50, 0.64), (0.58, 0.61))] as [((CGFloat, CGFloat), (CGFloat, CGFloat), (CGFloat, CGFloat))] {
        c.move(to: P(s, a.0, a.1)); c.addLine(to: P(s, b.0, b.1)); c.addLine(to: P(s, d.0, d.1)); c.strokePath()
    }
}

/// C: a whole cooked lobster from above: big claws up in a V, the body, a segmented tail and its fan.
func lobster(_ c: CGContext, _ s: CGFloat) {
    let dark = red2
    // antennae
    c.setStrokeColor(red); c.setLineWidth(0.016 * s); c.setLineCap(.round)
    c.move(to: P(s, 0.47, 0.68)); c.addCurve(to: P(s, 0.40, 0.92), control1: P(s, 0.44, 0.80), control2: P(s, 0.40, 0.86)); c.strokePath()
    c.move(to: P(s, 0.53, 0.68)); c.addCurve(to: P(s, 0.60, 0.92), control1: P(s, 0.56, 0.80), control2: P(s, 0.60, 0.86)); c.strokePath()
    // walking legs
    c.setLineWidth(0.02 * s)
    for (i, y) in [0.56, 0.51, 0.46].enumerated() {
        let dx = 0.13 + CGFloat(i) * 0.01
        c.move(to: P(s, 0.45, y)); c.addLine(to: P(s, 0.45 - dx, y - 0.05)); c.strokePath()
        c.move(to: P(s, 0.55, y)); c.addLine(to: P(s, 0.55 + dx, y - 0.05)); c.strokePath()
    }
    // arms to the claws
    c.setLineWidth(0.05 * s)
    c.move(to: P(s, 0.46, 0.62)); c.addLine(to: P(s, 0.33, 0.64)); c.addLine(to: P(s, 0.28, 0.68)); c.strokePath()
    c.move(to: P(s, 0.54, 0.62)); c.addLine(to: P(s, 0.67, 0.64)); c.addLine(to: P(s, 0.72, 0.68)); c.strokePath()
    claw(c, at: 0.27, 0.66, angle: 1.75, scale: 0.27, s)                                            // left claw, pointing up
    c.saveGState(); c.translateBy(x: s, y: 0); c.scaleBy(x: -1, y: 1)
    claw(c, at: 0.27, 0.66, angle: 1.75, scale: 0.27, s)                                            // right claw, mirrored
    c.restoreGState()
    // tail: segments narrowing down, then the fan
    for (i, y) in [0.39, 0.33, 0.27, 0.21].enumerated() {
        let w = 0.11 - CGFloat(i) * 0.012
        c.setFillColor(i % 2 == 0 ? red : dark)
        c.addPath(CGPath(roundedRect: R(s, 0.5 - w, y - 0.035, 2 * w, 0.07), cornerWidth: 0.03 * s, cornerHeight: 0.03 * s, transform: nil)); c.fillPath()
    }
    c.setFillColor(red)
    for (dx, rot) in [(-0.075, 0.45), (0.0, 0.0), (0.075, -0.45)] as [(CGFloat, CGFloat)] {
        c.saveGState(); c.translateBy(x: (0.5 + dx) * s, y: 0.15 * s); c.rotate(by: rot)
        c.fillEllipse(in: CGRect(x: -0.04 * s, y: -0.075 * s, width: 0.08 * s, height: 0.12 * s)); c.restoreGState()
    }
    // the body (carapace) over the joints, with eyes
    ellipse(c, s, 0.5, 0.53, 0.105, 0.16, red)
    c.setStrokeColor(dark); c.setLineWidth(0.014 * s)
    c.move(to: P(s, 0.415, 0.55)); c.addQuadCurve(to: P(s, 0.585, 0.55), control: P(s, 0.5, 0.50)); c.strokePath()
    ellipse(c, s, 0.465, 0.665, 0.016, 0.016, rgb(0x1A1A1A)); ellipse(c, s, 0.535, 0.665, 0.016, 0.016, rgb(0x1A1A1A))
}

let concepts: [(String, String, (CGContext, CGFloat) -> Void)] = [("a", "A · Lobster roll with a claw", roll), ("b", "B · Whoopie pie", whoopie), ("c", "C · Whole lobster", lobster)]
func icon(_ size: Int, _ f: (CGContext, CGFloat) -> Void) -> CGImage {
    canvas(size, size) { c in let s = CGFloat(size); ground(c, s); f(c, s) }
}
let sheet = canvas(1060, 3 * 600 + 40) { c in
    c.setFillColor(rgb(0xFBF6EC)); c.fill(CGRect(x: 0, y: 0, width: 1060, height: 3 * 600 + 40))
    for (i, (_, label, f)) in concepts.enumerated() {
        let y0 = CGFloat(3 * 600 + 40 - (i + 1) * 600)
        let mask = CGPath(roundedRect: CGRect(x: 0, y: 0, width: 1, height: 1), cornerWidth: 0.225, cornerHeight: 0.225, transform: nil)
        for (sz, x) in [(512, 40), (180, 600), (60, 840)] {
            let img = icon(sz, f)
            c.saveGState()
            var t = CGAffineTransform(scaleX: CGFloat(sz), y: CGFloat(sz)).translatedBy(x: CGFloat(x) / CGFloat(sz), y: (y0 + 40) / CGFloat(sz))
            c.addPath(mask.copy(using: &t)!); c.clip()
            c.draw(img, in: CGRect(x: CGFloat(x), y: y0 + 40, width: CGFloat(sz), height: CGFloat(sz)))
            c.restoreGState()
        }
        let attr = NSAttributedString(string: label, attributes: [.font: NSFont.systemFont(ofSize: 30, weight: .bold), .foregroundColor: NSColor(cgColor: ink)!])
        c.textPosition = CGPoint(x: 600, y: y0 + 470); CTLineDraw(CTLineCreateWithAttributedString(attr), c)
        let sub = NSAttributedString(string: "512 · 180 · 60 px", attributes: [.font: NSFont.systemFont(ofSize: 22, weight: .regular), .foregroundColor: NSColor(cgColor: ink)!])
        c.textPosition = CGPoint(x: 600, y: y0 + 432); CTLineDraw(CTLineCreateWithAttributedString(sub), c)
    }
}
save(sheet, "playbook/brand/concepts.png")
for (k, _, f) in concepts { save(icon(1024, f), "playbook/brand/concept-\(k)-1024.png") }
