#!/usr/bin/env python3
"""Refresh Japanese card-name index from the community Pokémon TCG API."""
import json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
API="https://pokemontcg.jacobcorbett.com/api/v1/cards"
names=set()
total=None
for page in range(1, 501):
    query=urllib.parse.urlencode({"language":"jp","limit":100,"page":page})
    url=API+"?"+query
    error=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"PokemonCardCatalog/1.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=35) as response:
                body=json.load(response)
            break
        except Exception as exc:
            error=exc
            time.sleep(2**attempt)
    else:
        raise RuntimeError(f"Page {page} failed: {error}")
    rows=body.get("data",[])
    if not isinstance(rows,list):
        raise RuntimeError("Unexpected API response")
    for card in rows:
        if isinstance(card,dict) and isinstance(card.get("name"),str):
            names.add(card["name"].strip())
    if body.get("total") is not None:
        total=int(body["total"])
    print(f"page={page} rows={len(rows)} names={len(names)} total={total}",flush=True)
    if not rows or len(rows)<100 or (total is not None and page*100>=total):
        break
    time.sleep(.25)
if len(names)<100:
    raise RuntimeError(f"Only {len(names)} names retrieved; keeping previous index")
payload={"updatedAt":datetime.now(timezone.utc).isoformat(),"source":API,"count":len(names),"names":sorted(names)}
path=Path("data/card-names.json")
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
print(f"Saved {len(names)} unique Japanese card names")
