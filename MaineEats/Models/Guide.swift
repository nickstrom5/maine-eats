import Foundation
import CoreLocation

/// The lists the app is built around. Each is a filter plus an order; none uses ratings (the app only publishes data it may).
enum Guide: String, CaseIterable, Identifiable, Hashable {
    case lobster, clams, sandwiches, sweets, franco, diners, oysters, dairy, icons, oldest, nearMe, all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .lobster: "Lobster Shacks & Rolls"
        case .clams: "Clam Shacks"
        case .sandwiches: "Red Snappers & Italians"
        case .sweets: "Whoopie Pies & Donuts"
        case .franco: "Franco-American"
        case .diners: "Diners"
        case .oysters: "Oyster Bars"
        case .dairy: "Dairy Bars"
        case .icons: "Maine Icons"
        case .oldest: "Oldest Places"
        case .nearMe: "Near Me"
        case .all: "All Restaurants"
        }
    }

    var subtitle: String {
        switch self {
        case .lobster: "Pounds, shacks and wharves, hand-checked, most open May to October"
        case .clams: "Whole-belly fried clams, chowder and clam cakes, hand-checked"
        case .sandwiches: "Bright-red snapper hot dogs and the Maine Italian, hand-checked"
        case .sweets: "Whoopie pies, potato donuts and blueberry pie, hand-checked"
        case .franco: "Poutine, meat pie and ployes, hand-checked"
        case .diners: "Long-running diners, hand-checked open"
        case .oysters: "Damariscotta River and Casco Bay oysters, hand-checked"
        case .dairy: "Ice cream stands and farm creameries, mostly seasonal"
        case .icons: "James Beard honorees and long-running institutions"
        case .oldest: "40 years or more at the same address, oldest first"
        case .nearMe: "Everything around you, closest first"
        case .all: "Restaurants, cafés, bars and bakeries statewide"
        }
    }

    /// The line at the top of a list, where a classic adds how it was checked (so it doesn't say "hand-checked" twice).
    var listSubtitle: String {
        switch self {
        case .lobster: "Pounds, shacks and wharves, most open May to October"
        case .clams: "Whole-belly fried clams, chowder and clam cakes"
        case .sandwiches: "Bright-red snapper hot dogs and the Maine Italian"
        case .sweets: "Whoopie pies, potato donuts and blueberry pie"
        case .franco: "Poutine, meat pie and ployes, from Lewiston to the St. John Valley"
        case .diners: "Long-running diners"
        case .oysters: "Damariscotta River and Casco Bay oysters"
        default: subtitle
        }
    }

    var systemImage: String {
        switch self {
        case .lobster: "fish"
        case .clams: "frying.pan"
        case .sandwiches: "takeoutbag.and.cup.and.straw"
        case .sweets: "birthday.cake"
        case .franco: "fork.knife.circle"
        case .diners: "cup.and.saucer"
        case .oysters: "water.waves"
        case .dairy: "snowflake"
        case .icons: "star.circle"
        case .oldest: "clock.arrow.circlepath"
        case .nearMe: "location"
        case .all: "fork.knife"
        }
    }

    /// The Maine classics: hand-checked lists, highlighted on Home.
    var isClassic: Bool { [.lobster, .clams, .sandwiches, .sweets, .franco, .diners, .oysters, .dairy].contains(self) }

    /// Guides whose order is a ranking worth numbering.
    var isRanked: Bool { [.icons, .oldest].contains(self) }

    var sortOptions: [SortOrder] {
        switch self {
        case .lobster, .clams, .sandwiches, .sweets, .franco, .diners, .oysters, .dairy: [.featured, .nearest, .oldest, .name]
        case .icons: [.iconic, .oldest, .nearest]
        case .oldest: [.oldest]
        case .nearMe: [.nearest]
        case .all: [.name, .nearest]
        }
    }

    var defaultSort: SortOrder { sortOptions[0] }

    /// The order a list opens in: the classics by distance when you're in Maine, featured otherwise (a reader in California
    /// shouldn't get a Kittery branch at 3,000 miles ahead of the Downeast originals).
    func defaultSort(inState: Bool) -> SortOrder { isClassic ? (inState ? .nearest : .featured) : defaultSort }

    func includes(_ p: Place) -> Bool {
        switch self {
        // the classics promise "hand-checked", so only places our research confirmed open; a listing merely named "… Lobster Pound"
        // isn't enough
        case .lobster: p.handChecked && !p.kinds.isDisjoint(with: [.lobsterShack, .lobsterRoll])
        case .clams: p.handChecked && p.kinds.contains(.clamShack)
        case .sandwiches: p.handChecked && !p.kinds.isDisjoint(with: [.redSnapper, .italianSandwich])
        case .sweets: p.handChecked && !p.kinds.isDisjoint(with: [.whoopiePie, .potatoDoughnut, .blueberryPie])
        case .franco: p.handChecked && p.kinds.contains(.francoAmerican)
        case .diners: p.handChecked && p.kinds.contains(.diner)
        case .oysters: p.handChecked && p.kinds.contains(.oysterBar)
        case .dairy: p.handChecked && p.kinds.contains(.dairyBar)
        case .icons: p.iconicPoints != nil
        case .oldest: p.isLongRunning
        case .nearMe, .all: true
        }
    }
}

enum SortOrder: String, CaseIterable, Identifiable {
    case featured, nearest, oldest, name, iconic
    var id: String { rawValue }
    var label: String {
        switch self {
        case .featured: "Featured first"
        case .nearest: "Nearest"
        case .oldest: "Oldest first"
        case .name: "A to Z"
        case .iconic: "Most iconic"
        }
    }
    /// The orders that rank, so only these number the rows (Nearest and A to Z aren't a ranking).
    var isRanking: Bool { self == .iconic || self == .oldest }
}

/// Filters shared by every list (and only lists: Home, the Map and Surprise me show each guide whole). Search text lives with
/// each list. Only the two toggles are kept across launches; a town or cuisine is for this visit.
struct Filters: Hashable, Codable {
    var town: String?
    var cuisine: String?
    var hideChains = false
    var confirmedOnly = false
    var includeNonRestaurants = false

    var activeCount: Int {
        [town != nil, cuisine != nil, hideChains, confirmedOnly, includeNonRestaurants].filter { $0 }.count
    }

    func allows(_ p: Place) -> Bool {
        if !includeNonRestaurants && p.isVenue { return false }
        if let town, p.city != town { return false }
        if let cuisine, p.cuisine != cuisine { return false }
        if hideChains && p.isChain && !p.isHandCheckedOriginal { return false }   // Amato's on India St stays; its branches go
        if confirmedOnly && p.tier == .listing && !p.handChecked { return false }   // hand-checked counts as confirmed
        return true
    }
}

enum Ranking {
    static func sort(_ places: [Place], by order: SortOrder, from here: CLLocation?) -> [Place] {
        // names compare by their place in the A to Z order (Place.nameRank), worked out once at load
        func name(_ a: Place, _ b: Place) -> Bool { a.nameRank < b.nameRank }
        switch order {
        case .nearest where here != nil:
            // each distance once, not per comparison
            let d = places.map { p in (p, p.coordinate.map { here!.distance(from: CLLocation(latitude: $0.latitude, longitude: $0.longitude)) } ?? .greatestFiniteMagnitude) }
            return d.sorted { $0.1 != $1.1 ? $0.1 < $1.1 : name($0.0, $1.0) }.map(\.0)
        case .featured, .nearest:
            // the featured score first (honored, long-running classics), then the verified year at this address, then name
            return places.sorted {
                let a = $0.featuredScore ?? -1, b = $1.featuredScore ?? -1
                if a != b { return a > b }
                let fa = $0.founded ?? 9999, fb = $1.founded ?? 9999
                return fa != fb ? fa < fb : name($0, $1)
            }
        case .oldest:
            return places.sorted { ($0.founded ?? 9999) != ($1.founded ?? 9999) ? ($0.founded ?? 9999) < ($1.founded ?? 9999) : name($0, $1) }
        case .name:
            return places.sorted(by: name)
        case .iconic:
            return places.sorted { ($0.iconicPoints ?? -1) != ($1.iconicPoints ?? -1) ? ($0.iconicPoints ?? -1) > ($1.iconicPoints ?? -1) : name($0, $1) }
        }
    }
}
