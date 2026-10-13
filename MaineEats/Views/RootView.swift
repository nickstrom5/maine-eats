import SwiftUI
import CoreLocation

struct RootView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.horizontalSizeClass) private var sizeClass
    /// the layout on screen; it follows the size class only after the model has carried the open list and place across
    @State private var layout: UserInterfaceSizeClass?

    var body: some View {
        Group {
            if let error = model.loadError {
                ContentUnavailableView("Couldn't open the list", systemImage: "exclamationmark.triangle", description: Text(error))
            } else if !model.isLoaded {
                ProgressView("Loading Maine's restaurants…").tint(Theme.ocean).foregroundStyle(Theme.muted)
            } else if (layout ?? sizeClass) == .regular {
                SplitRoot()
            } else {
                TabRoot()
            }
        }
        .background(Theme.surface)
        .onChange(of: sizeClass, initial: true) { _, new in
            // full width <-> a narrow window (Split View, Stage Manager): the same list and place on the other layout
            if layout != nil && layout != new {
                if new == .regular { model.syncToRegular() } else { model.syncToCompact() }
            }
            layout = new
        }
    }
}

/// iPhone: tabs, each with its own navigation stack.
struct TabRoot: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        TabView(selection: $model.tab) {
            NavigationStack(path: $model.guidesPath) {
                HomeView()
                    .navigationDestination(for: AppModel.Route.self) { route in
                        switch route {
                        case .guide(let g): GuideListView(guide: g)
                        case .place(let p): PlaceDetailView(place: p)
                        }
                    }
            }
                .tabItem { Label("Guides", systemImage: "list.bullet.rectangle") }.tag(AppModel.Tab.guides)
            NavigationStack(path: $model.mapPath) {
                MapScreen().navigationDestination(for: Place.self) { PlaceDetailView(place: $0) }
            }
                .tabItem { Label("Map", systemImage: "map") }.tag(AppModel.Tab.map)
            NavigationStack(path: $model.savedPath) {
                SavedView().navigationDestination(for: Place.self) { PlaceDetailView(place: $0) }
            }
                .tabItem { Label("Saved", systemImage: "heart") }.tag(AppModel.Tab.saved)
            NavigationStack { AboutView() }
                .tabItem { Label("About", systemImage: "info.circle") }.tag(AppModel.Tab.about)
        }
    }
}

/// iPad: guides in the sidebar, the list in the middle, the place on the right.
struct SplitRoot: View {
    @Environment(AppModel.self) private var model
    // .automatic opened a portrait iPad on a blank "Pick a place" page with the list hidden behind the sidebar button;
    // .all shows the list next to the place (and the sidebar too, in landscape)
    @State private var columns: NavigationSplitViewVisibility = .all

    enum SidebarItem: Hashable { case home, guide(Guide), map, saved, about }

    /// The sidebar is the model's tab and guide, so a Home card, Spotlight or a layout change moves it too.
    private var sidebar: Binding<SidebarItem?> {
        Binding(get: {
            switch model.tab {
            case .guides: model.selectedGuide.map { .guide($0) } ?? .home
            case .map: .map
            case .saved: .saved
            case .about: .about
            }
        }, set: { item in
            switch item {
            case .guide(let g): model.tab = .guides; model.selectedGuide = g; model.guidesPath = [.guide(g)]
            case .map: model.tab = .map
            case .saved: model.tab = .saved
            case .about: model.tab = .about
            case .home, nil: model.tab = .guides; model.selectedGuide = nil; model.guidesPath = []
            }
        })
    }

    var body: some View {
        @Bindable var model = model
        NavigationSplitView(columnVisibility: $columns) {
            List(selection: sidebar) {
                Label("Home", systemImage: "house").tag(SidebarItem.home)
                Section {
                    // a classic with too few hand-checked places isn't offered as a list (Franco-American had 1 in Oct 2026)
                    ForEach(Guide.allCases.filter(model.hasEnough)) { g in
                        Label(g.title, systemImage: g.systemImage).tag(SidebarItem.guide(g))
                    }
                } header: { Text("Guides") }
                Section {
                    Label("Map", systemImage: "map").tag(SidebarItem.map)
                    Label("Saved", systemImage: "heart").tag(SidebarItem.saved)
                    Label("About", systemImage: "info.circle").tag(SidebarItem.about)
                }
            }
            .navigationTitle("Maine Eats")
        } content: {
            switch sidebar.wrappedValue {
            // a fresh list per guide, so one guide's sort, search and paging don't carry over to the next
            case .guide(let g): GuideListView(guide: g, selection: $model.selectedPlace).id(g)
            case .map: MapScreen(selection: $model.selectedPlace)
            case .saved: SavedView(selection: $model.selectedPlace)
            case .about: AboutView()
            case .home, nil: HomeView()
            }
        } detail: {
            if let p = model.selectedPlace {
                NavigationStack { PlaceDetailView(place: p) }.id(p.id)
            } else {
                ContentUnavailableView("Pick a place", systemImage: "fork.knife", description: Text("Choose a lobster shack, a clam shack or any restaurant to see its details."))
            }
        }
        .navigationSplitViewStyle(.balanced)
        .tint(Theme.ocean)
    }
}
