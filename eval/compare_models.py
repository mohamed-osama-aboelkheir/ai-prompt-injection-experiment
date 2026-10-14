#!/usr/bin/env python3
"""
Compare victim models on the full Phase-1 corpus with no defense (1 run per payload).

The Haiku 4.5 column is the Phase-1 label itself: a payload under base/working/ leaked on
Haiku 4.5 when it was generated, one under base/failed/ didn't. Every other model comes from
a `run_matrix.py --defenses none --include-failed` CSV. Transfer = of the payloads that
worked (or failed) on Haiku 4.5, how many leaked on the other model.

  python eval/compare_models.py \
    --run "gpt-5-mini=eval/results/gpt-5-mini_none.csv" \
    --run "Haiku 5.5=eval/results/haiku-5-5_none.csv" \
    --out-md eval/results/compare_models_none.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from report import load_rows, wilson

BASE = "Haiku 4.5"
INTENTS = ("exfil", "prompt_theft")


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.1f}% ({k}/{n})" if n else "-"


def pct_ci(k: int, n: int) -> str:
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{pct(k, n)} [{100 * lo:.0f}–{100 * hi:.0f}]"


def load_run(path: Path) -> dict[tuple[str, str], dict]:
    """(intent, payload path) -> row, attack rows of the `none` defense only."""
    return {(r["intent"], r["payload"]): r for r in load_rows(path)
            if r["kind"] == "attack" and r["defense"] == "none"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, metavar="NAME=CSV")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", help="Numbers for slides/charts")
    args = ap.parse_args()

    runs = {}
    for spec in args.run:
        name, _, path = spec.partition("=")
        runs[name] = load_run(Path(path))
    names = list(runs)
    models = [BASE] + names

    # Corpus = payloads every run covers (they should all cover the same 325).
    keys = sorted(set.intersection(*(set(r) for r in runs.values())))
    missing = {n: len(set().union(*(set(r) for r in runs.values())) - set(r)) for n, r in runs.items()}

    def leaked(model: str, key) -> bool:
        if model == BASE:
            return "/base/working/" in key[1]
        return runs[model][key]["leaked"] == "True"

    by_intent = {i: [k for k in keys if k[0] == i] for i in INTENTS}
    data: dict = {"models": models, "intents": {}, "transfer": {}, "techniques": {}, "cost": {}}
    out = [f"# Victim model comparison, no defense, full Phase-1 corpus",
           "",
           f"{BASE} = Phase-1 label (the run that generated each payload). Others = one replay each "
           f"({', '.join(f'{n}: {len(runs[n])} payloads' for n in names)}; compared on the "
           f"{len(keys)} all runs share). Payloads were generated against {BASE} (Opus 5 attacker).",
           ""]
    if any(missing.values()):
        out += [f"⚠ Missing rows (not compared): {missing}", ""]

    # Overall per intent
    out += ["## Overall leak rate per intent (95% Wilson CI)", "",
            "| Intent | " + " | ".join(models) + " |", "|---" * (len(models) + 1) + "|"]
    for intent, ks in list(by_intent.items()) + [("both", keys)]:
        cells = []
        for m in models:
            k = sum(leaked(m, x) for x in ks)
            cells.append(pct_ci(k, len(ks)))
            data["intents"].setdefault(intent, {})[m] = [k, len(ks)]
        label = "**both**" if intent == "both" else intent
        out.append(f"| {label} | " + " | ".join(cells) + " |")

    # Transfer
    out += ["", f"## Transfer from {BASE}", "",
            f"| Model | Intent | {BASE}-working → leaked | {BASE}-failed → leaked | behaviour (leaked/attempted/refused/ignored/error) |",
            "|---|---|---|---|---|"]
    for m in names:
        for intent, ks in by_intent.items():
            w = [k for k in ks if leaked(BASE, k)]
            f = [k for k in ks if not leaked(BASE, k)]
            wk, fk = sum(leaked(m, k) for k in w), sum(leaked(m, k) for k in f)
            beh = Counter(runs[m][k]["behavior"] for k in ks)
            out.append(f"| {m} | {intent} | {pct(wk, len(w))} | {pct(fk, len(f))} | "
                       f"{beh['leaked']}/{beh['attempted']}/{beh['refused']}/{beh['ignored']}/{beh['error']} |")
            data["transfer"].setdefault(m, {})[intent] = {"working": [wk, len(w)], "failed": [fk, len(f)],
                                                          "behavior": dict(beh)}

    # Pairwise overlap among the non-base models
    if len(names) > 1:
        out += ["", "## Overlap (payloads that leaked on both)", "", "| Intent | Pair | Both | Only first | Only second |",
                "|---|---|---|---|---|"]
        for intent, ks in by_intent.items():
            for i, a in enumerate(models):
                for b in models[i + 1:]:
                    both = sum(leaked(a, k) and leaked(b, k) for k in ks)
                    oa = sum(leaked(a, k) and not leaked(b, k) for k in ks)
                    ob = sum(leaked(b, k) and not leaked(a, k) for k in ks)
                    out.append(f"| {intent} | {a} vs {b} | {both} | {oa} | {ob} |")

    # Per technique
    out += ["", "## Per technique (leaked / payloads)"]
    for intent, ks in list(by_intent.items()) + [("overall", keys)]:
        groups = defaultdict(list)
        for k in ks:
            groups[runs[names[0]][k]["technique"]].append(k)
        rows = []
        for tech, tks in groups.items():
            counts = [sum(leaked(m, k) for k in tks) for m in models]
            rows.append((tech, len(tks), counts))
            data["techniques"].setdefault(intent, {})[tech] = {"n": len(tks), **dict(zip(models, counts))}
        rows.sort(key=lambda r: (-max(r[2]), r[0]))
        out += ["", f"### {intent}", "", "| Technique | Payloads | " + " | ".join(models) + " |",
                "|---" * (len(models) + 2) + "|"]
        for tech, n, counts in rows:
            out.append(f"| {tech} | {n} | " + " | ".join(f"{100 * c / n:.0f}% ({c})" for c in counts) + " |")

    # Cost / latency
    out += ["", "## Cost and latency per victim run (measured)", "", "| Model | Mean cost | Median latency | Mean in / out tokens |",
            "|---|---|---|---|"]
    for m in names:
        rs = [runs[m][k] for k in keys]
        cost = statistics.mean(float(r["cost_usd"] or 0) for r in rs)
        lat = statistics.median(float(r["latency_ms"] or 0) for r in rs) / 1000
        tin = statistics.mean(float(r["input_tokens"] or 0) for r in rs)
        tout = statistics.mean(float(r["output_tokens"] or 0) for r in rs)
        out.append(f"| {m} | ${cost:.4f} | {lat:.0f} s | {tin:,.0f} / {tout:,.0f} |")
        data["cost"][m] = {"mean_usd": cost, "median_s": lat}

    Path(args.out_md).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
