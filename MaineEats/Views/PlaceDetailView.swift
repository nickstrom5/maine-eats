import SwiftUI
import MapKit

struct PlaceDetailView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let place: Place

    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var mapItem: MKMapItem?
    @State private var lookingUp = false
    @State private var notOnAppleMaps = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                actions
                if let c = place.coordinate { mapSnippet(c) }
                if place.handChecked { checked }
                if place.jamesBeard != nil || place.otherHonors != nil { honors }
                if let r = place.inspection { inspection(r) }
                if let host = place.host { hostVenue(host) }
                listing
                Link(destination: Links.problemEmail(for: place)) {
                    Label("Report a problem with this listing", systemImage: "exclamationmark.bubble").font(.subheadline.weight(.semibold))
                }
                .accessibilityHint("Writes an email about this place")
            }
            .padding(16)
        }
        .background(Theme.background)
        .navigationTitle(place.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                // not "Saved": that's the tab's name
                Button { model.toggleSaved(place) } label: {
                    Label(model.isSaved(place) ? "Remove from Saved" : "Save", systemImage: model.isSaved(place) ? "heart.fill" : "heart")
                }
                ShareLink(item: shareText) { Label("Share", systemImage: "square.and.arrow.up") }
            }
        }
        .mapItemDetailSheet(item: $mapItem)
        .alert("Not on Apple Maps", isPresented: $notOnAppleMaps) {
            Button("Open Apple Maps anyway") { AppleMaps.openInMaps(place) }
            Button("OK", role: .cancel) {}
        } message: {
            Text("Apple Maps doesn't have a listing for \(place.name) at this spot, so there are no ratings or hours to show here.")
        }
    }

    // MARK: sections

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            // shown in capitals, read as written (VoiceOver would spell a short capitalized name out as an acronym)
            let town = place.village.map { "\($0) · \(place.city ?? "")" } ?? place.city ?? "Maine"
            Text(town.uppercased())
                .font(.caption.weight(.bold)).tracking(1.2).foregroundStyle(Theme.ocean2)
                .accessibilityLabel(town)
            Text(place.name.uppercased())
                .displayFont(38).foregroundStyle(Theme.ocean)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityLabel(place.name)
                .accessibilityAddTraits(.isHeader)
            Text([place.fullAddress, place.cuisine].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).foregroundStyle(Theme.ink2)
                .textSelection(.enabled)
            if let phone = place.phoneText {
                Text(phone).font(.subheadline).foregroundStyle(Theme.ink2).textSelection(.enabled)
            }
            if let here = model.screenshotLocation ?? location.location, let l = place.location {
                Text("\(here.milesText(to: l)) away").font(.subheadline).foregroundStyle(Theme.muted)
            }
            PlaceChips(place: place)
        }
    }

    private var actions: some View {
        VStack(spacing: 10) {
            Button {
                lookingUp = true
                Task {
                    let item = await AppleMaps.findItem(for: place)
                    lookingUp = false
                    if let item { mapItem = item } else { notOnAppleMaps = true }
                }
            } label: {
                // at the largest text sizes the caption goes under the title, so "Ratings" isn't split across lines
                let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4)) : AnyLayout(HStackLayout())
                layout {
                    HStack {
                        if lookingUp { ProgressView().tint(.white) } else { Image(systemName: "star.bubble") }
                        Text("Ratings, hours & photos").fontWeight(.semibold)
                    }
                    if !typeSize.isAccessibilitySize { Spacer() }
                    Text("Apple Maps").font(.caption)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14)
                .foregroundStyle(.white)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.ocean))
            }
            .disabled(place.coordinate == nil || lookingUp)
            .accessibilityHint("Opens the Apple Maps place card with current ratings and hours")

            HStack(spacing: 10) {
                actionButton("Directions", "arrow.triangle.turn.up.right.diamond") { AppleMaps.openInMaps(place, directions: true) }
                // only a US number (Place.usPhone): a malformed one could dial another country
                if let phone = place.phone, let url = URL(string: "tel:\(phone)") {
                    actionButton("Call", "phone") { UIApplication.shared.open(url) }
                        .accessibilityLabel("Call \(place.phoneText ?? phone)")
                }
                if let web = place.website {
                    actionButton("Website", "safari") { UIApplication.shared.open(web) }
                }
            }
        }
    }

    private func actionButton(_ title: String, _ icon: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.title3)
                Text(title).font(.caption.weight(.semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 56)
            .foregroundStyle(Theme.ocean)
            .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
    }

    private func mapSnippet(_ c: CLLocationCoordinate2D) -> some View {
        Map(initialPosition: .region(MKCoordinateRegion(center: c, latitudinalMeters: 900, longitudinalMeters: 900)), interactionModes: []) {
            Marker(place.name, systemImage: MarkerGlyph.symbol(for: place), coordinate: c).tint(place.handChecked ? Theme.lobster : Theme.ocean)
        }
        .accessibilityLabel("Map of \(place.name)")
        .frame(height: 170)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        // a button rather than a tap on the whole map, so MapKit's own "Legal" link stays tappable
        .overlay(alignment: .topTrailing) {
            Button { AppleMaps.openInMaps(place) } label: {
                Label("Open in Maps", systemImage: "map")
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .foregroundStyle(Theme.ocean)
                    .background(Capsule().fill(.regularMaterial))
            }
            .padding(8)
            .accessibilityLabel("Open \(place.name) in Apple Maps")
        }
    }

    private var checked: some View {
        section("Hand-checked") {
            VStack(alignment: .leading, spacing: 8) {
                if let note = place.note { Text(note).font(.subheadline).foregroundStyle(Theme.ink2) }
                if !place.kinds.names.isEmpty { fact("On our lists", place.kinds.names.joined(separator: ", ")) }
                if let d = place.dishes { fact("Known for", d) }
                if let s = place.season { fact("Season", s) } else if place.isSeasonal { fact("Season", "Seasonal, usually about May to October; check before you go.") }
                if let f = place.founded { fact("At this address since", "\(f)") }
                if let b = place.branchOf { fact("A branch of", b) }
                Text("Checked open in \(model.researchChecked) against a \(model.sourceYears) source: the place's own site or menu, local news, or a tourism listing. Hours and menus change, so check before you go.")
                    .font(.caption).foregroundStyle(Theme.ink2)
            }
        }
    }

    private var honors: some View {
        section("Honors") {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(lines(place.jamesBeard, prefix: "James Beard: ") + lines(place.otherHonors, prefix: ""), id: \.self) { l in
                    Label(l, systemImage: "rosette").font(.subheadline).foregroundStyle(Theme.ink)
                }
                if let chef = place.chef { fact("Chef", chef) }
                Text("Honors are facts, not ratings. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.")
                    .font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private func inspection(_ r: Inspection) -> some View {
        section("Health inspection · official") {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 12) {
                    ResultBadge(inspection: r)
                    if let d = r.d { Text("Inspected \(Self.date(d))").font(.subheadline).foregroundStyle(Theme.ink2) }
                }
                Text("The latest result the City of Lewiston posts for this place\(model.lewistonFetched.map { " (read \(Self.date($0)))" } ?? "")."
                     + (r.n.map { " Inspected as \($0)." } ?? ""))
                    .font(.subheadline).foregroundStyle(Theme.ink2)
                if let url = r.reportURL {
                    Link("The city's inspection report", destination: url).font(.subheadline.weight(.semibold))
                }
                Text("Maine's official result is Pass or Fail, with no score or grade: a place fails with more than 3 critical or more than 10 non-critical violations (10-144 CMR Ch. 201). Lewiston is the only place in Maine that posts its results in a form this app can show; the state's own results are a one-at-a-time search.")
                    .font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private func hostVenue(_ host: String) -> some View {
        section("Host venue") {
            Text(host == "Oxford Casino" ? "Inside Oxford Casino Hotel in Oxford." : "Inside Hollywood Casino Hotel & Raceway in Bangor.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
        }
    }

    private var listing: some View {
        section("How we know it's here") {
            VStack(alignment: .leading, spacing: 8) {
                kv("Listed as", place.handChecked && place.tier != .licensed ? "Hand-checked" : place.tier.label)
                if place.tier == .licensed {
                    kv("License list", place.jurisdiction == .lewiston ? "City of Lewiston inspections" : "Maine liquor license (BABLO)")
                    if let k = place.licenseKind { kv("Licensed as", k) }
                }
                if place.chainCount >= 2 { kv("Locations in Maine", place.chainCount.formatted()) }
                Text(listingNote).font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private var listingNote: String {
        let checked = place.handChecked
        if place.source == "research" {
            return "On our hand-checked list (checked in \(model.researchChecked) against a \(model.sourceYears) source). The open map data didn't list it as a place to eat, so it's placed at its street address."
        }
        switch place.tier {
        case .licensed:
            return place.source == "official"
                ? "From the \(place.jurisdiction.listName). The open map data didn't have it, so it's placed at its street address."
                : "Matched to an active entry in the \(place.jurisdiction.listName)."
        case .confirmed where checked, .listing where checked:
            return "On our hand-checked list: checked open in \(model.researchChecked) against a \(model.sourceYears) source (its own site or menu, local news, or a tourism listing). It's in Overture's open map data too."
        case .confirmed, .listing:
            let rate = model.matchRate(for: place)
            let base = place.tier == .confirmed
                ? "A high-confidence listing in Overture's open map data."
                : "A single listing in Overture's open map data, so it may be closed or misfiled."
            let measured = rate.map { " Statewide, \($0) of listings like this matched an on-premises liquor license; only places that serve alcohol hold one, so a coffee shop or takeout counter can't match." } ?? ""
            return base + measured + (checked ? " It's also on our hand-checked list, checked in \(model.researchChecked) against a \(model.sourceYears) source." : "")
        }
    }

    // MARK: helpers

    private var shareText: String {
        [place.name, place.fullAddress, "via Maine Eats", Links.site.absoluteString].filter { !$0.isEmpty }.joined(separator: "\n")
    }

    static func date(_ iso: String) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX")
        guard let d = f.date(from: iso) else { return iso }
        return d.formatted(date: .abbreviated, time: .omitted)
    }

    private func lines(_ s: String?, prefix: String) -> [String] {
        (s ?? "").components(separatedBy: "; ").filter { !$0.isEmpty }.map { prefix + $0 }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased()).font(.caption.weight(.bold)).tracking(1).foregroundStyle(Theme.ink2)
            Divider()
            content()
        }
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            Text(value).font(.subheadline).foregroundStyle(Theme.ink2)
        }
    }

    @ViewBuilder
    private func kv(_ k: String, _ v: String?) -> some View {
        if let v {
            HStack(alignment: .firstTextBaseline) {
                Text(k).font(.subheadline).foregroundStyle(Theme.ink2)
                Spacer(minLength: 12)
                Text(v).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.trailing)
            }
        }
    }
}

/// The glyph a place gets on the maps: lobster and clams, oysters, sandwiches and hot dogs, sweets, diners, dairy bars, everything else.
enum MarkerGlyph {
    static func symbol(for p: Place) -> String {
        if !p.kinds.isDisjoint(with: [.lobsterShack, .lobsterRoll, .clamShack]) { return "fish.fill" }
        if p.kinds.contains(.oysterBar) { return "water.waves" }
        if !p.kinds.isDisjoint(with: [.redSnapper, .italianSandwich]) { return "takeoutbag.and.cup.and.straw.fill" }
        if !p.kinds.isDisjoint(with: [.whoopiePie, .potatoDoughnut, .blueberryPie]) { return "birthday.cake.fill" }
        if p.kinds.contains(.diner) || p.kinds.contains(.francoAmerican) { return "cup.and.saucer.fill" }
        if p.kinds.contains(.dairyBar) { return "snowflake" }
        return "fork.knife"
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
