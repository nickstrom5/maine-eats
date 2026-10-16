import SwiftUI

struct FiltersSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            Form {
                Section("Town") {
                    NavigationLink {
                        TownPicker()
                    } label: {
                        HStack {
                            Text("Town"); Spacer()
                            Text(model.filters.town ?? "All of Maine").foregroundStyle(Theme.muted)
                        }
                    }
                }
                Section("Cuisine") {
                    Picker("Cuisine", selection: $model.filters.cuisine) {
                        Text("All cuisines").tag(String?.none)
                        ForEach(model.cuisines, id: \.name) { c in Text("\(c.name) (\(c.count.formatted()))").tag(String?.some(c.name)) }
                    }
                }
                Section {
                    Toggle("Hide chains (5+ locations)", isOn: $model.filters.hideChains)
                    Toggle("Only licensed, high-confidence or hand-checked places", isOn: $model.filters.confirmedOnly)
                    Toggle("Include non-restaurants", isOn: $model.filters.includeNonRestaurants)
                } footer: {
                    Text("That means on Maine's liquor-license list or Lewiston's inspection list, a high-confidence map listing, or hand-checked by us. Hiding chains keeps a hand-checked original, like Amato's on India Street. Non-restaurants are gas-station and grocery counters, airport stands, corporate and campus cafeterias, candy shops and delivery-only brands. Filters apply to the lists; Home and the Map always show every place.")
                }
                if model.filters.activeCount > 0 {
                    Section { Button("Clear all filters", role: .destructive) { model.filters = Filters() } }
                }
            }
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
    }
}

/// Pick a town; the pick takes you back to Filters. A village finds its town ("mystic": Groton and Stonington).
struct TownPicker: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var townSearch = ""

    var body: some View {
        // as typed first ("nor" finds North Haven), then abbreviated ("n haven", "e hartford"); a typed word that got shortened
        // must be whole there, so "north" doesn't find New Haven by its "n"
        let q = Search.normalize(townSearch), short = Search.normalizeAddress(townSearch)
        let shortNeedle = " " + short + (q.split(separator: " ").last.map { Search.synonyms[String($0)] != nil } == true ? " " : "")
        let hit = { (name: String) in
            (" " + Search.normalize(name)).contains(" " + q) || (" " + Search.normalizeAddress(name) + " ").contains(shortNeedle)
        }
        var viaVillage: [String: [String]] = [:]
        if !q.isEmpty {
            for (village, towns) in model.villageTowns where hit(village) { for t in towns { viaVillage[t, default: []].append(village) } }
        }
        let towns = model.towns.filter { q.isEmpty || hit($0.name) || viaVillage[$0.name] != nil }
        return List {
            Button { pick(nil) } label: {
                HStack { Text("All of Maine"); Spacer(); if model.filters.town == nil { Image(systemName: "checkmark") } }
            }
            ForEach(towns, id: \.name) { t in
                Button { pick(t.name) } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(t.name).foregroundStyle(Theme.ink)
                            if let v = viaVillage[t.name], !hit(t.name) {
                                Text("Includes \(v.sorted().joined(separator: ", "))").font(.caption).foregroundStyle(Theme.muted)
                            }
                        }
                        Spacer()
                        Text(t.count.formatted()).foregroundStyle(Theme.muted).monospacedDigit()
                        if model.filters.town == t.name { Image(systemName: "checkmark").foregroundStyle(Theme.ocean) }
                    }
                }
            }
        }
        .searchable(text: $townSearch, prompt: "Find a town or village")
        .navigationTitle("Town")
    }

    private func pick(_ town: String?) {
        model.filters.town = town
        dismiss()
    }
}
