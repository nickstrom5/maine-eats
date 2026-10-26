import SwiftUI
import CoreSpotlight

@main
struct MaineEatsApp: App {
    @Environment(\.scenePhase) private var scenePhase
    @State private var model = AppModel()
    @State private var updater = DataUpdater()
    @State private var location = LocationService()

    init() {
        // Large titles in the same compressed black type as the home header.
        let navy = UIColor(Theme.ocean)
        UINavigationBar.appearance().largeTitleTextAttributes = [
            .font: UIFont.systemFont(ofSize: 36, weight: .black, width: .compressed), .foregroundColor: navy,
        ]
        UINavigationBar.appearance().titleTextAttributes = [
            .font: UIFont.systemFont(ofSize: 19, weight: .heavy, width: .compressed), .foregroundColor: navy,
        ]
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .environment(location)
                .environment(updater)
                .tint(Theme.ocean)
                .task {
                    await AppData.prepare()
                    await model.load()
                    ScreenshotMode.apply(to: model)
                    if model.isLoaded { updater.checkIfDue(placesInUse: model.places.count) }
                    if model.isLoaded && !ScreenshotMode.isActive {
                        SpotlightIndexer.indexIfNeeded(model.places, version: model.dataVersion)
                    }
                }
                .onContinueUserActivity(CSSearchableItemActionType) { activity in
                    guard let id = activity.userInfo?[CSSearchableItemActivityIdentifier] as? String else { return }
                    Task {
                        await model.load()
                        // an entry from before an id changed follows the alias; one for a place that's gone just opens the app
                        guard let p = model.place(id: id) else { return }
                        model.tab = .guides; model.selectedPlace = p; model.guidesPath = [.place(p)]
                    }
                }
        }
        .onChange(of: scenePhase) { _, phase in updater.phaseChanged(to: phase, placesInUse: model.isLoaded ? model.places.count : nil) }
    }
}
