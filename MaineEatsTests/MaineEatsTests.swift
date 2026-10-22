import XCTest
import CoreLocation
@testable import MaineEats

@MainActor
final class MaineEatsTests: XCTestCase {

    /// A tiny data file with the same shape as Resources/places.json (names and numbers are test values).
    nonisolated static let sampleJSON = """
        {"v":1,"generated":"2026-10-08","data_version":"abc123def456","research_checked":"October 2026","overture":"2026-09-23.1",
         "aliases":{"old-b":"b","older-b":"old-b","loop1":"loop2","loop2":"loop1"},
         "cities":["Portland","York","Wiscasset","Lewiston","Bangor","Kennebunkport","Waldoboro","South Portland"],
         "villages":["Cape Neddick","Peaks Island","Cape Porpoise"],
         "cuisines":["Seafood","Sandwiches & Deli","Bakery & Sweets","Bar & Pub","American & Other","Hot Dogs","Breakfast & Diner","Pizza"],
         "brands":["Dunkin'"],"hosts":["Hollywood Casino Bangor","Oxford Casino"],
         "tags":["lobster","clams","hotdog","italian","whoopie","donut","franco","diner","oyster","dairy"],"sources":["official","meta","AllThePlaces","DAC","research"],
         "count":13,"count_restaurants":12,
         "calibration":{"statewide_liquor":{"Meta, confidence 0.95+":{"n":2694,"matched":0.444},"Meta, 0.90-0.95":{"n":1136,"matched":0.242}}},
         "license_file":"10-2026.xlsx","license_date":"Oct 1, 2026","lewiston_fetched":"2026-10-08","lewiston_latest":"2026-03-30",
         "places":[
          {"id":"a","n":"Red's Eats","c":2,"cu":0,"t":2,"s":0,"j":1,"lk":"Restaurant","hc":1,"k":3,"g":1,"seas":1,"sea":"mid-April to mid-October","ip":90,"fs":80,"a":"41 Water St","z":"04578","la":44.0026,"lo":-69.6650,"f":1938,"dish":"lobster roll","jbf":"America's Classics 2001 (winner)","h":3,"ph":"+12078825010","w":"https://www.example-reds.com/"},
          {"id":"b","n":"Amato's","c":0,"cu":1,"t":1,"s":1,"hc":1,"k":16,"g":8,"ip":70,"fs":85,"a":"71 India St","la":43.6612,"lo":-70.2505,"f":1927,"dish":"Maine Italian sandwich","ph":"+2077734090","w":"javascript:alert(1)"},
          {"id":"c","n":"Nunan's Lobster Hut","c":5,"vi":2,"cu":0,"t":1,"s":1,"hc":1,"k":1,"g":1,"seas":1,"sea":"May to October","ip":60,"a":"9 Mills Rd","la":43.3700,"lo":-70.4330,"dish":"boiled lobster","h":4,"w":"example-nunans.com"},
          {"id":"d","n":"Simones' Hot Dog Stand","c":3,"cu":5,"t":1,"s":1,"hc":1,"k":8,"g":4,"ip":65,"fs":65,"a":"99 Chestnut St","la":44.0979,"lo":-70.2183,"f":1959,"ph":"(207) 782-8431","lw":{"r":"Pass","d":"2023-09-21","u":"https://www.lewistonmaine.gov/DocumentCenter/View/16517"}},
          {"id":"e","n":"Dunkin'","c":4,"cu":4,"t":1,"s":2,"b":0,"ch":400,"la":44.80,"lo":-68.77},
          {"id":"f","n":"Cape Neddick Diner","c":1,"vi":0,"cu":6,"t":0,"s":1,"g":128,"a":"10 Main St","la":43.17,"lo":-70.62},
          {"id":"g","n":"Irving","c":4,"cu":4,"t":1,"s":1,"v":1,"la":44.81,"lo":-68.78},
          {"id":"h","n":"Epic Buffet","c":4,"cu":4,"t":1,"s":1,"host":0,"la":44.7867,"lo":-68.7843},
          {"id":"i","n":"Lisbon Street Pizza","c":3,"cu":7,"t":1,"s":1,"a":"9 Lisbon St","la":44.09,"lo":-70.21,"lw":{"r":"Fail","d":"2026-03-30","u":"https://www.lewistonmaine.gov/DocumentCenter/View/1","n":"LISBON ST PIZZA"}},
          {"id":"j","n":"Gifford's Famous Ice Cream","c":4,"cu":2,"t":0,"s":1,"hc":1,"k":2048,"fs":40,"f":2023,"a":"1 Main St","la":44.79,"lo":-68.78},
          {"id":"k","n":"Peaks Cafe","c":0,"vi":1,"cu":4,"t":1,"s":1,"a":"10 Island Ave","la":43.655,"lo":-70.199},
          {"id":"l","n":"Route One Pizza","c":6,"cu":7,"t":1,"s":1,"a":"260 US-1","la":44.10,"lo":-69.37},
          {"id":"m","n":"Mill Creek Bistro","c":7,"cu":4,"t":1,"s":1,"a":"2 Main St","la":43.63,"lo":-70.24}
         ]}
        """

    private func sampleModel(defaults: UserDefaults? = nil, json: String = sampleJSON) async throws -> AppModel {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("places-test-\(UUID().uuidString).json")
        try json.data(using: .utf8)!.write(to: url)
        let model = AppModel(defaults: defaults ?? UserDefaults(suiteName: "test-\(UUID().uuidString)")!)
        await model.load(from: url)
        XCTAssertTrue(model.isLoaded, model.loadError ?? "")
        return model
    }

    func testDecodesAndHidesNonRestaurantsByDefault() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.places.count, 13)
        let all = m.list(.all, sort: .name, search: "", here: nil)
        XCTAssertFalse(all.contains { $0.name == "Irving" }, "gas-station counters are hidden unless asked for")
        m.filters.includeNonRestaurants = true
        XCTAssertTrue(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Irving" })
    }

    func testGuidesListOnlyHandCheckedPlaces() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(Set(m.list(.lobster, sort: .name, search: "", here: nil).map(\.id)), ["a", "c"], "a shack and a roll both count")
        XCTAssertEqual(m.list(.sandwiches, sort: .name, search: "", here: nil).map(\.id), ["b", "d"], "Italians and red snappers")
        XCTAssertEqual(m.list(.clams, sort: .name, search: "", here: nil), [])
        XCTAssertEqual(m.list(.diners, sort: .name, search: "", here: nil), [], "a listing merely named \u{201C}Diner\u{201D} stays out of the checked guide")
        XCTAssertEqual(m.list(.dairy, sort: .name, search: "", here: nil).map(\.id), ["j"])
        XCTAssertEqual(m.list(.all, sort: .name, search: "cape neddick diner", here: nil).map(\.id), ["f"], "but it's still in the directory")
        XCTAssertEqual(m.list(.oldest, sort: .oldest, search: "", here: nil).map(\.id), ["b", "a", "d"], "a 2023 opening isn't one of the oldest")
        XCTAssertFalse(m.place(id: "j")!.isLongRunning)
        XCTAssertTrue(m.place(id: "d")!.isLongRunning, "1959 is 40+ years before the data's 2026")
        XCTAssertEqual(m.list(.icons, sort: .iconic, search: "", here: nil).first?.id, "a")
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: nil), [], "near me needs a location")
    }

    func testVillagesAndTowns() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> Set<String> { Set(m.list(.all, sort: .name, search: q, here: nil).map(\.id)) }
        XCTAssertEqual(ids("cape porpoise"), ["c"], "a village narrows to its places")
        XCTAssertEqual(ids("kennebunkport"), ["c"], "and its town finds them too")
        XCTAssertEqual(ids("cape neddick"), ["f"], "Cape Neddick is a village of York")
        XCTAssertEqual(ids("york"), ["f"])
        XCTAssertEqual(ids("portland"), ["b", "k"], "Portland, not South Portland")
        XCTAssertEqual(ids("south portland"), ["m"])
        XCTAssertEqual(ids("peaks island"), ["k"])
        // stop words drop out next to a town, village or tag
        XCTAssertEqual(ids("lobster roll in wiscasset"), ["a"])
        XCTAssertEqual(ids("lobster in kennebunkport"), ids("lobster kennebunkport"))
        XCTAssertEqual(ids("near cape porpoise"), ids("cape porpoise"))
        XCTAssertEqual(ids("pizza near me"), ids("pizza"))
        XCTAssertFalse(ids("pizza").isEmpty)
        XCTAssertEqual(ids("near me"), ids(""))
        let nunans = m.place(id: "c")!
        XCTAssertEqual(nunans.placeName, "Cape Porpoise (Kennebunkport)")
        XCTAssertEqual(nunans.fullAddress, "9 Mills Rd, Cape Porpoise")
    }

    func testSearchTagsDishesAndStreets() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertEqual(Set(ids("lobster roll")), ["a", "c"])
        XCTAssertEqual(ids("red snapper"), ["d"], "the tag, not a word in a name")
        XCTAssertEqual(ids("italian sandwich"), ["b"])
        XCTAssertEqual(ids("boiled lobster"), ["c"], "a dish is searchable")
        XCTAssertEqual(ids("amatos"), ["b"], "\u{201C}Amatos\u{201D} finds Amato's")
        XCTAssertEqual(ids("mato"), [], "matches the start of words only")
        XCTAssertEqual(ids("india street"), ["b"], "street words match the abbreviated address")
        XCTAssertEqual(ids("water st"), ["a"])
        XCTAssertEqual(ids("hollywood casino"), ["h"], "the host casino is searchable")
        XCTAssertEqual(ids("route 1"), ["l"], "\u{201C}260 US-1\u{201D} is a route address")
        XCTAssertEqual(ids("us 1"), ["l"])
        XCTAssertEqual(ids("260 rt 1"), ["l"])
        XCTAssertEqual(ids("me 1"), ["l"], "a route word and its number stay together")
        XCTAssertEqual(ids("route 9"), [], "not any place with a 9 somewhere")
        XCTAssertEqual(Search.normalizeAddress("260 US-1"), "260 rt 1")
        XCTAssertEqual(Search.normalizeAddress("45 ME-3"), "45 rt 3")
        XCTAssertEqual(Search.normalizeAddress("12 Court St"), "12 ct st")
        XCTAssertEqual(ids("🦞"), [], "nothing searchable typed means no results, not everything")
        XCTAssertEqual(ids("!!! ?"), [])
    }

    func testSortsAndDefaults() async throws {
        let m = try await sampleModel()
        let oldPort = CLLocation(latitude: 43.6575, longitude: -70.2544)
        let near = m.list(.nearMe, sort: .nearest, search: "", here: oldPort)
        XCTAssertEqual(near.first?.id, "b", "Amato's is closest to the Old Port")
        XCTAssertEqual(m.list(.lobster, sort: .featured, search: "", here: nil).map(\.id), ["a", "c"], "Featured follows fs")
        XCTAssertEqual(m.list(.sandwiches, sort: .featured, search: "", here: nil).map(\.id), ["b", "d"], "fs, not the icon points")
        XCTAssertEqual(m.list(.icons, sort: .iconic, search: "", here: nil).first?.id, "a", "Most iconic follows ip")
        XCTAssertEqual(m.place(id: "c")!.featuredScore, 60, "no fs: the icon points stand in")
        let az = m.list(.all, sort: .name, search: "", here: nil).map(\.name)
        XCTAssertEqual(az, az.sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }, "A to Z")
        // a classic opens by distance only for a reader in Maine
        XCTAssertEqual(Guide.lobster.defaultSort(inState: true), .nearest)
        XCTAssertEqual(Guide.lobster.defaultSort(inState: false), .featured)
        XCTAssertEqual(Guide.all.defaultSort(inState: true), .name)
        XCTAssertTrue(LocationService.isInState(oldPort.coordinate))
        XCTAssertTrue(LocationService.isInState(CLLocationCoordinate2D(latitude: 47.25, longitude: -68.59)), "Fort Kent")
        XCTAssertTrue(LocationService.isInState(CLLocationCoordinate2D(latitude: 44.86, longitude: -66.98)), "Lubec")
        XCTAssertFalse(LocationService.isInState(CLLocationCoordinate2D(latitude: 37.3349, longitude: -122.009)))
        XCTAssertFalse(LocationService.isInState(CLLocationCoordinate2D(latitude: 42.36, longitude: -71.06)), "Boston")
    }

    /// Lists are built off the main thread and remembered; the result is the same list.
    func testListsBuiltInTheBackground() async throws {
        let m = try await sampleModel()
        let key = m.listKey(.all, sort: .name, search: "portland", here: nil)
        XCTAssertNil(m.cachedList(key))
        let built = await m.buildList(key, here: nil)
        XCTAssertEqual(built.map(\.id), m.list(.all, sort: .name, search: "portland", here: nil).map(\.id))
        XCTAssertEqual(m.cachedList(key)?.map(\.id), built.map(\.id))
        let a = CLLocation(latitude: 43.6575, longitude: -70.2544), b = CLLocation(latitude: 43.65755, longitude: -70.25445)
        XCTAssertEqual(m.listKey(.all, sort: .name, search: "", here: a), m.listKey(.all, sort: .name, search: "", here: nil))
        XCTAssertEqual(m.listKey(.nearMe, sort: .nearest, search: "", here: a), m.listKey(.nearMe, sort: .nearest, search: "", here: b))
        XCTAssertNotEqual(m.listKey(.nearMe, sort: .nearest, search: "", here: a), m.listKey(.nearMe, sort: .nearest, search: "", here: nil))
    }

    /// Filters are the lists' own: Home counts, the map and Surprise me show each guide whole, and only the two toggles
    /// outlast the visit.
    func testFiltersStayInTheLists() async throws {
        let defaults = UserDefaults(suiteName: "filters-\(UUID().uuidString)")!
        let m = try await sampleModel(defaults: defaults)
        m.filters = Filters(town: "Bangor", cuisine: "Seafood", hideChains: true, confirmedOnly: true, includeNonRestaurants: true)
        XCTAssertEqual(m.count(.lobster), 2, "Home counts ignore a town filter")
        XCTAssertEqual(m.mapPlaces(.lobster).count, 2, "so does the map")
        XCTAssertNotNil(m.randomPick(from: [.lobster], excluding: nil), "and Surprise me")
        XCTAssertTrue(m.list(.lobster, sort: .name, search: "", here: nil).isEmpty, "the list itself is filtered")
        let next = try await sampleModel(defaults: defaults)
        XCTAssertEqual(next.filters, Filters(hideChains: true, confirmedOnly: true), "town, cuisine and non-restaurants reset on launch")
    }

    /// One copy of what's open, for both layouts: an iPad window going narrow (or back) keeps the list and the place.
    func testLayoutChangeKeepsListAndPlace() async throws {
        let m = try await sampleModel()
        let nunans = m.place(id: "c")!, reds = m.place(id: "a")!
        m.tab = .guides; m.selectedGuide = .lobster; m.selectedPlace = nunans
        m.syncToCompact()
        XCTAssertEqual(m.guidesPath, [.guide(.lobster), .place(nunans)])
        m.guidesPath = [.guide(.icons), .place(reds)]
        m.syncToRegular()
        XCTAssertEqual(m.selectedGuide, .icons)
        XCTAssertEqual(m.selectedPlace, reds)
        m.guidesPath = [.guide(.diners)]
        m.syncToRegular()
        XCTAssertEqual(m.selectedGuide, .diners)
        XCTAssertNil(m.selectedPlace, "a list with no place open")
        m.tab = .map; m.selectedPlace = nunans
        m.syncToCompact()
        XCTAssertEqual(m.mapPath, [nunans])
        m.mapPath = [reds]
        m.syncToRegular()
        XCTAssertEqual(m.selectedPlace, reds)
        m.tab = .saved; m.savedPath = []
        m.syncToRegular()
        XCTAssertNil(m.selectedPlace)
    }

    func testFiltersSavedPlacesAndLabels() async throws {
        let m = try await sampleModel()
        m.filters.hideChains = true
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Dunkin'" })
        m.filters = Filters(confirmedOnly: true)
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.id == "f" }, "single listings drop out")
        XCTAssertTrue(m.list(.all, sort: .name, search: "", here: nil).contains { $0.id == "j" }, "hand-checked counts as confirmed")
        XCTAssertEqual(m.list(.dairy, sort: .name, search: "", here: nil).map(\.id), ["j"])
        m.filters = Filters(town: "Portland")
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)), ["b", "k"])
        let p = m.place(id: "b")!
        m.toggleSaved(p)
        XCTAssertEqual(m.savedPlaces.map(\.id), ["b"])
        m.toggleSaved(p)
        XCTAssertTrue(m.savedPlaces.isEmpty)
        XCTAssertEqual(m.matchRate(for: m.place(id: "b")!), "44%")
        XCTAssertNil(m.matchRate(for: m.place(id: "a")!), "licensed places don't cite a listing rate")
        XCTAssertEqual(m.place(id: "a")!.jamesBeardLabel, "America's Classic")
        XCTAssertEqual(m.place(id: "a")!.licenseKind, "Restaurant")
        XCTAssertEqual(m.place(id: "a")!.jurisdiction, .bablo)
        XCTAssertEqual(m.place(id: "h")!.host, "Hollywood Casino Bangor")
        XCTAssertEqual(m.place(id: "c")!.jamesBeardLabel, "James Beard nominee")
        XCTAssertTrue(m.place(id: "c")!.isSeasonal)
        XCTAssertEqual(PlaceDetailView.date("2026-03-30"), "Mar 30, 2026")
    }

    /// Lewiston's official result: Pass or Fail with its date and report, never a grade.
    func testLewistonInspections() async throws {
        let m = try await sampleModel()
        let pass = try XCTUnwrap(m.place(id: "d")!.inspection)
        XCTAssertTrue(pass.passed)
        XCTAssertEqual(pass.resultText, "Passed")
        XCTAssertEqual(pass.reportURL?.host, "www.lewistonmaine.gov")
        let fail = try XCTUnwrap(m.place(id: "i")!.inspection)
        XCTAssertFalse(fail.passed)
        XCTAssertEqual(fail.resultText, "Failed")
        XCTAssertEqual(fail.n, "LISBON ST PIZZA", "the name the city inspected it under")
        XCTAssertNil(m.place(id: "a")!.inspection, "no result where the city posts none")
        XCTAssertEqual(m.lewistonFetched, "2026-10-08")
        XCTAssertNil(Inspection(r: "Pass", d: nil, u: "javascript:alert(1)", n: nil).reportURL, "only a web link")
    }

    /// Call only dials a US number; Website only opens a web address.
    func testPhonesAndWebsites() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.place(id: "a")!.phone, "+12078825010")
        XCTAssertEqual(m.place(id: "a")!.phoneText, "(207) 882-5010")
        XCTAssertNil(m.place(id: "b")!.phone, "+20… would dial Egypt")
        XCTAssertNil(m.place(id: "d")!.phone, "not E.164")
        XCTAssertEqual(m.place(id: "a")!.website?.absoluteString, "https://www.example-reds.com/")
        XCTAssertNil(m.place(id: "b")!.website, "javascript: is never a link")
        XCTAssertNil(m.place(id: "c")!.website, "a scheme-less value isn't guessed at")
        XCTAssertNil(Place.usPhone("+1207555123"), "too short")
        XCTAssertNil(Place.usPhone("+11075551234"), "no area code starts with 1")
    }

    /// The build's own dates and sources, not ones written into the app.
    func testDataMeta() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.dataVersion, "abc123def456")
        XCTAssertEqual(m.researchChecked, "October 2026")
        XCTAssertEqual(m.sourceYears, "2025 or 2026")
        XCTAssertEqual(m.overtureRelease, "2026-09-23.1")
        XCTAssertEqual(m.licenseDate, "Oct 1, 2026")
        // an older file without the new keys (and with a license number) still opens
        let old = """
            {"generated":"2026-10-08","cities":["Portland"],"villages":[],"cuisines":["Pizza"],"brands":[],"hosts":[],"sources":["meta"],
             "count_restaurants":1,"calibration":{},
             "places":[{"id":"a","n":"Some Pizza","c":0,"cu":0,"t":1,"s":0,"lic":"RES-25-0000001","ph":"(207) 555-1234","w":"somepizza.com"}]}
            """
        let o = try await sampleModel(json: old)
        XCTAssertEqual(o.dataVersion, "2026-10-08", "Spotlight keys on the date when there's no hash")
        XCTAssertEqual(o.researchChecked, "October 2026")
        XCTAssertNil(o.overtureRelease)
        XCTAssertNil(o.licenseDate)
    }

    /// Saved places follow a place whose id changed, through a chain of changes, and the new ids are what's kept.
    func testSavedPlacesFollowAliases() async throws {
        let defaults = UserDefaults(suiteName: "alias-\(UUID().uuidString)")!
        defaults.set(["older-b", "old-b", "b", "gone", "loop1"], forKey: "saved")
        let m = try await sampleModel(defaults: defaults)
        XCTAssertEqual(m.savedPlaces.map(\.id), ["b"], "three ids for Amato's are one saved place")
        XCTAssertEqual(Set(defaults.stringArray(forKey: "saved") ?? []), ["b", "gone", "loop1"], "the remapped set is stored")
        XCTAssertEqual(m.place(id: "older-b")?.id, "b", "an old Spotlight id opens today's place")
        XCTAssertNil(m.place(id: "gone"), "an id that's gone opens nothing")
        XCTAssertNil(m.place(id: "loop1"), "a loop in the aliases ends")
    }

    func testSpotlightIndexesChainOriginalsNotBranches() throws {
        let file = try JSONDecoder().decode(DataFile.self, from: Data("""
            {"generated":"2026-10-08","cities":["Portland","Lewiston"],"villages":[],"cuisines":["Sandwiches & Deli"],"brands":[],"hosts":[],"sources":["meta"],
             "count_restaurants":3,"calibration":{},
             "places":[{"id":"pt","n":"Amato's","c":0,"cu":0,"t":1,"s":0,"hc":1,"ch":12},
                       {"id":"lw","n":"Amato's","c":1,"cu":0,"t":1,"s":0,"hc":1,"ch":12,"br":"Amato's, Portland"},
                       {"id":"x","n":"Some Deli","c":1,"cu":0,"t":1,"s":0}]}
            """.utf8))
        let places = file.places.map { Place($0, file: file) }
        XCTAssertEqual(SpotlightIndexer.featured(places).map(\.id), ["pt"])
        // and "Hide chains" keeps the original, not the branch
        XCTAssertTrue(Filters(hideChains: true).allows(places[0]))
        XCTAssertFalse(Filters(hideChains: true).allows(places[1]))
    }

    /// The real bundled file decodes and holds the guides the app promises.
    func testBundledData() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "bundle-\(UUID().uuidString)")!)
        await m.load()
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        XCTAssertGreaterThan(m.restaurantCount, 4_000)
        XCTAssertGreaterThan(m.towns.count, 280, "most of Maine's towns with a restaurant")
        XCTAssertGreaterThan(m.count(.lobster), 25)
        XCTAssertGreaterThan(m.count(.dairy), 25)
        // Icons: James Beard or other honors, or 40+ years at the address (not every hand-checked place)
        XCTAssertGreaterThan(m.count(.icons), 10)
        let iconYear = (Int(m.generated.prefix(4)) ?? 2026) - 40
        for p in m.places where Guide.icons.includes(p) {
            XCTAssertTrue(p.jamesBeard != nil || p.otherHonors != nil || (p.founded ?? 9999) <= iconYear, "\(p.name) (\(p.city ?? "")) isn't an icon")
        }
        XCTAssertEqual(Set(m.places.map(\.id)).count, m.places.count, "ids are unique")
        XCTAssertTrue(m.places.contains { $0.name == "Bagaduce Lunch" && $0.jamesBeardLabel == "America's Classic" && $0.city == "Penobscot" },
                      "Bagaduce Lunch is in Penobscot (James Beard files it under Brooksville)")
        XCTAssertTrue(m.list(.lobster, sort: .name, search: "red's eats", here: nil).contains { $0.city == "Wiscasset" && $0.isSeasonal },
                      "a hand-checked shack keeps its check (and its season) through duplicate merging")
        XCTAssertFalse(m.places.contains { $0.name.range(of: #"gentlem[ae]n'?s club|strip club|exotic dancer|cabaret"#, options: [.regularExpression, .caseInsensitive]) != nil },
                       "adult clubs aren't restaurants")
        XCTAssertFalse(m.places.contains { ($0.website?.absoluteString ?? "").range(
            of: #"yelp\.com|business\.site|google\.com|groupon\.com|yellowpages\.com|toasttab\.com|pressherald\.com"#, options: .regularExpression) != nil },
                       "directory and news links were checked out")
        // Lewiston's official results: only in Lewiston, always with a date, a result and the city's own report link
        let inspected = m.places.filter { $0.inspection != nil }
        XCTAssertGreaterThan(inspected.count, 30)
        for p in inspected {
            XCTAssertEqual(p.city, "Lewiston", "\(p.name) has a Lewiston result outside Lewiston")
            XCTAssertNotNil(p.inspection?.d, "\(p.name): an official result always shows its date")
            XCTAssertTrue(["Pass", "Fail"].contains(p.inspection?.r ?? ""), "\(p.name): Pass or Fail only")
            XCTAssertEqual(p.inspection?.reportURL?.host, "www.lewistonmaine.gov")
        }
        // Oldest Places: 40 or more years at the address; casino labels only at the casino's own address
        let cutoff = (Int(m.generated.prefix(4)) ?? 2026) - 40
        XCTAssertTrue(m.places.filter { Guide.oldest.includes($0) }.allSatisfy { ($0.founded ?? 9999) <= cutoff })
        for p in m.places where p.host != nil {
            XCTAssertTrue((p.host == "Hollywood Casino Bangor" && p.city == "Bangor" && (p.address ?? "").hasPrefix("500 Main"))
                          || (p.host == "Oxford Casino" && p.city == "Oxford" && (p.address ?? "").hasPrefix("777 Casino")),
                          "\(p.name) at \(p.address ?? "") isn't at its casino")
        }
        XCTAssertFalse(Set(m.places.compactMap(\.village)).contains { $0.range(of: #"\b(TWP|PLT|Township|Plantation)\b|\bT\d+ ?R\d+"#, options: .regularExpression) != nil },
                       "township codes aren't village names")
        // hand-checked places stay in their guides with "Only confirmed places" on
        func n(_ g: Guide) -> Int { m.list(g, sort: .name, search: "", here: nil).count }
        let lobster = n(.lobster), dairy = n(.dairy)
        XCTAssertEqual(lobster, m.count(.lobster), "a list without filters matches its Home card")
        m.filters.confirmedOnly = true
        XCTAssertEqual(n(.lobster), lobster)
        XCTAssertEqual(n(.dairy), dairy)
        m.filters = Filters(hideChains: true)
        XCTAssertTrue(m.list(.sandwiches, sort: .name, search: "", here: nil).contains { $0.name == "Amato's" && $0.address == "71 India St" },
                      "the original Amato's stays with Hide chains on")
        m.filters = Filters()
        let spotlight = SpotlightIndexer.featured(m.places)
        XCTAssertTrue(spotlight.contains { $0.name == "Red's Eats" })
        XCTAssertFalse(spotlight.contains { $0.branchOf != nil && $0.isChain })
    }

    /// The raw file, before decoding (PlaceRecord ignores unknown keys, so a leak would decode silently).
    private func bundledJSON() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle(for: AppModel.self).url(forResource: "places", withExtension: "json") ?? Bundle.main.url(forResource: "places", withExtension: "json"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }

    /// The app ships no Google-derived data: no rating, review, price or Google Maps field anywhere in the file.
    func testBundledDataHasNoRatingsOrReviews() throws {
        var bad: Set<String> = []
        func walk(_ v: Any) {
            if let d = v as? [String: Any] {
                for (k, x) in d {
                    let l = k.lowercased()
                    if ["rating", "ratings", "reviews", "price"].contains(l) || l.hasPrefix("gmap") || l.hasPrefix("review") { bad.insert(k) }
                    walk(x)
                }
            } else if let a = v as? [Any] {
                a.forEach(walk)
            }
        }
        walk(try bundledJSON())
        XCTAssertEqual(bad, [], "Google-style fields in places.json")
    }

    /// Every phone dials the US, every website is a web address, and no license holder's name or number ships.
    func testBundledPhonesWebsitesAndLicenses() throws {
        let json = try bundledJSON()
        let places = try XCTUnwrap(json["places"] as? [[String: Any]])
        let phones = places.compactMap { $0["ph"] as? String }
        XCTAssertFalse(phones.isEmpty)
        let badPhones = phones.filter { $0.range(of: #"^\+1[2-9]\d{9}$"#, options: .regularExpression) == nil }
        XCTAssertEqual(badPhones.count, 0, "not +1XXXXXXXXXX: \(badPhones.prefix(5))")
        let unscored = places.filter { $0["hc"] as? Int == 1 && $0["fs"] == nil }.compactMap { $0["n"] as? String }
        XCTAssertEqual(unscored.count, 0, "every hand-checked place has a featured score: \(unscored.prefix(5))")
        let sites = places.compactMap { $0["w"] as? String }
        let badSites = sites.filter { s in URL(string: s).map { !["http", "https"].contains($0.scheme?.lowercased() ?? "") } ?? true }
        XCTAssertEqual(badSites.count, 0, "not http(s): \(badSites.prefix(5))")
        XCTAssertFalse(places.contains { $0["lic"] != nil }, "license numbers don't ship")
        let raw = String(data: try JSONSerialization.data(withJSONObject: json), encoding: .utf8) ?? ""
        XCTAssertFalse(raw.contains("Legal Entity"), "BABLO's legal entity names never ship")
        let entity = places.compactMap { $0["n"] as? String }.filter { $0.range(of: #"\b(?:LLC|L\.L\.C\.|Inc\.?|Corp\.?)$"#, options: .regularExpression) != nil }
        XCTAssertEqual(entity, [], "a legal entity isn't a restaurant name")
    }

    /// Ids are stable across rebuilds: saved places and Spotlight entries depend on it.
    func testBundledPinnedIds() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "ids-\(UUID().uuidString)")!)
        await m.load()
        XCTAssertEqual(m.places.first { $0.name == "Red's Eats" && $0.city == "Wiscasset" }?.id, Self.redsID)
        XCTAssertEqual(m.places.first { $0.name == "Moody's Diner" && $0.city == "Waldoboro" }?.id, Self.moodysID)
        XCTAssertEqual(m.places.first { $0.name == "Amato's" && $0.address == "71 India St" }?.id, Self.amatosID)
    }
    static let redsID = "30d6d0e9b936", moodysID = "5d77988990d6", amatosID = "bb04bc817c5e"

    /// Natural searches on the real data.
    func testBundledSearch() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "search-\(UUID().uuidString)")!)
        await m.load()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertFalse(ids("lobster roll portland").isEmpty)
        XCTAssertEqual(ids("lobster roll in portland"), ids("lobster roll portland"))
        XCTAssertFalse(ids("cape neddick").isEmpty)
        XCTAssertEqual(ids("near cape neddick"), ids("cape neddick"))
        XCTAssertEqual(ids("pizza near me"), ids("pizza"))
        let sopo = m.list(.all, sort: .name, search: "south portland", here: nil)
        XCTAssertFalse(sopo.isEmpty)
        XCTAssertTrue(sopo.allSatisfy { $0.city == "South Portland" || $0.nameText.contains(" south portland") }, "South Portland, not Portland")
        for q in ["route 1", "us 1"] {
            XCTAssertTrue(m.list(.all, sort: .name, search: q, here: nil).contains { ($0.address ?? "").contains("US-1") || ($0.address ?? "").contains("Route 1") },
                          "\(q) finds a Route 1 address")
        }
    }
}

/// QA 2026-10-19, P1 3a: the support address is nick@eatsranked.com (Nick, 2026-10-12). The old Gmail address must not come back
/// anywhere in the app's source or bundled files.
final class SupportEmailTests: XCTestCase {
    func testSupportEmailIsEatsRanked() {
        XCTAssertEqual(Links.supportEmail, "nick@eatsranked.com")
    }

    func testNoGmailInAppSource() throws {
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("MaineEats")
        XCTAssertGreaterThan(SupportEmailScan.textFiles(under: root).count, 5, "the app's source folder wasn't found")
        XCTAssertEqual(SupportEmailScan.hits(under: root), [], "the app's source still has a Gmail address")
    }

    /// The guard fires on a broken copy: a folder with one planted Gmail address.
    func testGmailGuardCatchesABrokenCopy() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir.appendingPathComponent("App"), withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        try "static let supportEmail = \"someone@GMAIL.com\"\n".write(to: dir.appendingPathComponent("App/Links.swift"), atomically: true, encoding: .utf8)
        try "{\"ok\": \"nick@eatsranked.com\"}".write(to: dir.appendingPathComponent("App/data.json"), atomically: true, encoding: .utf8)
        XCTAssertEqual(SupportEmailScan.hits(under: dir), ["App/Links.swift"])
    }
}

enum SupportEmailScan {
    static let textExtensions: Set<String> = ["swift", "plist", "json", "strings", "xcstrings", "xcprivacy", "md", "txt", "html", "entitlements"]

    static func textFiles(under root: URL) -> [URL] {
        let all = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { textExtensions.contains($0.pathExtension.lowercased()) }
    }

    /// paths (relative to root) of text files that mention gmail.com, in any case
    static func hits(under root: URL) -> [String] {
        let base = root.resolvingSymlinksInPath().path + "/"
        return textFiles(under: root).compactMap { url in
            guard let text = try? String(contentsOf: url, encoding: .utf8),
                  text.range(of: "gmail.com", options: .caseInsensitive) != nil else { return nil }
            return url.resolvingSymlinksInPath().path.replacingOccurrences(of: base, with: "")
        }.sorted()
    }
}

/// QA 2026-10-19, P1 #13: outbound links ship without tracking tags (ref=google, referrer=google_food_ordering, cn_channel, utm_* …).
/// pipeline/tracking_params.py strips them in the export; these are the same rules.
final class TrackingParamTests: XCTestCase {
    func testNoTrackingParametersInBundledLinks() throws {
        let files = TrackingParams.bundledJSON()
        XCTAssertFalse(files.isEmpty, "no bundled JSON found")
        var hits: [String] = []
        for url in files {
            let text = try String(contentsOf: url, encoding: .utf8)
            hits += TrackingParams.tracked(in: text).map { "\(url.lastPathComponent): \($0)" }
        }
        XCTAssertEqual(hits, [], "links with tracking parameters in the app's bundled data")
    }

    /// The guard fires on a broken copy (four kinds of tracking tag, one in escaped JSON) and leaves a store's own parameters alone.
    func testTrackingGuardCatchesABrokenCopy() {
        let broken = #"[{"w":"https:\/\/places.example.com\/menu?ref=google"},{"w":"https://a.example/?utm_source=gmb&store=4"},"#
            + #"{"w":"https://b.example/x?referrer=google_food_ordering"},{"w":"https://c.example/order/1?cn_channel=cn_google"}]"#
        XCTAssertEqual(TrackingParams.tracked(in: broken).count, 4)
        let clean = #"[{"w":"https://order.example.com/menu?restaurantId=51&location=7"},{"w":"https://shop.example.com/?cid=12&ref=gs"}]"#
        XCTAssertEqual(TrackingParams.tracked(in: clean), [])
    }
}

enum TrackingParams {
    /// tracking by name, whatever the value
    static let keys = try! NSRegularExpression(pattern: #"^(?:utm[_-].*|gclid|gbraid|wbraid|dclid|fbclid|msclkid|mc_cid|mc_eid|_ga|_gl|igsh|"#
        + #"igshid|mibextid|srsltid|cn_channel|y_source|rwg_token|olonwp|ost_redirect_attribution|cmpid|yext_?.*)$"#, options: [.caseInsensitive])
    /// tracking only with these values
    static let values: [String: String] = ["ref": #"^(?:google|gmb|gbp|yext|bookmarks)\b"#, "referrer": "^google",
                                           "source": #"^(?:google|gmb|gbp|yext)\b"#, "cid": "^RF:YXT", "cmp": "^OKC-"]

    /// every .json file in the app bundle, subfolders included
    static func bundledJSON() -> [URL] {
        let all = FileManager.default.enumerator(at: Bundle.main.bundleURL, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { $0.pathExtension == "json" && !$0.path.contains("/PlugIns/") }
    }

    static func isTracking(_ key: String, _ value: String) -> Bool {
        let k = key.trimmingCharacters(in: .whitespaces)
        if keys.firstMatch(in: k, range: NSRange(k.startIndex..., in: k)) != nil { return true }
        guard let pattern = values[k.lowercased()] else { return false }
        return value.trimmingCharacters(in: .whitespaces).range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
    }

    /// links in a JSON text whose query carries a tracking parameter
    static func tracked(in text: String) -> [String] {
        let t = text.replacingOccurrences(of: "\\/", with: "/")
        let rx = try! NSRegularExpression(pattern: #"https?://[^\s"'<>\\]+"#)
        return rx.matches(in: t, range: NSRange(t.startIndex..., in: t)).compactMap { m -> String? in
            let s = String(t[Range(m.range, in: t)!])
            guard let q = s.split(separator: "?", maxSplits: 1).dropFirst().first else { return nil }
            let query = q.split(separator: "#", maxSplits: 1, omittingEmptySubsequences: false).first ?? ""
            for part in query.split(separator: "&") {
                let kv = part.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
                let k = String(kv[0]).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String(kv[0])
                let v = kv.count > 1 ? (String(kv[1]).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String(kv[1])) : ""
                if isTracking(k, v) { return s }
            }
            return nil
        }
    }
}
