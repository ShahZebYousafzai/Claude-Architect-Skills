"""A scripted, thread-safe stand-in for the Anthropic client for multi-agent runs.

Why a new fake: with parallel subagents, requests from different agents arrive in
an unpredictable order, so one list of scripted replies (Session 2's FakeClient)
no longer works. This client routes each request to the right script:

  * the coordinator is recognised by its delegate_task tool;
  * a subagent is recognised by its toolset (matched against SUBAGENTS);
  * each conversation is identified by its FIRST user message, and is bound to the
    first unused script for that agent whose `match` text appears in it.

Each call sleeps `latency` seconds to imitate model time, so parallel vs sequential
timings are meaningful offline. Real research tools still run (with their own latency).
"""
import json
import threading
import time
from types import SimpleNamespace as NS

from subagents import SUBAGENTS


def text(t):
    return NS(type="text", text=t)


def tool_use(id, name, **tool_input):
    return NS(type="tool_use", id=id, name=name, input=tool_input)


def reply(stop_reason, *blocks):
    return NS(stop_reason=stop_reason, content=list(blocks))


def _first_user_text(messages):
    first = messages[0]["content"]
    if isinstance(first, str):
        return first
    return " ".join(getattr(b, "text", "") if not isinstance(b, dict) else b.get("text", "") for b in first)


class RoutingFakeClient:
    def __init__(self, scripts, latency=0.25):
        # scripts: {"coordinator": [(match, [replies])], "web_researcher": [(match, [replies])], ...}
        self._scripts = {agent: [{"match": m, "replies": list(r), "used": False} for m, r in items]
                         for agent, items in scripts.items()}
        self._bound = {}
        self._lock = threading.Lock()
        self.latency = latency
        self.requests = []
        self.messages = self

    def _agent_for(self, kwargs):
        names = {t["name"] for t in kwargs.get("tools", [])}
        if "delegate_task" in names:
            return "coordinator"
        for name, spec in SUBAGENTS.items():
            if names == set(spec.tools):
                return name
        raise AssertionError(f"Request with unexpected toolset {sorted(names)}: subagent tools must be scoped")

    def create(self, **kwargs):
        time.sleep(self.latency)
        agent = self._agent_for(kwargs)
        key = (agent, _first_user_text(kwargs["messages"]))
        with self._lock:
            self.requests.append({"agent": agent, "system": kwargs.get("system"),
                                  "tools": [t["name"] for t in kwargs.get("tools", [])],
                                  "n_messages": len(kwargs["messages"]),
                                  "first_message": key[1]})
            script = self._bound.get(key)
            if script is None:
                for candidate in self._scripts.get(agent, []):
                    if not candidate["used"] and candidate["match"].lower() in key[1].lower():
                        candidate["used"] = True
                        script = self._bound[key] = candidate
                        break
            if script is None:
                raise AssertionError(f"No script left for {agent} with first message: {key[1][:120]!r}")
            if not script["replies"]:
                raise AssertionError(f"{agent} asked for more replies than scripted")
            return script["replies"].pop(0)


# ---------------------------------------------------------------- shared content
CONTEXT = (
    "Overall question: why did Northwind's return rate rise in Q3 2026 and what should change before "
    "the holidays. Northwind sells camping gear online in the US and ships mostly with SwiftShip. "
    "Period of interest: Q3 2026 compared with Q2 2026. Record dates for every source."
)


def _final(report):
    return reply("end_turn", text(json.dumps(report)))


def _f(claim, evidence, sid, typ, title, date, locator):
    return {"claim": claim, "evidence": evidence,
            "source": {"source_id": sid, "type": typ, "title": title, "date": date, "locator": locator}}


WEB_REPORT = {
    "subagent": "web_researcher", "status": "complete",
    "findings": [
        _f("Industry average return rate for outdoor gear online was 11.8% in H1 2026; fit, transit damage and "
           "'not as described' are the top reasons.", "11.8% in H1 2026; fit 31%, damaged in transit 22%, not as described 19%",
           "W1", "web", "2026 Outdoor E-commerce Returns Benchmark", "2026-08-14",
           "https://research.trailhead-analytics.example/outdoor-returns-2026"),
        _f("Free return shipping raised 'changed mind' returns by about 3 points within a quarter.",
           "'changed mind' returns rise by about 3 percentage points", "W1", "web",
           "2026 Outdoor E-commerce Returns Benchmark", "2026-08-14",
           "https://research.trailhead-analytics.example/outdoor-returns-2026"),
        _f("SwiftShip's Columbus hub ran at reduced capacity from late July; delays of 3-5 days and more damage claims in August.",
           "delays of 3 to 5 days and a rise in damaged-parcel claims during August", "W3", "web",
           "SwiftShip hub congestion delays parcels across the Midwest", "2026-08-22",
           "https://freightdaily.example/news/swiftship-columbus-hub-delays"),
        _f("Photo/colour mismatches typically double 'not as described' returns for a SKU.",
           "'not as described' returns for that SKU typically double", "W4", "web",
           "Not as described: how product photos drive returns", "2026-06-10",
           "https://ecominsights.example/articles/photos-and-returns"),
    ],
    "coverage": "search_web x2, fetch_web_page x3 (W1, W3, W4). W2 (2024) seen in results; W5 (product review) not relevant.",
    "gaps": ["W2 (2024) gives an 8% category rate; older than W1 and conflicts with it."],
}

DOC_REPORT_R1 = {
    "subagent": "doc_analyst", "status": "complete",
    "findings": [
        _f("Tent pole batch TP-0726 had hairline cracks; about 1,150 Trailhead 2P tents shipped 2026-07-08 to 2026-08-01.",
           "About 1,150 tents with TP-0726 poles shipped between 2026-07-08 and 2026-08-01",
           "NW-QA-2026-031", "internal", "QA incident report: tent pole batch TP-0726", "2026-08-03", "page 2"),
        _f("Sleeping bag and jacket size charts were migrated on 2026-07-15 with cm values in inch columns for 14 SKUs; "
           "'runs small' became the top support theme that week.",
           "chest and length values were entered in centimetres in columns labelled inches for 14 SKUs",
           "NW-MERCH-LOG", "internal", "Merchandising change log, Q3 2026", "2026-09-30", "page 1"),
        _f("SwiftShip on-time delivery fell from 96% to 81% and damage rose from 0.6% to 1.4% in August.",
           "On-time delivery fell from 96% in July to 81% in August", "NW-LOG-CARRIER-Q3", "internal",
           "Carrier performance report: SwiftShip, July to September 2026", "2026-10-05", "page 1"),
        _f("Ridge pocket stove photos (published 2026-08-02) show the orange sample; production units are olive.",
           "Photos were taken of the orange pre-production sample; production units are olive",
           "NW-MERCH-LOG", "internal", "Merchandising change log, Q3 2026", "2026-09-30", "page 2"),
    ],
    "coverage": "search_internal_docs x3; read NW-QA-2026-031 p1-2, NW-SUP-Q3 p1-2, NW-LOG-CARRIER-Q3 p1, NW-MERCH-LOG p1-2.",
    "gaps": ["Did not search for returns policy changes in Q3."],
}

DOC_REPORT_POLICY = {
    "subagent": "doc_analyst", "status": "complete",
    "findings": [
        _f("Return shipping became free for all orders from 2026-07-01 (previously USD 7.95 deducted).",
           "From 2026-07-01, return shipping is free for all orders", "NW-POLICY-RET", "internal",
           "Returns policy, effective 2026-07-01", "2026-06-20", "page 1"),
    ],
    "coverage": "search_internal_docs 'returns policy free return shipping'; read NW-POLICY-RET p1.",
    "gaps": [],
}

DATA_REPORT = {
    "subagent": "data_analyst", "status": "partial",
    "findings": [
        _f("Overall return rate rose from 9.1% (Q2) to 13.4% (Q3); tents doubled from 7.0% to 15.2%.",
           "overall 9.1 -> 13.4; tents 7.0 -> 15.2; apparel 12.0 -> 19.5; sleeping_bags 8.5 -> 14.0",
           "DS-RET-2026", "dataset", "Returns database", "2026-09-21", "Q2-2026 vs Q3-2026, breakdown=category"),
        _f("Defect share of returns rose from 15% to 24%, damaged in transit from 12% to 21%, not as described from 9% to 15%, "
           "changed mind from 7% to 11%.", "defect 15->24, damaged_in_transit 12->21, not_as_described 9->15, changed_mind 7->11",
           "DS-RET-2026", "dataset", "Returns database", "2026-09-21", "Q2-2026 vs Q3-2026, breakdown=reason"),
    ],
    "coverage": "Q2-2026 complete; Q3-2026 only through 2026-09-21 (warehouse backlog).",
    "gaps": ["Q3 figures are partial: last 9 days of September not loaded."],
}

GOOD_FINAL = """# Why Northwind's returns rose in Q3 2026

Return rate rose from 9.1% to 13.4% (DS-RET-2026, Q3 partial to 2026-09-21). Five drivers, by evidence strength:

1. **Product quality: tent pole batch TP-0726.** ~1,150 Trailhead 2P tents shipped 2026-07-08 to 08-01 with cracking poles (NW-QA-2026-031, 2026-08-03). Tent returns 7.0% -> 15.2%; defect share 15% -> 24% (DS-RET-2026).
2. **Size and fit: size chart migration.** cm values in inch columns for 14 SKUs from 2026-07-15 (NW-MERCH-LOG); "runs small" was the top support theme (NW-SUP-Q3). Apparel 12.0% -> 19.5%.
3. **Shipping damage: SwiftShip Columbus hub.** On-time 96% -> 81%, damage 0.6% -> 1.4% in August (NW-LOG-CARRIER-Q3, 2026-10-05; W3, 2026-08-22). Damaged in transit 12% -> 21%.
4. **Listing accuracy: stove photos.** Photos show the orange sample, units ship olive (NW-MERCH-LOG). Not as described 9% -> 15%; W4 (2026-06-10) says mismatches double these returns.
5. **Returns policy: free return shipping from 2026-07-01** (NW-POLICY-RET). Changed mind 7% -> 11%, in line with W1's ~3-point effect (2026-08-14).

**Recommendations:** replace TP-0726 poles proactively; fix the 14 size charts; re-shoot STOVE-1 photos; add a second carrier for Midwest lanes until mid-October; keep free returns but monitor changed-mind share.

**Coverage and gaps:** Q3 data partial (to 2026-09-21). Industry benchmark sources disagree: 11.8% (W1, 2026) vs ~8% (W2, 2024); W1 is newer and larger."""

NARROW_FINAL = """# Q3 2026 returns: quality review

Tents: supplier pole batch TP-0726 had hairline cracks; about 1,150 tents shipped with them (NW-QA-2026-031). This explains the increase.
Sleeping bags: no QA incident or defect report found.
Stoves: no QA incident or defect report found.
Recommendation: replace the affected tent poles and tighten supplier inspection."""


def _web_script():
    return [
        reply("tool_use", tool_use("w1", "search_web", query="outdoor gear e-commerce return rate 2026")),
        reply("tool_use", tool_use("w2", "fetch_web_page", source_id="W1"),
              tool_use("w3", "search_web", query="SwiftShip delays damage August 2026")),
        reply("tool_use", tool_use("w4", "fetch_web_page", source_id="W3"),
              tool_use("w5", "fetch_web_page", source_id="W4")),
        _final(WEB_REPORT),
    ]


def _doc_script():
    return [
        reply("tool_use", tool_use("d1", "search_internal_docs", query="tent pole defect QA incident"),
              tool_use("d2", "search_internal_docs", query="support ticket themes Q3")),
        reply("tool_use", tool_use("d3", "read_internal_doc", doc_id="NW-QA-2026-031", page=2),
              tool_use("d4", "read_internal_doc", doc_id="NW-SUP-Q3", page=1),
              tool_use("d5", "read_internal_doc", doc_id="NW-SUP-Q3", page=2)),
        reply("tool_use", tool_use("d6", "read_internal_doc", doc_id="NW-LOG-CARRIER-Q3", page=1),
              tool_use("d7", "read_internal_doc", doc_id="NW-MERCH-LOG", page=1),
              tool_use("d8", "read_internal_doc", doc_id="NW-MERCH-LOG", page=2)),
        _final(DOC_REPORT_R1),
    ]


def _policy_script():
    return [
        reply("tool_use", tool_use("p1", "search_internal_docs", query="returns policy free return shipping")),
        reply("tool_use", tool_use("p2", "read_internal_doc", doc_id="NW-POLICY-RET", page=1)),
        _final(DOC_REPORT_POLICY),
    ]


def _data_script():
    return [
        reply("tool_use", tool_use("s1", "query_return_stats", quarter="Q2-2026", breakdown="category"),
              tool_use("s2", "query_return_stats", quarter="Q3-2026", breakdown="category")),
        reply("tool_use", tool_use("s3", "query_return_stats", quarter="Q2-2026", breakdown="reason"),
              tool_use("s4", "query_return_stats", quarter="Q3-2026", breakdown="reason")),
        _final(DATA_REPORT),
    ]


def _coordinator_round1():
    return reply(
        "tool_use",
        text("I'll split this by source type so the three specialists can work in parallel."),
        tool_use("c1", "delegate_task", subagent_type="web_researcher",
                 task="Find external evidence on what drives online outdoor-gear returns in 2026: industry "
                      "benchmarks, carrier disruption news (especially SwiftShip), and research on listing accuracy.",
                 context=CONTEXT),
        tool_use("c2", "delegate_task", subagent_type="doc_analyst",
                 task="Find what changed inside Northwind during Q3 2026 that could raise returns: QA incidents, "
                      "support ticket themes, carrier performance, merchandising changes.",
                 context=CONTEXT),
        tool_use("c3", "delegate_task", subagent_type="data_analyst",
                 task="Measure the change from Q2 to Q3 2026 in return rate by product category and in the share "
                      "of each return reason.",
                 context=CONTEXT),
    )


def _coordinator_round2():
    return reply(
        "tool_use",
        text("Post-purchase policy is unexamined and 'changed mind' rose 7% -> 11%. Following up."),
        tool_use("c4", "delegate_task", subagent_type="doc_analyst",
                 task="Check whether a returns policy change took effect in Q3 2026 (return window, return "
                      "shipping cost) and give its effective date.",
                 context=CONTEXT + " Earlier findings: 'changed mind' share rose from 7% (Q2) to 11% (Q3) "
                      "(DS-RET-2026); W1 (2026-08-14) reports free return shipping adds about 3 points to "
                      "changed-mind returns."),
    )


def good_scripts():
    """Model-driven run: 3 parallel delegations, one gap-driven follow-up, then synthesis."""
    return {
        "coordinator": [("", [_coordinator_round1(), _coordinator_round2(), reply("end_turn", text(GOOD_FINAL))])],
        "web_researcher": [("external evidence", _web_script())],
        "doc_analyst": [("inside Northwind", _doc_script()), ("returns policy change", _policy_script())],
        "data_analyst": [("Measure the change", _data_script())],
    }


def _narrow_doc(category, qa_hit):
    steps = [reply("tool_use", tool_use(f"n{category[:2]}1", "search_internal_docs",
                                        query=f"{category} quality defect QA incident"))]
    if qa_hit:
        steps.append(reply("tool_use", tool_use(f"n{category[:2]}2", "read_internal_doc",
                                                doc_id="NW-QA-2026-031", page=1)))
        report = {"subagent": "doc_analyst", "status": "complete",
                  "findings": [_f("Pole batch TP-0726 cracked; about 1,150 tents affected.",
                                  "Hairline cracks found in aluminium pole sections from supplier batch TP-0726",
                                  "NW-QA-2026-031", "internal", "QA incident report: tent pole batch TP-0726",
                                  "2026-08-03", "page 1")],
                  "coverage": f"QA incidents for {category}", "gaps": []}
    else:
        report = {"subagent": "doc_analyst", "status": "complete", "findings": [],
                  "coverage": f"QA incidents for {category}: none found", "gaps": []}
    steps.append(_final(report))
    return steps


def narrow_scripts():
    """Every subagent succeeds; the decomposition was too narrow. (Mirror of sample Q7.)"""
    coordinator = [
        reply("tool_use",
              tool_use("k1", "delegate_task", subagent_type="doc_analyst",
                       task="Find quality defects behind tent returns in Q3 2026.", context="Northwind, Q3 2026."),
              tool_use("k2", "delegate_task", subagent_type="doc_analyst",
                       task="Find quality defects behind sleeping bag returns in Q3 2026.", context="Northwind, Q3 2026."),
              tool_use("k3", "delegate_task", subagent_type="doc_analyst",
                       task="Find quality defects behind stove returns in Q3 2026.", context="Northwind, Q3 2026.")),
        reply("end_turn", text(NARROW_FINAL)),
    ]
    return {
        "coordinator": [("", coordinator)],
        "doc_analyst": [("tent returns", _narrow_doc("tents", True)),
                        ("sleeping bag returns", _narrow_doc("sleeping bags", False)),
                        ("stove returns", _narrow_doc("stoves", False))],
    }


def fault_scripts():
    """The returns database times out. The data_analyst reports a structured failure;
    the coordinator keeps going and lists the gap. (Session 4 propagation, now across agents.)"""
    failed = {
        "subagent": "data_analyst", "status": "failed", "findings": [],
        "coverage": "Attempted query_return_stats Q2-2026 and Q3-2026 (category); both timed out, retried once.",
        "gaps": ["Returns database unavailable (transient timeout). Quantities of change could not be measured. "
                 "Alternative: rerun later, or use NW-SUP-Q3 ticket counts as a rough proxy."],
        "error": {"errorCategory": "transient", "isRetryable": True, "message": "query_return_stats timed out after 10s"},
    }
    data = [
        reply("tool_use", tool_use("f1", "query_return_stats", quarter="Q2-2026", breakdown="category")),
        reply("tool_use", tool_use("f2", "query_return_stats", quarter="Q2-2026", breakdown="category")),
        _final(failed),
    ]
    coordinator = [_coordinator_round1(), reply("end_turn", text(FAULT_FINAL))]
    return {
        "coordinator": [("", coordinator)],
        "web_researcher": [("external evidence", _web_script())],
        "doc_analyst": [("inside Northwind", _doc_script())],
        "data_analyst": [("Measure the change", data)],
    }


FAULT_FINAL = """# Why Northwind's returns rose in Q3 2026 (provisional)

Drivers supported by documents: tent pole batch TP-0726 (NW-QA-2026-031); size chart unit errors from 2026-07-15
(NW-MERCH-LOG, NW-SUP-Q3); SwiftShip Columbus hub delays and damage in August (NW-LOG-CARRIER-Q3, W3);
stove photos showing the wrong colour (NW-MERCH-LOG, W4).

**Coverage and gaps:** the returns database timed out (data_analyst: transient, retryable), so the size of each
driver is NOT measured in this run. Returns policy changes were not examined. Rerun the data task before
prioritising fixes by impact."""
