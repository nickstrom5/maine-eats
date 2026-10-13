import SwiftUI

struct AboutView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("MAINE EATS").displayFont(30).foregroundStyle(Theme.ocean)
                    Text("A free guide to \(model.restaurantCount.formatted()) Maine restaurants, with hand-checked lists of lobster shacks and pounds, clam shacks, red snappers and Maine Italians, whoopie pies and potato donuts, diners, oyster bars and dairy bars. No account, no ads, no tracking.")
                        .font(.subheadline).foregroundStyle(Theme.ink2)
                    Text("Maine Eats is an independent app by Nicholas Soderstrom. It is not affiliated with, endorsed by or operated by the State of Maine, Maine CDC or its Health Inspection Program, the Bureau of Alcoholic Beverages and Lottery Operations, the City of Lewiston, the James Beard Foundation, Michelin, Apple, or any restaurant, brand, team or chain.")
                        .font(.footnote).foregroundStyle(Theme.muted)
                }
                .padding(.vertical, 4)
            }
            Section("How the lists are built") {
                Text("Lobster shacks, clam shacks, red snappers and Italians, whoopie pies and donuts, diners, oyster bars, dairy bars and the icons are hand-checked: each was checked in \(model.researchChecked) against a \(model.sourceYears) source (the place's own website or menu, local news, or a town or chamber listing), with the address checked. Many coastal places are seasonal: a winter closing isn't a closure.")
                Text("The rest come from Overture Maps' open place data and the State of Maine's list of liquor licenses\(model.licenseDate.map { " (current as of \($0))" } ?? ""). Map listings are kept only at high confidence, and each place says how sure we are: statewide, the most confident listings matched an on-premises liquor license \(rate("Meta, confidence 0.95+")) of the time (only places that serve alcohol hold one). Website links are checked, and any that no longer belong to the place are left out.")
                Text("Maine's official inspection result is Pass or Fail, with no score or grade. The state's results are a one-at-a-time search, so the app shows a result only where the City of Lewiston posts it, with its date and a link to the report.")
                Text("Ratings, reviews, hours and photos are Apple Maps' own, shown live in Apple's place card. This app doesn't store or rank by them.")
            }
            .font(.subheadline).foregroundStyle(Theme.ink2)
            Section("Sources") {
                source("Overture Maps Foundation", "Restaurant listings and websites come from Overture Maps Foundation places data (overturemaps.org)\(model.overtureRelease.map { ", release \($0)" } ?? ""), filtered and reformatted for this app.\n• Data from Meta, Microsoft, DAC and BrightQuery. Available under CDLA Permissive 2.0.\n• Data from Foursquare. Copyright 2026 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0. Foursquare data was transformed to the Overture schema; this app further filtered and reformatted it. See the NOTICE below.\n• Data from AllThePlaces. Available under CC0 1.0.", "https://overturemaps.org")
                source("Maine Bureau of Alcoholic Beverages and Lottery Operations", "Liquor license data (maine.gov/dafs/bablo), published monthly as public information: used for each premises' trade name, address and license class only, never the license holder. The State of Maine does not endorse this app, and license information may change between updates.", "https://www.maine.gov/dafs/bablo/liquor-licensing/license-data")
                source("City of Lewiston", "Restaurant Inspection Reports (lewistonmaine.gov), shown as posted with their dates and linked to the city's reports. The city does not endorse this app.", "https://www.lewistonmaine.gov/621/Restaurant-Inspection-Reports")
                source("Maine CDC Health Inspection Program", "Licenses and inspects Maine's eating places. Look up any place's inspections in the state's search.", "https://apps.web.maine.gov/online/hip_search/health-inspection-search.html")
                source("Town outlines", "U.S. Census Bureau cartographic boundary files, 2025 (public domain), used to place each restaurant in its Maine town, city or plantation.", nil)
                source("Honors", "James Beard Foundation awards, nominees, semifinalists and America's Classics are reported as facts and checked by hand against public announcements. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. There is no MICHELIN Guide for Maine. MICHELIN is a trademark of Michelin. Other names belong to their owners.", "https://www.jamesbeard.org/awards/search-past-awards")
                source("Maps", "Maps, place cards and directions by Apple Maps.", nil)
            }
            Section("Licenses") {
                NavigationLink("Community Data License Agreement – Permissive 2.0") { LicenseText(file: "CDLA-Permissive-2.0", title: "CDLA Permissive 2.0") }
                NavigationLink("Apache License 2.0") { LicenseText(file: "Apache-2.0", title: "Apache License 2.0") }
                NavigationLink("Foursquare OS Places NOTICE") { LicenseText(file: "Foursquare-NOTICE", title: "Foursquare NOTICE") }
            }
            Section("Privacy") {
                Text("The app collects nothing. Your location, if you allow it, only sorts lists by distance and shows where you are on the map, on this device. Saved places stay on this device.")
                    .font(.subheadline).foregroundStyle(Theme.ink2)
                Link("Privacy policy", destination: Links.privacy)
                Link("Terms of use", destination: Links.terms)
            }
            Section("Help") {
                Link("Report a missing or closed place", destination: Links.correctionEmail)
                Link("Email \(Links.supportEmail)", destination: URL(string: "mailto:\(Links.supportEmail)")!)
                Link("Website", destination: Links.site)
                Text("Data as of \(PlaceDetailView.date(model.generated)). Places open and close; check before you go. Version \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0")")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
        }
        .navigationTitle("About")
        .tint(Theme.ocean)
    }

    private func rate(_ group: String) -> String {
        guard let g = model.calibration["statewide_liquor"]?[group] else { return "many" }
        return "\(Int((g.matched * 100).rounded()))%"
    }

    @ViewBuilder
    private func source(_ name: String, _ detail: String, _ url: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            if let url, let u = URL(string: url) { Link(name, destination: u).font(.subheadline.weight(.semibold)) }
            else { Text(name).font(.subheadline.weight(.semibold)) }
            Text(detail).font(.caption).foregroundStyle(Theme.muted)
        }
    }
}

/// A bundled license text (Resources/Licenses), reflowed rather than shown as raw 80-column lines.
struct LicenseText: View {
    let file: String
    let title: String

    var body: some View {
        ScrollView {
            Text(text).font(.footnote).foregroundStyle(Theme.ink).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding()
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var text: String {
        guard let url = Bundle.main.url(forResource: file, withExtension: "txt"),
              let raw = try? String(contentsOf: url, encoding: .utf8) else { return "License text missing." }
        // join hard-wrapped lines into paragraphs; keep blank lines and list items as breaks
        var out: [String] = []
        for para in raw.components(separatedBy: "\n\n") {
            let lines = para.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
            var joined = ""
            for l in lines where !l.isEmpty {
                let startsItem = l.hasPrefix("–") || l.hasPrefix("-") || l.range(of: #"^\(?[a-z0-9]{1,3}[.)]\s"#, options: .regularExpression) != nil
                joined += joined.isEmpty ? l : (startsItem ? "\n" + l : " " + l)
            }
            if !joined.isEmpty { out.append(joined) }
        }
        return out.joined(separator: "\n\n")
    }
}
