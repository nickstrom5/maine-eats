import SwiftUI
import MapKit

struct MapScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    var selection: Binding<Place?>? = nil

    @State private var layer: Layer = .lobster
    @State private var region: MKCoordinateRegion?
    /// "My location": where to move the map (a new object each tap, so a second tap re-centers after panning away)
    @State private var centerOn: CLLocation?
    @State private var centerWhenFound = false
    @State private var notice: String?
    /// "My location" from outside Maine: said for as long as the map stays on the whole state
    @State private var outside = false
    @State private var askSettings = false
    /// places on one spot (a food hall, a casino floor) from a tapped cluster, and the one picked from that list
    @State private var stacked: Stack?
    @State private var picked: Place?

    struct Stack: Identifiable {
        let id = UUID()
        let places: [Place]
    }

    /// All 4,000+ restaurants at once would keep the map busy (16,000 pins took over a minute in QA), so the Everything layer fills in
    /// only once you zoom to about town size (this many degrees of latitude on screen), and only for what's in view.
    private static let everythingSpan = 0.2

    enum Layer: String, CaseIterable, Identifiable {
        case lobster = "Lobster", clams = "Clam shacks", sweets = "Sweets", dairy = "Dairy bars", icons = "Icons", all = "Everything"
        var id: String { rawValue }
        var guide: Guide {
            switch self {
            case .lobster: .lobster
            case .clams: .clams
            case .sweets: .sweets
            case .dairy: .dairy
            case .icons: .icons
            case .all: .all
            }
        }
    }

    var body: some View {
        // the whole guide, whatever a list's filters say (the map has no filter control)
        let layerPlaces = model.mapPlaces(layer.guide)
        // the smaller side decides: a tall, narrow iPad column shows a lot of latitude even at town zoom
        let zoomedOut = layer == .all && min(region?.span.latitudeDelta ?? .infinity, region?.span.longitudeDelta ?? .infinity) > Self.everythingSpan
        // a quarter screen of margin around the view, so a short pan doesn't show empty edges
        let places = layer != .all ? layerPlaces : zoomedOut ? [] : layerPlaces.filter { inView($0, margin: 0.75) }
        let onScreen = layer == .all ? places.filter { inView($0, margin: 0.5) }.count : places.count
        ZStack(alignment: .top) {
            ClusteredMap(places: places, showsUser: location.location != nil, center: centerOn, start: ScreenshotMode.mapRegion,
                         onRegion: { r in region = r; if r.span.latitudeDelta < 0.5 { outside = false } },
                         onStack: { stacked = Stack(places: $0.sorted { $0.name < $1.name }) }) { openPlace($0) }
            .ignoresSafeArea(edges: .bottom)
            VStack(spacing: 6) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Layer.allCases) { l in
                            Button { layer = l } label: {
                                Text(l.rawValue).font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 12).padding(.vertical, 8)
                                    .foregroundStyle(layer == l ? .white : Theme.ocean)
                                    .background(Capsule().fill(layer == l ? Theme.ocean : Theme.surface))
                                    .overlay(Capsule().strokeBorder(Theme.rule2, lineWidth: layer == l ? 0 : 1))
                            }
                            .accessibilityAddTraits(layer == l ? .isSelected : [])
                        }
                    }
                    .padding(.horizontal, 12)
                }
                .accessibilityIdentifier("layers")
                Text(notice ?? (zoomedOut ? "Zoom in to a town to see all \(layerPlaces.count.formatted()) places"
                               : "\(onScreen.formatted()) \(onScreen == 1 ? "place" : "places")\(layer == .all ? " here" : "") · tap a pin, then its name"))
                    .font(.caption).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
                    .accessibilityIdentifier("mapHint")
                if outside {
                    Text("You're outside Maine, so the map stays on the state.")
                        .font(.caption).foregroundStyle(Theme.ink2)
                        .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
                        .accessibilityIdentifier("outsideNote")
                }
            }
            .padding(.top, 8)
        }
        .navigationTitle("Map")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $stacked, onDismiss: { if let p = picked { picked = nil; openPlace(p) } }) { stack in
            NavigationStack {
                List(stack.places) { p in
                    Button { picked = p; stacked = nil } label: { PlaceRow(place: p) }
                }
                .listStyle(.plain)
                .navigationTitle("\(stack.places.count) places at this spot")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { stacked = nil } } }
            }
            .presentationDetents([.medium, .large])
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    if location.isDenied {
                        askSettings = true
                    } else {
                        // a fix from launch may be miles out of date, so always ask for a fresh one; a very recent fix moves the map now
                        if let here = location.location, here.timestamp.timeIntervalSinceNow > -60 { center(on: here) }
                        centerWhenFound = true
                        location.request()
                    }
                } label: { Label("My location", systemImage: "location") }
            }
        }
        .onChange(of: location.location) { _, here in
            guard centerWhenFound, let here else { return }
            centerWhenFound = false
            center(on: here)
        }
        .onChange(of: location.failed) { _, failed in
            guard failed && centerWhenFound else { return }
            centerWhenFound = false
            // the map already moved to a fix from the last minute or so; only say so when there was nothing to go on
            if (location.location?.timestamp.timeIntervalSinceNow ?? -.infinity) < -90 {
                flash("Couldn't find your location. Check that Location Services is on.")
            }
        }
        .alert("Location is off", isPresented: $askSettings) {
            Button("Open Settings") { LocationService.openSettings() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Turn on location for Maine Eats in Settings to center the map on you. It stays on your device.")
        }
    }
}

extension MapScreen {
    private func openPlace(_ p: Place) {
        if let selection { selection.wrappedValue = p } else { model.mapPath.append(p) }
    }

    /// Town-level zoom on the reader, unless they're outside Maine: then the map stays on the state and says why.
    private func center(on here: CLLocation) {
        if location.isOutsideState {
            outside = true
        } else {
            outside = false
            centerOn = CLLocation(latitude: here.coordinate.latitude, longitude: here.coordinate.longitude)
        }
    }

    private func flash(_ text: String) {
        notice = text
        Task { try? await Task.sleep(for: .seconds(5)); if notice == text { notice = nil } }
    }

    /// Within `margin` spans of the map's center: 0.5 is what's on screen.
    private func inView(_ p: Place, margin: Double) -> Bool {
        guard let r = region, let c = p.coordinate else { return false }
        return abs(c.latitude - r.center.latitude) <= r.span.latitudeDelta * margin && abs(c.longitude - r.center.longitude) <= r.span.longitudeDelta * margin
    }
}

/// MKMapView with clustering: SwiftUI's Map can't cluster thousands of pins.
struct ClusteredMap: UIViewRepresentable {
    let places: [Place]
    let showsUser: Bool
    /// move the map here (town-level zoom) whenever a new location object arrives
    var center: CLLocation? = nil
    /// where the map opens (screenshots); otherwise the whole state
    var start: MKCoordinateRegion? = nil
    var onRegion: (MKCoordinateRegion) -> Void = { _ in }
    /// a tapped cluster that zooming can't split
    var onStack: ([Place]) -> Void = { _ in }
    let onSelect: (Place) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(PlaceMarker.self, forAnnotationViewWithReuseIdentifier: PlaceMarker.id)
        map.register(ClusterMarker.self, forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier)
        map.setRegion(start ?? MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 45.25, longitude: -69.15),
                                                  span: MKCoordinateSpan(latitudeDelta: 4.7, longitudeDelta: 4.6)), animated: false)
        let start = map.region
        DispatchQueue.main.async { onRegion(start) }
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onRegion = onRegion
        context.coordinator.onStack = onStack
        map.showsUserLocation = showsUser
        if let c = center, c !== context.coordinator.centered {
            context.coordinator.centered = c
            map.setRegion(MKCoordinateRegion(center: c.coordinate, span: MKCoordinateSpan(latitudeDelta: 0.12, longitudeDelta: 0.12)), animated: true)
        }
        let want = Set(places.map(\.id))
        let have = map.annotations.compactMap { $0 as? PlaceAnnotation }
        let haveIds = Set(have.map(\.place.id))
        guard want != haveIds else { return }
        map.removeAnnotations(have.filter { !want.contains($0.place.id) })
        map.addAnnotations(places.filter { !haveIds.contains($0.id) }.map(PlaceAnnotation.init))
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var onSelect: ((Place) -> Void)?
        var onRegion: ((MKCoordinateRegion) -> Void)?
        var onStack: (([Place]) -> Void)?
        var centered: CLLocation?

        func mapView(_ map: MKMapView, regionDidChangeAnimated animated: Bool) {
            let r = map.region
            DispatchQueue.main.async { self.onRegion?(r) }   // not during a SwiftUI view update
        }

        func mapView(_ map: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation { return nil }
            if annotation is MKClusterAnnotation { return nil }   // the registered ClusterMarker
            return map.dequeueReusableAnnotationView(withIdentifier: PlaceMarker.id, for: annotation)
        }

        func mapView(_ map: MKMapView, annotationView view: MKAnnotationView, calloutAccessoryControlTapped control: UIControl) {
            if let a = view.annotation as? PlaceAnnotation { onSelect?(a.place) }
        }

        func mapView(_ map: MKMapView, didSelect annotation: MKAnnotation) {
            guard let cluster = annotation as? MKClusterAnnotation else { return }
            map.deselectAnnotation(cluster, animated: false)
            let members = cluster.memberAnnotations.compactMap { $0 as? PlaceAnnotation }
            // places sharing one point never split however far in you zoom, and near full zoom nothing more will: list them
            let first = members.first.map { CLLocation(latitude: $0.coordinate.latitude, longitude: $0.coordinate.longitude) }
            let onePoint = first.map { f in
                members.allSatisfy { CLLocation(latitude: $0.coordinate.latitude, longitude: $0.coordinate.longitude).distance(from: f) < 2 }
            } ?? false
            if !members.isEmpty && (onePoint || map.region.span.latitudeDelta < 0.002) {
                onStack?(members.map(\.place))
            } else {
                map.showAnnotations(cluster.memberAnnotations, animated: true)
            }
        }
    }
}

final class PlaceAnnotation: NSObject, MKAnnotation {
    let place: Place
    let coordinate: CLLocationCoordinate2D
    var title: String? { place.name }
    var subtitle: String? { place.townLine }
    init(_ p: Place) { place = p; coordinate = p.coordinate! }
}

final class PlaceMarker: MKMarkerAnnotationView {
    static let id = "place"
    override var annotation: MKAnnotation? { didSet { configure() } }

    private func configure() {
        clusteringIdentifier = "places"
        canShowCallout = true
        let info = UIButton(type: .detailDisclosure)
        info.accessibilityLabel = "Details"
        rightCalloutAccessoryView = info
        guard let p = (annotation as? PlaceAnnotation)?.place else { return }
        let classic = p.handChecked
        markerTintColor = UIColor(classic ? Theme.lobster : Theme.ocean)   // lobster coral carries a white glyph; buoy yellow washed out on the map
        glyphTintColor = .white
        glyphImage = UIImage(systemName: MarkerGlyph.symbol(for: p))
        displayPriority = classic ? .defaultHigh : .defaultLow
    }
}

final class ClusterMarker: MKMarkerAnnotationView {
    override var annotation: MKAnnotation? {
        didSet {
            markerTintColor = UIColor(Theme.ocean)
            glyphText = (annotation as? MKClusterAnnotation).map { "\($0.memberAnnotations.count)" }
            displayPriority = .defaultHigh
        }
    }
}
