"""Read-only diagnostics for LinkedIn's live About editor UI."""
from __future__ import annotations
from typing import Any

async def debug_about_editor(page) -> dict[str, Any]:
    result={"url":page.url,"title":await page.title(),"authenticated":False,
            "about_headings":[],"edit_candidates":[],"selected_candidate":None,
            "dialog":{"opened":False,"role":None,"text":"","fields":[]},"actions":[],"errors":[]}
    try:
        from .linkedin_reader import current_session_state
        state=await current_session_state(page); result["authenticated"]=bool(state.get("authenticated")); result["session"]=state
    except Exception as exc: result["errors"].append(f"session:{type(exc).__name__}:{exc}")
    try:
        result["about_headings"]=await page.locator("main h1, main h2, main h3, main h4, main [role='heading']").evaluate_all(
            """els=>els.map((el,i)=>({index:i,tag:el.tagName,text:(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,300)})).filter(x=>/\babout\b/i.test(x.text)).slice(0,20)"""
        )
    except Exception as exc: result["errors"].append(f"headings:{type(exc).__name__}:{exc}")
    try:
        result["edit_candidates"]=await page.locator("main button, main a, main [role='button'], main [data-control-name]").evaluate_all(
            """els=>els.map((el,i)=>{const n=v=>(v||'').replace(/\s+/g,' ').trim();const label=n(el.getAttribute('aria-label')),title=n(el.getAttribute('title')),text=n(el.innerText||el.textContent),hay=[label,title,text].join(' ');if(!/\bedit\b/i.test(hay))return null;let s=el,aboutScope=false,scopeText='';for(let d=0;d<8&&s;d++,s=s.parentElement){const t=n(s.innerText||s.textContent);if(/\babout\b/i.test(t)&&t.length<12000){aboutScope=true;scopeText=t.slice(0,500);break}}return {index:i,tag:el.tagName,label,title,text:text.slice(0,200),aboutScope,scopeText}}).filter(Boolean).slice(0,50)"""
        )
    except Exception as exc: result["errors"].append(f"candidates:{type(exc).__name__}:{exc}")
    selected=next((x for x in result["edit_candidates"] if x.get("aboutScope")),None); result["selected_candidate"]=selected
    if selected is None:
        result["actions"].append("no_about_scoped_edit_control_found"); return result
    try:
        loc=page.locator("main button, main a, main [role='button'], main [data-control-name]").nth(int(selected["index"]))
        await loc.scroll_into_view_if_needed(timeout=5000); await loc.click(timeout=5000); result["actions"].append("clicked_about_scoped_edit_control")
    except Exception as exc:
        result["errors"].append(f"click:{type(exc).__name__}:{exc}"); return result
    try:
        for _ in range(10):
            await page.wait_for_timeout(300)
            dialogs=page.locator("[role='dialog']")
            if await dialogs.count():
                d=dialogs.last
                if await d.is_visible():
                    fields=await d.locator("textarea,input,[contenteditable='true']").evaluate_all(
                        """els=>els.map((el,i)=>({index:i,tag:el.tagName,name:el.getAttribute('name')||'',ariaLabel:el.getAttribute('aria-label')||'',placeholder:el.getAttribute('placeholder')||'',role:el.getAttribute('role')||'',valueLength:typeof el.value==='string'?el.value.length:(el.innerText||el.textContent||'').length}))"""
                    )
                    result["dialog"]={"opened":True,"role":await d.get_attribute("role"),"text":" ".join((await d.inner_text()).split())[:4000],"fields":fields[:20]}; break
            modals=page.locator("div[aria-modal='true'], [data-test-modal]")
            if await modals.count():
                m=modals.last
                if await m.is_visible():
                    result["dialog"]={"opened":True,"role":await m.get_attribute("role"),"text":" ".join((await m.inner_text()).split())[:4000],
                        "fields":await m.locator("textarea,input,[contenteditable='true']").evaluate_all(
                            """els=>els.map((el,i)=>({index:i,tag:el.tagName,name:el.getAttribute('name')||'',ariaLabel:el.getAttribute('aria-label')||'',placeholder:el.getAttribute('placeholder')||'',role:el.getAttribute('role')||'',valueLength:typeof el.value==='string'?el.value.length:(el.innerText||el.textContent||'').length}))"""
                        )}
                    break
    except Exception as exc: result["errors"].append(f"dialog:{type(exc).__name__}:{exc}")
    finally:
        try: await page.keyboard.press("Escape"); result["actions"].append("closed_with_escape_without_saving")
        except Exception as exc: result["errors"].append(f"close:{type(exc).__name__}:{exc}")
    return result
