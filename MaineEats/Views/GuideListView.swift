import SwiftUI
import CoreLocation

struct GuideListView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let guide: Guide
    /// iPad passes a selection; iPhone pushes the place onto the stack
    var selection: Binding<Place?>? = nil

    @State private var sort: SortOrder?
    @State private var search = ""
    @State private var searching = false
    @State private var showFilters = false
    @State private var shown = 100
    /// The list, built off the main thread (AppModel.buildList) for the key it was built for. Until the first one arrives
    /// there's nothing to say "no matches" about.
    @State private var places: [Place] = []
    @State private var built: AppModel.ListKey?

    /// A sort this guide doesn't offer (left over from another guide) is ignored.
    private var order: SortOrder {
        if let sort, guide.sortOptions.contains(sort) { return sort }
        return guide.defaultSort(inState: here.map { LocationService.isInState($0.coordinate) } ?? false)
    }
    private var here: CLLocation? { model.screenshotLocation ?? location.location }

    var body: some View {
        let key = model.listKey(guide, sort: order, search: search, here: here)
        List {
            Section {
                Text(guide.listSubtitle + (guide.isClassic ? ". Each one hand-checked against a \(model.sourceYears) source." : ""))
                    .font(.subheadline).foregroundStyle(Theme.muted)
                    .listRowSeparator(.hidden)
                if guide == .icons {
                    Text("Points come from honors and years at the address; not a rating.")
                        .font(.caption).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if guide == .lobster {
                    Text("Many shacks close for the winter. Seasons are noted where the place posts them; check before you drive.")
                        .font(.caption).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if (order == .nearest || guide == .nearMe) && here == nil { locationPrompt }
                if order == .nearest && model.screenshotLocation == nil && location.isOutsideState {
                    Text("You're outside Maine. Every place here is in Maine, so distances are from where you are now.")
                        .font(.subheadline).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if model.filters.activeCount > 0 { activeFilters }
            }
            Section {
                if built == nil {
                    ProgressView().frame(maxWidth: .infinity).listRowSeparator(.hidden)
                } else if built == key && places.isEmpty && !(guide == .nearMe && here == nil) {
                    ContentUnavailableView {
                        Label(search.isEmpty ? "Nothing here" : "No matches", systemImage: "magnifyingglass")
                    } description: {
                        Text(search.isEmpty ? "No places match your filters." : "No places match “\(search)” with your filters.")
                    } actions: {
                        if model.filters.activeCount > 0 { Button("Clear filters") { model.filters = Filters() } }
                        if !search.isEmpty { Button("Clear search") { search = "" } }
                    }
                }
                ForEach(Array(places.prefix(shown).enumerated()), id: \.element.id) { i, p in
                    row(p, rank: order.isRanking && hasMetric(p) ? i + 1 : nil)
                }
                if places.count > shown {
                    Button("Show more (\((places.count - shown).formatted()) left)") { shown += 200 }
                        .frame(maxWidth: .infinity).foregroundStyle(Theme.ocean)
                }
            } header: {
                Text(built == nil ? "" : "\(places.count.formatted()) \(places.count == 1 ? "place" : "places") · \(order.label)").textCase(nil).foregroundStyle(Theme.ink2)
            }
        }
        .listStyle(.plain)
        .navigationTitle(guide.title)
        .navigationBarTitleDisplayMode(.large)
        .searchable(text: $search, isPresented: $searching, placement: .navigationBarDrawer(displayMode: .always), prompt: "Name, town or street")
        .onChange(of: search) { shown = 100 }
        .onChange(of: sort) { shown = 100 }
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                if guide.sortOptions.count > 1 {
                    Menu {
                        Picker("Sort", selection: Binding(get: { order }, set: { sort = $0; if $0 == .nearest { location.request() } })) {
                            ForEach(guide.sortOptions) { Text($0.label).tag($0) }
                        }
                    } label: { Label("Sort", systemImage: "arrow.up.arrow.down") }
                }
                Button { showFilters = true } label: {
                    Label("Filters", systemImage: model.filters.activeCount > 0 ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                }
            }
        }
        .sheet(isPresented: $showFilters) { FiltersSheet() }
        .task(id: key) { await rebuild(key) }
        .task {
            if !ScreenshotMode.isActive && (guide == .nearMe || order == .nearest) { location.request() }
            // from the Home search box: the field is active once the list has pushed in, so the keyboard is up
            if model.focusSearch && guide == .all {
                model.focusSearch = false
                try? await Task.sleep(for: .milliseconds(450))
                searching = true
            }
        }
    }

    /// Every change (a keystroke, a sort, a filter, moving 100 m) builds the list away from the main thread; a list built
    /// before is reused, and while typing it waits for a pause.
    private func rebuild(_ key: AppModel.ListKey) async {
        if let hit = model.cachedList(key) { places = hit; built = key; return }
        if let built, built.search != key.search {
            try? await Task.sleep(for: .milliseconds(120))
            if Task.isCancelled { return }
        }
        let out = await model.buildList(key, here: here)
        if Task.isCancelled { return }
        places = out
        built = key
    }

    /// The ranking's own number: places without a year (Oldest first) or points (Most iconic) sort last, unnumbered.
    private func hasMetric(_ p: Place) -> Bool {
        order == .oldest ? p.founded != nil : order == .iconic ? p.iconicPoints != nil : false
    }

    @ViewBuilder
    private func row(_ p: Place, rank: Int?) -> some View {
        let metric = metricText(p)
        if let selection {
            Button { selection.wrappedValue = p } label: { PlaceRow(place: p, rank: rank, metric: metric) }
                .listRowBackground(selection.wrappedValue?.id == p.id ? Theme.surface2 : Theme.surface)
        } else {
            NavigationLink(value: AppModel.Route.place(p)) { PlaceRow(place: p, rank: rank, metric: metric) }
        }
    }

    private func metricText(_ p: Place) -> PlaceRow.Metric? {
        switch order {
        case .nearest: if let here, let l = p.location { return .text(here.milesText(to: l), "away") }
        case .oldest: if let f = p.founded { return .text("\(f)", "since") }
        default: break   // Most iconic shows what earns the place (its year below, its honor as a chip), never a score
        }
        if let f = p.founded, guide != .all { return .text("\(f)", "since") }
        return nil
    }

    private var locationPrompt: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(location.isDenied ? "Location is off for this app. Turn it on in Settings to sort by distance."
                 : location.failed ? "Couldn't find your location. Check that Location Services is on, then try again."
                 : "Sort by distance from where you are. Your location stays on this device.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
            if location.isDenied {
                Button("Open Settings") { LocationService.openSettings() }.buttonStyle(.bordered).tint(Theme.ocean)
            } else {
                Button(location.failed ? "Try again" : "Use my location") { location.request() }.buttonStyle(.borderedProminent).tint(Theme.ocean)
            }
        }
        .padding(.vertical, 4)
        .listRowSeparator(.hidden)
    }

    private var activeFilters: some View {
        HStack {
            Text("\(model.filters.activeCount) filter\(model.filters.activeCount == 1 ? "" : "s") on").font(.subheadline).foregroundStyle(Theme.ink2)
            Spacer()
            Button("Clear") { model.filters = Filters() }.font(.subheadline.weight(.semibold))
        }
        .listRowSeparator(.hidden)
    }
}

struct PlaceRow: View {
    enum Metric { case text(String, String) }
    let place: Place
    var rank: Int?
    var metric: Metric?

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            if let rank {
                Text("\(rank)")
                    .displayFont(rank < 100 ? 26 : 20).monospacedDigit()
                    .foregroundStyle(rank <= 3 ? Theme.onBuoy : Theme.ocean)
                    .frame(minWidth: 38, minHeight: 38)
                    .background(RoundedRectangle(cornerRadius: 8).fill(rank <= 3 ? Theme.buoy : .clear))
                    .accessibilityLabel("Rank \(rank)")
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(place.name).font(.body.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.leading)
                Text(place.townLine).font(.subheadline).foregroundStyle(Theme.muted)
                PlaceChips(place: place, compact: true)
            }
            Spacer(minLength: 8)
            if case .text(let big, let small) = metric {
                VStack(alignment: .trailing, spacing: 0) {
                    Text(big).displayFont(22).foregroundStyle(Theme.ocean).monospacedDigit()
                    Text(small).font(.caption2).foregroundStyle(Theme.muted)
                }
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

/// The small labels on a place: Maine classics, honors, the casino it's in, chain size, how sure we are it's real.
struct PlaceChips: View {
    let place: Place
    var compact = false

    var body: some View {
        let chips = items
        if !chips.isEmpty {
            FlowLayout(spacing: 5) {
                ForEach(chips, id: \.0) { Chip(text: $0.0, style: $0.1) }
            }
        }
    }

    private var items: [(String, Chip.Style)] {
        var out: [(String, Chip.Style)] = []
        if let jb = place.jamesBeardLabel { out.append((jb, .ocean)) } else if place.otherHonors != nil { out.append(("Honored", .ocean)) }
        for k in place.kinds.names where k != "Historic" { out.append((k, .buoy)) }
        if place.kinds.isEmpty {   // places outside the research still carry tags from their names (a "… Diner", a "… Lobster Pound")
            if place.tags.contains(.lobster) { out.append(("Lobster", .buoy)) }
            if place.tags.contains(.diner) { out.append(("Diner", .buoy)) }
        }
        if let r = place.inspection, !compact { out.append(("Lewiston inspection: \(r.resultText)", .plain)) }
        if place.isSeasonal { out.append(("Seasonal", .plain)) }
        if let host = place.host { out.append(("At \(host)", .plain)) }
        if place.isChain { out.append(("Chain · \(place.chainCount)", .plain)) }
        if place.tier == .listing && !place.handChecked && place.tags.isEmpty { out.append(("Listing only", .dashed)) }
        return compact ? Array(out.prefix(4)) : out
    }
}

/// Wraps chips onto new lines.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, widest: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > maxW { y += rowH + spacing; x = 0; rowH = 0 }
            x += s.width + spacing; rowH = max(rowH, s.height); widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, maxW), height: y + rowH)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX { y += rowH + spacing; x = bounds.minX; rowH = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing; rowH = max(rowH, s.height)
        }
    }
}
