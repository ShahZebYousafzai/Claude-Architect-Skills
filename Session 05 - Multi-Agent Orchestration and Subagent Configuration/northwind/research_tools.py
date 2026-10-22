"""Session 5: the five research tools, split across three specialist subagents.

Each function returns a plain dict. run_research_tool() wraps them and turns
failures into the structured error shape from Session 4
(errorCategory / isRetryable / message), so a subagent can decide to retry,
work around, or report the gap upward.

TOOL_LATENCY simulates network time (seconds per call) so the sequential vs
parallel comparison shows a real difference even with the offline fake client.
"""
import os
import re
import time

from research_corpus import INTERNAL_DOCS, RETURN_STATS, WEB_SOURCES

TOOL_LATENCY = float(os.environ.get("NW_TOOL_LATENCY", "0.2"))


# ---------------------------------------------------------------- faults
class ResearchTimeout(Exception):
    """A transient failure: the source did not answer in time."""


_FAULTS = {}   # tool name -> remaining number of calls that should fail


def inject_research_fault(tool: str, times: int = 1) -> None:
    """Make the next `times` calls to `tool` time out (Session 4 style fault)."""
    _FAULTS[tool] = times


def clear_research_faults() -> None:
    _FAULTS.clear()


def _maybe_fail(tool: str) -> None:
    if _FAULTS.get(tool, 0) > 0:
        _FAULTS[tool] -= 1
        raise ResearchTimeout(f"{tool} timed out after 10s")


# ---------------------------------------------------------------- helpers
def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def _score(query: str, text: str) -> int:
    return len(_words(query) & _words(text))


def _snippet(text: str, n: int = 180) -> str:
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


# ---------------------------------------------------------------- web
def search_web(query: str, max_results: int = 4) -> dict:
    _maybe_fail("search_web")
    time.sleep(TOOL_LATENCY)
    ranked = sorted(WEB_SOURCES.values(),
                    key=lambda s: _score(query, s["title"] + " " + s["text"]), reverse=True)
    hits = [s for s in ranked if _score(query, s["title"] + " " + s["text"]) > 0][:max_results]
    return {
        "query": query,
        "results": [
            {"source_id": s["source_id"], "title": s["title"], "publisher": s["publisher"],
             "date": s["date"], "url": s["url"], "snippet": _snippet(s["text"])}
            for s in hits
        ],
    }


def fetch_web_page(source_id: str) -> dict:
    _maybe_fail("fetch_web_page")
    time.sleep(TOOL_LATENCY)
    page = WEB_SOURCES.get(source_id)
    if page is None:
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": f"No web page with source_id {source_id!r}. Use an id from search_web results."}
    return dict(page)


# ---------------------------------------------------------------- internal docs
def search_internal_docs(query: str, max_results: int = 4) -> dict:
    _maybe_fail("search_internal_docs")
    time.sleep(TOOL_LATENCY)

    def doc_text(d):
        return d["title"] + " " + " ".join(d["pages"])

    ranked = sorted(INTERNAL_DOCS.values(), key=lambda d: _score(query, doc_text(d)), reverse=True)
    hits = [d for d in ranked if _score(query, doc_text(d)) > 0][:max_results]
    return {
        "query": query,
        "results": [
            {"doc_id": d["source_id"], "title": d["title"], "owner": d["owner"], "date": d["date"],
             "pages": len(d["pages"]), "snippet": _snippet(d["pages"][0])}
            for d in hits
        ],
    }


def read_internal_doc(doc_id: str, page: int = 1) -> dict:
    _maybe_fail("read_internal_doc")
    time.sleep(TOOL_LATENCY)
    doc = INTERNAL_DOCS.get(doc_id)
    if doc is None:
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": f"No internal document {doc_id!r}. Use a doc_id from search_internal_docs."}
    if not 1 <= int(page) <= len(doc["pages"]):
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": f"{doc_id} has pages 1 to {len(doc['pages'])}; page {page} does not exist."}
    return {"doc_id": doc_id, "title": doc["title"], "owner": doc["owner"], "date": doc["date"],
            "page": int(page), "of_pages": len(doc["pages"]), "text": doc["pages"][int(page) - 1]}


# ---------------------------------------------------------------- dataset
def query_return_stats(quarter: str, breakdown: str = "category") -> dict:
    _maybe_fail("query_return_stats")
    time.sleep(TOOL_LATENCY)
    quarter = quarter.strip().upper().replace(" ", "-")
    key = {"category": "rate_by_category", "reason": "reason_share"}.get(breakdown)
    if key is None:
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": "breakdown must be 'category' (return rate %) or 'reason' (share of returns %)."}
    if quarter not in RETURN_STATS[key]:
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": f"No data for {quarter}. Available: {sorted(RETURN_STATS[key])}."}
    return {"dataset_id": RETURN_STATS["dataset_id"], "quarter": quarter, "breakdown": breakdown,
            "unit": "return rate %" if breakdown == "category" else "% of all returns",
            "values": RETURN_STATS[key][quarter], "coverage": RETURN_STATS["coverage"][quarter]}


# ---------------------------------------------------------------- definitions
RESEARCH_TOOL_DEFS = {
    "search_web": {
        "name": "search_web",
        "description": (
            "Search PUBLIC web articles (industry benchmarks, news, trade blogs). Returns up to 4 hits "
            "with source_id, title, publisher, date, url and a snippet. Snippets are not evidence: call "
            "fetch_web_page for the full text before citing. Does not search Northwind's internal documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Keywords, e.g. 'outdoor gear return rate 2026'"}},
            "required": ["query"],
        },
    },
    "fetch_web_page": {
        "name": "fetch_web_page",
        "description": "Get the full text and metadata of one web result by its source_id (e.g. 'W1') from search_web.",
        "input_schema": {
            "type": "object",
            "properties": {"source_id": {"type": "string", "description": "An id returned by search_web, e.g. 'W3'"}},
            "required": ["source_id"],
        },
    },
    "search_internal_docs": {
        "name": "search_internal_docs",
        "description": (
            "Search Northwind's INTERNAL documents (QA reports, support ticket summaries, logistics reports, "
            "merchandising change logs, policies). Returns doc_id, title, owner, date, page count and a snippet. "
            "Use read_internal_doc to read a page before citing it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Keywords, e.g. 'tent pole defect'"}},
            "required": ["query"],
        },
    },
    "read_internal_doc": {
        "name": "read_internal_doc",
        "description": "Read one page of an internal document by doc_id (from search_internal_docs). Pages start at 1.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "e.g. 'NW-QA-2026-031'"},
                "page": {"type": "integer", "description": "Page number, starting at 1", "default": 1},
            },
            "required": ["doc_id"],
        },
    },
    "query_return_stats": {
        "name": "query_return_stats",
        "description": (
            "Query Northwind's returns database (dataset DS-RET-2026). quarter is 'Q2-2026' or 'Q3-2026'. "
            "breakdown='category' gives return rate % per product category; breakdown='reason' gives each "
            "return reason's share of all returns. Every answer includes a coverage field: report it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quarter": {"type": "string", "description": "'Q2-2026' or 'Q3-2026'"},
                "breakdown": {"type": "string", "enum": ["category", "reason"]},
            },
            "required": ["quarter", "breakdown"],
        },
    },
}

RESEARCH_FUNCTIONS = {
    "search_web": search_web,
    "fetch_web_page": fetch_web_page,
    "search_internal_docs": search_internal_docs,
    "read_internal_doc": read_internal_doc,
    "query_return_stats": query_return_stats,
}


def run_research_tool(name: str, tool_input: dict) -> dict:
    """Execute one research tool and return a dict. Never raises.

    Failures come back in the Session 4 shape so the model can act on them:
    transient -> isRetryable True; bad input -> validation, isRetryable False.
    """
    fn = RESEARCH_FUNCTIONS.get(name)
    if fn is None:
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": f"Unknown tool {name!r}."}
    try:
        return fn(**tool_input)
    except ResearchTimeout as exc:
        return {"isError": True, "errorCategory": "transient", "isRetryable": True,
                "message": str(exc), "attempted": {"tool": name, "input": tool_input}}
    except TypeError as exc:
        return {"isError": True, "errorCategory": "validation", "isRetryable": False,
                "message": f"Bad arguments for {name}: {exc}"}
