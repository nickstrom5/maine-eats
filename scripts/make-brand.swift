// Regenerates the brand images: the app icon (a lobster roll in a New England split-top bun with a red claw lying level on top, on
// flat deep ocean teal; Nick's pick, Oct 9, 2026: concept A of scripts/icon-concepts.swift, redrawn the same day in the shared Eats
// Ranked icon style he approved, ../state-prompts/ICON-STYLE.md: same food and colours, no wave, no tilt), docs/brand/, and the
// site's og.png, favicons and manifest icons.
// Usage: swift scripts/make-brand.swift   (run from me-eats/)
//        swift scripts/make-brand.swift og ["<tagline>"]   redraws docs/og.png only, never the icons. scripts/make-site.py runs
//        this whenever the restaurant or town count changes; without a tagline it reads og_line from playbook/site-numbers.json.
import AppKit
import CoreGraphics

let root = FileManager.default.currentDirectoryPath
func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: a)
}
let ocean = rgb(0x0E4D5C), white = rgb(0xFFFFFF), ink = rgb(0x10262E)

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

/// The lobster roll in an s x s box, CoreGraphics y-up. Paints nothing behind the food, so og.png can call it at another size.
func roll(_ c: CGContext, _ s: CGFloat) {
    let ocean = rgb(0x0E4D5C)    // the ground; also the 13 px separation rings round the claw's parts
    let toast = rgb(0xD38B39)    // the bun's buttered, griddled flat side (3.4:1 on the ground)
    let crust = rgb(0xF0C47E)    // the bun's soft top crust, the lighter top plane (1.8:1 above the toast)
    let red = rgb(0xD8402A)      // cooked shell: the claw and the outside of the meat
    let meat = rgb(0xF8E0D0)     // lobster meat, white inside
    let lettuce = rgb(0x7DB548)  // one thin line of lettuce between bun and meat
    func P(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * s, y: y * s) }
    let ring = 0.0254 * s        // a 26 px round-join stroke under a fill shows as a 13 px ring
    c.setLineCap(.round); c.setLineJoin(.round)

    // Bun: 0.72 x 0.24, flat bottom, soft rounded ends (bottom corners 97 px, top corners 77 px), top edge dipping 16 px.
    let x0: CGFloat = 0.14, x1: CGFloat = 0.86, y0: CGFloat = 0.22, y1: CGFloat = 0.46
    let low: CGFloat = 0.095, high: CGFloat = 0.075, dip: CGFloat = 0.016

    // Meat: five chunks heaped in the split, back pair first. Each is red all over with a white oval clipped inside it, dropped
    // by `cap` and nudged sideways by `lean`, so the red shows as a crescent wrapping one upper shoulder, like the outside of
    // a curled tail piece, and the white as the meat inside. The bun's near side hides their lower parts.
    let chunks: [(x: CGFloat, y: CGFloat, rx: CGFloat, ry: CGFloat, cap: CGFloat, lean: CGFloat)] = [
        (0.37, 0.555, 0.115, 0.075, 0.03, -0.03), (0.63, 0.555, 0.115, 0.075, 0.03, 0.03),
        (0.245, 0.50, 0.095, 0.072, 0.03, 0.045), (0.50, 0.51, 0.12, 0.075, 0.032, -0.03), (0.755, 0.50, 0.095, 0.072, 0.03, -0.045)]
    for k in chunks {
        let r = CGRect(x: (k.x - k.rx) * s, y: (k.y - k.ry) * s, width: 2 * k.rx * s, height: 2 * k.ry * s)
        c.setFillColor(red); c.fillEllipse(in: r)
        c.saveGState(); c.addEllipse(in: r); c.clip()
        c.setFillColor(meat); c.fillEllipse(in: r.offsetBy(dx: k.lean * s, dy: -k.cap * s).insetBy(dx: -0.02 * s, dy: 0))
        c.restoreGState()
    }

    // Lettuce: a 51 px round-cap line following the bun's top edge, showing about 25 px above it.
    let leaf = CGMutablePath()
    leaf.move(to: P(x0 + 0.05, y1 + 0.002))
    leaf.addQuadCurve(to: P(x1 - 0.05, y1 + 0.002), control: P(0.5, y1 + 0.002 - 2 * dip))
    c.setStrokeColor(lettuce); c.setLineWidth(0.05 * s); c.addPath(leaf); c.strokePath()

    // Bun: toast over the whole shape, then the crust as a top plane 0.06 deep whose lower edge follows the top edge's dip.
    let bun = CGMutablePath()
    bun.move(to: P(x0 + low, y0)); bun.addLine(to: P(x1 - low, y0))
    bun.addQuadCurve(to: P(x1, y0 + low), control: P(x1, y0)); bun.addLine(to: P(x1, y1 - high))
    bun.addQuadCurve(to: P(x1 - high, y1), control: P(x1, y1))
    bun.addQuadCurve(to: P(x0 + high, y1), control: P(0.5, y1 - 2 * dip))
    bun.addQuadCurve(to: P(x0, y1 - high), control: P(x0, y1)); bun.addLine(to: P(x0, y0 + low))
    bun.addQuadCurve(to: P(x0 + low, y0), control: P(x0, y0)); bun.closeSubpath()
    c.saveGState(); c.addPath(bun); c.clip()
    c.setFillColor(toast); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    let yb = y1 - 0.06
    let top = CGMutablePath()
    top.move(to: P(0, yb)); top.addLine(to: P(x0, yb))
    top.addQuadCurve(to: P(x1, yb), control: P(0.5, yb - 2.5 * dip))
    top.addLine(to: P(1, yb)); top.addLine(to: P(1, 1)); top.addLine(to: P(0, 1)); top.closeSubpath()
    c.setFillColor(crust); c.addPath(top); c.fillPath()
    c.restoreGState()

    // Claw: lying level on the heap, pincers to the right. Claw units: length 1 = 0.56 of the canvas, from the back of the
    // knuckle (x 0) to the tip of the moving finger; centre line y 0. Three red parts (knuckle, hand with its fixed finger,
    // moving finger) filled as one silhouette over one 13 px teal ring, so the claw stands off the red of the meat with no
    // lines inside it (like Chicago's dog): the knuckle shows as a pinch at the wrist and the hinge as a dip on top.
    // The fingers run from the crotch at 0.55 to the tips: the V opens to about 100 px at the tips.
    let L: CGFloat = 0.56, ox: CGFloat = 0.5 - L / 2, oy: CGFloat = 0.665
    func Q(_ x: CGFloat, _ y: CGFloat) -> CGPoint { P(ox + x * L, oy + y * L) }
    let knuckle = CGPath(ellipseIn: CGRect(x: (ox + 0.0 * L) * s, y: (oy - 0.095 * L) * s, width: 0.16 * L * s, height: 0.19 * L * s), transform: nil)
    let hand = CGMutablePath()   // the hand and its fixed finger, 0.38 units tall
    hand.move(to: Q(0.12, 0.08))
    hand.addCurve(to: Q(0.32, 0.185), control1: Q(0.16, 0.15), control2: Q(0.23, 0.185))     // wrist up to the top of the hand
    hand.addCurve(to: Q(0.51, 0.11), control1: Q(0.42, 0.185), control2: Q(0.48, 0.16))      // down to the hinge
    hand.addCurve(to: Q(0.55, 0.0), control1: Q(0.52, 0.07), control2: Q(0.53, 0.03))        // into the crotch
    hand.addCurve(to: Q(0.96, -0.03), control1: Q(0.70, -0.05), control2: Q(0.85, -0.07))     // inside of the fixed finger, to its tip
    hand.addCurve(to: Q(0.38, -0.19), control1: Q(0.88, -0.12), control2: Q(0.70, -0.19))     // underside of finger and hand
    hand.addCurve(to: Q(0.12, -0.08), control1: Q(0.24, -0.19), control2: Q(0.15, -0.15))
    hand.addCurve(to: Q(0.12, 0.08), control1: Q(0.105, -0.03), control2: Q(0.105, 0.03))    // the wrist
    hand.closeSubpath()
    let finger = CGMutablePath()   // the moving finger, hinged on top of the hand, lifted open and hooking down at the tip
    finger.move(to: Q(0.44, 0.15))
    finger.addCurve(to: Q(0.78, 0.26), control1: Q(0.52, 0.25), control2: Q(0.66, 0.28))
    finger.addCurve(to: Q(1.0, 0.145), control1: Q(0.87, 0.245), control2: Q(0.94, 0.215))
    finger.addCurve(to: Q(0.58, 0.05), control1: Q(0.92, 0.125), control2: Q(0.72, 0.09))      // its inside edge, back to the hinge
    finger.addCurve(to: Q(0.44, 0.15), control1: Q(0.51, 0.035), control2: Q(0.44, 0.09))
    finger.closeSubpath()
    let parts = [knuckle, hand, finger] as [CGPath]
    c.setLineWidth(ring); c.setStrokeColor(ocean)
    for part in parts { c.addPath(part) }
    c.strokePath()                                   // one ring round the whole claw, none between its parts
    c.setFillColor(red)
    for part in parts { c.addPath(part); c.fillPath() }
}

/// The app icon: deep ocean teal edge to edge, then the roll. No wave, no gradient, no tilt.
func icon(_ size: Int) -> CGImage {
    canvas(size, size) { c in let s = CGFloat(size); c.setFillColor(ocean); c.fill(CGRect(x: 0, y: 0, width: s, height: s)); roll(c, s) }
}
func text(_ c: CGContext, _ str: String, font: NSFont, color: CGColor, at p: CGPoint) {
    let attr = NSAttributedString(string: str, attributes: [.font: font, .foregroundColor: NSColor(cgColor: color)!])
    c.textPosition = p; CTLineDraw(CTLineCreateWithAttributedString(attr), c)
}
func heavy(_ size: CGFloat) -> NSFont { NSFont(name: "HelveticaNeue-CondensedBlack", size: size) ?? NSFont.systemFont(ofSize: size, weight: .black) }

let args = Array(CommandLine.arguments.dropFirst())
let ogOnly = args.first == "og"
if !ogOnly {
    let appIcon = icon(1024)
    save(appIcon, "MaineEats/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png")
    save(appIcon, "docs/brand/icon-1024.png")
    save(icon(512), "docs/icon-512.png")
    save(icon(192), "docs/icon-192.png")
    save(icon(180), "docs/apple-touch-icon.png")
    save(icon(32), "docs/favicon-32.png")
}
func ogLine() -> String {
    if ogOnly && args.count > 1 { return args[1] }
    let url = URL(fileURLWithPath: root + "/playbook/site-numbers.json")
    guard let data = try? Data(contentsOf: url), let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let line = json["og_line"] as? String else {
        return "Lobster shacks, clam shacks & Maine restaurants"
    }
    return line
}
let tagline = ogLine()
let cream = rgb(0xFBF6EC), buoy = rgb(0xF2B705), seaGlass = rgb(0xCDE6E3)
let og = canvas(1200, 630) { c in
    c.setFillColor(ocean); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 630))
    c.setFillColor(buoy); c.fill(CGRect(x: 72, y: 470, width: 90, height: 12))
    text(c, "MAINE", font: heavy(130), color: white, at: CGPoint(x: 66, y: 330))
    text(c, "EATS", font: heavy(130), color: buoy, at: CGPoint(x: 66, y: 205))
    text(c, tagline, font: NSFont.systemFont(ofSize: 30, weight: .semibold), color: cream, at: CGPoint(x: 70, y: 145))
    text(c, "Free for iPhone and iPad", font: NSFont.systemFont(ofSize: 28, weight: .regular), color: seaGlass, at: CGPoint(x: 70, y: 95))
    c.saveGState(); c.translateBy(x: 760, y: 120); roll(c, 400); c.restoreGState()
}
save(og, "docs/og.png")
