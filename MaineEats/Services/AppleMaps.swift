import MapKit
import UIKit

/// Finds the Apple Maps listing for a place so the app can show Apple's own place card (ratings, hours, photos).
/// Those live details are Apple's licensed data, shown in Apple's UI; the app stores none of it.
enum AppleMaps {
    static func findItem(for p: Place) async -> MKMapItem? {
        guard let c = p.coordinate else { return nil }
        let req = MKLocalSearch.Request()
        req.naturalLanguageQuery = p.name
        req.region = MKCoordinateRegion(center: c, latitudinalMeters: 800, longitudinalMeters: 800)
        req.resultTypes = .pointOfInterest
        guard let items = try? await MKLocalSearch(request: req).start().mapItems else { return nil }
        let here = CLLocation(latitude: c.latitude, longitude: c.longitude)
        // the place's own town says nothing either ("Guilford Lobster Pound" isn't "Guilford Mooring")
        let town = Set(Search.normalize([p.city, p.village].compactMap { $0 }.joined(separator: " ")).split(separator: " ").map(String.init))
        let want = Search.normalize(p.name), ours = distinctive(want).subtracting(town)
        let scored = items.compactMap { item -> (MKMapItem, Double)? in
            let loc = item.placemark.location ?? here
            let d = loc.distance(from: here)
            guard d < 350 else { return nil }
            let name = Search.normalize(item.name ?? "")
            guard !name.isEmpty else { return nil }
            // half the distinctive words in common (a shared "pizza" says nothing), or right at the spot with at least a word
            // in common: otherwise it's a neighbor, and the "Not on Apple Maps" alert is the honest answer
            let theirs = distinctive(name).subtracting(town)
            let shared = Double(ours.intersection(theirs).count) / Double(max(1, min(ours.count, theirs.count)))
            let anyWord = !Set(want.split(separator: " ")).isDisjoint(with: name.split(separator: " "))
            guard name == want || shared >= 0.5 || (d < 60 && anyWord) else { return nil }
            return (item, shared * 2 - d / 350)
        }
        return scored.max { $0.1 < $1.1 }?.0
    }

    /// A normalized name's words that identify a business, with plurals folded ("pepes" -> "pepe"); pipeline/common.py `_stems`.
    static func distinctive(_ normalized: String) -> Set<String> {
        Set(normalized.split(separator: " ").map { w in
            let w = String(w)
            return generic.contains(w) || w.count <= 3 || !w.hasSuffix("s") ? w : String(w.dropLast())
        }).subtracting(generic)
    }

    /// Words that don't identify a business on their own (pipeline/common.py GENERIC, lowercased).
    static let generic = Set("""
        pizza pizzeria pho taco tacos taqueria grill grille kitchen express house coffee bar pub tavern food foods store shop
        market deli bakery chicken fish bbq sushi thai chinese mexican indian italian gyros burger burgers wings donuts donut
        beef tea juice north south east west park square station union town village street ave avenue center plaza lake lakes
        river bay new old best golden little big king star original famous fresh hot grand la el los las de del on the y at of
        lounge snack snacks noodle noodles asian shrimp patio club supper inn lodge saloon resort brewing brewery company brew
        hall custard frozen cheese curds fry brats brat wisconsin bake cafeteria corner spot stop place room sports family
        steakhouse steak diner creamery ice cream hut wok meal fusion buffet cuisine eats eatery lobster lobsters clam clams
        shack dock docks harbor harbour shore shoreline maine me downeast down coast coastal island isle isles pine pines tree
        pound wharf marina seafood cove point landing route rt hill hills valley pier beach buoy buoys lighthouse moose
        blueberry whoopie drive in drivein italian italians sandwich sandwiches oyster oysters new england yankee
        """.split(whereSeparator: \.isWhitespace).map(String.init))

    /// Fallback: open Apple Maps at the place's name and location.
    static func openInMaps(_ p: Place, directions: Bool = false) {
        guard let c = p.coordinate else {
            if let q = p.fullAddress.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
               let url = URL(string: "https://maps.apple.com/?q=\(q)") { UIApplication.shared.open(url) }
            return
        }
        let item = MKMapItem(placemark: MKPlacemark(coordinate: c))
        item.name = p.name
        item.openInMaps(launchOptions: directions ? [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving] : nil)
    }
}
