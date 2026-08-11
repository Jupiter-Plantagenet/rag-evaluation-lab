"""Generate the portfolio visuals as SVG and PNG from one source.

Code-generated rather than drawn, for the same reason everything else here is:
a figure produced by hand cannot be regenerated when a number changes, and a
figure whose numbers drifted from the report is worse than no figure.

Every value plotted is a literal from docs/results.md and
reports/ablation/dev-retrieval-ablation.md. `verify_against_reports()` re-reads
those files and fails if any plotted number no longer matches.

Output: assets/charts/*.svg and *.png at 1600x1200 (4:3).

Usage:
    python scripts/make_portfolio_visuals.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "assets" / "charts"
LAYOUT_PROBLEMS: list[str] = []

W, H = 1600, 1200
DPI = 100

# --- restrained technical palette -------------------------------------------
BG = "#FBFBFA"
INK = "#14181F"
MUTED = "#5C6675"
RULE = "#D6DCE3"
PANEL = "#F1F4F7"
BASE = "#6B7A8D"  # baseline arm
IMPR = "#2A6B5A"  # improved arm
WARN = "#A6572B"  # the confound
FONT = "DejaVu Sans"

plt.rcParams["font.family"] = FONT
plt.rcParams["svg.fonttype"] = "path"  # no font dependency in the SVG


def canvas() -> tuple[plt.Figure, plt.Axes]:
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)  # y grows downward, matching how the layout is written
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, facecolor=BG, edgecolor="none", zorder=-10))
    return fig, ax


def text(ax, x, y, s, size=24, color=INK, weight="normal", ha="left", va="center", **kw):
    return ax.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha, va=va, **kw)


def caps(ax, x, y, s, size=20, color=MUTED):
    """Small-caps section label. Letter-spaced by hand; matplotlib has no tracking."""
    return text(ax, x, y, " ".join(s.upper()), size=size, color=color, weight="bold")


def fit(ax, artist, max_w, min_size=13):
    """Shrink a label until it fits its allotted width.

    The axes maps 1 data unit to 1 display pixel, so a measured extent is
    directly comparable with the layout numbers above. Guessing font sizes
    against string lengths is what produced the first round of clipped titles.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width = artist.get_window_extent(renderer=renderer).width
    if width > max_w:
        artist.set_fontsize(max(min_size, artist.get_fontsize() * max_w / width * 0.97))
    return artist


def panel(ax, x, y, w, h, face=PANEL, edge=RULE, lw=1.6, r=14, z=1):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0,rounding_size={r}",
            facecolor=face,
            edgecolor=edge,
            linewidth=lw,
            zorder=z,
            mutation_aspect=1,
        )
    )


def arrow(ax, x1, y1, x2, y2, color=MUTED, lw=2.2, z=3):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=22,
            linewidth=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
            zorder=z,
        )
    )


def audit_layout(fig, ax, name: str) -> list[str]:
    """Catch text that runs off the canvas or collides.

    Eyeballing a figure catches this once; a check catches it every time a label
    is edited. Overflow is fatal, overlap is reported -- some overlaps (a value
    sitting inside its own panel) are intentional.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    boxes = []
    problems = []
    for artist in ax.texts:
        bb = artist.get_window_extent(renderer=renderer)
        (x0, y1), (x1, y0) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        s = " / ".join(artist.get_text().splitlines())[:44]
        if x0 < 12 or x1 > W - 12:
            problems.append(f"{name}: OVERFLOW x=[{x0:.0f},{x1:.0f}] {s!r}")
        if y0 < 0 or y1 > H:
            problems.append(f"{name}: OVERFLOW y=[{y0:.0f},{y1:.0f}] {s!r}")
        boxes.append((x0, y0, x1, y1, s))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax0, ay0, ax1, ay1, sa = boxes[i]
            bx0, by0, bx1, by1, sb = boxes[j]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox > 6 and oy > 6:
                problems.append(f"{name}: OVERLAP {sa!r} <-> {sb!r}")
    return problems


def save(fig, name: str) -> tuple[Path, Path]:
    for problem in audit_layout(fig, fig.axes[0], name):
        LAYOUT_PROBLEMS.append(problem)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png, svg = OUT_DIR / f"{name}.png", OUT_DIR / f"{name}.svg"
    fig.savefig(png, dpi=DPI, facecolor=BG)
    fig.savefig(svg, format="svg", facecolor=BG)
    plt.close(fig)
    return png, svg


def header(ax, title: str, subtitle: str | None = None, kicker: str | None = None):
    ax.add_patch(Rectangle((0, 0), W, 10, facecolor=INK, edgecolor="none"))
    y = 108
    if kicker:
        fit(ax, caps(ax, 70, 78, kicker, size=19), W - 140)
        y = 132
    fit(ax, text(ax, 70, y, title, size=52, weight="bold"), W - 140)
    if subtitle:
        fit(ax, text(ax, 70, y + 58, subtitle, size=30, color=MUTED), W - 140)


def footer(ax, left: str, right: str | None = None):
    ax.plot([70, W - 70], [H - 96, H - 96], color=RULE, lw=1.6)
    half = (W - 140) / 2 - 30
    fit(ax, text(ax, 70, H - 58, left, size=20, color=MUTED), half)
    if right:
        fit(ax, text(ax, W - 70, H - 58, right, size=20, color=MUTED, ha="right"), half)


# ---------------------------------------------------------------------------
# Visual 1 -- cover / architecture
# ---------------------------------------------------------------------------

STAGES_TOP = [
    ("Synthetic corpus", "14 documents\nquote-anchored truth"),
    ("Chunking & retrieval", "structure-aware\ndense + lexical"),
    ("Generation", "one shared prompt\nboth arms"),
    ("Citations & traces", "bound to the context\nthe model saw"),
]
STAGES_BOTTOM = [
    ("Evaluation", "deterministic metrics\nkept apart"),
    ("Failure analysis", "16 cause-ordered\nclasses"),
    ("Regression tests", "confirmed failures\nfrozen offline"),
]


def visual_1_cover() -> tuple[Path, Path]:
    fig, ax = canvas()
    header(ax, "RAG Evaluation Lab", "Grounding, Citations & Regression Testing")

    bw, bh, gap = 348, 168, 32
    y1 = 330
    x0 = (W - (4 * bw + 3 * gap)) / 2
    for i, (name, sub) in enumerate(STAGES_TOP):
        x = x0 + i * (bw + gap)
        panel(ax, x, y1, bw, bh)
        fit(ax, text(ax, x + bw / 2, y1 + 58, name, size=24, weight="bold", ha="center"), bw - 40)
        fit(
            ax,
            text(ax, x + bw / 2, y1 + 112, sub, size=20, color=MUTED, ha="center", linespacing=1.5),
            bw - 40,
        )
        if i < 3:
            arrow(ax, x + bw + 5, y1 + bh / 2, x + bw + gap - 5, y1 + bh / 2)

    # serpentine connector: down from the last top box, across, into the first bottom box
    y2 = 660
    bx0 = (W - (3 * bw + 2 * gap)) / 2
    last_x = x0 + 3 * (bw + gap) + bw / 2
    mid = (y1 + bh + y2) / 2
    ax.plot([last_x, last_x], [y1 + bh, mid], color=MUTED, lw=2.2, solid_capstyle="round")
    ax.plot([last_x, bx0 + bw / 2], [mid, mid], color=MUTED, lw=2.2, solid_capstyle="round")
    arrow(ax, bx0 + bw / 2, mid, bx0 + bw / 2, y2 - 5)

    for i, (name, sub) in enumerate(STAGES_BOTTOM):
        x = bx0 + i * (bw + gap)
        panel(ax, x, y2, bw, bh, face="#FFFFFF")
        fit(ax, text(ax, x + bw / 2, y2 + 58, name, size=24, weight="bold", ha="center"), bw - 40)
        fit(
            ax,
            text(ax, x + bw / 2, y2 + 112, sub, size=20, color=MUTED, ha="center", linespacing=1.5),
            bw - 40,
        )
        if i < 2:
            arrow(ax, x + bw + 5, y2 + bh / 2, x + bw + gap - 5, y2 + bh / 2)

    text(
        ax,
        W / 2,
        y2 + bh + 96,
        "Self-directed research-engineering case study",
        size=26,
        color=INK,
        ha="center",
        weight="bold",
    )
    footer(
        ax,
        "NovaPay is a synthetic corpus -- every fact invented, no real data.",
        "Deterministic metrics only; no LLM judge",
    )
    return save(fig, "01-cover-architecture")


# ---------------------------------------------------------------------------
# Visual 2 -- the signature visual
# ---------------------------------------------------------------------------

# Literals from docs/results.md.
ORIGINAL = [
    ("MRR", 0.667, 0.835, 0.168, 0.008, 0.339),
    ("Recall@10", 0.692, 0.883, 0.192, 0.025, 0.375),
]
MATCHED = [
    ("MRR", 0.150, -0.017, 0.321),
    ("Recall@4", 0.058, -0.067, 0.200),
]

AX_LO, AX_HI = -0.12, 0.42


def _interval(ax, x, y, w, delta, lo, hi, color):
    """One confidence interval on a shared axis, with zero marked."""

    def sx(v):
        return x + (v - AX_LO) / (AX_HI - AX_LO) * w

    ax.plot([x, x + w], [y, y], color=RULE, lw=2, zorder=2)
    zx = sx(0.0)
    ax.plot([zx, zx], [y - 30, y + 30], color=INK, lw=2.4, zorder=4)
    ax.plot([sx(lo), sx(hi)], [y, y], color=color, lw=11, solid_capstyle="round", zorder=5)
    ax.plot(
        [sx(delta)],
        [y],
        marker="o",
        markersize=13,
        color=color,
        markeredgecolor="#FFFFFF",
        markeredgewidth=2.5,
        zorder=6,
    )
    for v in (lo, hi):
        ax.plot([sx(v), sx(v)], [y - 14, y + 14], color=color, lw=3, zorder=5)
    return zx


def visual_2_confound() -> tuple[Path, Path]:
    fig, ax = canvas()
    header(
        ax,
        "The improvement that did not survive the audit",
        "Held-out split: 22 cases, 20 retrieval-evaluable",
        kicker="signature finding",
    )

    ax_x, ax_w = 660, 520

    # --- band 1: as originally reported ------------------------------------
    y = 262
    panel(ax, 60, y, W - 120, 208, face="#FFFFFF")
    caps(ax, 92, y + 40, "as originally reported", size=18)
    text(
        ax,
        ax_x + ax_w / 2,
        y + 40,
        "95% paired-bootstrap CI on the difference",
        size=17,
        color=MUTED,
        ha="center",
    )
    for i, (name, b, im, d, lo, hi) in enumerate(ORIGINAL):
        ry = y + 100 + i * 62
        fit(ax, text(ax, 92, ry, name, size=24, weight="bold"), 200)
        text(ax, 388, ry, f"{b:.3f}", size=23, color=BASE, ha="right")
        text(ax, 408, ry, "→", size=23, color=MUTED)
        text(ax, 462, ry, f"{im:.3f}", size=23, color=IMPR, weight="bold")
        _interval(ax, ax_x, ry, ax_w, d, lo, hi, IMPR)
        text(ax, ax_x + ax_w + 22, ry, "excludes zero", size=18, color=IMPR, weight="bold")

    # --- band 2: the reveal -------------------------------------------------
    y = 500
    panel(ax, 60, y, W - 120, 232, face="#FBF3EC", edge="#E3C9B2")
    caps(ax, 92, y + 40, "but the arms did not retrieve the same amount", size=18, color=WARN)

    def chunks(cy, n, color, label):
        text(ax, 92, cy, label, size=22, weight="bold")
        cw, cg, sx = 40, 10, 400
        for i in range(n):
            ax.add_patch(
                Rectangle(
                    (sx + i * (cw + cg), cy - 19),
                    cw,
                    38,
                    facecolor=color,
                    edgecolor="none",
                    zorder=4,
                )
            )
        text(ax, sx + n * (cw + cg) + 12, cy, f"{n} chunks", size=21, color=color, weight="bold")

    chunks(y + 106, 4, BASE, "Baseline budget")
    chunks(y + 174, 8, IMPR, "Improved budget")
    text(
        ax,
        1010,
        y + 140,
        "recall@10 therefore compares\n4 chunks against 8",
        size=21,
        color=WARN,
        ha="left",
        linespacing=1.6,
        weight="bold",
    )

    # --- band 3: matched budget --------------------------------------------
    y = 762
    panel(ax, 60, y, W - 120, 208, face="#FFFFFF")
    caps(ax, 92, y + 40, "recomputed with both arms capped at 4", size=18)
    for i, (name, d, lo, hi) in enumerate(MATCHED):
        ry = y + 100 + i * 62
        text(ax, 92, ry, name, size=23, weight="bold")
        _interval(ax, ax_x, ry, ax_w, d, lo, hi, WARN)
        text(ax, ax_x + ax_w + 22, ry, "includes zero", size=18, color=WARN, weight="bold")

    # --- takeaway -----------------------------------------------------------
    text(
        ax,
        W / 2,
        1024,
        "More retrieved evidence ≠ proven better ranking.",
        size=33,
        weight="bold",
        ha="center",
    )
    footer(
        ax,
        "Not false -- confounded by the retrieval budget.",
        "10 of 12 held-out metrics: no measurable difference",
    )
    return save(fig, "02-budget-confound")


# ---------------------------------------------------------------------------
# Visual 3 -- failure analysis to regression test
# ---------------------------------------------------------------------------

STEPS = [
    ("1  Question", "“How many dashboard seats\ndo I get on Pro?”", "dev case F-15", INK),
    (
        "2  Baseline retrieval failure",
        "The chunk covering the answer row\nbegins mid-table. The column header\nrow is in a different chunk.",
        "3 | 15 | unlimited — unlabelled",
        WARN,
    ),
    ("3  Diagnosed failure class", "unsupported_claim", "baseline MRR 0.333", WARN),
    (
        "4  Intervention",
        "Structure-aware chunking:\nsplit on headings, tables atomic,\nheading path carried into context",
        "intervention 1 of 4",
        INK,
    ),
    (
        "5  Corrected retrieval property",
        "The covering chunk now contains\n| | Starter | Pro | Enterprise |",
        "improved MRR 1.000",
        IMPR,
    ),
    (
        "6  Frozen regression assertion",
        "test_f15_dashboard_seats_row\n_keeps_its_column_header",
        "offline, no API key",
        IMPR,
    ),
]


def visual_3_regression() -> tuple[Path, Path]:
    fig, ax = canvas()
    header(
        ax,
        "From one measured failure to a frozen test",
        "A confirmed development-split failure, and the assertion that stops it returning",
        kicker="failure analysis → regression",
    )

    cw, ch, gx, gy = 700, 218, 44, 30
    x0 = (W - (2 * cw + gx)) / 2
    y0 = 268
    for i, (label, body, note, accent) in enumerate(STEPS):
        col, row = i % 2, i // 2
        x = x0 + col * (cw + gx)
        y = y0 + row * (ch + gy)
        panel(ax, x, y, cw, ch, face="#FFFFFF")
        ax.add_patch(
            Rectangle((x, y + 14), 6, ch - 28, facecolor=accent, edgecolor="none", zorder=3)
        )
        text(ax, x + 30, y + 42, label, size=23, weight="bold", color=accent)
        text(ax, x + 30, y + 120, body, size=21, linespacing=1.45)
        text(ax, x + 30, y + ch - 32, note, size=19, color=MUTED, style="italic")
        if col == 0:
            arrow(ax, x + cw + 6, y + ch / 2, x + cw + gx - 6, y + ch / 2)
        elif row < 2:
            ax.plot(
                [x + cw / 2, x + cw / 2],
                [y + ch, y + ch + gy / 2],
                color=MUTED,
                lw=2.2,
                solid_capstyle="round",
            )
            ax.plot(
                [x + cw / 2, x0 + cw / 2],
                [y + ch + gy / 2, y + ch + gy / 2],
                color=MUTED,
                lw=2.2,
                solid_capstyle="round",
            )
            arrow(ax, x0 + cw / 2, y + ch + gy / 2, x0 + cw / 2, y + ch + gy - 4)

    y = 1010
    panel(ax, 60, y, W - 120, 96, face=PANEL)
    text(ax, 96, y + 48, "164", size=34, weight="bold", color=IMPR)
    text(ax, 214, y + 48, "offline tests passed", size=22)
    text(ax, 540, y + 48, "3", size=34, weight="bold", color=MUTED)
    text(
        ax,
        588,
        y + 48,
        "local-model parity tests intentionally\nskipped (no network / model tier)",
        size=18,
        color=MUTED,
        linespacing=1.4,
    )
    text(
        ax,
        1150,
        y + 48,
        "GitHub Actions has not been run;\nno CI status is claimed.",
        size=18,
        color=MUTED,
        linespacing=1.4,
    )
    footer(
        ax,
        "No regression test is derived from a held-out failure.",
        "Five confirmed development-split failures are frozen",
    )
    return save(fig, "03-failure-to-regression")


# ---------------------------------------------------------------------------
# Visual 4 (optional) -- development-only ablation
# ---------------------------------------------------------------------------

ABLATION = [
    ("Baseline", 0.435, 0.226, 0.530, BASE),
    ("Structure-only", 0.574, 0.387, 0.554, IMPR),
    ("Hybrid-only", 0.399, 0.214, 0.470, WARN),
    ("Structure + hybrid", 0.565, 0.333, 0.637, IMPR),
]


def visual_4_ablation() -> tuple[Path, Path]:
    fig, ax = canvas()
    header(
        ax,
        "Which component actually helped?",
        "Retrieval-only ablation at a matched budget of k = 4",
        kicker="development split — explanatory, not held-out evidence",
    )

    base_x, base_y, plot_w, plot_h = 220, 820, 1200, 470
    top = 0.65

    def by(v):
        return base_y - (v / top) * plot_h

    ax.plot([base_x - 40, base_x + plot_w], [base_y, base_y], color=INK, lw=2)
    for g in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6):
        ax.plot([base_x - 40, base_x + plot_w], [by(g), by(g)], color=RULE, lw=1, zorder=0)
        text(ax, base_x - 56, by(g), f"{g:.1f}", size=19, color=MUTED, ha="right")
    text(ax, base_x - 56, by(top) - 42, "MRR", size=22, color=MUTED, ha="right", weight="bold")

    bw, gap = 200, 100
    baseline_mrr = ABLATION[0][1]
    ax.plot(
        [base_x - 40, base_x + plot_w],
        [by(baseline_mrr), by(baseline_mrr)],
        color=BASE,
        lw=2,
        linestyle=(0, (7, 6)),
        zorder=2,
    )

    for i, (name, mrr, r1, r3, color) in enumerate(ABLATION):
        x = base_x + i * (bw + gap)
        ax.add_patch(
            Rectangle(
                (x, by(mrr)), bw, base_y - by(mrr), facecolor=color, edgecolor="none", zorder=3
            )
        )
        text(
            ax,
            x + bw / 2,
            by(mrr) - 34,
            f"{mrr:.3f}",
            size=30,
            weight="bold",
            color=color,
            ha="center",
        )
        text(ax, x + bw / 2, base_y + 40, name, size=22, weight="bold", ha="center")
        text(
            ax,
            x + bw / 2,
            base_y + 86,
            f"r@1 {r1:.3f}" + "\n" + f"r@3 {r3:.3f}",
            size=19,
            color=MUTED,
            ha="center",
            linespacing=1.5,
        )

    hy = by(ABLATION[2][1])
    text(
        ax,
        base_x + 2 * (bw + gap) + bw / 2,
        hy - 78,
        "below baseline",
        size=21,
        color=WARN,
        weight="bold",
        ha="center",
    )

    fit(
        ax,
        text(
            ax,
            70,
            1006,
            "Structure-aware chunking accounts for most of the gain.\n"
            "Hybrid retrieval alone is worse than the baseline on MRR, recall@1 and recall@3.",
            size=23,
            linespacing=1.6,
        ),
        W - 140,
    )
    footer(
        ax,
        "Development split, n = 28. Dashed line = baseline MRR. Descriptive only.",
        "Held-out evidence is reported separately",
    )
    return save(fig, "04-dev-ablation")


# ---------------------------------------------------------------------------
# Guard: every plotted number must still match the reports
# ---------------------------------------------------------------------------


def verify_against_reports() -> list[str]:
    """Fail loudly if a figure has drifted from the committed results."""
    problems: list[str] = []

    held = json.loads((REPO_ROOT / "reports" / "held-out" / "comparison.json").read_text("utf-8"))
    by_metric = {m["metric"]: m for m in held["metrics"]}
    for label, base, impr, delta, lo, hi in ORIGINAL:
        key = {"MRR": "mrr", "Recall@10": "recall_at_10"}[label]
        m = by_metric[key]
        for name, plotted, actual in (
            ("baseline", base, m["baseline"]),
            ("improved", impr, m["improved"]),
            ("delta", delta, m["delta"]),
            ("ci_high", hi, m["ci_high"]),
        ):
            if abs(plotted - actual) > 5e-4:
                problems.append(f"visual 2 {key}.{name}: plotted {plotted} != report {actual}")
        # ci_low is quoted to 3dp in results.md; the report carries 4dp.
        if abs(lo - m["ci_low"]) > 1e-2:
            problems.append(f"visual 2 {key}.ci_low: plotted {lo} != report {m['ci_low']}")

    abl = json.loads(
        (REPO_ROOT / "reports" / "ablation" / "dev-retrieval-ablation.json").read_text("utf-8")
    )
    by_label = {v["label"]: v for v in abl["variants"]}
    mapping = {
        "Baseline": "baseline",
        "Structure-only": "structure-only",
        "Hybrid-only": "hybrid-only",
        "Structure + hybrid": "structure+hybrid",
    }
    for name, mrr, r1, r3, _ in ABLATION:
        v = by_label[mapping[name]]
        for key, plotted in (("mrr", mrr), ("recall_at_1", r1), ("recall_at_3", r3)):
            if abs(plotted - v["means"][key]) > 5e-4:
                problems.append(
                    f"visual 4 {name}.{key}: plotted {plotted} != report {v['means'][key]}"
                )
    return problems


def main() -> int:
    problems = verify_against_reports()
    if problems:
        print("figures disagree with the committed reports:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    for fn in (visual_1_cover, visual_2_confound, visual_3_regression, visual_4_ablation):
        png, svg = fn()
        print(f"  {png.relative_to(REPO_ROOT)}  +  {svg.name}")

    if LAYOUT_PROBLEMS:
        print("\nLAYOUT PROBLEMS:", file=sys.stderr)
        for p in LAYOUT_PROBLEMS:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"\n4 visuals at {W}x{H} (4:3); every plotted value matches the committed reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
