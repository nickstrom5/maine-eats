import CoreSpotlight
import UniformTypeIdentifiers

/// Puts the hand-checked places (lobster shacks, clam shacks, Italians and red snappers, whoopie pies, diners, dairy bars, honorees)
/// into iPhone search, so "lobster roll wiscasset" in Spotlight can open the place in the app. Re-indexed whenever the data changes (`data_version`),
/// so a fix or a closure reaches Spotlight with the next update.
enum SpotlightIndexer {
    static let domain = "places"
    private static let versionKey = "spotlightIndexedVersion"

    static func indexIfNeeded(_ places: [Place], version: String, defaults: UserDefaults = .standard) {
        guard CSSearchableIndex.isIndexingAvailable(), defaults.string(forKey: versionKey) != version else { return }
        let items = featured(places).map { p -> CSSearchableItem in
            let attrs = CSSearchableItemAttributeSet(contentType: .content)
            attrs.title = p.name
            var kinds = p.kinds.names.filter { $0 != "Historic" }
            if let jb = p.jamesBeardLabel { kinds.append(jb) }
            attrs.contentDescription = ([kinds.joined(separator: " · ")] + [p.fullAddress]).filter { !$0.isEmpty }.joined(separator: "\n")
            attrs.keywords = kinds + [p.city, p.village, p.cuisine, p.dishes, "Maine"].compactMap { $0 }
            if let c = p.coordinate { attrs.latitude = NSNumber(value: c.latitude); attrs.longitude = NSNumber(value: c.longitude); attrs.supportsNavigation = true }
            return CSSearchableItem(uniqueIdentifier: p.id, domainIdentifier: domain, attributeSet: attrs)
        }
        CSSearchableIndex.default().deleteSearchableItems(withDomainIdentifiers: [domain]) { _ in
            CSSearchableIndex.default().indexSearchableItems(items) { error in
                if error == nil { defaults.set(version, forKey: versionKey) }
            }
        }
    }

    /// The hand-checked places; of a hand-checked chain, only the original (Amato's on India St), not its branches.
    static func featured(_ places: [Place]) -> [Place] {
        places.filter { !$0.isVenue && $0.handChecked && (!$0.isChain || $0.branchOf == nil) }
    }
}
