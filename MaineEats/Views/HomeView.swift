import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @State private var lastRandom: String?
    private let columns = [GridItem(.adaptive(minimum: 158), spacing: 12)]

    /// Guides with too few hand-checked places to be worth a card stay in the iPad sidebar only.
    private var guides: [Guide] {
        [Guide.lobster, .clams, .sandwiches, .sweets, .franco, .diners, .oysters, .dairy, .icons, .oldest, .nearMe, .all]
            .filter(model.hasEnough)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                // screenshots leave the seasonal card out, so the lead shot holds all year
                if isShackSeason && model.count(.lobster) > 0 && !ScreenshotMode.isActive { seasonCard }
                Button { model.openSearch() } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(Theme.ocean)
                        Text("Search by name, town or street").foregroundStyle(Theme.muted)
                        Spacer()
                    }
                    .font(.subheadline)
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.ocean, lineWidth: 2))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Search every restaurant")
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(guides) { g in
                        Button { model.openGuide(g) } label: { GuideCard(guide: g, count: model.count(g)) }
                            .buttonStyle(.plain)
                    }
                }
                surpriseButton
                Text("Ratings, hours and photos come live from Apple Maps on each place. Lists are built from open map data, Maine's liquor-license list, Lewiston's posted inspections and hand-checked research. See About for sources.")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
            .padding(16)
        }
        .background(Theme.background)
        .navigationTitle("")
        .toolbar(.hidden, for: .navigationBar)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("MAINE\nEATS")
                .displayFont(56)
                .foregroundStyle(Theme.ocean)
                .lineSpacing(-6)
                .accessibilityLabel("Maine Eats")
                .accessibilityAddTraits(.isHeader)
            ZStack {
                Shoreline().fill(Theme.seaGlass).offset(y: -3)
                Shoreline().fill(Theme.ocean2)
            }
            .frame(height: 12).accessibilityHidden(true)
            Text("Lobster shack & clam guide")
                .font(.headline).foregroundStyle(Theme.ink)
            Text("Lobster pounds, clam shacks, whoopie pies and diners we checked open, plus \(model.restaurantCount.formatted()) restaurants in \(model.towns.count.formatted()) towns.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
        }
        .padding(.top, 8)
    }

    /// May through October, when the lobster pounds and clam shacks are open.
    private var isShackSeason: Bool { (5...10).contains(Calendar.current.component(.month, from: .now)) }

    private var seasonCard: some View {
        Button { model.openGuide(.lobster) } label: {
            HStack(spacing: 12) {
                Image(systemName: "fish.fill").font(.title2).foregroundStyle(Theme.buoy)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Shack season").displayFont(24).foregroundStyle(.white)
                    Text("Lobster pounds and clam shacks, open till about mid-October").font(.subheadline).foregroundStyle(.white)
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(.white)
            }
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 14).fill(Theme.ocean))
        }
        .buttonStyle(.plain)
    }

    private var surpriseButton: some View {
        Button {
            if let p = model.randomPick(from: [.lobster, .clams, .sandwiches, .sweets, .franco, .diners, .oysters, .dairy], excluding: lastRandom) {
                lastRandom = p.id
                model.guidesPath.append(.place(p))
                model.selectedPlace = p
            }
        } label: {
            Label("Surprise me with a Maine classic", systemImage: "dice")
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity).padding(12)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.buoy))
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.onBuoy)
    }
}

struct GuideCard: View {
    let guide: Guide
    let count: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: guide.systemImage).font(.title3).foregroundStyle(Theme.ocean)
                    .frame(width: 36, height: 36).background(Circle().fill(guide.isClassic ? Theme.buoySoft : Theme.surface2))
                Spacer()
                if guide != .nearMe && guide != .all {   // "All" would just repeat the total in the header
                    Text(count.formatted()).displayFont(22).foregroundStyle(Theme.ocean).monospacedDigit()
                }
            }
            Text(guide.title).displayFont(22, weight: .heavy).foregroundStyle(Theme.ink).lineLimit(3).minimumScaleFactor(0.8)
            Text(guide.subtitle).font(.caption).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 150, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(guide.isClassic ? Theme.buoy.opacity(0.7) : Theme.rule))
        .accessibilityElement(children: .combine)
        .accessibilityHint(guide == .nearMe ? "" : "\(count) places")
    }
}
