"""Session 5: the sources the Northwind research pipeline can reach (Exercise 4).

Research question used all session:
    "Why did return rates at Northwind Outfitters rise in Q3 2026,
     and what should we change before the holiday season?"

Three kinds of source, one per specialist subagent:
  * "web"      -> public articles      (web_researcher: search_web, fetch_web_page)
  * "internal" -> company documents    (doc_analyst:    search_internal_docs, read_internal_doc)
  * "dataset"  -> the returns database (data_analyst:   query_return_stats)

The corpus is fixed so every run is reproducible and costs nothing to search.
It is deliberately realistic: five real drivers spread across different source
types, one decoy article, and two benchmark figures that disagree (2024 vs 2026).
Session 14 reuses that disagreement for provenance and conflict handling.
"""

WEB_SOURCES = {
    "W1": {
        "source_id": "W1",
        "type": "web",
        "title": "2026 Outdoor E-commerce Returns Benchmark",
        "publisher": "Trailhead Retail Analytics",
        "date": "2026-08-14",
        "url": "https://research.trailhead-analytics.example/outdoor-returns-2026",
        "text": (
            "Across 140 outdoor-gear online stores, the average return rate in H1 2026 was 11.8%, "
            "up from 10.9% in H1 2025. Return reasons: wrong size or fit 31%, damaged in transit 22%, "
            "not as described 19%, product defect 14%, changed mind 14%. Stores that introduced free "
            "return shipping saw 'changed mind' returns rise by about 3 percentage points within one quarter."
        ),
    },
    "W2": {
        "source_id": "W2",
        "type": "web",
        "title": "Why outdoor gear returns are so high",
        "publisher": "GearBiz Blog",
        "date": "2024-03-02",
        "url": "https://gearbiz.example/blog/outdoor-returns",
        "text": (
            "The outdoor category has a return rate of around 8%, well below fashion. Most returns are "
            "sizing issues on jackets and sleeping bags. Retailers can cut returns with clearer size charts."
        ),
    },
    "W3": {
        "source_id": "W3",
        "type": "web",
        "title": "SwiftShip hub congestion delays parcels across the Midwest",
        "publisher": "Freight Daily News",
        "date": "2026-08-22",
        "url": "https://freightdaily.example/news/swiftship-columbus-hub-delays",
        "text": (
            "SwiftShip's Columbus sortation hub has run at reduced capacity since late July while new "
            "automation is installed. Shippers report delivery delays of 3 to 5 days and a rise in "
            "damaged-parcel claims during August. SwiftShip expects normal capacity by mid-October."
        ),
    },
    "W4": {
        "source_id": "W4",
        "type": "web",
        "title": "Not as described: how product photos drive returns",
        "publisher": "E-com Insights",
        "date": "2026-06-10",
        "url": "https://ecominsights.example/articles/photos-and-returns",
        "text": (
            "When a product photo shows a different colour or finish from the item shipped, 'not as "
            "described' returns for that SKU typically double. Retailers that audit photos against the "
            "physical product before launch avoid most of these returns."
        ),
    },
    "W5": {
        "source_id": "W5",
        "type": "web",
        "title": "Best backpacking tents of 2026",
        "publisher": "Summit Gear Reviews",
        "date": "2026-05-01",
        "url": "https://summitgear.example/reviews/best-tents-2026",
        "text": (
            "The Trailhead 2-person tent is our budget pick: light, quick to pitch, and good value. "
            "We tested the spring 2026 production run and had no issues with the poles."
        ),
    },
}

INTERNAL_DOCS = {
    "NW-QA-2026-031": {
        "source_id": "NW-QA-2026-031",
        "type": "internal",
        "title": "QA incident report: tent pole batch TP-0726",
        "owner": "Quality Assurance",
        "date": "2026-08-03",
        "pages": [
            "Summary. Hairline cracks found in aluminium pole sections from supplier batch TP-0726, used "
            "in the Trailhead 2-person tent (SKU TENT-2P). Cracks open under normal tension during pitching.",
            "Scope. About 1,150 tents with TP-0726 poles shipped between 2026-07-08 and 2026-08-01. "
            "Corrective action: batch quarantined on 2026-08-02; replacement pole kits offered to affected customers.",
        ],
    },
    "NW-SUP-Q3": {
        "source_id": "NW-SUP-Q3",
        "type": "internal",
        "title": "Support ticket themes, Q3 2026",
        "owner": "Customer Support",
        "date": "2026-10-02",
        "pages": [
            "Top theme: 'runs small' on sleeping bags and jackets, starting the week of 2026-07-15. "
            "Second theme: 'pole snapped' on the Trailhead 2-person tent (July and August orders).",
            "Other themes: 'arrived damaged' tickets doubled in August, mostly SwiftShip deliveries to the "
            "Midwest. 'Colour not as shown' on the Ridge pocket stove: photos show orange, the stove ships in olive.",
        ],
    },
    "NW-LOG-CARRIER-Q3": {
        "source_id": "NW-LOG-CARRIER-Q3",
        "type": "internal",
        "title": "Carrier performance report: SwiftShip, July to September 2026",
        "owner": "Logistics",
        "date": "2026-10-05",
        "pages": [
            "On-time delivery fell from 96% in July to 81% in August, recovering to 90% in September. "
            "Parcel damage rate rose from 0.6% to 1.4% in August. Worst lane: Columbus hub (Midwest).",
        ],
    },
    "NW-MERCH-LOG": {
        "source_id": "NW-MERCH-LOG",
        "type": "internal",
        "title": "Merchandising change log, Q3 2026",
        "owner": "Merchandising",
        "date": "2026-09-30",
        "pages": [
            "2026-07-15: size charts for sleeping bags and outerwear migrated to the new vendor template. "
            "Known issue logged 2026-09-12: chest and length values were entered in centimetres in columns "
            "labelled inches for 14 SKUs.",
            "2026-08-02: new photo set published for the Ridge pocket stove (STOVE-1). Photos were taken "
            "of the orange pre-production sample; production units are olive.",
        ],
    },
    "NW-POLICY-RET": {
        "source_id": "NW-POLICY-RET",
        "type": "internal",
        "title": "Returns policy, effective 2026-07-01",
        "owner": "Customer Experience",
        "date": "2026-06-20",
        "pages": [
            "From 2026-07-01, return shipping is free for all orders (previously USD 7.95 deducted from the "
            "refund). The return window stays at 60 days.",
        ],
    },
}

# Returns database. Q3 data is loaded only through 2026-09-21 (the warehouse
# backlog), so any Q3 figure is PARTIAL. A good data_analyst says so.
RETURN_STATS = {
    "dataset_id": "DS-RET-2026",
    "coverage": {"Q2-2026": "2026-04-01 to 2026-06-30 (complete)",
                 "Q3-2026": "2026-07-01 to 2026-09-21 (partial: warehouse backlog)"},
    "rate_by_category": {
        "Q2-2026": {"tents": 7.0, "sleeping_bags": 8.5, "apparel": 12.0, "stoves": 5.0,
                    "lighting": 4.0, "overall": 9.1},
        "Q3-2026": {"tents": 15.2, "sleeping_bags": 14.0, "apparel": 19.5, "stoves": 9.8,
                    "lighting": 5.1, "overall": 13.4},
    },
    "reason_share": {
        "Q2-2026": {"defect": 15, "size_fit": 30, "damaged_in_transit": 12,
                    "not_as_described": 9, "changed_mind": 7, "other": 27},
        "Q3-2026": {"defect": 24, "size_fit": 29, "damaged_in_transit": 21,
                    "not_as_described": 15, "changed_mind": 11, "other": 0},
    },
}

ALL_SOURCES = {**WEB_SOURCES, **INTERNAL_DOCS}

# Ground truth used by the coverage checker (answer_keys_s5.py). The five drivers
# sit in different source types on purpose: no single subagent can find them all.
DRIVERS = {
    "product_quality": "Tent pole batch TP-0726 cracks (NW-QA-2026-031, NW-SUP-Q3)",
    "size_fit": "Size chart migration 2026-07-15 with unit errors (NW-MERCH-LOG, NW-SUP-Q3)",
    "shipping_damage": "SwiftShip Columbus hub delays and damage in August (W3, NW-LOG-CARRIER-Q3)",
    "listing_accuracy": "Stove photos show orange, units ship olive (NW-MERCH-LOG, NW-SUP-Q3, W4)",
    "returns_policy": "Free return shipping from 2026-07-01 raised 'changed mind' returns (NW-POLICY-RET, W1)",
}
