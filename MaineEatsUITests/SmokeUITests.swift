import XCTest
import CoreLocation

/// Taps through every screen and control a reviewer is likely to touch, on iPhone (tabs) and iPad (split view).
/// Pass = nothing crashes and each screen shows what it should. Slow (network place cards, map tiles), so CI runs
/// only the unit tests; run this before every App Store submission:
/// xcodebuild test -scheme MaineEats -only-testing:MaineEatsUITests -destination 'id=<sim>'
final class SmokeUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        // the location prompt can appear on Near Me or the Nearest sort; answer it like a first-time user would
        addUIInterruptionMonitor(withDescription: "Location") { alert in
            for b in ["Allow While Using App", "Allow Once", "Don’t Allow", "Don't Allow"] where alert.buttons[b].exists {
                alert.buttons[b].tap(); return true
            }
            return false
        }
        app.launch()
    }

    private func button(containing text: String) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    /// A Home guide card, by its identifier: a text match could land on the Shack season card, which also says "clam shacks".
    private static let guideIDs = ["Lobster Shacks & Rolls": "lobster", "Clam Shacks": "clams", "Red Snappers & Italians": "sandwiches",
                                   "Whoopie Pies & Donuts": "sweets", "Diners": "diners", "Oyster Bars": "oysters", "Dairy Bars": "dairy",
                                   "Maine Icons": "icons", "Oldest Places": "oldest", "Near Me": "nearMe", "All Restaurants": "all"]
    private func card(_ title: String) -> XCUIElement { app.buttons["guide.\(Self.guideIDs[title] ?? title)"] }

    private func text(containing text: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func waitFor(_ e: XCUIElement, _ seconds: TimeInterval = 10, _ what: String) {
        XCTAssertTrue(e.waitForExistence(timeout: seconds), "missing: \(what)")
    }

    /// Waits for an element's label to contain a text (a label changes in place, so existence alone proves nothing).
    private func waitForLabel(_ e: XCUIElement, containing t: String, _ seconds: TimeInterval = 10, _ what: String) {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if e.exists && e.label.contains(t) { return }
            Thread.sleep(forTimeInterval: 0.5)
        }
        XCTFail("missing: \(what) (label: \(e.exists ? e.label : "none"))")
    }

    /// The map's own hint and note, by identifier: a query that matches text across a map full of pins can time out.
    private var mapHint: XCUIElement { app.staticTexts["mapHint"] }

    /// Double-taps the middle of the map by screen point: the map's frame is read once, while it's statewide and nearly empty,
    /// because resolving the map element again later means snapshotting every pin.
    private func zoomMapIn(times: Int) {
        let f = app.maps.firstMatch.frame
        let middle = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: f.midX, dy: f.midY + f.height * 0.05))
        for _ in 0..<times { middle.doubleTap(); Thread.sleep(forTimeInterval: 0.8) }
    }

    private func scrollTo(_ e: XCUIElement, max: Int = 8) {
        var n = 0
        while !e.isHittable && n < max { app.swipeUp(); n += 1 }
    }

    private var isPad: Bool { UIDevice.current.userInterfaceIdiom == .pad }

    /// A map layer chip: the row scrolls sideways (six layers don't fit on a phone), so bring the chip into view first.
    /// (isHittable throws for a chip scrolled off the screen, so this reads the chip's frame instead.)
    private func tapLayer(_ name: String) {
        let chip = app.buttons[name]
        waitFor(chip, 5, "map layer \(name)")
        let row = app.scrollViews["layers"], screen = app.windows.firstMatch.frame
        for _ in 0..<6 {
            let mid = chip.frame.midX
            if mid > screen.minX + 20 && mid < screen.maxX - 20 { break }
            if mid >= screen.maxX - 20 { row.swipeLeft() } else { row.swipeRight() }
            Thread.sleep(forTimeInterval: 0.4)
        }
        chip.tap()
    }

    /// Place detail: Apple Maps card (or the "not on Apple Maps" fallback), save, share.
    private func exerciseDetail(named name: String) {
        waitFor(text(containing: name), 10, "detail for \(name)")
        let card = button(containing: "Ratings, hours")
        waitFor(card, 5, "Apple Maps button")
        card.tap()
        // either Apple's place card sheet or our fallback alert
        let fallback = app.alerts["Not on Apple Maps"]
        let deadline = Date().addingTimeInterval(15)
        var opened = false
        while Date() < deadline && !opened {
            if fallback.exists { fallback.buttons["OK"].tap(); opened = true; break }
            // Apple's place card closes with "Dismiss"
            let close = app.buttons.matching(NSPredicate(format: "label IN[c] {'Dismiss', 'Close'} OR identifier IN[c] {'Dismiss', 'Close'}")).firstMatch
            if close.exists && close.isHittable { close.tap(); opened = true; break }
            Thread.sleep(forTimeInterval: 0.5)
        }
        if !opened { app.swipeDown(velocity: .fast) }   // dismiss the sheet if its close button isn't labelled
        XCTAssertEqual(app.state, .runningForeground)
        // the heart in the navigation bar (the tab bar's "Saved" is another button)
        let save = app.navigationBars.buttons["Save"], unsave = app.navigationBars.buttons["Remove from Saved"]
        if save.waitForExistence(timeout: 3) {
            save.tap()
            // on iPad Apple's card is a centered sheet that a tap outside dismisses; that first tap may only close it
            if !unsave.waitForExistence(timeout: 2) && save.exists { save.tap() }
            waitFor(unsave, 3, "the heart turns to Remove from Saved")
        }
        let share = app.buttons["Share"]
        if share.exists {
            share.tap()
            Thread.sleep(forTimeInterval: 1.5)
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR label ==[c] 'Cancel'")).firstMatch
            if close.exists { close.tap() } else { app.swipeDown(velocity: .fast) }
        }
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// A clean start for each section, so one screen's navigation state can't strand the next (also proves saved places persist).
    private func fresh() {
        app.terminate()
        app.launch()
        waitFor(text(containing: "Lobster shack & clam guide"), 15, "home header")
    }

    func testTourEveryScreen() throws {
        if isPad { try padTour(); return }
        waitFor(text(containing: "Lobster shack & clam guide"), 15, "home header")

        // Lobster Shacks & Rolls: sort, filters, search
        card("Lobster Shacks & Rolls").tap()
        waitFor(app.navigationBars["Lobster Shacks & Rolls"], 5, "lobster list")
        waitFor(text(containing: "places ·"), 5, "list count header")
        app.buttons["Sort"].tap()
        waitFor(app.buttons["Oldest first"], 3, "sort menu"); app.buttons["Oldest first"].tap()
        waitFor(text(containing: "Oldest first"), 3, "sorted header")
        app.buttons["Filters"].tap()
        waitFor(app.navigationBars["Filters"], 5, "filters sheet")
        // tap the switch itself (its right edge) once the sheet has finished sliding up; a tap on the middle of a Toggle row
        // lands on the label
        let hide = app.switches.matching(NSPredicate(format: "label CONTAINS 'Hide chains'")).firstMatch
        waitFor(hide, 3, "hide-chains toggle")
        Thread.sleep(forTimeInterval: 1.5)
        hide.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        let on = expectation(for: NSPredicate(format: "value == '1'"), evaluatedWith: hide)
        wait(for: [on], timeout: 5)
        app.buttons["Done"].tap()
        waitFor(text(containing: "1 filter on"), 3, "active-filter row")
        button(containing: "Clear").tap()
        XCTAssertFalse(text(containing: "filter on").waitForExistence(timeout: 1), "filters cleared")
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 3, "search field"); search.tap(); search.typeText("wiscasset")
        waitFor(button(containing: "Red's Eats"), 5, "wiscasset finds Red's Eats")

        // the full directory → a known place → Apple Maps card, save, share
        fresh()
        button(containing: "Search every restaurant").tap()
        // the Home search box opens the directory ready to type: no second tap on the field
        waitFor(app.searchFields.firstMatch, 5, "directory search")
        waitFor(app.keyboards.firstMatch, 5, "keyboard up for the search field")
        app.typeText("moodys diner")
        let moodys = button(containing: "Moody's Diner")
        waitFor(moodys, 5, "Moody's Diner in results"); moodys.tap()
        exerciseDetail(named: "MOODY'S DINER")

        // every other guide opens with a list
        for g in ["Clam Shacks", "Red Snappers & Italians", "Whoopie Pies & Donuts", "Diners", "Oyster Bars", "Dairy Bars", "Maine Icons", "Oldest Places", "Near Me", "All Restaurants"] {
            fresh()
            let c = card(g)
            scrollTo(c)
            c.tap()
            if g == "Near Me" { app.swipeDown() }   // any interaction lets the monitor answer the location prompt (a tap could open a row)
            waitFor(app.navigationBars[g], 5, "\(g) list")
            if g != "Near Me" { waitFor(text(containing: "places ·"), 5, "\(g) count header") }
        }

        // surprise me
        fresh()
        let surprise = button(containing: "Surprise me")
        scrollTo(surprise); surprise.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a random Maine classic")

        // Map: every layer
        fresh()
        app.tabBars.buttons["Map"].tap()
        for l in ["Clam shacks", "Sweets", "Dairy bars", "Icons", "Everything", "Lobster"] {
            tapLayer(l)
            // statewide, Everything asks you to zoom in instead of drawing 4,000 pins
            waitForLabel(mapHint, containing: l == "Everything" ? "Zoom in to a town" : "tap a pin", 5, "map hint for \(l)")
        }

        // Saved: Moody's Diner saved earlier survived relaunches; remove it
        app.tabBars.buttons["Saved"].tap()
        let saved = button(containing: "Moody's Diner")
        waitFor(saved, 5, "saved place")
        saved.swipeLeft()
        if app.buttons["Remove"].waitForExistence(timeout: 2) { app.buttons["Remove"].tap() }

        // About
        app.tabBars.buttons["About"].tap()
        waitFor(text(containing: "MAINE EATS"), 5, "about header")
        let privacy = app.buttons["Privacy policy"].exists ? app.buttons["Privacy policy"] : app.links["Privacy policy"]
        scrollTo(privacy)
        XCTAssertTrue(privacy.exists, "privacy link")
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// iPad sidebar row. The rows themselves carry no label; the name is a text inside the "Sidebar" list.
    private func sidebarItem(_ name: String) -> XCUIElement {
        app.collectionViews["Sidebar"].staticTexts[name]
    }

    private func padTour() throws {
        // iPad opens on Home in portrait, and a Home card opens its guide
        waitFor(text(containing: "Lobster shack & clam guide"), 15, "Home at launch in portrait")
        card("Lobster Shacks & Rolls").tap()
        waitFor(app.navigationBars["Lobster Shacks & Rolls"], 5, "a Home card opens its guide on iPad")
        XCUIDevice.shared.orientation = .landscapeLeft     // all three columns
        Thread.sleep(forTimeInterval: 1.5)
        // a sort picked in one guide doesn't carry over to the next
        app.buttons["Sort"].tap()
        waitFor(app.buttons["A to Z"], 3, "sort menu"); app.buttons["A to Z"].tap()
        waitFor(text(containing: "· A to Z"), 3, "sorted A to Z")
        sidebarItem("Oldest Places").tap()
        waitFor(app.navigationBars["Oldest Places"], 5, "Oldest Places list")
        waitFor(text(containing: "· Oldest first"), 3, "Oldest Places in its own order")
        for g in ["Clam Shacks", "Red Snappers & Italians", "Maine Icons", "Diners", "Oldest Places", "All Restaurants", "Lobster Shacks & Rolls"] {
            let item = sidebarItem(g)
            waitFor(item, 5, "sidebar \(g)"); item.tap()
            waitFor(app.navigationBars[g], 5, "\(g) list")
        }
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 5, "search"); search.tap(); search.typeText("five islands")
        let row = button(containing: "Five Islands Lobster")
        waitFor(row, 5, "Five Islands Lobster Co. in results"); row.tap()
        exerciseDetail(named: "FIVE ISLANDS LOBSTER CO.")
        for s in ["Map", "Saved", "About"] {
            let item = sidebarItem(s)
            waitFor(item, 5, "sidebar \(s)"); item.tap()
        }
        waitFor(text(containing: "MAINE EATS"), 5, "about header")
        XCUIDevice.shared.orientation = .portrait
        Thread.sleep(forTimeInterval: 1.5)
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testEverythingLayerFillsInWhenZoomed() {
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Lobster shack & clam guide"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        tapLayer("Everything")
        waitForLabel(mapHint, containing: "Zoom in to a town", 5, "zoom hint statewide")
        zoomMapIn(times: 6)
        waitForLabel(mapHint, containing: "here", 15, "restaurants appear once zoomed in")
        XCTAssertEqual(app.state, .runningForeground)
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// "My location" moves the map to you at town level, which also fills in the Everything layer.
    /// The simulator's own location resets to Apple's campus, so each location test sets where "you" are.
    private func openMapEverything(at here: CLLocation) {
        // a clean slate: scripts/capture-screenshots.sh revokes location, and the last test left the simulator somewhere else.
        // Resetting asks again (the interruption monitor allows it), and relaunching makes the app's first fix this one.
        app.resetAuthorizationStatus(for: .location)
        XCUIDevice.shared.location = XCUILocation(location: here)
        app.terminate(); app.launch()
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Lobster shack & clam guide"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        tapLayer("Everything")
        waitForLabel(mapHint, containing: "Zoom in to a town", 5, "zoom hint statewide")
        app.buttons["My location"].tap()
        tapLayer("Everything")    // an interaction, so the monitor can answer the permission prompt if it appears
    }

    func testMyLocationCentersTheMap() {
        openMapEverything(at: CLLocation(latitude: 43.6575, longitude: -70.2544))   // Portland's Old Port
        waitForLabel(mapHint, containing: "here", 20, "map moved to the simulated location and filled in")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// App Review is usually in California: the map says so and stays on Maine rather than showing an empty map.
    func testMyLocationOutsideMaine() {
        openMapEverything(at: CLLocation(latitude: 37.3349, longitude: -122.009))
        // the note stays while the map is on the whole state
        waitFor(app.staticTexts["outsideNote"], 20, "the outside-Maine note")
        waitForLabel(mapHint, containing: "Zoom in to a town", 8, "the map stayed statewide")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// Apple's accessibility audit on the main iPhone screens. Prints every issue (prefixed AUDIT) instead of failing,
    /// so a run lists them all; read the log and fix what's ours (system bars and Apple's place card aren't).
    func testAccessibilityAudit() throws {
        if isPad { return }
        waitFor(text(containing: "Lobster shack & clam guide"), 15, "home header")
        func audit(_ screen: String) throws {
            try app.performAccessibilityAudit { issue in
                let el = issue.element.map { "\($0.elementType.rawValue) '\($0.label.prefix(40))'" } ?? "-"
                print("AUDIT [\(screen)] \(issue.auditType.rawValue) | \(issue.compactDescription) | \(el)")
                return true
            }
        }
        try audit("home")
        card("Lobster Shacks & Rolls").tap()
        waitFor(text(containing: "places ·"), 5, "lobster list")
        try audit("lobster")
        app.buttons.matching(NSPredicate(format: "label CONTAINS ' · '")).firstMatch.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a place")
        try audit("detail")
        app.tabBars.buttons["About"].tap()
        try audit("about")
        // not the Map tab: auditing thousands of MapKit annotations times out, and those views are Apple's
    }

    func testLaunchIsQuick() {
        // the bundled data decodes off the main thread; the home screen should be up well within a few seconds on a phone. On a
        // simulator the time measures the Mac as much as the app (11 s with a load average of 230), so there it's logged and
        // only a hang fails.
        #if targetEnvironment(simulator)
        let limit = 30.0
        #else
        let limit = 6.0
        #endif
        app.terminate()
        let start = Date()
        app.launch()
        let ready = isPad ? app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'places ·' OR label CONTAINS 'Lobster shack & clam guide'")).firstMatch
                          : text(containing: "Lobster shack & clam guide")
        XCTAssertTrue(ready.waitForExistence(timeout: 8), "home didn't appear")
        let secs = Date().timeIntervalSince(start)
        print("launch to home: \(String(format: "%.2f", secs)) s")
        XCTAssertLessThan(secs, limit)
    }
}
