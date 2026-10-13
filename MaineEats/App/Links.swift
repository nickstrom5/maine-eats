import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages. Until the maine.eatsranked.com DNS record exists, links use the github.io address; once it
/// resolves (dig shows the CNAME) and Pages serves it, switch these with scripts/make-site.py's CUSTOM_DOMAIN. GitHub forwards
/// the old address, so builds that shipped with it keep working.
enum Links {
    static let base = "https://nickstrom5.github.io/maine-eats"
    static let site = URL(string: base + "/")!
    static let privacy = URL(string: base + "/privacy.html")!
    static let terms = URL(string: base + "/terms.html")!
    static let supportEmail = "work-with-nick@gmail.com"

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=Maine%20Eats%20correction")!
    }

    /// "Report a problem with this listing": the place's name and town in the subject, its id and address in the body.
    static func problemEmail(for p: Place) -> URL {
        let subject = "Maine Eats: problem with \(p.name), \(p.placeName ?? "Maine")"
        let body = "What's wrong with this listing (closed, moved, wrong name or details)?\n\n\n\(p.name)\n\(p.fullAddress)\nId: \(p.id)"
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&=+?#")
        func enc(_ s: String) -> String { s.addingPercentEncoding(withAllowedCharacters: allowed) ?? "" }
        return URL(string: "mailto:\(supportEmail)?subject=\(enc(subject))&body=\(enc(body))") ?? correctionEmail
    }
}
