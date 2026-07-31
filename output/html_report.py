"""HTML report — generates a dashboard-style price comparison report."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config.constants import TIMEZONE
from models.product import ComparisonResult
from services.spot_helper import get_spot_for_product
from services.spot_history import SpotDataPoint
from services.spot_price import SpotPrices

OUTPUT_DIR = Path(__file__).parent.parent / "data"


def export_html(
    results: list[ComparisonResult],
    spot: SpotPrices | None = None,
    history: list[SpotDataPoint] | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
    failed_dealers: list[str] | None = None,
    assessment: str | None = None,
) -> Path:
    """Generate an HTML report and return the file path."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(ZoneInfo(TIMEZONE))
    if filename is None:
        filename = f"prices_{timestamp:%Y%m%d_%H%M%S}.html"
    elif not filename.endswith(".html"):
        filename = f"{filename}.html"
    filepath = output_dir / filename

    html = _build_html(results, spot, history, timestamp, failed_dealers or [], assessment)
    filepath.write_text(html)

    return filepath


def _get_group(canonical_name: str) -> str:
    name_lower = canonical_name.lower()
    metal = "Gold" if "gold" in name_lower else "Silver"

    weight_match = re.match(r"(\d+(?:oz|g|kg))", name_lower)
    if weight_match:
        return f"{weight_match.group(1)} {metal}"

    if "1 oz" in name_lower:
        return f"1oz {metal}"

    return f"Other {metal}"


def _sort_groups(groups: list[str]) -> list[str]:
    weight_order = {"1g": 1, "5g": 2, "10g": 3, "20g": 4, "1oz": 5,
                    "50g": 6, "100g": 7, "250g": 8, "500g": 9, "10oz": 10, "1kg": 11}

    def sort_key(g: str) -> tuple:
        metal_rank = 0 if "Gold" in g else 1
        match = re.match(r"(\d+(?:oz|g|kg))", g.lower())
        weight_rank = weight_order.get(match.group(1), 99) if match else 99
        return (metal_rank, weight_rank)

    return sorted(groups, key=sort_key)


def _build_html(
    results: list[ComparisonResult],
    spot: SpotPrices | None,
    history: list[SpotDataPoint] | None,
    timestamp: datetime,
    failed_dealers: list[str] | None = None,
    assessment: str | None = None,
) -> str:
    groups: defaultdict[str, list[str]] = defaultdict(list)

    for result in results:
        group = _get_group(result.canonical_name)
        groups[group].append(_product_card(result, spot, group))

    group_order = _sort_groups(list(groups.keys()))

    gold_groups = [g for g in group_order if "Gold" in g]
    silver_groups = [g for g in group_order if "Silver" in g]

    filter_pills = []
    filter_pills.append('<button class="pill active" data-filter="all">All</button>')
    filter_pills.append('<button class="pill pill-gold" data-filter="gold">Gold</button>')
    filter_pills.append('<button class="pill pill-silver" data-filter="silver">Silver</button>')

    weight_pills = []
    seen_weights = []
    for g in group_order:
        match = re.match(r"(\d+(?:oz|g|kg))", g.lower())
        if match and match.group(1) not in seen_weights:
            seen_weights.append(match.group(1))
            weight_pills.append(f'<button class="pill pill-weight" data-weight="{match.group(1)}">{match.group(1)}</button>')

    sections = []
    for g in group_order:
        metal = "gold" if "Gold" in g else "silver"
        match = re.match(r"(\d+(?:oz|g|kg))", g.lower())
        weight = match.group(1) if match else "other"
        cards = "".join(groups[g])
        sections.append(
            f'<div class="group-section" data-metal="{metal}" data-weight="{weight}">'
            f'<h2 class="group-heading">{g}</h2>'
            f'<div class="cards-grid">{cards}</div></div>'
        )

    spot_html = _spot_hero(spot, history) if spot else ""
    assessment_html = _assessment_section(assessment) if assessment else ""
    top_deals_html = _top_deals_section(results, spot) if spot else ""
    chart_html = _chart_section(history) if history else ""
    promo_html = _promotions_section(results)
    failed_html = ""
    if failed_dealers:
        dealer_list = ", ".join(failed_dealers)
        failed_html = f'<div class="failed-notice"><span class="failed-icon">!</span> <strong>Data unavailable:</strong> {dealer_list}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SG Bullion Prices — {timestamp:%d %b %Y}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
{_CSS}
</style>
</head>
<body>
<div class="dashboard">
    <header class="header">
        <div class="header-top">
            <h1>SG Bullion Prices</h1>
            <p class="tagline">Because gold is gold, and silver is silver. I care about nothing but the price.</p>
            <span class="timestamp">{timestamp:%d %b %Y, %H:%M} SGT</span>
        </div>
        {failed_html}
    </header>

    {spot_html}
    {assessment_html}
    {top_deals_html}
    {chart_html}
    {promo_html}

    <div class="filter-bar" id="filter-bar">
        <div class="filter-row">
            {"".join(filter_pills)}
        </div>
        <div class="filter-row weight-row">
            <button class="pill pill-weight active" data-weight="all">All sizes</button>
            {"".join(weight_pills)}
        </div>
    </div>

    <main class="main-content">
        {"".join(sections)}
    </main>
</div>
<script>
{_JS}
</script>
</body>
</html>"""


def _top_deals_section(results: list[ComparisonResult], spot: SpotPrices | None) -> str:
    """Show top 3 lowest-premium products for gold and silver separately."""
    if not spot:
        return ""

    gold_deals = []
    silver_deals = []

    for result in results:
        cheapest = result.cheapest
        if not cheapest:
            continue

        spot_price = get_spot_for_product(result.canonical_name, spot)
        if not spot_price or spot_price <= 0:
            continue

        premium_pct = float((cheapest.price - spot_price) / spot_price * 100)
        entry = (result.canonical_name, cheapest.dealer, cheapest.price, premium_pct, cheapest.url)

        if "gold" in result.canonical_name.lower():
            gold_deals.append(entry)
        else:
            silver_deals.append(entry)

    gold_deals.sort(key=lambda x: x[3])
    silver_deals.sort(key=lambda x: x[3])

    sections = []
    for label, deals in [("Gold", gold_deals[:3]), ("Silver", silver_deals[:3])]:
        if not deals:
            continue
        rows = []
        for i, (name, dealer, price, pct, url) in enumerate(deals):
            medal = ["&#129351;", "&#129352;", "&#129353;"][i]
            dealer_link = f'<a href="{url}" target="_blank">{dealer}</a>' if url else dealer
            pct_class = "premium-low" if pct <= 3 else "premium-mid" if pct <= 5 else "premium-high"
            rows.append(f"""
                <tr>
                    <td class="td-rank">{medal}</td>
                    <td class="td-product">{name}</td>
                    <td class="td-dealer">{dealer_link}</td>
                    <td class="td-price">SGD {price:,.2f}</td>
                    <td class="td-premium {pct_class}">{pct:+.1f}%</td>
                </tr>""")
        sections.append(f"""
        <div class="top-deals-group">
            <h3>{label}</h3>
            <table class="top-deals-table">
                <thead>
                    <tr><th></th><th>Product</th><th>Dealer</th><th>Price</th><th>Premium</th></tr>
                </thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </div>""")

    if not sections:
        return ""

    return f"""
    <section class="top-deals-section">
        <h2>Best Buys — Lowest Premium</h2>
        {"".join(sections)}
    </section>"""


def _assessment_section(assessment: str) -> str:
    escaped = assessment.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""
    <section class="assessment-section">
        <div class="assessment-header">
            <span class="assessment-icon">&#9672;</span>
            <h2>Market Insight</h2>
        </div>
        <p class="assessment-text">{escaped}</p>
        <span class="assessment-disclaimer">AI-generated analysis — not financial advice</span>
    </section>"""


def _spot_hero(spot: SpotPrices, history: list[SpotDataPoint] | None) -> str:
    gold_change = ""
    silver_change = ""

    if history and len(history) >= 2:
        prev = history[-2]
        if spot.gold_oz and prev.gold_sgd and prev.gold_sgd > 0:
            pct = float((spot.gold_oz - prev.gold_sgd) / prev.gold_sgd * 100)
            arrow = "&#9650;" if pct >= 0 else "&#9660;"
            cls = "change-up" if pct >= 0 else "change-down"
            gold_change = f'<span class="spot-change {cls}">{arrow} {abs(pct):.2f}%</span>'
        if spot.silver_oz and prev.silver_sgd and prev.silver_sgd > 0:
            pct = float((spot.silver_oz - prev.silver_sgd) / prev.silver_sgd * 100)
            arrow = "&#9650;" if pct >= 0 else "&#9660;"
            cls = "change-up" if pct >= 0 else "change-down"
            silver_change = f'<span class="spot-change {cls}">{arrow} {abs(pct):.2f}%</span>'

    gold_section = ""
    if spot.gold_oz:
        gold_section = f"""
        <div class="spot-item spot-gold">
            <span class="spot-label">Gold</span>
            <span class="spot-value">SGD {spot.gold_oz:,.2f}</span>
            <span class="spot-unit">per troy oz</span>
            {gold_change}
        </div>"""

    silver_section = ""
    if spot.silver_oz:
        silver_section = f"""
        <div class="spot-item spot-silver">
            <span class="spot-label">Silver</span>
            <span class="spot-value">SGD {spot.silver_oz:,.2f}</span>
            <span class="spot-unit">per troy oz</span>
            {silver_change}
        </div>"""

    return f"""
    <section class="spot-hero">
        <div class="spot-grid">
            {gold_section}
            {silver_section}
        </div>
        <p class="spot-source">Source: {spot.source}</p>
    </section>"""


def _chart_section(history: list[SpotDataPoint]) -> str:
    labels = []
    gold_data = []
    silver_data = []

    for point in history:
        labels.append(f'"{point.date}"')
        gold_data.append(str(round(float(point.gold_sgd), 2)) if point.gold_sgd else "null")
        silver_data.append(str(round(float(point.silver_sgd), 2)) if point.silver_sgd else "null")

    return f"""
    <section class="chart-section">
        <h2>12-Month Spot Trend</h2>
        <div class="chart-wrapper">
            <div class="chart-box">
                <span class="chart-label">Gold (SGD/oz)</span>
                <canvas id="goldChart"></canvas>
            </div>
            <div class="chart-box">
                <span class="chart-label">Silver (SGD/oz)</span>
                <canvas id="silverChart"></canvas>
            </div>
        </div>
    </section>
    <script>
    (function() {{
        const labels = [{",".join(labels)}];
        const goldData = [{",".join(gold_data)}];
        const silverData = [{",".join(silver_data)}];

        const baseOpts = {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ intersect: false, mode: 'index' }},
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                    backgroundColor: '#1e293b',
                    titleFont: {{ family: 'Inter' }},
                    bodyFont: {{ family: 'Inter' }},
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {{
                        label: ctx => 'SGD ' + ctx.parsed.y.toLocaleString(undefined, {{minimumFractionDigits: 2}})
                    }}
                }}
            }},
            scales: {{
                x: {{
                    border: {{ display: false }},
                    grid: {{ display: false }},
                    ticks: {{
                        font: {{ family: 'Inter', size: 11 }},
                        color: '#94a3b8',
                        maxRotation: 0,
                        callback: function(val, idx) {{
                            const d = new Date(labels[idx]);
                            return d.toLocaleDateString('en-SG', {{month: 'short'}});
                        }}
                    }}
                }},
                y: {{
                    border: {{ display: false }},
                    grid: {{ color: '#f1f5f9' }},
                    ticks: {{
                        font: {{ family: 'Inter', size: 11 }},
                        color: '#94a3b8',
                        callback: val => val.toLocaleString()
                    }}
                }}
            }}
        }};

        new Chart(document.getElementById('goldChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: goldData,
                    borderColor: '#d97706',
                    backgroundColor: 'rgba(217, 119, 6, 0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#d97706',
                    pointBorderWidth: 0,
                    borderWidth: 2.5,
                }}]
            }},
            options: baseOpts
        }});

        new Chart(document.getElementById('silverChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: silverData,
                    borderColor: '#64748b',
                    backgroundColor: 'rgba(100, 116, 139, 0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#64748b',
                    pointBorderWidth: 0,
                    borderWidth: 2.5,
                }}]
            }},
            options: baseOpts
        }});
    }})();
    </script>"""


def _promotions_section(results: list[ComparisonResult]) -> str:
    promos = []
    seen = set()

    for result in results:
        for p in result.prices:
            if p.promotion and p.url not in seen:
                seen.add(p.url)
                promos.append((result.canonical_name, p))

    if not promos:
        return ""

    promos.sort(key=lambda x: -x[1].promotion.discount_pct)

    rows = []
    for canonical_name, p in promos:
        promo = p.promotion
        dealer_link = f'<a href="{p.url}" target="_blank">{p.dealer}</a>' if p.url else p.dealer
        rows.append(f"""
            <div class="promo-item">
                <div class="promo-info">
                    <span class="promo-product">{canonical_name}</span>
                    <span class="promo-dealer">{dealer_link}</span>
                </div>
                <div class="promo-prices">
                    <span class="promo-regular">SGD {promo.regular_price:,.2f}</span>
                    <span class="promo-offer">SGD {promo.offer_price:,.2f}</span>
                    <span class="promo-badge">-{promo.discount_pct:.1f}%</span>
                </div>
            </div>""")

    return f"""
    <section class="promo-section">
        <h2>Active Promotions</h2>
        <div class="promo-list">
            {"".join(rows)}
        </div>
    </section>"""


def _product_card(result: ComparisonResult, spot: SpotPrices | None, group: str) -> str:
    spot_price = get_spot_for_product(result.canonical_name, spot)

    in_stock = [p for p in result.prices if p.in_stock]
    out_of_stock = [p for p in result.prices if not p.in_stock]
    cheapest = result.cheapest
    show_expand = len(in_stock) > 3

    rows = []
    for i, p in enumerate(in_stock):
        premium_str = ""
        premium_class = ""
        heatmap_style = ""
        if spot_price and spot_price > 0:
            premium_pct = float((p.price - spot_price) / spot_price * 100)
            premium_str = f"{premium_pct:+.1f}%"
            if premium_pct <= 3:
                premium_class = "premium-low"
                heatmap_style = "background: rgba(34,197,94,0.06);"
            elif premium_pct <= 5:
                premium_class = "premium-mid"
                heatmap_style = "background: rgba(245,158,11,0.06);"
            else:
                premium_class = "premium-high"
                heatmap_style = "background: rgba(239,68,68,0.06);"

        is_cheapest = cheapest and p.dealer == cheapest.dealer and p.price == cheapest.price
        row_class = "cheapest-row" if is_cheapest else ""
        hidden_class = " hidden-row" if show_expand and i >= 3 else ""
        badge = ' <span class="best-badge">BEST</span>' if is_cheapest and len(in_stock) > 1 else ""

        dealer_link = f'<a href="{p.url}" target="_blank">{p.dealer}</a>' if p.url else p.dealer
        rows.append(f"""
            <tr class="{row_class}{hidden_class}" style="{heatmap_style}">
                <td class="td-dealer">{dealer_link}{badge}</td>
                <td class="td-price">SGD {p.price:,.2f}</td>
                <td class="td-premium {premium_class}">{premium_str}</td>
            </tr>""")

    for p in out_of_stock:
        dealer_link = f'<a href="{p.url}" target="_blank">{p.dealer}</a>' if p.url else p.dealer
        rows.append(f"""
            <tr class="oos-row hidden-row">
                <td class="td-dealer">{dealer_link}</td>
                <td class="td-price">SGD {p.price:,.2f}</td>
                <td class="td-premium oos">OUT OF STOCK</td>
            </tr>""")

    expand_btn = ""
    total_hidden = (len(in_stock) - 3 if show_expand else 0) + len(out_of_stock)
    if total_hidden > 0:
        expand_btn = f'<button class="expand-btn" onclick="toggleExpand(this)">Show {total_hidden} more</button>'

    summary = ""
    if cheapest and len(in_stock) > 1:
        most_expensive = in_stock[-1]
        savings = most_expensive.price - cheapest.price
        premium_text = ""
        if spot_price and spot_price > 0:
            premium_pct = float((cheapest.price - spot_price) / spot_price * 100)
            premium_text = f'<span class="card-premium">{premium_pct:.1f}% over spot</span>'

        summary = f"""
        <div class="card-summary">
            <span class="card-savings">Save SGD {savings:,.2f}</span>
            {premium_text}
        </div>"""

    return f"""
    <div class="product-card">
        <h3 class="card-title">{result.canonical_name}</h3>
        <table class="card-table">
            <thead>
                <tr><th>Dealer</th><th>Price</th><th>Premium</th></tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        {expand_btn}
        {summary}
    </div>"""


_JS = """
document.addEventListener('DOMContentLoaded', function() {
    let activeMetal = 'all';
    let activeWeight = 'all';

    document.querySelectorAll('.filter-row:first-child .pill').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-row:first-child .pill').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeMetal = this.dataset.filter;
            applyFilters();
        });
    });

    document.querySelectorAll('.pill-weight').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.pill-weight').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            activeWeight = this.dataset.weight;
            applyFilters();
        });
    });

    function applyFilters() {
        document.querySelectorAll('.group-section').forEach(section => {
            const metal = section.dataset.metal;
            const weight = section.dataset.weight;
            const metalMatch = activeMetal === 'all' || metal === activeMetal;
            const weightMatch = activeWeight === 'all' || weight === activeWeight;
            section.style.display = (metalMatch && weightMatch) ? '' : 'none';
        });
    }

    // Sticky filter bar
    const filterBar = document.getElementById('filter-bar');
    if (filterBar) {
        const observer = new IntersectionObserver(
            ([e]) => e.target.classList.toggle('stuck', e.intersectionRatio < 1),
            { threshold: [1], rootMargin: '-1px 0px 0px 0px' }
        );
        observer.observe(filterBar);
    }
});

function toggleExpand(btn) {
    if (!btn.dataset.original) {
        btn.dataset.original = btn.textContent;
    }

    const card = btn.closest('.product-card');
    const hidden = card.querySelectorAll('.hidden-row');
    const isExpanded = btn.classList.contains('expanded');

    hidden.forEach(row => {
        row.style.display = isExpanded ? 'none' : '';
    });

    btn.classList.toggle('expanded');
    btn.textContent = isExpanded ? btn.dataset.original : 'Show less';
}
"""

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #f8fafc;
    color: #0f172a;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}

.dashboard {
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}

/* Header */
.header { margin-bottom: 1.5rem; }
.header-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
}
h1 {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #0f172a;
}
.tagline {
    font-size: 0.85rem;
    color: #64748b;
    font-style: italic;
    margin: 0.25rem 0 0.5rem;
}
.timestamp {
    font-size: 0.8rem;
    font-weight: 500;
    color: #64748b;
    background: #e2e8f0;
    padding: 0.25rem 0.75rem;
    border-radius: 100px;
}

.failed-notice {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 10px;
    padding: 0.6rem 1rem;
    margin-top: 1rem;
    color: #991b1b;
    font-size: 0.85rem;
}
.failed-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    background: #dc2626;
    color: white;
    border-radius: 50%;
    font-size: 0.7rem;
    font-weight: 700;
    flex-shrink: 0;
}

/* Top Deals */
.top-deals-section {
    background: #fff;
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.top-deals-section h2 {
    font-size: 1rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 1.25rem;
}
.top-deals-group { margin-bottom: 1.25rem; }
.top-deals-group:last-child { margin-bottom: 0; }
.top-deals-group h3 {
    font-size: 0.8rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.5rem;
}
.top-deals-table {
    width: 100%;
    border-collapse: collapse;
}
.top-deals-table th {
    text-align: left;
    font-size: 0.65rem;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.5rem 0.5rem;
    border-bottom: 1px solid #f1f5f9;
}
.top-deals-table th:nth-child(4),
.top-deals-table th:nth-child(5) { text-align: right; }
.top-deals-table td {
    padding: 0.75rem 0.5rem;
    font-size: 0.9rem;
    border-bottom: 1px solid #f8fafc;
}
.top-deals-table .td-rank { font-size: 1.2rem; width: 2rem; }
.top-deals-table .td-product { font-weight: 600; color: #1e293b; }
.top-deals-table .td-dealer a {
    color: #64748b;
    text-decoration: none;
    border-bottom: 1px dashed #cbd5e1;
}
.top-deals-table .td-dealer a:hover { color: #2563eb; border-color: #2563eb; }
.top-deals-table .td-price {
    text-align: right;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}
.top-deals-table .td-premium {
    text-align: right;
    font-weight: 700;
    font-size: 0.85rem;
}

/* Assessment */
.assessment-section {
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border: 1px solid #bae6fd;
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
}
.assessment-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}
.assessment-icon {
    font-size: 1.1rem;
    color: #0284c7;
}
.assessment-header h2 {
    font-size: 0.95rem;
    font-weight: 700;
    color: #0c4a6e;
    margin: 0;
}
.assessment-text {
    font-size: 0.9rem;
    line-height: 1.7;
    color: #1e293b;
}
.assessment-disclaimer {
    display: block;
    margin-top: 0.75rem;
    font-size: 0.7rem;
    color: #64748b;
    font-style: italic;
}

/* Spot Hero */
.spot-hero {
    margin-bottom: 1.5rem;
}
.spot-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}
.spot-item {
    background: #0f172a;
    border-radius: 16px;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}
.spot-gold { border-top: 3px solid #d97706; }
.spot-silver { border-top: 3px solid #94a3b8; }
.spot-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
}
.spot-value {
    font-size: 1.6rem;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}
.spot-unit {
    font-size: 0.75rem;
    color: #64748b;
}
.spot-change {
    font-size: 0.8rem;
    font-weight: 600;
    margin-top: 0.25rem;
}
.change-up { color: #22c55e; }
.change-down { color: #ef4444; }
.spot-source {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 0.75rem;
}

/* Chart */
.chart-section {
    background: #fff;
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.chart-section h2 {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: #334155;
}
.chart-wrapper {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}
.chart-box {
    position: relative;
    height: 200px;
}
.chart-label {
    position: absolute;
    top: 0;
    left: 0;
    font-size: 0.7rem;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.chart-box canvas {
    margin-top: 1.25rem;
}

/* Promotions */
.promo-section {
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    border: 1px solid #fde68a;
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.promo-section h2 {
    font-size: 1rem;
    font-weight: 700;
    color: #92400e;
    margin-bottom: 1rem;
}
.promo-list { display: flex; flex-direction: column; gap: 0.75rem; }
.promo-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    background: rgba(255,255,255,0.7);
    border-radius: 10px;
}
.promo-info { display: flex; flex-direction: column; gap: 0.15rem; }
.promo-product { font-weight: 600; font-size: 0.9rem; color: #1e293b; }
.promo-dealer { font-size: 0.8rem; color: #64748b; }
.promo-dealer a { color: inherit; text-decoration: none; border-bottom: 1px dashed #94a3b8; }
.promo-dealer a:hover { color: #2563eb; border-color: #2563eb; }
.promo-prices { display: flex; align-items: center; gap: 0.75rem; flex-shrink: 0; }
.promo-regular { font-size: 0.8rem; color: #94a3b8; text-decoration: line-through; }
.promo-offer { font-size: 0.95rem; font-weight: 700; color: #1e293b; }
.promo-badge {
    background: #dc2626;
    color: white;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
}

/* Filter Bar */
.filter-bar {
    position: sticky;
    top: 0;
    z-index: 100;
    background: #f8fafc;
    padding: 1rem 0;
    margin-bottom: 1.5rem;
    transition: box-shadow 0.2s, padding 0.2s;
}
.filter-bar.stuck {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    padding: 0.75rem 1rem;
    margin-left: -1.5rem;
    margin-right: -1.5rem;
    border-radius: 0 0 12px 12px;
    background: rgba(248,250,252,0.95);
    backdrop-filter: blur(8px);
}
.filter-row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.weight-row { margin-top: 0.5rem; }
.pill {
    padding: 0.4rem 1rem;
    border: 1px solid #e2e8f0;
    border-radius: 100px;
    background: #fff;
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    font-weight: 500;
    color: #64748b;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
}
.pill:hover { border-color: #cbd5e1; background: #f1f5f9; }
.pill.active {
    background: #0f172a;
    color: #fff;
    border-color: #0f172a;
}
.pill-gold.active { background: #d97706; border-color: #d97706; }
.pill-silver.active { background: #64748b; border-color: #64748b; }

/* Product Cards */
.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 1rem;
}
.group-heading {
    font-size: 1.15rem;
    font-weight: 700;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e2e8f0;
    color: #1e293b;
}
.group-section { margin-bottom: 2rem; }

.product-card {
    background: #fff;
    border-radius: 16px;
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s;
}
.product-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.card-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.75rem;
}
.card-table {
    width: 100%;
    border-collapse: collapse;
}
.card-table th {
    text-align: left;
    font-size: 0.65rem;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.4rem 0.5rem;
    border-bottom: 1px solid #f1f5f9;
}
.card-table th:nth-child(2),
.card-table th:nth-child(3) { text-align: right; }
.card-table td {
    padding: 0.5rem;
    font-size: 0.85rem;
    border-bottom: 1px solid #f8fafc;
}
.td-dealer { font-weight: 500; }
.td-dealer a {
    color: inherit;
    text-decoration: none;
    border-bottom: 1px dashed rgba(0,0,0,0.2);
}
.td-dealer a:hover { color: #2563eb; border-color: #2563eb; }
.td-price {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}
.td-premium {
    text-align: right;
    font-size: 0.8rem;
    font-weight: 600;
}
.premium-low { color: #22c55e; }
.premium-mid { color: #f59e0b; }
.premium-high { color: #ef4444; }
.oos { color: #94a3b8; font-style: italic; font-size: 0.75rem; }
.oos-row td { color: #cbd5e1; }

.cheapest-row td { color: #0f172a; }
.cheapest-row .td-price {
    font-weight: 800;
    font-size: 0.95rem;
}
.best-badge {
    display: inline-block;
    background: #22c55e;
    color: #fff;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    margin-left: 0.4rem;
    vertical-align: middle;
    letter-spacing: 0.02em;
}
.hidden-row { display: none; }

.expand-btn {
    display: block;
    width: 100%;
    margin-top: 0.5rem;
    padding: 0.4rem;
    border: 1px dashed #e2e8f0;
    border-radius: 8px;
    background: transparent;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    font-weight: 500;
    color: #64748b;
    cursor: pointer;
    transition: all 0.15s;
}
.expand-btn:hover { background: #f1f5f9; border-color: #cbd5e1; }

.card-summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #f1f5f9;
    flex-wrap: wrap;
    gap: 0.5rem;
}
.card-savings {
    font-weight: 700;
    font-size: 0.8rem;
    color: #22c55e;
}
.card-premium {
    font-size: 0.75rem;
    color: #94a3b8;
    font-weight: 500;
}

/* Mobile */
@media (max-width: 768px) {
    .dashboard { padding: 1rem; }
    h1 { font-size: 1.4rem; }
    .spot-grid { grid-template-columns: 1fr; }
    .spot-value { font-size: 1.4rem; }
    .chart-wrapper { grid-template-columns: 1fr; }
    .chart-box { height: 180px; }
    .cards-grid { grid-template-columns: 1fr; }
    .filter-row { overflow-x: auto; flex-wrap: nowrap; padding-bottom: 0.25rem; }
    .filter-bar.stuck { margin-left: -1rem; margin-right: -1rem; }
    .promo-item { flex-direction: column; align-items: flex-start; }
    .promo-prices { margin-top: 0.25rem; }
}
"""
