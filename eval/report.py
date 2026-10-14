#!/usr/bin/env python3
"""
Turn eval/results/results.csv into the writeup deliverables:
  * a Markdown report (eval/results/report.md) with a per-INTENT Attack-Success-Rate
    matrix (defense x victim model, one row per guardrail judge) with 95% Wilson
    intervals, a payloads-that-ever-landed table and a benign false-positive column, and
  * one grouped bar chart per intent (eval/results/effectiveness_<intent>.png) if
    matplotlib is installed.

The point of splitting by intent: `scoped_mcp` should drive `exfil` ASR to 0 but leave
`prompt_theft` ASR high (scoping tools can't stop the model printing its own prompt),
while `guardrail` / `spotlight` cut both — which is why access control alone isn't enough.

ASR (Attack Success Rate) = fraction of attack runs that leaked (each payload is replayed
`repeats` times per config). Lower is better. Also reported: how many distinct payloads
landed at least once — the number an attacker who simply retries cares about.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def short(model: str) -> str:
    return model.split(":", 1)[-1] if model else "-"


def row_label(r: dict) -> str:
    """Defense, plus the judge model for guardrail defenses (one row per judge)."""
    return f"{r['defense']} [{short(r['guardrail_model'])}]" if r.get("guardrail_model") else r["defense"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def fmt_rate(k: int, n: int) -> str:
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{100.0 * k / n:.0f}% ({100 * lo:.0f}-{100 * hi:.0f})"


def build_tables(rows: list[dict]):
    attack = [r for r in rows if r["kind"] == "attack"]
    control = [r for r in rows if r["kind"] == "control"]
    labels = sorted({row_label(r) for r in rows}, key=lambda d: (not d.startswith("none"), d))
    app_models = sorted({r["app_model"] for r in rows})

    leaked = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(lambda: defaultdict(int))
    ever = defaultdict(lambda: defaultdict(set))     # payloads that leaked at least once
    payloads = defaultdict(lambda: defaultdict(set))
    for r in attack:
        d, m = row_label(r), r["app_model"]
        totals[d][m] += 1
        payloads[d][m].add(r["payload"])
        if r["leaked"] == "True":
            leaked[d][m] += 1
            ever[d][m].add(r["payload"])

    fp_block = defaultdict(int)
    fp_total = defaultdict(int)
    for r in control:
        fp_total[row_label(r)] += 1
        if r["outcome"] == "blocked":
            fp_block[row_label(r)] += 1
    return labels, app_models, leaked, totals, ever, payloads, fp_block, fp_total


def render_markdown_section(intent, rows, labels, app_models, leaked, totals, ever, payloads,
                            fp_block, fp_total) -> str:
    cols = [short(m) for m in app_models]
    lines = [f"## Intent: `{intent}`", "",
             "**Attack Success Rate** per run, with 95% Wilson interval — lower is better. "
             "Rows are defenses (guardrail rows name the judge model); columns are victim models.", "",
             "| Defense | " + " | ".join(cols) + " | Benign FP |",
             "|" + "---|" * (len(cols) + 2)]
    for d in labels:
        cells = [fmt_rate(leaked[d][m], totals[d][m]) for m in app_models]
        lines.append(f"| `{d}` | " + " | ".join(cells) + f" | {fmt_rate(fp_block[d], fp_total[d])} |")
    lines += ["", "**Payloads that landed at least once** across the repeats (an attacker can retry):", "",
              "| Defense | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for d in labels:
        cells = [f"{len(ever[d][m])}/{len(payloads[d][m])}" if payloads[d][m] else "-" for m in app_models]
        lines.append(f"| `{d}` | " + " | ".join(cells) + " |")
    if rows and "behavior" in rows[0]:
        # Defense signal vs model behaviour: a pre-filter that let the payload through counts
        # as a miss even when the victim model then refused or ignored it.
        behaviors = ["leaked", "refused", "attempted", "ignored", "not_run", "error"]
        lines += ["", "**Defense signal vs victim behaviour** (attack runs). _Detected_ = the defense "
                  "itself fired (pre-filter blocked, or the scoped MCP denied a call); `-` = the defense "
                  "has no detector of its own, compare its ASR with `none`. The behaviour columns say what "
                  "the victim model did when it ran — `refused`/`ignored` after a pre-filter pass are "
                  "misses the model happened to cover.", "",
                  "| Defense | Detected | " + " | ".join(behaviors) + " |", "|" + "---|" * (len(behaviors) + 2)]
        for d in labels:
            drows = [r for r in rows if r["kind"] == "attack" and row_label(r) == d]
            has_signal = any(r["signal"] for r in drows)
            det = fmt_rate(sum(r["detected"] == "True" for r in drows), len(drows)) if has_signal else "-"
            counts = {b: sum(1 for r in drows if r["behavior"] == b) for b in behaviors}
            lines.append(f"| `{d}` | {det} | " + " | ".join(str(counts[b]) for b in behaviors) + " |")
    else:
        outcomes = ["leaked", "safe", "blocked", "unavailable", "error"]
        lines += ["", "| Defense | " + " | ".join(outcomes) + " |", "|" + "---|" * (len(outcomes) + 1)]
        for d in labels:
            drows = [r for r in rows if r["kind"] == "attack" and row_label(r) == d]
            counts = {o: sum(1 for r in drows if r["outcome"] == o) for o in outcomes}
            lines.append(f"| `{d}` | " + " | ".join(str(counts[o]) for o in outcomes) + " |")
    return "\n".join(lines) + "\n"


def render_chart(intent, defenses, app_models, leaked, totals, out_png: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"(matplotlib unavailable, skipping chart for {intent}: {e})")
        return
    x = np.arange(len(defenses))
    width = 0.8 / max(1, len(app_models))
    fig, ax = plt.subplots(figsize=(max(8, len(defenses) * 1.3), 5))
    for i, m in enumerate(app_models):
        vals = [100.0 * leaked[d][m] / totals[d][m] if totals[d][m] else 0 for d in defenses]
        ax.bar(x + i * width, vals, width, label=short(m))
    ax.set_ylabel("Attack Success Rate (%) — lower is better")
    ax.set_title(f"Mitigation effectiveness — intent: {intent}")
    ax.set_xticks(x + width * (len(app_models) - 1) / 2)
    ax.set_xticklabels(defenses, rotation=30, ha="right")
    ax.set_ylim(0, 100)
    ax.legend(title="victim model")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    print(f"Wrote chart -> {out_png}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(_REPO_ROOT / "eval" / "results" / "results.csv"))
    ap.add_argument("--out-md", default=str(_REPO_ROOT / "eval" / "results" / "report.md"))
    args = ap.parse_args()

    rows = load_rows(Path(args.results))
    if not rows:
        ap.error("No rows in results CSV.")
    for r in rows:
        r.setdefault("intent", "exfil")  # tolerate pre-intent CSVs
    intents = sorted({r["intent"] for r in rows})

    doc = ["# Prompt-injection mitigation effectiveness", "",
           "_ASR = Attack Success Rate (lower is better). Benign FP = benign control wrongly blocked._", ""]
    out_dir = Path(args.out_md).parent
    for intent in intents:
        rows_i = [r for r in rows if r["intent"] == intent]
        d, m, leaked, totals, ever, pls, fpb, fpt = build_tables(rows_i)
        doc.append(render_markdown_section(intent, rows_i, d, m, leaked, totals, ever, pls, fpb, fpt))
        render_chart(intent, d, m, leaked, totals, out_dir / f"effectiveness_{intent}.png")

    md = "\n".join(doc)
    Path(args.out_md).write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote report -> {args.out_md}")


if __name__ == "__main__":
    main()
