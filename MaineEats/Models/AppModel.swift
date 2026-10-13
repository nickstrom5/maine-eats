import Foundation
import Observation
import CoreLocation

/// The whole app's state: the bundled places, filters, saved places and what's selected.
@MainActor
@Observable
final class AppModel {
    private(set) var places: [Place] = []
    private(set) var isLoaded = false
    private(set) var loadError: String?
    /// the date of the license data in this build
    private(set) var generated = ""
    /// changes with every rebuild of the data (older files: `generated`), so Spotlight re-indexes after any fix
    private(set) var dataVersion = ""
    /// when the hand-checked guides were last researched: "October 2026"
    private(set) var researchChecked = ""
    /// the Overture Maps release the listings come from
    private(set) var overtureRelease: String?
    /// when the Farmington Valley Health District's ratings were copied (an ISO date), and each town's ratings page
    private(set) var lewistonFetched: String?
    private(set) var licenseDate: String?
    /// old id -> new id for places whose id changed since an earlier build
    private(set) var aliases: [String: String] = [:]
    private(set) var restaurantCount = 0
    private(set) var calibration: [String: [String: CalibrationGroup]] = [:]
    /// towns sorted by how many restaurants they have
    private(set) var towns: [(name: String, count: Int)] = []
    private(set) var cuisines: [(name: String, count: Int)] = []
    /// normalized town name -> display name ("bar harbor" -> "Bar Harbor")
    private(set) var townKeys: [String: String] = [:]
    /// normalized village name -> display name ("cape neddick" -> "Cape Neddick"), for villages that aren't also a town's name
    private(set) var villageKeys: [String: String] = [:]
    /// each village's town or towns ("Cape Neddick" -> York), for the town picker
    private(set) var villageTowns: [String: [String]] = [:]

    /// the lists' filters (Home, the Map and Surprise me ignore them)
    var filters = Filters() { didSet { saveFilters() } }
    private(set) var saved: Set<String> = []
    /// how many places each guide has, before filters (the Home cards)
    private(set) var guideCounts: [Guide: Int] = [:]

    // Navigation, one copy for both layouts, so an iPad going from full width to a narrow window (or back) keeps the open
    // list and place. The iPad's sidebar is `tab` + `selectedGuide` (nil = Home) and its detail column `selectedPlace`;
    // the iPhone's stacks are the paths. `syncToCompact` and `syncToRegular` carry one over to the other.
    var selectedGuide: Guide?
    var selectedPlace: Place?
    var tab: Tab = .guides
    enum Tab: Hashable { case guides, map, saved, about }
    /// the iPhone guides stack: a guide, then a place
    var guidesPath: [Route] = []
    enum Route: Hashable { case guide(Guide), place(Place) }
    /// the iPhone Map and Saved stacks: the place opened from there
    var mapPath: [Place] = []
    var savedPath: [Place] = []
    /// set by the Home search box: All Restaurants opens with its search field active, so typing needs no second tap
    var focusSearch = false

    /// Open a guide from Home: pushes it on iPhone, selects it in the iPad sidebar.
    func openGuide(_ g: Guide) {
        tab = .guides
        selectedGuide = g
        guidesPath = [.guide(g)]
    }

    /// iPad to iPhone layout: the stacks rebuilt from what the split view shows.
    func syncToCompact() {
        switch tab {
        case .guides: guidesPath = (selectedGuide.map { [Route.guide($0)] } ?? []) + (selectedPlace.map { [Route.place($0)] } ?? [])
        case .map: mapPath = selectedPlace.map { [$0] } ?? []
        case .saved: savedPath = selectedPlace.map { [$0] } ?? []
        case .about: break
        }
    }

    /// iPhone to iPad layout: the sidebar and the detail column from the open stack.
    func syncToRegular() {
        switch tab {
        case .guides:
            selectedGuide = guidesPath.compactMap { if case .guide(let g) = $0 { g } else { nil } }.last
            selectedPlace = guidesPath.compactMap { if case .place(let p) = $0 { p } else { nil } }.last
        case .map: selectedPlace = mapPath.last
        case .saved: selectedPlace = savedPath.last
        case .about: break
        }
    }

    /// The Home search box: every restaurant, ready to type.
    func openSearch() {
        focusSearch = true
        openGuide(.all)
    }

    /// a fixed "you are here" for screenshots, so lists sort by distance without a permission prompt
    var screenshotLocation: CLLocation?

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        saved = Set(defaults.stringArray(forKey: "saved") ?? [])
        // the two toggles carry over; a town or cuisine picked last time doesn't
        if let data = defaults.data(forKey: "filters"), let f = try? JSONDecoder().decode(Filters.self, from: data) {
            filters = Filters(hideChains: f.hideChains, confirmedOnly: f.confirmedOnly)
        }
    }

    func load(from url: URL? = Bundle.main.url(forResource: "places", withExtension: "json")) async {
        guard !isLoaded else { return }
        guard let url else { loadError = "The restaurant data is missing from the app."; return }
        do {
            let (file, places) = try await Task.detached(priority: .userInitiated) { () throws -> (DataFile, [Place]) in
                let data = try Data(contentsOf: url)
                let file = try JSONDecoder().decode(DataFile.self, from: data)
                var places = file.places.map { Place($0, file: file) }
                let az = places.indices.sorted { places[$0].name.localizedCaseInsensitiveCompare(places[$1].name) == .orderedAscending }
                for (rank, i) in az.enumerated() { places[i].nameRank = rank }
                return (file, places)
            }.value
            apply(file: file, places: places)
        } catch {
            loadError = "The restaurant data couldn't be read (\(error.localizedDescription))."
        }
    }

    func apply(file: DataFile, places: [Place]) {
        self.places = places
        generated = file.generated
        dataVersion = file.data_version ?? file.generated
        researchChecked = file.research_checked ?? Self.monthYear(file.generated)
        overtureRelease = file.overture
        lewistonFetched = file.lewiston_fetched
        licenseDate = file.license_date
        aliases = file.aliases ?? [:]
        // saved places follow a place whose id changed in this build
        let ids = Set(places.map(\.id))
        let remapped = Set(saved.map { ids.contains($0) ? $0 : resolve($0) })
        if remapped != saved {
            saved = remapped
            defaults.set(Array(saved).sorted(), forKey: "saved")
        }
        restaurantCount = file.count_restaurants
        calibration = file.calibration
        var tc: [String: Int] = [:], cc: [String: Int] = [:]
        for p in places where !p.isVenue {
            if let c = p.city { tc[c, default: 0] += 1 }
            cc[p.cuisine, default: 0] += 1
        }
        towns = tc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        cuisines = cc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        var keys: [String: String] = [:]
        for (name, _) in towns {   // biggest town wins a shared spelling
            let k = Search.normalizeAddress(name)
            if keys[k] == nil { keys[k] = name }
        }
        townKeys = keys
        var vk: [String: String] = [:]
        for v in Set(places.compactMap(\.village)) {
            let k = Search.normalizeAddress(v)
            if keys[k] == nil { vk[k] = v }
        }
        villageKeys = vk
        villageTowns = Dictionary(grouping: places.filter { !$0.isVenue && $0.village != nil && $0.city != nil }, by: { $0.village! })
            .mapValues { Array(Set($0.compactMap(\.city))).sorted() }
        guideCounts = Dictionary(uniqueKeysWithValues: Guide.allCases.map { g in (g, places.lazy.filter { g.includes($0) && !$0.isVenue }.count) })
        listCache = [:]
        mapCache = [:]
        isLoaded = true
    }

    /// A place by id; an id from an earlier build (a Spotlight entry, a saved place) follows `aliases` to today's.
    func place(id: String) -> Place? {
        if let p = places.first(where: { $0.id == id }) { return p }
        let now = resolve(id)
        return now == id ? nil : places.first { $0.id == now }
    }

    /// Follows `aliases` through any chain of changes; a loop leaves the id as it was.
    func resolve(_ id: String) -> String {
        var now = id, seen: Set<String> = [id]
        while let next = aliases[now] {
            guard seen.insert(next).inserted else { return id }
            now = next
        }
        return now
    }

    /// The hand-checked research's window, "2025 or 2026" for research done in 2026.
    var sourceYears: String {
        guard let r = researchChecked.range(of: #"[0-9]{4}"#, options: .regularExpression), let y = Int(researchChecked[r]) else { return "recent" }
        return "\(y - 1) or \(y)"
    }

    /// "2026-10-05" -> "October 2026" (for a data file that predates `research_checked`)
    private static func monthYear(_ iso: String) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX")
        guard let d = f.date(from: iso) else { return iso }
        f.dateFormat = "MMMM yyyy"
        return f.string(from: d)
    }

    // MARK: lists

    /// Everything that decides a list. Lists are built off the main thread and remembered by this key.
    struct ListKey: Hashable, Sendable {
        let guide: Guide
        let sort: SortOrder
        let search: String
        let filters: Filters
        /// where you are, to about 100 m, and only for an order by distance (moving a few metres doesn't rebuild a list)
        let spot: [Int]?
    }

    func listKey(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> ListKey {
        let byDistance = guide == .nearMe || sort == .nearest
        let spot = byDistance ? here.map { [Int(($0.coordinate.latitude * 1000).rounded()), Int(($0.coordinate.longitude * 1000).rounded())] } : nil
        return ListKey(guide: guide, sort: sort, search: search, filters: filters, spot: spot)
    }

    /// The data a list is built from, copied out for a background task (arrays copy on write, so this is cheap).
    struct ListInputs: Sendable {
        let places: [Place]
        let towns: [String: String]
        let villages: [String: String]
    }

    @ObservationIgnored private var listCache: [ListKey: [Place]] = [:]

    func cachedList(_ key: ListKey) -> [Place]? { listCache[key] }

    /// A list built away from the main thread (each keystroke, location fix or filter change), then remembered.
    func buildList(_ key: ListKey, here: CLLocation?) async -> [Place] {
        if let hit = listCache[key] { return hit }
        let inputs = ListInputs(places: places, towns: townKeys, villages: villageKeys)
        let out = await Task.detached(priority: .userInitiated) { Self.build(key, here: here, from: inputs) }.value
        if listCache.count > 60 { listCache.removeAll() }
        listCache[key] = out
        return out
    }

    /// Places in a guide, filtered and searched, in the chosen order (synchronous, for tests and one-off use).
    func list(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> [Place] {
        Self.build(listKey(guide, sort: sort, search: search, here: here), here: here,
                   from: ListInputs(places: places, towns: townKeys, villages: villageKeys))
    }

    nonisolated static func build(_ key: ListKey, here: CLLocation?, from inputs: ListInputs) -> [Place] {
        let guide = key.guide, filters = key.filters
        let q = Search.parse(key.search, towns: inputs.towns, villages: inputs.villages)
        // typed something, but nothing searchable ("🍕", "!!!"): show nothing rather than everything ("near me" alone is everything)
        if q.unsearchable { return [] }
        if guide == .nearMe && here == nil { return [] }
        var out = inputs.places.filter { guide.includes($0) && filters.allows($0) && (q.isEmpty || Search.matches($0, q)) }
        out = Ranking.sort(out, by: key.sort, from: here)
        if !q.tokens.isEmpty && !(guide.isRanked) {   // name matches first when searching
            let named = out.filter { Search.nameMatches($0, q) }
            if !named.isEmpty && named.count < out.count {
                let ids = Set(named.map(\.id))
                out = named + out.filter { !ids.contains($0.id) }
            }
        }
        return out
    }

    @ObservationIgnored private var mapCache: [Guide: [Place]] = [:]

    /// A map layer: the guide's places that have a pin, before filters.
    func mapPlaces(_ guide: Guide) -> [Place] {
        if let hit = mapCache[guide] { return hit }
        let out = places.filter { guide.includes($0) && !$0.isVenue && $0.coordinate != nil }
        mapCache[guide] = out
        return out
    }

    /// A guide's size on its Home card: the whole guide, whatever a list's filters say.
    func count(_ guide: Guide) -> Int { guideCounts[guide] ?? 0 }

    /// Guides with too few hand-checked places to be worth a Home card.
    /// A classic needs at least 4 hand-checked places to be offered as a list, on Home and in the iPad sidebar.
    func hasEnough(_ guide: Guide) -> Bool { !guide.isClassic || count(guide) >= 4 }

    // MARK: saved places

    func isSaved(_ p: Place) -> Bool { saved.contains(p.id) }

    func toggleSaved(_ p: Place) {
        if saved.contains(p.id) { saved.remove(p.id) } else { saved.insert(p.id) }
        defaults.set(Array(saved).sorted(), forKey: "saved")
    }

    var savedPlaces: [Place] { places.filter { saved.contains($0.id) }.sorted { $0.name < $1.name } }

    /// A random hand-checked classic (lobster shack, clam shack, Italian, whoopie pie, diner, dairy bar...), never the one just shown.
    func randomPick(from guides: [Guide], excluding last: String?) -> Place? {
        let pool = places.filter { p in guides.contains { $0.includes(p) } && !p.isVenue && p.id != last }
        return pool.randomElement()
    }

    private func saveFilters() {
        let kept = Filters(hideChains: filters.hideChains, confirmedOnly: filters.confirmedOnly)
        if let data = try? JSONEncoder().encode(kept) { defaults.set(data, forKey: "filters") }
    }

    // MARK: honest labels

    /// "44%": how often a listing of this kind matched an on-premises liquor license statewide (calibration.json, BABLO's list).
    func matchRate(for p: Place) -> String? {
        let group: String
        switch (p.source, p.tier) {
        case ("meta", .confirmed): group = "Meta, confidence 0.95+"
        case ("meta", _): group = "Meta, 0.90-0.95"
        case ("AllThePlaces", _), ("DAC", _): group = "brand feed"
        default: return nil
        }
        guard let g = calibration["statewide_liquor"]?[group], g.n >= 20 else { return nil }
        return "\(Int((g.matched * 100).rounded()))%"
    }
}
