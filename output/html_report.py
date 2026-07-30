"""HTML report — generates a styled price comparison report with filter dropdown."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
) -> Path:
    """Generate an HTML report and return the file path."""
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(ZoneInfo("Asia/Singapore"))
    if filename is None:
        filename = f"prices_{timestamp:%Y%m%d_%H%M%S}.html"
    elif not filename.endswith(".html"):
        filename = f"{filename}.html"
    filepath = output_dir / filename

    html = _build_html(results, spot, history, timestamp, failed_dealers or [])
    filepath.write_text(html)

    return filepath


def _get_group(canonical_name: str) -> str:
    """Derive a group label like '1oz Gold' or '1kg Silver' from the product name."""
    name_lower = canonical_name.lower()
    metal = "Gold" if "gold" in name_lower else "Silver"

    weight_match = re.match(r"(\d+(?:oz|g|kg))", name_lower)
    if weight_match:
        return f"{weight_match.group(1)} {metal}"

    if "1 oz" in name_lower:
        return f"1oz {metal}"

    return f"Other {metal}"


def _build_html(
    results: list[ComparisonResult],
    spot: SpotPrices | None,
    history: list[SpotDataPoint] | None,
    timestamp: datetime,
    failed_dealers: list[str] | None = None,
) -> str:
    groups: defaultdict[str, list[str]] = defaultdict(list)

    for result in results:
        group = _get_group(result.canonical_name)
        groups[group].append(_product_section(result, spot, group))

    group_order = _sort_groups(list(groups.keys()))
    options = ['<option value="all">All Products</option>']
    for g in group_order:
        options.append(f'<option value="{g}">{g}</option>')

    sections = []
    for g in group_order:
        cards = "".join(groups[g])
        sections.append(f'<div class="group-section" data-group="{g}">'
                        f'<h2 class="group-heading">{g}</h2>{cards}</div>')

    spot_html = _spot_section(spot) if spot else ""
    chart_html = _chart_section(history) if history else ""
    promo_html = _promotions_section(results)
    failed_html = ""
    if failed_dealers:
        dealer_list = ", ".join(failed_dealers)
        failed_html = f"""
    <div class="failed-notice">
        <strong>Data unavailable:</strong> {dealer_list}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bullion Price Comparison — {timestamp:%d %b %Y %H:%M}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
{_CSS}
</style>
</head>
<body>
<div class="container">
    <h1>Bullion Price Comparison</h1>
    <p class="timestamp">Generated: {timestamp:%A, %d %B %Y at %H:%M:%S} SGT</p>
    {failed_html}
    {spot_html}
    {chart_html}
    {promo_html}
    <div class="filter-bar">
        <label for="group-filter">Filter by size:</label>
        <select id="group-filter" onchange="filterGroup(this.value)">
            {"".join(options)}
        </select>
    </div>
    {"".join(sections)}
</div>
<script>
{_JS}
</script>
</body>
</html>"""


def _sort_groups(groups: list[str]) -> list[str]:
    """Sort groups: gold first, then silver, each by weight ascending."""
    weight_order = {"1g": 1, "5g": 2, "10g": 3, "20g": 4, "1oz": 5,
                    "50g": 6, "100g": 7, "250g": 8, "500g": 9, "10oz": 10, "1kg": 11}

    def sort_key(g: str) -> tuple:
        metal_rank = 0 if "Gold" in g else 1
        match = re.match(r"(\d+(?:oz|g|kg))", g.lower())
        weight_rank = weight_order.get(match.group(1), 99) if match else 99
        return (metal_rank, weight_rank)

    return sorted(groups, key=sort_key)


def _spot_section(spot: SpotPrices) -> str:
    rows = []
    if spot.gold_oz:
        rows.append(f'<tr><td>Gold</td><td class="price">SGD {spot.gold_oz:,.2f}</td></tr>')
    if spot.silver_oz:
        rows.append(f'<tr><td>Silver</td><td class="price">SGD {spot.silver_oz:,.2f}</td></tr>')

    return f"""
    <div class="spot-card">
        <h2>Spot Prices <span class="unit">(per troy oz)</span></h2>
        <table class="spot-table">
            {"".join(rows)}
        </table>
        <p class="source">Source: {spot.source}</p>
    </div>"""


def _promotions_section(results: list[ComparisonResult]) -> str:
    """Generate a highlighted section showing all active promotions."""
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
        rows.append(f"""
            <tr>
                <td class="promo-product">{canonical_name}</td>
                <td class="promo-dealer">{'<a href="' + p.url + '" target="_blank">' + p.dealer + '</a>' if p.url else p.dealer}</td>
                <td class="promo-regular"><s>SGD {promo.regular_price:,.2f}</s></td>
                <td class="promo-offer">SGD {promo.offer_price:,.2f}</td>
                <td class="promo-discount">-{promo.discount_pct:.1f}%</td>
            </tr>""")

    return f"""
    <div class="promo-card">
        <h2>Active Promotions</h2>
        <table class="promo-table">
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Dealer</th>
                    <th>Regular</th>
                    <th>Offer</th>
                    <th>Discount</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>"""


def _chart_section(history: list[SpotDataPoint]) -> str:
    """Generate the 12-month spot price chart using Chart.js."""
    labels = []
    gold_data = []
    silver_data = []

    for point in history:
        labels.append(f'"{point.date}"')
        gold_data.append(str(round(float(point.gold_sgd), 2)) if point.gold_sgd else "null")
        silver_data.append(str(round(float(point.silver_sgd), 2)) if point.silver_sgd else "null")

    return f"""
    <div class="chart-card">
        <h2>Spot Price — 12 Month Trend</h2>
        <div class="chart-tabs">
            <button class="chart-tab active" onclick="showChart('gold')">Gold</button>
            <button class="chart-tab" onclick="showChart('silver')">Silver</button>
        </div>
        <div class="chart-container" id="chart-gold">
            <canvas id="goldChart"></canvas>
        </div>
        <div class="chart-container" id="chart-silver" style="display:none;">
            <canvas id="silverChart"></canvas>
        </div>
    </div>
    <script>
    (function() {{
        const labels = [{",".join(labels)}];
        const goldData = [{",".join(gold_data)}];
        const silverData = [{",".join(silver_data)}];

        const chartOpts = {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ intersect: false, mode: 'index' }},
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                    callbacks: {{
                        label: ctx => 'SGD ' + ctx.parsed.y.toLocaleString(undefined, {{minimumFractionDigits: 2}})
                    }}
                }}
            }},
            scales: {{
                x: {{
                    grid: {{ display: false }},
                    ticks: {{
                        callback: function(val, idx) {{
                            const d = new Date(labels[idx]);
                            return d.toLocaleDateString('en-SG', {{month: 'short', year: '2-digit'}});
                        }}
                    }}
                }},
                y: {{
                    grid: {{ color: '#f2f2f7' }},
                    ticks: {{
                        callback: val => 'SGD ' + val.toLocaleString()
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
                    borderColor: '#D4AF37',
                    backgroundColor: 'rgba(212, 175, 55, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: '#D4AF37',
                }}]
            }},
            options: chartOpts
        }});

        new Chart(document.getElementById('silverChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    data: silverData,
                    borderColor: '#8E8E93',
                    backgroundColor: 'rgba(142, 142, 147, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: '#8E8E93',
                }}]
            }},
            options: chartOpts
        }});
    }})();

    function showChart(metal) {{
        document.getElementById('chart-gold').style.display = metal === 'gold' ? '' : 'none';
        document.getElementById('chart-silver').style.display = metal === 'silver' ? '' : 'none';
        document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
        event.target.classList.add('active');
    }}
    </script>"""


def _product_section(result: ComparisonResult, spot: SpotPrices | None, group: str) -> str:
    spot_price = get_spot_for_product(result.canonical_name, spot)

    in_stock = [p for p in result.prices if p.in_stock]
    out_of_stock = [p for p in result.prices if not p.in_stock]
    cheapest = result.cheapest

    rows = []
    for p in in_stock:
        premium_str = ""
        premium_class = ""
        if spot_price and spot_price > 0:
            premium_pct = ((p.price - spot_price) / spot_price) * 100
            premium_str = f"{premium_pct:+.1f}%"
            if premium_pct <= 4:
                premium_class = "premium-low"
            elif premium_pct <= 6:
                premium_class = "premium-mid"
            else:
                premium_class = "premium-high"

        is_cheapest = cheapest and p.dealer == cheapest.dealer and p.price == cheapest.price
        row_class = "cheapest-row" if is_cheapest else ""
        badge = ' <span class="badge">BEST</span>' if is_cheapest and len(in_stock) > 1 else ""

        dealer_link = f'<a href="{p.url}" target="_blank">{p.dealer}</a>' if p.url else p.dealer
        rows.append(f"""
            <tr class="{row_class}">
                <td class="dealer">{dealer_link}{badge}</td>
                <td class="price">SGD {p.price:,.2f}</td>
                <td class="premium {premium_class}">{premium_str}</td>
            </tr>""")

    for p in out_of_stock:
        dealer_link = f'<a href="{p.url}" target="_blank">{p.dealer}</a>' if p.url else p.dealer
        rows.append(f"""
            <tr class="oos-row">
                <td class="dealer">{dealer_link}</td>
                <td class="price">SGD {p.price:,.2f}</td>
                <td class="premium oos">OUT OF STOCK</td>
            </tr>""")

    summary = ""
    if cheapest and len(in_stock) > 1:
        most_expensive = in_stock[-1]
        savings = most_expensive.price - cheapest.price
        premium_text = ""
        if spot_price and spot_price > 0:
            premium = cheapest.price - spot_price
            premium_pct = (premium / spot_price) * 100
            premium_text = f'<span class="summary-premium">Premium: SGD {premium:,.2f} ({premium_pct:.1f}% over spot)</span>'

        summary = f"""
        <div class="summary">
            <span class="summary-savings">Save SGD {savings:,.2f} vs {most_expensive.dealer}</span>
            {premium_text}
        </div>"""

    return f"""
    <div class="product-card" data-group="{group}">
        <h3>{result.canonical_name}</h3>
        <table class="price-table">
            <thead>
                <tr>
                    <th>Dealer</th>
                    <th>Price</th>
                    <th>Premium</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        {summary}
    </div>"""


_JS = """
function filterGroup(value) {
    const sections = document.querySelectorAll('.group-section');
    sections.forEach(section => {
        if (value === 'all' || section.dataset.group === value) {
            section.style.display = '';
        } else {
            section.style.display = 'none';
        }
    });
}
"""

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f7;
    color: #1d1d1f;
    padding: 2rem;
    line-height: 1.5;
}
.container { max-width: 800px; margin: 0 auto; }
h1 {
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}
.timestamp {
    color: #6e6e73;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}
.filter-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    padding: 1rem;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.filter-bar label {
    font-size: 0.9rem;
    font-weight: 500;
    color: #6e6e73;
}
.filter-bar select {
    font-size: 0.95rem;
    padding: 0.5rem 1rem;
    border: 1px solid #e5e5ea;
    border-radius: 8px;
    background: #f5f5f7;
    color: #1d1d1f;
    font-weight: 500;
    cursor: pointer;
    outline: none;
}
.filter-bar select:focus {
    border-color: #007aff;
    box-shadow: 0 0 0 3px rgba(0,122,255,0.1);
}
.failed-notice {
    background: #fff3f3;
    border: 1px solid #ffcdd2;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
    color: #c62828;
    font-size: 0.9rem;
}
.promo-card {
    background: linear-gradient(135deg, #fff8e1 0%, #fff3cd 100%);
    border: 1px solid #ffd54f;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.promo-card h2 {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: #e65100;
}
.promo-table {
    width: 100%;
    border-collapse: collapse;
}
.promo-table th {
    text-align: left;
    font-size: 0.75rem;
    font-weight: 500;
    color: #6e6e73;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.5rem 0.5rem;
    border-bottom: 1px solid #ffe082;
}
.promo-table td {
    padding: 0.6rem 0.5rem;
    border-bottom: 1px solid #fff3cd;
    font-size: 0.9rem;
}
.promo-product { font-weight: 500; }
.promo-dealer { color: #6e6e73; }
.promo-regular { color: #8e8e93; }
.promo-offer { font-weight: 700; color: #1d1d1f; }
.promo-discount {
    font-weight: 700;
    color: #e65100;
    text-align: right;
}
.chart-card {
    background: #fff;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.chart-card h2 {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 1rem;
}
.chart-tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}
.chart-tab {
    padding: 0.4rem 1rem;
    border: 1px solid #e5e5ea;
    border-radius: 8px;
    background: #f5f5f7;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    color: #6e6e73;
    transition: all 0.15s;
}
.chart-tab.active {
    background: #1d1d1f;
    color: #fff;
    border-color: #1d1d1f;
}
.chart-container {
    height: 280px;
    position: relative;
}
.group-section {
    margin-bottom: 2rem;
}
.group-heading {
    font-size: 1.3rem;
    font-weight: 700;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e5e5ea;
    color: #1d1d1f;
}
.spot-card {
    background: #1d1d1f;
    color: #f5f5f7;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.spot-card h2 {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}
.spot-card .unit { font-weight: 400; color: #a1a1a6; }
.spot-table { width: 100%; }
.spot-table td {
    padding: 0.4rem 0;
    font-size: 1rem;
}
.spot-table .price {
    text-align: right;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}
.source {
    margin-top: 0.75rem;
    font-size: 0.8rem;
    color: #a1a1a6;
}
.product-card {
    background: #fff;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.product-card h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: #1d1d1f;
}
.price-table {
    width: 100%;
    border-collapse: collapse;
}
.price-table th {
    text-align: left;
    font-size: 0.75rem;
    font-weight: 500;
    color: #6e6e73;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.5rem 0;
    border-bottom: 1px solid #e5e5ea;
}
.price-table th:nth-child(2),
.price-table th:nth-child(3) { text-align: right; }
.price-table td {
    padding: 0.6rem 0;
    border-bottom: 1px solid #f2f2f7;
    font-size: 0.95rem;
}
.price-table .dealer { font-weight: 500; }
.price-table .dealer a, .promo-dealer a {
    color: inherit;
    text-decoration: none;
    border-bottom: 1px dashed rgba(0,0,0,0.3);
}
.price-table .dealer a:hover, .promo-dealer a:hover {
    border-bottom-style: solid;
    color: #2563eb;
}
.price-table .price {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}
.price-table .premium {
    text-align: right;
    font-size: 0.85rem;
    font-weight: 500;
}
.premium-low { color: #34c759; }
.premium-mid { color: #ff9500; }
.premium-high { color: #ff3b30; }
.oos { color: #8e8e93; font-style: italic; font-size: 0.8rem; }
.oos-row td { color: #8e8e93; }
.cheapest-row td { color: #1d1d1f; }
.cheapest-row .price { font-weight: 700; }
.badge {
    display: inline-block;
    background: #34c759;
    color: #fff;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    margin-left: 0.5rem;
    vertical-align: middle;
}
.summary {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid #e5e5ea;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
}
.summary-savings {
    font-weight: 600;
    color: #34c759;
    font-size: 0.9rem;
}
.summary-premium {
    font-size: 0.85rem;
    color: #6e6e73;
}
@media (max-width: 600px) {
    body { padding: 1rem; }
    .summary { flex-direction: column; align-items: flex-start; }
    .filter-bar { flex-direction: column; align-items: flex-start; }
}
"""
