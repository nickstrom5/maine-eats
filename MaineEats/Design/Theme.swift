import SwiftUI

/// The cozy Maine coast (Nick, 2026-10-09: "ocean vibes", "cozy"), light only: sea-salt cream, deep ocean teal #0E4D5C, sea glass,
/// buoy yellow #F2B705 as a fill under dark text only (as text on white it's 1.8:1), and sand. No team marks, no state seal.
enum Theme {
    static let ocean = Color(hex: 0x0E4D5C)
    static let ocean2 = Color(hex: 0x236B78)
    static let seaGlass = Color(hex: 0xCDE6E3)
    static let buoy = Color(hex: 0xF2B705)
    static let onBuoy = Color(hex: 0x10262E)
    static let buoySoft = Color(hex: 0xFBEBC2)
    static let onBuoySoft = Color(hex: 0x5F4300)
    static let lobster = Color(hex: 0xC2492F)
    static let gray = Color(hex: 0x8A8270)
    static let ink = Color(hex: 0x10262E)
    static let ink2 = Color(hex: 0x2D4750)
    static let muted = Color(hex: 0x566B70)
    static let background = Color(hex: 0xFBF6EC)
    static let surface = Color(hex: 0xFFFDF8)
    static let surface2 = Color(hex: 0xF4EDDF)
    static let surface3 = Color(hex: 0xE9E0CC)
    static let rule = Color(hex: 0xE6DCC8)
    static let rule2 = Color(hex: 0xCDBEA3)
    static let sea = Color(hex: 0xDCECEC)

    /// Maine's official inspection result: Pass or Fail (no grades). Green and red with white text, both above 4.5:1.
    static let passColor = Color(hex: 0x1B6B3A)
    static let failColor = Color(hex: 0xA8321F)
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

/// A small uppercase label: "SEASONAL", "HAND-CHECKED".
struct Chip: View {
    enum Style { case buoy, ocean, plain, dashed }
    let text: String
    var style: Style = .plain

    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.bold))
            .tracking(0.4)
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(style == .ocean ? Color.white : style == .buoy ? Theme.onBuoySoft : style == .dashed ? Theme.muted : Theme.ocean)
            .background {
                RoundedRectangle(cornerRadius: 5).fill(style == .buoy ? Theme.buoySoft : style == .ocean ? Theme.ocean : style == .dashed ? .clear : Theme.surface2)
            }
            .overlay {
                if style == .dashed { RoundedRectangle(cornerRadius: 5).strokeBorder(Theme.rule2, style: StrokeStyle(lineWidth: 1, dash: [3, 2])) }
            }
            .accessibilityLabel(text)
    }
}

/// Lewiston's official result, Passed or Failed, as a small badge (never a grade).
struct ResultBadge: View {
    let inspection: Inspection

    var body: some View {
        Text(inspection.resultText.uppercased())
            .font(.caption.weight(.heavy))
            .tracking(0.4)
            .foregroundStyle(.white)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .background(RoundedRectangle(cornerRadius: 6).fill(inspection.passed ? Theme.passColor : Theme.failColor))
            .accessibilityLabel("Inspection result: \(inspection.resultText)")
    }
}

/// The Maine coast: two low waves, the one Maine element in the header.
struct Shoreline: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        let mid = r.midY, amp = r.height * 0.38, w = r.width
        p.move(to: CGPoint(x: 0, y: mid))
        let n = 6
        for i in 0..<n {
            let x0 = w * CGFloat(i) / CGFloat(n), x1 = w * CGFloat(i + 1) / CGFloat(n)
            p.addCurve(to: CGPoint(x: x1, y: mid), control1: CGPoint(x: x0 + (x1 - x0) * 0.33, y: mid - amp), control2: CGPoint(x: x0 + (x1 - x0) * 0.66, y: mid + amp))
        }
        p.addLine(to: CGPoint(x: w, y: r.maxY)); p.addLine(to: CGPoint(x: 0, y: r.maxY)); p.closeSubpath()
        return p
    }
}

/// Condensed, heavy display type for titles and big numbers (the system font's compressed width). It scales with the
/// reader's text size, capped at 1.6× so a big number can't swallow its row.
struct DisplayFont: ViewModifier {
    let size: CGFloat
    var weight: Font.Weight = .black
    @ScaledMetric(relativeTo: .body) private var scale: CGFloat = 1

    func body(content: Content) -> some View {
        content.font(.system(size: size * min(scale, 1.6), weight: weight).width(.compressed))
    }
}

extension View {
    func displayFont(_ size: CGFloat, weight: Font.Weight = .black) -> some View {
        modifier(DisplayFont(size: size, weight: weight))
    }
}
