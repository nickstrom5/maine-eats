import Foundation

/// Search that matches the start of words, the way the web leaderboard does:
/// "amatos" finds Amato's, "north main" finds N Main St, "bar harbor" or a village like "cape neddick" narrows to that place,
/// and "lobster roll", "clam shack", "whoopie pie", "poutine" or "dairy bar" mean those Maine classics (or a place named that way).
struct Search {
    static let typeSynonyms = ["avenue": "ave", "av": "ave", "street": "st", "boulevard": "blvd", "road": "rd", "drive": "dr", "place": "pl",
                               "court": "ct", "parkway": "pkwy", "highway": "hwy", "lane": "ln", "trail": "trl", "circle": "cir", "terrace": "ter",
                               "turnpike": "tpke", "route": "rt", "rte": "rt"]
    static let synonyms: [String: String] = typeSynonyms.merging(["north": "n", "south": "s", "east": "e", "west": "w", "saint": "st", "mount": "mt"]) { a, _ in a }
    static let abbreviations = Set(synonyms.values)
    static let typeAbbreviations = Set(typeSynonyms.values)
    static let tagPhrases: [(String, PlaceTags)] = [("lobster rolls", .lobster), ("lobster roll", .lobster), ("lobster pounds", .lobster),
                                                   ("lobster pound", .lobster), ("lobster shacks", .lobster), ("lobster shack", .lobster),
                                                   ("clam shacks", .clams), ("clam shack", .clams), ("fried clams", .clams),
                                                   ("red snappers", .hotDog), ("red snapper", .hotDog), ("hot dogs", .hotDog), ("hot dog", .hotDog), ("hotdogs", .hotDog),
                                                   ("italian sandwiches", .italian), ("italian sandwich", .italian), ("italians", .italian),
                                                   ("whoopie pies", .whoopie), ("whoopie pie", .whoopie), ("whoopies", .whoopie),
                                                   ("potato donuts", .donut), ("potato donut", .donut), ("potato doughnuts", .donut), ("potato doughnut", .donut),
                                                   ("poutine", .franco), ("tourtiere", .franco), ("meat pie", .franco), ("ployes", .franco), ("franco american", .franco),
                                                   ("oyster bars", .oyster), ("oyster bar", .oyster), ("oysters", .oyster),
                                                   ("dairy bars", .dairy), ("dairy bar", .dairy), ("diners", .diner), ("diner", .diner)]

    /// Lowercase, no accents or apostrophes, "&" as "and" ("B&B" stays "bb"), everything else a single space.
    static func normalize(_ s: String) -> String {
        var t = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .init(identifier: "en_US")).lowercased()
        t = t.replacingOccurrences(of: #"\b([a-z0-9])\s*&\s*([a-z0-9])\b"#, with: "$1$2", options: .regularExpression)
        t = t.replacingOccurrences(of: "&", with: " and ")
        t = t.replacingOccurrences(of: #"['’`]"#, with: "", options: .regularExpression)
        t = t.replacingOccurrences(of: #"[^\p{L}\p{N}]+"#, with: " ", options: .regularExpression)
        return t.trimmingCharacters(in: .whitespaces)
    }

    /// Addresses (only) get their street words abbreviated so "north main street" finds "N Main St".
    static func normalizeAddress(_ s: String) -> String {
        routes(normalize(s).split(separator: " ").map(String.init)).map { synonyms[$0] ?? $0 }.joined(separator: " ")
    }

    /// A route number: "ME-3", "US 1", "Rte 66" and "route 32" all read "rt <number>".
    static let routeWords: Set<String> = ["me", "us", "rte", "route", "rt"]
    static func routes(_ words: [String]) -> [String] {
        words.indices.map { i in
            let next = i + 1 < words.count ? words[i + 1] : ""
            return routeWords.contains(words[i]) && !next.isEmpty && next.allSatisfy({ ("0"..."9").contains($0) }) ? "rt" : words[i]
        }
    }

    struct Query {
        var tokens: [[String]] = []     // each token: needles, any of which may match
        var town: String?
        var village: String?
        var placePhrase: String?
        var tag: PlaceTags?
        var tagPhrase: String?
        /// typed something, but nothing searchable ("🍕", "!!!"): nothing to look for
        var unsearchable = false
        var isEmpty: Bool { tokens.isEmpty && town == nil && village == nil && tag == nil }
    }

    /// `towns` maps a normalized town name ("bar harbor", "south portland") to its display name; `villages` the same for villages
    /// ("cape neddick", "peaks island"), which narrow to places with that village name.
    static func parse(_ text: String, towns: [String: String], villages: [String: String] = [:]) -> Query {
        var q = Query()
        var raw = normalize(text).split(separator: " ").map(String.init)
        q.unsearchable = raw.isEmpty && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        var w = 0   // "near me" asks for nothing
        while w + 1 < raw.count { if raw[w] == "near" && raw[w + 1] == "me" { raw.removeSubrange(w...w + 1) } else { w += 1 } }
        guard !raw.isEmpty else { return q }
        var mapped = routes(raw).map { synonyms[$0] ?? $0 }
        func find(_ phrase: String) -> Range<Int>? {
            let p = phrase.split(separator: " ").map(String.init)
            guard p.count <= mapped.count else { return nil }
            for i in 0...(mapped.count - p.count) where Array(mapped[i..<i + p.count]) == p { return i..<i + p.count }
            return nil
        }
        func cut(_ r: Range<Int>) -> String {
            let words = raw[r].joined(separator: " ")
            raw.removeSubrange(r); mapped.removeSubrange(r)
            return words
        }
        for (phrase, tag) in tagPhrases {
            if let r = find(normalize(phrase)) { q.tag = tag; q.tagPhrase = cut(r); break }
        }
        // the single longest town or village named in the query wins ("new preston" is the village, not the town of Preston;
        // a town wins a tie), unless a street type follows it ("new britain ave" is a street)
        let named: [(key: String, isTown: Bool)] = towns.keys.map { ($0, true) } + villages.keys.map { ($0, false) }
        let keys = named.sorted { (a, b) -> Bool in
            if a.key.count != b.key.count { return a.key.count > b.key.count }
            if a.isTown != b.isTown { return a.isTown }
            return a.key < b.key
        }
        for (key, isTown) in keys {
            if let r = find(key), !(r.upperBound < mapped.count && typeAbbreviations.contains(mapped[r.upperBound])) {
                if isTown { q.town = towns[key] } else { q.village = villages[key] }
                q.placePhrase = cut(r)
                break
            }
        }
        // stop words go once a town, village or tag is set, or when any other word is left ("lobster in bar harbor")
        let stop: Set<String> = ["the", "and", "of", "a", "in", "near"]
        var idx = Array(raw.indices)
        if q.town != nil || q.village != nil || q.tag != nil || idx.contains(where: { !stop.contains(mapped[$0]) }) {
            idx = idx.filter { !stop.contains(mapped[$0]) }
        }
        var skip = -1
        for (n, i) in idx.enumerated() where i != skip {
            let token = raw[i], isLast = n == idx.count - 1
            // a route and its number stay together: "me 3", "route 3" and "rte 3" find an address on Rt 3 (or a name that says it),
            // not a Mexican place with a 3 in its address (the web app does the same)
            if routeWords.contains(token), n + 1 < idx.count, idx[n + 1] == i + 1, raw[i + 1].allSatisfy({ ("0"..."9").contains($0) }) {
                q.tokens.append([" rt \(raw[i + 1]) ", " \(token) \(raw[i + 1]) "]); skip = i + 1; continue
            }
            if mapped[i] != token { q.tokens.append([" \(mapped[i]) ", " \(token)"]); continue }
            let whole = (abbreviations.contains(token) && (!isLast || token.count > 1)) || (token.count <= 2 && !isLast)
            var needles = [" " + token + (whole ? " " : "")]
            // what people call a place ("reds", "amatos") may be a possessive the name doesn't have
            if token.count >= 4 && token.hasSuffix("s") && !whole { needles.append(" " + token.dropLast()) }
            if isLast && token.count >= 3 {
                for (word, abbr) in typeSynonyms where word != token && word.hasPrefix(token) { needles.append(" \(abbr) ") }
            }
            q.tokens.append(needles)
        }
        // "chapel st": a finished street type sticks to the word before it
        if q.tokens.count >= 2, let last = idx.last, typeAbbreviations.contains(mapped[last]) {
            let prev = idx[idx.count - 2]
            q.tokens.removeLast(2)
            q.tokens.append([" \(mapped[prev]) \(mapped[last]) ", " \(raw[prev]) \(raw[last])"])
        }
        return q
    }

    static func matches(_ p: Place, _ q: Query) -> Bool {
        if let tag = q.tag, !p.tags.contains(tag) {
            let stem = normalize(q.tagPhrase ?? "").replacingOccurrences(of: #"s$"#, with: "", options: .regularExpression)
            if stem.isEmpty || !p.nameText.contains(" " + stem) { return false }
        }
        if let town = q.town, p.city != town {
            if !p.nameText.contains(" " + normalize(q.placePhrase ?? "")) { return false }
        }
        if let village = q.village, p.village != village {
            if !p.nameText.contains(" " + normalize(q.placePhrase ?? "")) { return false }
        }
        for needles in q.tokens where !needles.contains(where: { p.searchText.contains($0) }) { return false }
        return true
    }

    /// Name matches first ("harbor" puts Harbor Dogs ahead of places in Bar Harbor).
    static func nameMatches(_ p: Place, _ q: Query) -> Bool {
        !q.tokens.isEmpty && q.tokens.allSatisfy { needles in needles.contains { p.nameText.contains($0) } }
    }
}
