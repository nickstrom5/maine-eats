import SwiftUI

struct SavedView: View {
    @Environment(AppModel.self) private var model
    var selection: Binding<Place?>? = nil

    var body: some View {
        let places = model.savedPlaces
        List {
            if places.isEmpty {
                ContentUnavailableView("Nothing saved yet", systemImage: "heart",
                                       description: Text("Tap the heart on a lobster shack or a dairy bar to keep it here for your next trip."))
            }
            ForEach(places) { p in
                Button {
                    if let selection { selection.wrappedValue = p } else { model.savedPath.append(p) }
                } label: { PlaceRow(place: p) }
                .swipeActions { Button("Remove", role: .destructive) { model.toggleSaved(p) } }
            }
        }
        .listStyle(.plain)
        .navigationTitle("Saved")
    }
}
