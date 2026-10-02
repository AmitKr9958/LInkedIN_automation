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
from .llm_client import LLMError, chat_json, provider_status
from .profile_grounding import validate_profile_drafts
from .outreach import associate_people_with_jobs, build_outreach_plan
from .job_preferences import DEFAULT_JOB_PREFERENCES
from .drafting import hiring_contact_message

READ_SKILLS = {"auth", "profile", "jobs", "people", "companies", "posts", "saved", "notifications"}
APPROVAL_SKILLS = {"connections", "messaging", "engagement", "followups", "outreach"}

def skill_catalog() -> list[dict[str, Any]]:
    fields = {
        "auth": [], "profile": [],
        "jobs": [{"name":"query","label":"Job query","default":"Power BI"},{"name":"location","label":"Locations (comma separated)","default":"Gurgaon/Gurugram, Noida, Delhi, Remote India"},{"name":"max_posted_hours","label":"Posted within hours","type":"number","default":48}],
        "people": [
            {"name":"query","label":"Search terms","default":"Power BI recruiter"},
            {"name":"location","label":"Locations (comma separated)","default":"Gurgaon/Gurugram, Noida, Delhi, India"},
            {"name":"job_title","label":"Associated job title (optional)"},
            {"name":"company","label":"Associated company (optional)"},
            {"name":"job_url","label":"Associated job URL (optional)"},
        ],
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
        "profile_optimizer": [
            {"name":"source","label":"Profile source","type":"select","options":["live","manual"],"default":"live"},
            {"name":"profile","label":"Profile JSON (used for manual source)","type":"textarea","default":'{"name":"","headline":"","about":"","experience":"","skills":"","featured":""}'},
        ],
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


def _verified_certifications(profile: dict[str, Any]) -> set[str]:
    """Return certification-style codes explicitly present in profile evidence."""
    import re
    evidence = " ".join(
        str(profile.get(field, "") or "")
        for field in ("headline", "about", "experience", "skills", "featured")
    )
    return {token.upper() for token in re.findall(r"\b(?:DP|PL|AZ|AI)-\d{3}\b", evidence, re.I)}


def _sanitize_certification_claims(value: Any, allowed: set[str]) -> Any:
    """Remove unsupported certification codes from model output without inventing facts."""
    import re
    if isinstance(value, dict):
        return {k: _sanitize_certification_claims(v, allowed) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_certification_claims(v, allowed) for v in value]
    if not isinstance(value, str):
        return value

    def clean(match: re.Match[str]) -> str:
        token = match.group(0).upper()
        return match.group(0) if token in allowed else ""

    cleaned = re.sub(r"\b(?:DP|PL|AZ|AI)-\d{3}\b", clean, value, flags=re.I)
    return " ".join(cleaned.split()).strip()

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
            auto_jobs = []
            auto_diagnostics = {}
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

                    if name == "people" and not str(inputs.get("job_title", "")).strip() and not str(inputs.get("company", "")).strip():
                        # Keep the automatic association lightweight: one LinkedIn job
                        # search per location instead of three sequential navigations. The
                        # combined OR query still gives the matcher evidence across the
                        # target roles while avoiding dashboard request timeouts.
                        job_query = '"Power BI" OR "Data Analyst" OR "Business Intelligence"'
                        job_result = await run_read_on_page(
                            page,
                            "jobs",
                            query=job_query,
                            keywords=job_query,
                            location=location,
                            max_posted_hours=float(DEFAULT_JOB_PREFERENCES.posted_within_hours),
                        )
                        auto_diagnostics[f"{location}:target_roles"] = job_result.diagnostics or {}
                        auto_jobs.extend(job_result.data or [])

            # De-duplicate by the stable URL when available.
            seen = set()
            data = []
            for item in results:
                key = getattr(item, "href", "") or getattr(item, "url", "") or repr(item)
                if key in seen:
                    continue
                seen.add(key)
                data.append(item)
            if name == "people":
                job_title = str(inputs.get("job_title", "")).strip()
                company = str(inputs.get("company", "")).strip()
                job_url = str(inputs.get("job_url", "")).strip()
                if job_title or company:
                    job = {
                        "title": job_title,
                        "company": company,
                        "location": raw_locations,
                        "url": job_url,
                    }
                    targets = build_outreach_plan(data, job, limit=10)
                    enriched = []
                    for target in targets:
                        draft = hiring_contact_message(
                            target.name,
                            job_title,
                            company,
                            target.target_type,
                            target.relevance_reason,
                            ["Power BI", "SQL", "Data Analytics"],
                        )
                        row = target.to_dict()
                        row["associated_job_title"] = job_title
                        row["associated_company"] = company
                        row["associated_job_url"] = job_url
                        row["association_type"] = "manual_job_context"
                        row["suggested_message"] = draft.text
                        row["message_status"] = "drafted"
                        row["outreach_status"] = "not_sent"
                        enriched.append(row)
                    diagnostics["contact_matching"] = {
                        "mode": "manual",
                        "job_title": job_title,
                        "company": company,
                        "matched": len(enriched),
                        "note": "Scored from already-read person records; no LinkedIn action was performed.",
                    }
                    return {"skill":name,"mode":"read","data":enriched,"diagnostics":diagnostics}

                # Automatic association uses jobs collected while the persistent browser
                # session was open above. No closed Playwright page is reused here.
                job_seen = set()
                unique_jobs = []
                for job in auto_jobs:
                    key = getattr(job, "href", "") or getattr(job, "url", "") or repr(job)
                    if key in job_seen:
                        continue
                    job_seen.add(key)
                    unique_jobs.append(job)

                associations = associate_people_with_jobs(data, unique_jobs, limit_per_person=1)
                enriched = []
                for item in associations:
                    person = item["person"]
                    selected = item["associated_jobs"][0] if item["associated_jobs"] else None
                    if selected:
                        job = selected["job"]
                        job_data = (
                            job.to_dict()
                            if hasattr(job, "to_dict")
                            else {
                                key: getattr(job, key, "")
                                for key in (
                                    "title", "company", "location", "url", "href", "posted"
                                )
                            }
                            if not isinstance(job, dict)
                            else job
                        )
                        associated_title = str(job_data.get("title", "") or "")
                        associated_company = str(job_data.get("company", "") or "")
                        associated_url = str(job_data.get("url") or job_data.get("href") or "")
                        association_type = selected["association"]
                        association_reason = "; ".join(selected["signals"])
                        target = build_outreach_plan(
                            [person],
                            {
                                "title": associated_title,
                                "company": associated_company,
                                "location": str(job_data.get("location", "") or ""),
                                "url": associated_url,
                            },
                            limit=1,
                        )
                        if target:
                            target = target[0]
                            draft = hiring_contact_message(
                                target.name,
                                associated_title,
                                associated_company,
                                target.target_type,
                                target.relevance_reason,
                                ["Power BI", "SQL", "Data Analytics"],
                            )
                            row = target.to_dict()
                        else:
                            row = {
                                "name": str(getattr(person, "name", "") or ""),
                                "profile_url": str(getattr(person, "href", "") or ""),
                                "title": str(getattr(person, "headline", "") or ""),
                                "company": str(getattr(person, "company", "") or ""),
                                "target_type": "other",
                                "relevance_score": 0,
                                "matching_signals": [],
                            }
                            draft = hiring_contact_message(
                                row["name"],
                                associated_title,
                                associated_company,
                                row["target_type"],
                                association_reason,
                                ["Power BI", "SQL", "Data Analytics"],
                            )
                        row["associated_job_title"] = associated_title
                        row["associated_company"] = associated_company
                        row["associated_job_url"] = associated_url
                        row["associated_job_location"] = str(job_data.get("location", "") or "")
                        row["associated_job_posted"] = str(job_data.get("posted", "") or "")
                        row["association_type"] = association_type
                        row["association_score"] = selected["score"]
                        row["association_reason"] = association_reason
                        row["suggested_message"] = draft.text
                        row["message_status"] = "drafted"
                        row["outreach_status"] = "not_sent"
                        enriched.append(row)

                diagnostics["contact_matching"] = {
                    "mode": "automatic",
                    "jobs_considered": len(unique_jobs),
                    "matched": len(enriched),
                    "freshness_hours": float(DEFAULT_JOB_PREFERENCES.posted_within_hours),
                    "note": "Associated from already-read LinkedIn people and fresh target-role jobs. No LinkedIn action was performed.",
                    "job_searches": auto_diagnostics,
                }
                return {"skill":name,"mode":"read","data":enriched,"diagnostics":diagnostics}
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
    if name == "profile_optimizer":
        source = str(inputs.get("source", "live")).strip().lower()
        if source == "live":
            live = await run_read("profile")
            profile_data = live.data.to_dict() if hasattr(live.data, "to_dict") else dict(live.data or {})
            # Never expose LinkedIn pronouns as a professional headline. LinkedIn's
            # top-card DOM changes frequently and can place pronouns beside the name.
            headline = " ".join(str(profile_data.get("headline", "")).split())
            if headline.lower() in {"he/him", "she/her", "they/them", "he him", "she her", "they them"}:
                profile_data["headline"] = ""
        else:
            profile_data = _json_value(str(inputs.get("profile", "{}")), {}) or {}
        baseline = profile_audit(profile_data)
        verified_certifications = sorted(_verified_certifications(profile_data))
        prompt = {
            "profile": profile_data,
            "audit": baseline,
            "verified_evidence": {
                "sections_present": {
                    key: bool(profile_data.get(key))
                    for key in ("headline", "about", "experience", "skills", "featured")
                },
                "certifications_explicitly_present": verified_certifications,
            },
            "evidence_rules": [
                "Treat the supplied section audit as authoritative for whether a section is present.",
                "Do not say Experience, Skills, or Featured are missing when the supplied profile field contains text.",
                "Do not infer certifications from target roles, skills, technologies, or likely career paths.",
                "Only mention a certification code if it appears explicitly in the supplied profile evidence.",
            ],
            "target_roles": [
                "Power BI Developer",
                "Business Intelligence",
                "Data Analyst",
                "Reporting / MIS",
                "BI Lead / Consultant",
            ],
            "target_market": "Delhi NCR / Gurgaon / Noida / Remote India",
        }
        llm_error = None
        try:
            ai = chat_json(
                system=(
                    "You are a senior LinkedIn profile strategist and ATS-aware recruiter. "
                    "Improve a professional LinkedIn profile for the stated target roles. "
                    "Use only evidence present in the supplied profile; never invent employers, "
                    "job titles, certifications, metrics, technologies, or achievements. "
                    "Return JSON with keys: overall_assessment, strengths, missing_information, "
                    "headline_options, about_draft, experience_improvements, skills_to_highlight, "
                    "featured_recommendations, keyword_strategy, next_actions. "
                    "headline_options must be an array of 3 strings. experience_improvements "
                    "and next_actions must be arrays. Clearly mark recommendations that require "
                    "the user to supply missing facts."
                ),
                user=json.dumps(prompt, ensure_ascii=False),
                temperature=0.2,
                max_tokens=2600,
            )
            
        except LLMError as exc:
            ai = {
                "overall_assessment": "Deterministic profile audit completed; AI recommendations were unavailable.",
                "strengths": [],
                "missing_information": [],
                "headline_options": [],
                "about_draft": "",
                "experience_improvements": [],
                "skills_to_highlight": [],
                "featured_recommendations": [],
                "keyword_strategy": [],
                "next_actions": [],
            }
            llm_error = str(exc)
        ai = _sanitize_certification_claims(ai, set(verified_certifications))
        headline_options = (
            [str(item) for item in ai.get("headline_options", []) if str(item).strip()]
            if isinstance(ai.get("headline_options"), list)
            else []
        )
        # Validate every headline option independently. A single safe option must
        # not hide unsupported claims in another option shown to the user.
        headline_grounding = [
            validate_profile_drafts(profile_data, {"headline": option})["fields"]["headline"]
            for option in headline_options
        ]
        grounding = validate_profile_drafts(
            profile_data,
            {
                "headline": headline_options[0] if headline_options else "",
                "about": ai.get("about_draft", ""),
                "experience": "\n".join(
                    str(item) for item in ai.get("experience_improvements", [])
                    if str(item).strip()
                ) if isinstance(ai.get("experience_improvements"), list) else "",
            },
        )
        grounding["headline_options"] = [
            {
                "index": index + 1,
                "text": option,
                "status": option_result.get("status", "not_provided"),
                "issues": option_result.get("issues", []),
            }
            for index, (option, option_result) in enumerate(zip(headline_options, headline_grounding))
        ]
        headline_blockers = [
            {
                "field": f"headline_option_{item['index']}",
                **issue,
            }
            for item in grounding["headline_options"]
            for issue in item.get("issues", [])
        ]
        if headline_blockers:
            grounding["publishable"] = False
            grounding["blocking_issues"] = list(grounding.get("blocking_issues", [])) + headline_blockers
        sections = baseline.get("sections", {})
        readable = {
            "title": "Profile Optimizer",
            "status": "Analysis completed",
            "safety": "No LinkedIn profile changes were made.",
            "profile": {
                "name": profile_data.get("name", ""),
                "headline": profile_data.get("headline", ""),
                "location": profile_data.get("location", ""),
            },
            "section_audit": {
                "Headline": "Found" if sections.get("headline") else "Not detected",
                "About": "Found" if sections.get("about") else "Not detected",
                "Experience": "Found" if sections.get("experience") else "Not detected",
                "Skills": "Found" if sections.get("skills") else "Not detected",
                "Featured": "Found" if sections.get("featured") else "Not detected",
            },
            "assessment": ai.get("overall_assessment", ""),
            "headline_recommendations": ai.get("headline_options", []),
            "about_recommendation": ai.get("about_draft", ""),
            "experience_recommendations": ai.get("experience_improvements", []),
            "skills_to_highlight": ai.get("skills_to_highlight", []),
            "featured_recommendations": ai.get("featured_recommendations", []),
            "strengths": ai.get("strengths", []),
            "missing_information": ai.get("missing_information", []),
            "next_actions": ai.get("next_actions", []),
            "ai_error": llm_error or "",
            "source_grounding": grounding,
        }
        return {
            "skill": name,
            "mode": "local",
            "source": source,
            "provider": provider_status(),
            "profile": profile_data,
            "baseline_audit": baseline,
            "ai_optimization": ai,
            "readable_result": readable,
            "ai_error": llm_error or "",
            "source_grounding": grounding,
            "message": (
                "AI generated recommendations only. No LinkedIn profile changes were made."
                if not llm_error
                else "Read-only profile audit completed. AI recommendations were unavailable; no LinkedIn profile changes were made."
            ),
        }
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
