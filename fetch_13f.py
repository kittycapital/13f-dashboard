#!/usr/bin/env python3
"""
SEC EDGAR 13F Holdings Fetcher
Fetches latest 13F filings for top hedge funds via free SEC EDGAR API.
Designed to run via GitHub Actions on a schedule.
Output: data/holdings.json
"""

import json
import time
import gzip
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# SEC EDGAR requires a User-Agent header
HEADERS = {
    "User-Agent": "KleveraDashboard/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}

# ──────────────────────────────────────────────
# Top Hedge Funds - CIK Numbers
# ──────────────────────────────────────────────
FUNDS = {
    # Group A: 2025 Winners + Clean 13F
    "1647251": {
        "name": "TCI Fund Management",
        "manager": "크리스 혼 (Chris Hohn)",
        "group": "A",
        "tag": "2025 #1 Dollar Gains",
        "emoji": "🏆",
        "strategy": "Activist/Concentrated Equity",
        "return_2025": None,
    },
    "1535392": {
        "name": "Soroban Capital Partners",
        "manager": "에릭 만델블랫 (Eric Mandelblatt)",
        "group": "A",
        "tag": "2025 +25%",
        "emoji": "📈",
        "strategy": "Long/Short Equity",
        "return_2025": 25.0,
    },
    "1336528": {
        "name": "Pershing Square Capital",
        "manager": "빌 애크먼 (Bill Ackman)",
        "group": "A",
        "tag": "Concentrated",
        "emoji": "🎯",
        "strategy": "Concentrated Equity",
        "return_2025": None,
    },
    "1656456": {
        "name": "Appaloosa Management",
        "manager": "데이비드 테퍼 (David Tepper)",
        "group": "A",
        "tag": "Contrarian",
        "emoji": "🔄",
        "strategy": "Macro-Equity",
        "return_2025": None,
    },
    # Group B: Legendary Names
    "1067983": {
        "name": "Berkshire Hathaway",
        "manager": "워런 버핏 (Warren Buffett)",
        "group": "B",
        "tag": "Legend",
        "emoji": "👑",
        "strategy": "Value Investing",
        "return_2025": None,
    },
    "1649339": {
        "name": "Scion Asset Management",
        "manager": "마이클 버리 (Michael Burry)",
        "group": "B",
        "tag": "Big Short",
        "emoji": "🎬",
        "strategy": "Value/Contrarian",
        "return_2025": None,
    },
    "1029160": {
        "name": "Soros Fund Management",
        "manager": "조지 소로스 (George Soros)",
        "group": "B",
        "tag": "Macro Legend",
        "emoji": "🌍",
        "strategy": "Global Macro",
        "return_2025": None,
    },
    "1536411": {
        "name": "Duquesne Family Office",
        "manager": "스탠리 드러켄밀러 (Stanley Druckenmiller)",
        "group": "B",
        "tag": "GOAT Trader",
        "emoji": "🐐",
        "strategy": "Macro/Growth",
        "return_2025": None,
    },
    "1603466": {
        "name": "ARK Investment Management",
        "manager": "캐시 우드 (Cathie Wood)",
        "group": "B",
        "tag": "Innovation",
        "emoji": "🚀",
        "strategy": "Disruptive Innovation",
        "return_2025": None,
    },
    # Group C: 2025 Top Performers (Top holdings only)
    "1350694": {
        "name": "Bridgewater Associates",
        "manager": "레이 달리오 (Ray Dalio, 설립)",
        "group": "C",
        "tag": "2025 +34%",
        "emoji": "🌊",
        "strategy": "Global Macro",
        "return_2025": 34.0,
    },
    "1009207": {
        "name": "D.E. Shaw & Co.",
        "manager": "데이비드 쇼 (David Shaw)",
        "group": "C",
        "tag": "2025 +28%",
        "emoji": "🤖",
        "strategy": "Quant Multi-Strategy",
        "return_2025": 28.2,
    },
    "1037389": {
        "name": "Renaissance Technologies",
        "manager": "짐 사이먼스 (Jim Simons, 설립)",
        "group": "C",
        "tag": "Quant King",
        "emoji": "🧮",
        "strategy": "Quantitative",
        "return_2025": None,
    },
    "1423053": {
        "name": "Citadel Advisors",
        "manager": "켄 그리핀 (Ken Griffin)",
        "group": "C",
        "tag": "2025 +10.2%",
        "emoji": "🏰",
        "strategy": "Multi-Strategy",
        "return_2025": 10.2,
    },
}


def fetch_url(url: str, max_retries: int = 3) -> bytes:
    """Fetch URL with retry logic and rate limiting."""
    for attempt in range(max_retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
                # Decompress gzip if needed (0x1f 0x8b is gzip magic bytes)
                if data[:2] == b'\x1f\x8b':
                    data = gzip.decompress(data)
                return data
        except HTTPError as e:
            if e.code == 429:
                wait = 12 * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {e.code} for {url}")
                raise
        except Exception as e:
            print(f"  Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise
    return b""


def get_latest_13f_url(cik: str) -> tuple[str, str, str]:
    """Get the latest 13F filing accession number and period for a given CIK.
    Returns (accession_no_raw, period, accession_no_formatted)
    """
    cik_padded = cik.zfill(10)
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    print(f"  Fetching submissions for CIK {cik}...")
    data = json.loads(fetch_url(submissions_url))

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])

    for i, form in enumerate(forms):
        if form in ("13F-HR", "13F-HR/A"):
            accession_formatted = accessions[i]  # e.g. "0000950123-25-008343"
            accession_raw = accession_formatted.replace("-", "")
            period = report_dates[i] if i < len(report_dates) else dates[i]
            return accession_raw, period, accession_formatted

    return "", "", ""


def find_info_table_url(cik: str, accession_raw: str, accession_formatted: str) -> str:
    """Find the informationTable XML file URL by parsing the filing index."""

    # Method 1: Use the index.json to find the XML file
    index_json_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_raw}/{accession_formatted}-index.json"
    print(f"  Trying index JSON: {index_json_url}")

    try:
        data = json.loads(fetch_url(index_json_url))
        base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_raw}/"
        for item in data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            name_lower = name.lower()
            # Look for XML files that contain holdings data
            if name_lower.endswith(".xml") and "infotable" in name_lower:
                url = base_url + name
                print(f"  Found via JSON index: {name}")
                return url
        # If no infotable found, look for any XML that's not the primary doc
        for item in data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            name_lower = name.lower()
            if name_lower.endswith(".xml") and "primary" not in name_lower:
                url = base_url + name
                print(f"  Found XML candidate: {name}")
                return url
    except Exception as e:
        print(f"  JSON index failed: {e}")

    # Method 2: Fetch the HTML index page and parse it
    index_html_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_raw}/{accession_formatted}-index.htm"
    print(f"  Trying HTML index: {index_html_url}")

    try:
        html = fetch_url(index_html_url).decode("utf-8", errors="ignore")
        base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_raw}/"

        # Find XML files linked in the page
        import re
        links = re.findall(r'href="([^"]*\.xml)"', html, re.IGNORECASE)
        for link in links:
            if "infotable" in link.lower() or "information" in link.lower():
                if link.startswith("http"):
                    return link
                return base_url + link.split("/")[-1]

        # Also check for table descriptions mentioning "INFORMATION TABLE"
        if "INFORMATION TABLE" in html.upper():
            for link in links:
                name_lower = link.lower()
                if name_lower.endswith(".xml") and "primary" not in name_lower:
                    if link.startswith("http"):
                        return link
                    return base_url + link.split("/")[-1]
    except Exception as e:
        print(f"  HTML index failed: {e}")

    # Method 3: Try common filenames directly
    base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_raw}/"
    common_names = [
        "form13fInfoTable.xml",
        "infotable.xml",
        "InfoTable.xml",
        "INFOTABLE.XML",
        "information_table.xml",
        "xslForm13F_X02.xml",
    ]
    for name in common_names:
        try:
            test_url = base_url + name
            fetch_url(test_url)
            print(f"  Found via filename probe: {name}")
            return test_url
        except Exception:
            continue

    return ""


def parse_13f_xml(xml_data: bytes) -> list[dict]:
    """Parse 13F XML information table into holdings list."""
    holdings = []

    # Handle various XML namespaces used in 13F filings
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        # Try removing encoding declaration
        text = xml_data.decode("utf-8", errors="ignore")
        if "<?xml" in text:
            text = text[text.index("?>") + 2 :]
        root = ET.fromstring(text)

    # Find all infoTable entries (handle namespace variations)
    # Auto-detect namespace from root tag
    ns_patterns = [
        "{http://www.sec.gov/edgar/document/thirteenf/informationtable}",
        "{http://www.sec.gov/edgar/thirteenf}",
        "{http://www.sec.gov/edgar/common/informationtable}",
        "",
    ]
    
    # Try to extract namespace from root element
    root_tag = root.tag
    if "{" in root_tag:
        auto_ns = root_tag[:root_tag.index("}") + 1]
        if auto_ns not in ns_patterns:
            ns_patterns.insert(0, auto_ns)

    info_tables = []
    for ns in ns_patterns:
        info_tables = root.findall(f".//{ns}infoTable")
        if info_tables:
            break

    for entry in info_tables:
        holding = {}
        for ns in ns_patterns:
            name = entry.findtext(f"{ns}nameOfIssuer")
            if name:
                holding["name"] = name.strip()
                holding["title"] = (
                    entry.findtext(f"{ns}titleOfClass", "COM").strip()
                )
                holding["cusip"] = entry.findtext(f"{ns}cusip", "").strip()

                # Value is in thousands in the XML
                val_text = entry.findtext(f"{ns}value", "0")
                holding["value"] = int(val_text) * 1000

                shares_node = entry.find(f"{ns}shrsOrPrnAmt")
                if shares_node is not None:
                    sh_text = shares_node.findtext(f"{ns}sshPrnamt", "0")
                    holding["shares"] = int(sh_text)
                    holding["type"] = shares_node.findtext(
                        f"{ns}sshPrnamtType", "SH"
                    )
                else:
                    holding["shares"] = 0
                    holding["type"] = "SH"

                holding["discretion"] = entry.findtext(
                    f"{ns}investmentDiscretion", "SOLE"
                ).strip()
                break

        if holding.get("name"):
            holdings.append(holding)

    return holdings


def process_fund(cik: str, fund_info: dict) -> dict:
    """Process a single fund's 13F filing."""
    print(f"\n{'='*60}")
    print(f"Processing: {fund_info['name']} ({fund_info['manager']})")
    print(f"CIK: {cik}")

    result = {
        "cik": cik,
        "name": fund_info["name"],
        "manager": fund_info["manager"],
        "group": fund_info["group"],
        "tag": fund_info["tag"],
        "emoji": fund_info["emoji"],
        "strategy": fund_info["strategy"],
        "return_2025": fund_info["return_2025"],
        "period": "",
        "total_value": 0,
        "num_holdings": 0,
        "top_holdings": [],
        "all_holdings": [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }

    try:
        # Step 1: Get latest 13F filing URL
        accession_raw, period, accession_formatted = get_latest_13f_url(cik)
        if not accession_raw:
            result["error"] = "No 13F filing found"
            return result

        result["period"] = period
        print(f"  Period: {period}")
        print(f"  Accession: {accession_formatted}")

        time.sleep(0.15)  # SEC rate limit: 10 req/sec

        # Step 2: Find the information table XML
        xml_url = find_info_table_url(cik, accession_raw, accession_formatted)
        if not xml_url:
            result["error"] = "Could not find information table XML"
            return result

        print(f"  XML: {xml_url}")
        time.sleep(0.15)

        # Step 3: Fetch and parse the XML
        xml_data = fetch_url(xml_url)
        holdings = parse_13f_xml(xml_data)

        if not holdings:
            result["error"] = "No holdings parsed from XML"
            return result

        # Step 4: Calculate totals and sort
        total_value = sum(h["value"] for h in holdings)
        result["total_value"] = total_value
        result["num_holdings"] = len(holdings)

        # Sort by value descending
        holdings.sort(key=lambda x: x["value"], reverse=True)

        # Add portfolio weight
        for h in holdings:
            h["weight"] = round(h["value"] / total_value * 100, 2) if total_value > 0 else 0

        # Top 20 for display
        result["top_holdings"] = holdings[:20]

        # For Group C (large multi-strategy), only keep top 10
        if fund_info["group"] == "C":
            result["top_holdings"] = holdings[:10]

        # Store all for cross-fund analysis (limit to top 50)
        result["all_holdings"] = holdings[:50]

        print(f"  ✅ {len(holdings)} holdings, total ${total_value:,.0f}")
        print(f"  Top: {holdings[0]['name']} ({holdings[0]['weight']}%)")

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")

    return result


def find_cross_fund_overlap(all_funds: list[dict]) -> list[dict]:
    """Find stocks held by multiple funds."""
    stock_funds = {}  # cusip -> {name, funds: [...], total_value}

    for fund in all_funds:
        if fund.get("error"):
            continue
        for h in fund.get("all_holdings", []):
            cusip = h.get("cusip", "")
            if not cusip:
                continue
            if cusip not in stock_funds:
                stock_funds[cusip] = {
                    "name": h["name"],
                    "cusip": cusip,
                    "funds": [],
                    "total_value": 0,
                }
            stock_funds[cusip]["funds"].append({
                "fund": fund["name"],
                "manager": fund["manager"],
                "value": h["value"],
                "shares": h["shares"],
                "weight": h.get("weight", 0),
            })
            stock_funds[cusip]["total_value"] += h["value"]

    # Filter to stocks held by 2+ funds, sort by fund count
    overlaps = []
    for v in stock_funds.values():
        if len(v["funds"]) >= 2:
            v["fund_count"] = len(v["funds"])
            v["fund_names"] = [f["fund"] for f in v["funds"]]
            overlaps.append(v)
    overlaps.sort(key=lambda x: (-x["fund_count"], -x["total_value"]))

    return overlaps[:30]


def main():
    print("=" * 60)
    print("SEC EDGAR 13F Holdings Fetcher")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"Tracking {len(FUNDS)} funds")
    print("=" * 60)

    results = []

    for cik, info in FUNDS.items():
        try:
            result = process_fund(cik, info)
            results.append(result)
            time.sleep(0.5)  # Be nice to SEC servers
        except Exception as e:
            print(f"  ❌ Fatal error for {info['name']}: {e}")
            results.append({
                "cik": cik,
                "name": info["name"],
                "manager": info["manager"],
                "group": info["group"],
                "tag": info["tag"],
                "emoji": info["emoji"],
                "strategy": info["strategy"],
                "return_2025": info["return_2025"],
                "error": str(e),
                "top_holdings": [],
                "all_holdings": [],
            })

    # Cross-fund analysis
    print(f"\n{'='*60}")
    print("Running cross-fund overlap analysis...")
    overlaps = find_cross_fund_overlap(results)
    print(f"Found {len(overlaps)} stocks held by 2+ funds")

    # Build output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "num_funds": len(results),
        "funds": results,
        "cross_fund_overlap": overlaps,
    }

    # Save to data directory
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "holdings.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved to {out_path}")
    print(f"Finished: {datetime.now(timezone.utc).isoformat()}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    success = sum(1 for r in results if not r.get("error"))
    print(f"Success: {success}/{len(results)}")
    for r in results:
        status = "✅" if not r.get("error") else "❌"
        holdings_count = r.get("num_holdings", 0)
        print(f"  {status} {r['name']}: {holdings_count} holdings")


if __name__ == "__main__":
    main()
