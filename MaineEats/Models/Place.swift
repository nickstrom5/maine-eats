import Foundation
import CoreLocation

// MARK: - The bundled data file (Resources/places.json), written by pipeline/maine.py with ME_APP=1

struct DataFile: Decodable {
    /// the date of the license data the build used
    let generated: String
    /// a hash of the places, new with every rebuild that changes anything (older files: none, so `generated` stands in)
    let data_version: String?
    /// when the hand-checked guides were last researched: "October 2026"
    let research_checked: String?
    /// the Overture Maps release: "2026-09-23.1"
    let overture: String?
    /// ids that changed since an earlier build: old id -> new id, so saved places and Spotlight entries follow a place
    let aliases: [String: String]?
    /// the BABLO license file the build used ("10-2026.xlsx") and BABLO's own "current as of" date for it ("Oct 1, 2026")
    let license_file: String?
    let license_date: String?
    /// when Lewiston's inspection page was read, and the newest inspection on it
    let lewiston_fetched: String?
    let lewiston_latest: String?
    let cities: [String]
    let villages: [String]
    let cuisines: [String]
    let brands: [String]
    let hosts: [String]
    let sources: [String]
    let count_restaurants: Int
    /// match rates measured against official lists: "statewide_liquor" (BABLO licenses) and "lewiston" (the city's inspected places)
    let calibration: [String: [String: CalibrationGroup]]
    let places: [PlaceRecord]
}

struct CalibrationGroup: Decodable, Hashable {
    let n: Int
    let matched: Double
}

/// The City of Lewiston's latest posted inspection: Maine's official result is Pass or Fail (10-144 CMR Ch. 201 §6(D): more than 3
/// critical or more than 10 non-critical violations fails), with no score or grade. Only Lewiston posts its results in bulk.
struct Inspection: Decodable, Hashable {
    /// "Pass" or "Fail"
    let r: String
    /// "2025-08-27"
    let d: String?
    /// the city's report (a PDF on lewistonmaine.gov)
    let u: String?
    /// the name the city inspected it under, when that isn't the name shown
    let n: String?
    var passed: Bool { r == "Pass" }
    var resultText: String { passed ? "Passed" : "Failed" }
    var reportURL: URL? { u.flatMap { URL(string: $0) }.flatMap { ["https", "http"].contains($0.scheme ?? "") ? $0 : nil } }
}

struct PlaceRecord: Decodable {
    let id: String
    let n: String
    let c: Int?
    let vi: Int?
    let cu: Int
    let t: Int
    let s: Int
    let a: String?
    let z: String?
    let la: Double?
    let lo: Double?
    let b: Int?
    let ch: Int?
    let j: Int?
    let lk: String?
    let v: Int?
    let bar: Int?
    let host: Int?
    let g: Int?
    let hc: Int?
    let k: Int?
    let h: Int?
    let ip: Double?
    /// the featured score of a hand-checked place (the classics' "Featured first" order); `ip` is only on icons
    let fs: Double?
    let note: String?
    let jbf: String?
    let hon: String?
    let dish: String?
    let sea: String?
    let seas: Int?
    let br: String?
    let chef: String?
    let f: Int?
    let w: String?
    let ph: String?
    let lw: Inspection?
}

// MARK: - The model the views use

/// Maine tags, from names and the hand-checked research (never from reviews). Bit order = TAGS in pipeline/maine.py.
struct PlaceTags: OptionSet, Hashable {
    let rawValue: Int
    static let lobster = PlaceTags(rawValue: 1)
    static let clams = PlaceTags(rawValue: 2)
    static let hotDog = PlaceTags(rawValue: 4)
    static let italian = PlaceTags(rawValue: 8)
    static let whoopie = PlaceTags(rawValue: 16)
    static let donut = PlaceTags(rawValue: 32)
    static let franco = PlaceTags(rawValue: 64)
    static let diner = PlaceTags(rawValue: 128)
    static let oyster = PlaceTags(rawValue: 256)
    static let dairy = PlaceTags(rawValue: 512)
}

/// What the hand-checked research says a place is (data/research/README.md `kinds`; bit order = KINDS in pipeline/maine.py).
struct Kinds: OptionSet, Hashable {
    let rawValue: Int
    static let lobsterShack = Kinds(rawValue: 1)
    static let lobsterRoll = Kinds(rawValue: 2)
    static let clamShack = Kinds(rawValue: 4)
    static let redSnapper = Kinds(rawValue: 8)
    static let italianSandwich = Kinds(rawValue: 16)
    static let whoopiePie = Kinds(rawValue: 32)
    static let potatoDoughnut = Kinds(rawValue: 64)
    static let blueberryPie = Kinds(rawValue: 128)
    static let francoAmerican = Kinds(rawValue: 256)
    static let diner = Kinds(rawValue: 512)
    static let oysterBar = Kinds(rawValue: 1024)
    static let dairyBar = Kinds(rawValue: 2048)
    static let oldest = Kinds(rawValue: 4096)

    static let labels: [(Kinds, String)] = [(.lobsterShack, "Lobster shack"), (.lobsterRoll, "Lobster roll"), (.clamShack, "Clam shack"),
                                            (.redSnapper, "Red snappers"), (.italianSandwich, "Maine Italians"), (.whoopiePie, "Whoopie pies"),
                                            (.potatoDoughnut, "Potato donuts"), (.blueberryPie, "Blueberry pie"), (.francoAmerican, "Franco-American"),
                                            (.diner, "Diner"), (.oysterBar, "Oyster bar"), (.dairyBar, "Dairy bar"), (.oldest, "Historic")]
    var names: [String] { Kinds.labels.filter { contains($0.0) }.map(\.1) }
}

/// How a place got on the list. The share that matched a licensed business comes from calibration.json.
enum Tier: Int, Comparable {
    case listing = 0        // one map listing
    case confirmed = 1      // a high-confidence Meta listing, or a hand-checked place
    case licensed = 2       // on the state liquor-license list (BABLO) or Lewiston's inspection list

    static func < (a: Tier, b: Tier) -> Bool { a.rawValue < b.rawValue }

    var label: String {
        switch self {
        case .licensed: "Licensed"
        case .confirmed: "High-confidence listing"   // not "confirmed": these matched a liquor license at about twice the rate of others
        case .listing: "Listing only"
        }
    }
}

enum Jurisdiction: Int {
    case none = 0, bablo = 1, lewiston = 2
    var listName: String {
        switch self {
        case .bablo: "Maine Bureau of Alcoholic Beverages and Lottery Operations liquor licenses"
        case .lewiston: "City of Lewiston restaurant inspection list"
        case .none: ""
        }
    }
}

struct Place: Identifiable, Hashable {
    let id: String
    let name: String
    let address: String?
    /// the Maine town, city, plantation or unorganized territory it's in (the municipality)
    let city: String?
    /// the village people call it, when it isn't the town: Cape Neddick, Peaks Island, Northeast Harbor
    let village: String?
    let zip: String?
    let coordinate: CLLocationCoordinate2D?
    let cuisine: String
    let brand: String?
    let chainCount: Int
    let tier: Tier
    let jurisdiction: Jurisdiction
    /// the BABLO premises class: "Class A Restaurant", "Class A Restaurant/Lounge", "Restaurant", "Class A Lounge", "Hotel"...
    let licenseKind: String?
    let source: String
    let isVenue: Bool
    let isBar: Bool
    /// Hollywood Casino Bangor or Oxford Casino: restaurants inside a casino
    let host: String?
    let tags: PlaceTags
    /// On our hand-checked list (data/research): confirmed open with a 2025–26 source.
    let handChecked: Bool
    let kinds: Kinds
    let honorFlags: Int
    /// the Icons guide's order (honors and years at the address); only icons have it, and it's never shown as a number
    let iconicPoints: Double?
    /// the classics' "Featured first" order
    let featuredScore: Double?
    let note: String?
    let jamesBeard: String?
    let otherHonors: String?
    let dishes: String?
    let season: String?
    let isSeasonal: Bool
    let branchOf: String?
    let chef: String?
    let founded: Int?
    /// 40 or more years at this address, counted from the data's own year (the Oldest Places list; a 2023 opening isn't one)
    let isLongRunning: Bool
    /// http or https only
    let website: URL?
    /// a US number, "+12075551234"; anything else could ring abroad, so it isn't offered
    let phone: String?
    /// Lewiston's latest posted inspection (official Pass/Fail with its date), when the city has one for this place
    let inspection: Inspection?
    /// normalized text for search: name, town, village, zip, cuisine, brand, dishes, then the address with street words abbreviated
    let searchText: String
    let nameText: String
    /// position in the A to Z order of every place, worked out once at load so sorting never compares names
    var nameRank = 0

    static func == (a: Place, b: Place) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    var isHonored: Bool { handChecked }
    var isChain: Bool { chainCount >= 5 }
    /// a hand-checked place that isn't someone's branch: Amato's on India St, though Amato's has many
    var isHandCheckedOriginal: Bool { handChecked && branchOf == nil }
    var jamesBeardLabel: String? {
        if honorFlags & 1 != 0 { return "America's Classic" }
        if honorFlags & 2 != 0 { return "James Beard winner" }
        if honorFlags & 4 != 0 { return "James Beard nominee" }
        if honorFlags & 8 != 0 { return "James Beard semifinalist" }
        return nil
    }
    /// "Cape Neddick (York)" or "Portland"
    var placeName: String? {
        guard let city else { return village }
        return village.map { "\($0) (\(city))" } ?? city
    }
    var townLine: String { [placeName, cuisine].compactMap { $0 }.joined(separator: " · ") }
    var fullAddress: String {
        [address, [village ?? city, zip].compactMap { $0 }.joined(separator: " ")].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
    }
    var location: CLLocation? { coordinate.map { CLLocation(latitude: $0.latitude, longitude: $0.longitude) } }
    /// "(207) 555-1234"
    var phoneText: String? {
        phone.map { p in "(\(p.dropFirst(2).prefix(3))) \(p.dropFirst(5).prefix(3))-\(p.dropFirst(8))" }
    }

    static func usPhone(_ s: String?) -> String? {
        guard let s, s.range(of: #"^\+1[2-9][0-9]{9}$"#, options: .regularExpression) != nil else { return nil }
        return s
    }

    /// A website link only when it's a web address: no other scheme, and nothing scheme-less that could resolve oddly.
    static func webURL(_ s: String?) -> URL? {
        guard let s, let u = URL(string: s), ["http", "https"].contains(u.scheme?.lowercased() ?? ""), !(u.host ?? "").isEmpty else { return nil }
        return u
    }

    init(_ r: PlaceRecord, file: DataFile) {
        let city = r.c.flatMap { $0 < file.cities.count ? file.cities[$0] : nil }
        let village = r.vi.flatMap { $0 < file.villages.count ? file.villages[$0] : nil }
        let cuisine = r.cu < file.cuisines.count ? file.cuisines[r.cu] : "American & Other"
        let brand = r.b.flatMap { $0 < file.brands.count ? file.brands[$0] : nil }
        let host = r.host.flatMap { $0 < file.hosts.count ? file.hosts[$0] : nil }
        id = r.id
        name = r.n
        address = r.a
        self.city = city
        self.village = village
        zip = r.z
        if let la = r.la, let lo = r.lo { coordinate = CLLocationCoordinate2D(latitude: la, longitude: lo) } else { coordinate = nil }
        self.cuisine = cuisine
        self.brand = brand
        chainCount = r.ch ?? 1
        tier = Tier(rawValue: r.t) ?? .listing
        jurisdiction = Jurisdiction(rawValue: r.j ?? 0) ?? .none
        licenseKind = r.lk
        source = r.s < file.sources.count ? file.sources[r.s] : "meta"
        isVenue = r.v == 1
        isBar = r.bar == 1
        self.host = host
        tags = PlaceTags(rawValue: r.g ?? 0)
        handChecked = r.hc == 1
        kinds = Kinds(rawValue: r.k ?? 0)
        honorFlags = r.h ?? 0
        iconicPoints = r.ip
        featuredScore = r.fs ?? r.ip
        note = r.note
        jamesBeard = r.jbf
        otherHonors = r.hon
        dishes = r.dish
        season = r.sea
        isSeasonal = r.seas == 1
        branchOf = r.br
        chef = r.chef
        founded = r.f
        isLongRunning = r.f.map { $0 <= (Int(file.generated.prefix(4)) ?? 2026) - 40 } ?? false
        website = Self.webURL(r.w)
        phone = Self.usPhone(r.ph)
        inspection = r.lw
        // the dishes a place is known for are searchable too: "fried clams", "whoopie pie"
        searchText = " " + Search.normalize([r.n, city, village, r.z, cuisine, brand, host, r.dish].compactMap { $0 }.joined(separator: " ")) + " "
            + Search.normalizeAddress(r.a ?? "") + " "
        nameText = " " + Search.normalize([r.n, brand].compactMap { $0 }.joined(separator: " ")) + " "
    }
}
