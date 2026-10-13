import Foundation
import CoreLocation
import MapKit
import UIKit

/// `-screenshot <name>` opens one screen with fixed state for App Store screenshots (scripts/capture-screenshots.sh).
/// Names: home, lobster, clams, sweets, detail, map, icons, saved, about.
enum ScreenshotMode {
    /// Debug builds only: an App Store build ignores the launch argument, so no one can reach seeded screens or fake locations.
    static var name: String? {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screenshot"), i + 1 < args.count else { return nil }
        return args[i + 1]
        #else
        return nil
        #endif
    }
    static var isActive: Bool { name != nil }

    /// The map shot opens on Portland's peninsula at neighborhood zoom, so the pins show one by one rather than as statewide clusters.
    static var mapRegion: MKCoordinateRegion? {
        name == "map" ? MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 43.6555, longitude: -70.2600),
                                           span: MKCoordinateSpan(latitudeDelta: 0.045, longitudeDelta: 0.03)) : nil
    }

    @MainActor
    static func apply(to model: AppModel) {
        guard let name, model.isLoaded else { return }
        model.filters = Filters()
        // Portland's Old Port, so "nearest" lists have distances without a permission prompt
        model.screenshotLocation = CLLocation(latitude: 43.6575, longitude: -70.2544)
        // the first hand-checked place with this name (a branch never stands in for the original)
        let named = { (p: Place, n: String) in p.name.lowercased().hasPrefix(n.lowercased()) }
        let pick = { (n: String) in model.places.first { named($0, n) && $0.handChecked && $0.branchOf == nil } ?? model.places.first { named($0, n) } }
        for n in ["Red's Eats", "Eventide Oyster Co.", "Moody's Diner", "Bagaduce Lunch"] {
            if let p = pick(n), !model.isSaved(p) { model.toggleSaved(p) }
        }
        let open = { (g: Guide) in model.tab = .guides; model.selectedGuide = g; model.guidesPath = [.guide(g)] }
        switch name {
        case "lobster": open(.lobster)
        case "clams": open(.clams)
        case "sweets": open(.sweets)
        case "icons": open(.icons)
        case "detail":
            open(.lobster)
            if let p = pick("Red's Eats") ?? model.places.first { model.selectedPlace = p; model.guidesPath.append(.place(p)) }
        case "map": model.tab = .map
        case "saved": model.tab = .saved
        case "about": model.tab = .about
        default: model.tab = .guides; model.selectedGuide = nil
        }
        // iPad shows the place column next to every list, so give each shot a place instead of "Pick a place".
        guard UIDevice.current.userInterfaceIdiom == .pad, model.selectedPlace == nil else { return }
        let place: Place? = switch name {
        case "lobster": pick("Five Islands Lobster Co.")
        case "clams": pick("The Clam Shack")
        case "sweets": pick("Moody's Diner")
        case "icons": pick("Bagaduce Lunch")
        case "saved": pick("Moody's Diner")
        case "about": nil
        case "map": pick("Eventide Oyster Co.")
        default: pick("Red's Eats")
        }
        model.selectedPlace = place
    }
}
