#!/usr/bin/env python3
"""Fetch a public Japanese Pokémon deck page and extract card IDs/counts.
Only writes a deck when the parsed counts total exactly 60.
"""
import argparse
import json
import re
import urllib.request
from urllib.parse import urljoin
from datetime import datetime, timezone
from pathlib import Path
from html import unescape

BASE = "https://www.pokemon-card.com"
CODE_RE = re.compile(r"^[A-Za-z0-9-]{10,60}$")
FIELD_RE = re.compile(r'<input\b(?=[^>]*\b(?:id|name)=[\'"]?(deck_pok|deck_gds|deck_tool|deck_sup|deck_sta|deck_ene)[\'"]?)[^>]*>', re.I)
ATTR_RE = re.compile(r'([\w-]+)\s*=\s*([\'"])(.*?)\2', re.S)
ENTRY_RE = re.compile(r"(\d{4,6})_(\d{1,2})_(\d+)")
CATEGORIES = {"deck_pok": "ポケモン", "deck_pke": "ポケモン", "deck_tech": "その他", "deck_gds": "グッズ", "deck_tool": "ポケモンのどうぐ", "deck_sup": "サポート", "deck_sta": "スタジアム", "deck_ene": "エネルギー"}

def parse_deck(html):
    cards = []
    diagnostics = []
    for match in re.finditer(r"<input\b[^>]*>", html, re.I | re.S):
        attrs = {k.lower(): unescape(v) for k, _, v in ATTR_RE.findall(match.group())}
        field = attrs.get("id") if attrs.get("id") in CATEGORIES else attrs.get("name")
        if field not in CATEGORIES:
            continue
        raw = attrs.get("value", "")
        matches = ENTRY_RE.findall(raw)
        diagnostics.append({"field": field, "matched": len(matches), "rawLength": len(raw), "sample": raw[:140]})
        for card_id, count, main in matches:
            cards.append({"cardId": card_id, "count": int(count), "category": CATEGORIES[field]})
    return cards, diagnostics

def extract_js_map(html, property_name):
    """Read ID-to-string mappings in inline JavaScript."""
    anchor = re.search(r"\b" + re.escape(property_name) + r"\s*[:=]\s*\{", html)
    if not anchor:
        return {}
    start = anchor.end()
    depth = 1
    end = start
    while end < len(html) and depth:
        if html[end] == "{":
            depth += 1
        elif html[end] == "}":
            depth -= 1
        end += 1
    body = html[start:end - 1]
    values = {}
    pattern = r"""['"]?(\d{4,6})['"]?\s*:\s*(['"])(.*?)\2"""
    for m in re.finditer(pattern, body, re.S):
        values[m.group(1)] = unescape(m.group(3).replace("\\/", "/"))
    return values


def enrich_cards(html, cards):
    pictures = extract_js_map(html, "searchItemCardPict")
    names = extract_js_map(html, "searchItemCardName")
    print("Card image mappings:", len(pictures), "name mappings:", len(names))
    print("Deck page image references:", re.findall(r"""(?:src|data-src)=[\'"]([^\'"]+\.(?:jpg|png|webp)[^\'"]*)""", html, re.I)[:8])
    for card in cards:
        cid = card["cardId"]
        if cid in pictures:
            url = urljoin(BASE, pictures[cid])
            if url.startswith(BASE + "/"):
                card["imageUrl"] = url
        if cid in names:
            card["name"] = names[cid]
    print("Deck cards with images:", sum("imageUrl" in c for c in cards))
    return cards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("code")
    args = parser.parse_args()
    code = args.code.strip()
    if not CODE_RE.fullmatch(code):
        raise ValueError("Invalid deck code")
    url = f"{BASE}/deck/confirm.html/deckID/{code}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; deck-indexer/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    cards, diagnostics = parse_deck(html)
    print("Page bytes:", len(html))
    print("Parsed fields:", json.dumps(diagnostics, ensure_ascii=False))
    print("Other deck-related input names:", sorted(set(re.findall(r'<input[^>]+(?:id|name)=[\\\'"]([^\\\'"]*deck[^\\\'"]*)', html, re.I)))[:30])
    cards = enrich_cards(html, cards)
    total = sum(c["count"] for c in cards)
    if total != 60:
        raise RuntimeError(f"Deck validation failed: parsed {len(cards)} entries / {total} cards, expected 60. Not saving incomplete data.")
    output = Path("data/decks") / f"{code}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"deckCode": code, "source": url, "updatedAt": datetime.now(timezone.utc).isoformat(), "total": total, "cards": cards}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {total} cards ({len(cards)} unique prints) to {output}")

if __name__ == "__main__":
    main()
