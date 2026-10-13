"""Measure which tool Claude picks FIRST for a request (Session 3).

Selection happens on the first call, so we do not need the whole loop: one request
per case, no tools executed. That keeps every run cheap and fast.

    result = evaluate(CASES, TOOLS, label="baseline")
    print_eval(result)
    compare(baseline, improved)
"""
from concurrent.futures import ThreadPoolExecutor

from common import MODEL, SYSTEM, client as default_client
from selection_cases import NONE


def first_call(request, tools, system=SYSTEM, tool_choice=None, client=default_client, model=MODEL):
    """One request. Returns (list of tool names requested, response). [NONE] if no tool."""
    kwargs = dict(model=model, max_tokens=512, system=system, tools=tools,
                  messages=[{"role": "user", "content": request}])
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    response = client.messages.create(**kwargs)
    names = [b.name for b in response.content if b.type == "tool_use"]
    return (names or [NONE]), response


def evaluate(cases, tools, system=SYSTEM, repeats=2, label="", client=default_client, workers=6,
             aliases=None):
    """Run every case `repeats` times. Scores the first tool requested in each run.

    aliases maps a renamed tool to the name the cases expect, e.g.
    {"get_order_details": "lookup_order"}, so a renamed toolset is scored fairly.
    """
    aliases = aliases or {}
    jobs = [(c, r) for c in cases for r in range(repeats)]

    def run(job):
        case, _ = job
        names, _ = first_call(case["request"], tools, system=system, client=client)
        return case["id"], aliases.get(names[0], names[0])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        picks = list(pool.map(run, jobs))

    rows = []
    for case in cases:
        chosen = [p for cid, p in picks if cid == case["id"]]
        rows.append({
            "id": case["id"],
            "request": case["request"],
            "expect": case["expect"],
            "picks": chosen,
            "correct": sum(p in case["expect"] for p in chosen),
            "consistent": len(set(chosen)) == 1,
        })
    total = len(cases) * repeats
    return {
        "label": label or "run",
        "rows": rows,
        "accuracy": sum(r["correct"] for r in rows) / total,
        "consistency": sum(r["consistent"] for r in rows) / len(rows),
        "repeats": repeats,
    }


def print_eval(result, only_misses=False):
    print(f"== {result['label']}: accuracy {result['accuracy']:.0%}, "
          f"consistent across repeats {result['consistency']:.0%} ==")
    for r in result["rows"]:
        ok = r["correct"] == len(r["picks"])
        if only_misses and ok:
            continue
        mark = "ok  " if ok else "MISS"
        flip = "" if r["consistent"] else "  (flips)"
        print(f"{mark} {r['id']:<3} picked {', '.join(r['picks']):<32} want {'/'.join(sorted(r['expect']))}{flip}")
        if not ok:
            print(f"         \"{r['request']}\"")


def spread(result, ids):
    """Which distinct tools were picked for a group of cases that share one intent."""
    picks = [p for r in result["rows"] if r["id"] in ids for p in r["picks"]]
    return {name: picks.count(name) for name in sorted(set(picks))}


def compare(*results):
    """Side-by-side table of several evaluate() results over the same cases."""
    head = f"{'case':<5}" + "".join(f"{res['label'][:22]:<24}" for res in results)
    print(head)
    print("-" * len(head))
    for i, row in enumerate(results[0]["rows"]):
        line = f"{row['id']:<5}"
        for res in results:
            r = res["rows"][i]
            line += f"{r['correct']}/{len(r['picks'])} {r['picks'][0][:16]:<18}"
        print(line)
    print("-" * len(head))
    print(f"{'acc':<5}" + "".join(f"{res['accuracy']:<24.0%}" for res in results))
    print(f"{'cons':<5}" + "".join(f"{res['consistency']:<24.0%}" for res in results))


def lint_tools(tools):
    """Quick checklist from the official guidance. Prints issues; returns True if none.

    A heuristic, not a grader: it cannot tell a good description from a long one.
    The selection tests are the real measure.
    """
    names = {t["name"] for t in tools}
    clean = True
    for t in tools:
        d = t.get("description", "")
        issues = []
        if d.count(". ") + d.endswith(".") < 3:
            issues.append("fewer than 3 sentences (docs: at least 3-4)")
        if " use " not in f" {d.lower()} " and "use it" not in d.lower():
            issues.append("does not say WHEN to use it")
        if not any(other in d for other in names - {t["name"]}):
            issues.append("names no neighbouring tool (no boundary: 'use X instead')")
        if "return" not in d.lower():
            issues.append("does not say what it returns")
        for prop, spec in t["input_schema"].get("properties", {}).items():
            if not spec.get("description"):
                issues.append(f"parameter '{prop}' has no description")
        print(("ok    " if not issues else "CHECK ") + t["name"])
        for i in issues:
            print("        -", i)
        clean &= not issues
    return clean
