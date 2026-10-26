import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages. Until the maine.eatsranked.com DNS record exists, links use the github.io address; once it
/// resolves (dig shows the CNAME) and Pages serves it, switch these with scripts/make-site.py's CUSTOM_DOMAIN. GitHub forwards
/// the old address, so builds that shipped with it keep working.
enum Links {
    static let base = "https://nickstrom5.github.io/maine-eats"
    static let site = URL(string: base + "/")!
    /// The app's data updates: scripts/publish_app_data.py writes docs/data/app/ (OTA-DATA.md).
    static let appData = URL(string: site.absoluteString + "data/app/")!
    static let privacy = URL(string: base + "/privacy.html")!
    static let terms = URL(string: base + "/terms.html")!
    static let supportEmail = "nick@eatsranked.com"

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

    // MARK: Share

    /// The web app. It opens a place's panel from the hash, explore/#p=<id> (readHash in scripts/explore.js), using the app's ids.
    static let explore = URL(string: site.absoluteString + "explore/")!

    /// What Share sends: the place's own page in the web app, never an Apple Maps or Google link (Apple Maps has its own button).
    /// The id is escaped the way the page's encodeURIComponent would escape it. The web app lists every place
    /// the app does (a unit test checks the ids against docs/data).
    static func share(_ place: Place) -> URL {
        guard let id = place.id.addingPercentEncoding(withAllowedCharacters: uriComponent),
              let url = URL(string: explore.absoluteString + "#p=" + id) else { return explore }
        return url
    }

    /// The text that goes with the link: the place, its town and the app. No street address, which Messages turns into a Maps link.
    static func shareMessage(_ place: Place) -> String {
        [place.name, place.city ?? ""].filter { !$0.isEmpty }.joined(separator: ", ") + ", on Maine Eats"
    }

    /// What encodeURIComponent leaves as is.
    private static let uriComponent = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()")
}
