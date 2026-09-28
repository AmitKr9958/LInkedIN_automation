from __future__ import annotations

import json
from typing import Any

from .approval_queue import ApprovalQueue
from .content_skills import (
    analyze_engagers, content_plan, draft_comment, draft_reply,
    employee_advocacy_plan, extract_hook, humanize, interviewer_questions,
    profile_audit, repurpose, write_post,
)
from .skill_registry import list_skills
from .browser import linkedin_browser
from .skill_runtime import ensure_authenticated, run_read, run_read_on_page
from .workflows import login_check

READ_SKILLS = {"auth", "profile", "jobs", "people", "companies", "posts", "saved", "notifications"}
APPROVAL_SKILLS = {"connections", "messaging", "engagement", "followups", "outreach"}

def skill_catalog() -> list[dict[str, Any]]:
    fields = {
        "auth": [], "profile": [],
        "jobs": [{"name":"query","label":"Job query","default":"Power BI"},{"name":"location","label":"Locations (comma separated)","default":"Gurgaon/Gurugram, Noida, Delhi, Remote India"},{"name":"max_posted_hours","label":"Posted within hours","type":"number","default":48}],
        "people": [{"name":"query","label":"Search","default":"Power BI recruiter"},{"name":"location","label":"Locations (comma separated)","default":"Gurgaon/Gurugram, Noida, Delhi, India"}],
        "companies": [{"name":"query","label":"Company search","default":"data analytics"}],
        "posts": [{"name":"query","label":"Post search","default":"Power BI"}],
        "saved": [], "notifications": [],
        "post_writer": [{"name":"topic","label":"Topic"},{"name":"angle","label":"Angle"},{"name":"hook","label":"Optional hook"}],
        "content_planner": [{"name":"theme","label":"Theme"},{"name":"audience","label":"Audience"},{"name":"days","label":"Days","type":"number","default":7}],
        "comment_drafter": [{"name":"post_text","label":"Post text","type":"textarea"},{"name":"point","label":"Your point","type":"textarea"}],
        "reply_handler": [{"name":"comment_text","label":"Comment","type":"textarea"},{"name":"response","label":"Your response","type":"textarea"}],
        "post_audit": [{"name":"text","label":"Post draft","type":"textarea"}],
        "humanizer": [{"name":"text","label":"Draft to clean","type":"textarea"}],
        "hook_extractor": [{"name":"text","label":"Post text","type":"textarea"}],
        "repurposer": [{"name":"source","label":"Source content","type":"textarea"},{"name":"goal","label":"Goal","default":"engagement"}],
        "profile_optimizer": [{"name":"profile","label":"Profile JSON","type":"textarea","default":'{"headline":"","about":"","experience":"","skills":"","featured":""}'}],
        "interviewer": [{"name":"topic","label":"Topic"}], "story_bank": [],
        "engager_analytics": [{"name":"rows","label":"Engager records JSON","type":"textarea","default":"[]"},{"name":"target_titles","label":"Target titles (comma separated)"}],
        "thread_monitor": [{"name":"rows","label":"Thread records JSON","type":"textarea","default":"[]"}],
        "employee_advocacy": [{"name":"team_size","label":"Team size","type":"number","default":10},{"name":"goal","label":"Goal"}],
        "leadgen": [{"name":"description","label":"Lead-generation goal","type":"textarea"}],
        "connections": [{"name":"target","label":"Target/profile URL"},{"name":"payload","label":"Requested action","type":"textarea"}],
        "messaging": [{"name":"target","label":"Target"},{"name":"payload","label":"Message draft","type":"textarea"}],
        "engagement": [{"name":"target","label":"Post/comment URL"},{"name":"payload","label":"Requested engagement","type":"textarea"}],
        "followups": [{"name":"target","label":"Target"},{"name":"payload","label":"Follow-up draft","type":"textarea"}],
        "outreach": [{"name":"target","label":"Job/post/profile URL"},{"name":"payload","label":"Outreach plan","type":"textarea"}],
    }
    mutating = {s.name for s in list_skills() if s.mutating}
    return [{"name":s.name,"description":s.description,"mutating":s.name in mutating,
             "mode":"read" if s.name in READ_SKILLS else ("approval" if s.name in APPROVAL_SKILLS else "local"),
             "fields":fields.get(s.name,[])} for s in list_skills()]

def _json_value(value: str, default: Any = None) -> Any:
    try: return json.loads(value)
    except (TypeError, json.JSONDecodeError): return default

async def run_skill(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    known = {s["name"] for s in skill_catalog()}
    if name not in known: raise ValueError(f"Unknown skill: {name}")

    if name == "auth":
        result = await login_check(wait_for_login=False)
        return {"skill":name,"mode":"read","status":result.status,"action":result.action,"details":result.details}

    if name in READ_SKILLS:
        if name in {"jobs","people"}:
            query = str(inputs.get("query","Power BI"))
            raw_locations = str(inputs.get("location","")).strip()
            locations = [x.strip() for x in raw_locations.replace(";", ",").split(",") if x.strip()]
            if not locations:
                locations = ["Gurgaon/Gurugram"]
            results = []
            diagnostics = {
                "requested_locations": locations,
                "location_runs": {},
                "session_reused": True,
            }

            # Reuse one authenticated persistent browser session for all
            # requested locations. The previous implementation opened and
            # closed Playwright for every location, multiplying startup and
            # authentication overhead and increasing profile-lock risk.
            async with linkedin_browser() as browser:
                page = browser.pages[0] if browser.pages else await browser.new_page()
                auth_state = await ensure_authenticated(page)
                diagnostics["authentication"] = {
                    "authenticated": bool(auth_state.get("authenticated")),
                    "confidence": auth_state.get("confidence"),
                }

                for location in locations:
                    kwargs = {"query": query, "keywords": query, "location": location}
                    if name == "jobs" and str(inputs.get("max_posted_hours","")).strip():
                        try:
                            kwargs["max_posted_hours"] = float(inputs["max_posted_hours"])
                        except ValueError:
                            raise ValueError("Posted within hours must be a number")
                    result = await run_read_on_page(page, name, **kwargs)
                    diagnostics["location_runs"][location] = result.diagnostics or {}
                    results.extend(result.data or [])

            # De-duplicate by the stable URL when available.
            seen = set()
            data = []
            for item in results:
                key = getattr(item, "href", "") or getattr(item, "url", "") or repr(item)
                if key in seen:
                    continue
                seen.add(key)
                data.append(item)
            return {"skill":name,"mode":"read","data":data,"diagnostics":diagnostics}
        kwargs = {}
        if name in {"companies","posts"}:
            kwargs["query"] = str(inputs.get("query","data analytics" if name=="companies" else "Power BI"))
        result = await run_read(name, **kwargs)
        data = result.data
        return {"skill":name,"mode":"read","data":data,"diagnostics":result.diagnostics}

    if name in APPROVAL_SKILLS:
        target = str(inputs.get("target","")).strip() or "manual-review"
        payload = str(inputs.get("payload","")).strip()
        if not payload: raise ValueError("Requested action/draft is required")
        item_id = ApprovalQueue().add(f"skill:{name}",target,payload)
        return {"skill":name,"mode":"approval","status":"pending_approval","approval_id":item_id,
                "message":"Prepared for human approval. No LinkedIn account action was executed."}

    if name=="post_writer":
        return write_post(str(inputs.get("topic","")),str(inputs.get("angle","")),str(inputs.get("hook",""))).__dict__
    if name=="content_planner":
        return {"plan":content_plan(str(inputs.get("theme","")),str(inputs.get("audience","")),int(inputs.get("days",7)))}
    if name=="comment_drafter": return draft_comment(str(inputs.get("post_text","")),str(inputs.get("point",""))).__dict__
    if name=="reply_handler": return draft_reply(str(inputs.get("comment_text","")),str(inputs.get("response",""))).__dict__
    if name=="post_audit":
        from .post_audit import audit_post
        return audit_post(str(inputs.get("text","")))
    if name=="humanizer": return humanize(str(inputs.get("text","")))
    if name=="hook_extractor": return extract_hook(str(inputs.get("text","")))
    if name=="repurposer": return repurpose(str(inputs.get("source","")),str(inputs.get("goal","engagement"))).__dict__
    if name=="profile_optimizer": return profile_audit(_json_value(str(inputs.get("profile","{}")),{}) or {})
    if name=="interviewer": return {"questions":interviewer_questions(str(inputs.get("topic","")))}
    if name=="story_bank":
        from .story_bank import StoryBank
        return {"stories":[x.to_dict() for x in StoryBank().list(50)]}
    if name=="engager_analytics":
        rows=_json_value(str(inputs.get("rows","[]")),[]) or []
        titles=[x.strip() for x in str(inputs.get("target_titles","")).split(",") if x.strip()]
        return {"rows":analyze_engagers(rows,titles)}
    if name=="thread_monitor":
        from .content_skills import thread_followups
        return {"followups":thread_followups(_json_value(str(inputs.get("rows","[]")),[]) or [])}
    if name=="employee_advocacy": return employee_advocacy_plan(int(inputs.get("team_size",10)),str(inputs.get("goal","")))
    if name=="leadgen":
        return {"status":"local_plan","goal":str(inputs.get("description","")),
                "next_step":"Use Job/People/Company read skills to gather evidence, then prepare an approval item."}
    raise ValueError(f"Skill {name} has no safe execution adapter yet.")
