from __future__ import annotations
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def normalize_job_url(url: str) -> str:
    if not url: return ""
    p=urlsplit(url)
    if not p.netloc: return url
    query=[(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith(("trk","tracking","utm_"))]
    path=p.path.rstrip("/")
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),path,"",urlencode(query)))

def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen=set(); out=[]
    for job in jobs:
        item=dict(job)
        key=normalize_job_url(item.get("url") or item.get("href") or "")
        if key:
            item["url"]=key
        else:
            key="|".join(str(item.get(k,"")).strip().lower() for k in ("title","company","location"))
        if key in seen: continue
        seen.add(key); out.append(item)
    return out
