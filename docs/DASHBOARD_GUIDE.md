# LinkedIn Automation Control Center

## The simple mental model

There are three pieces:

1. **LinkedIn** — your real LinkedIn account and browser session.
2. **Agent** — the Python/Playwright program that reads LinkedIn and stores local results.
3. **Control Center** — a small local web page at `http://127.0.0.1:8765` that lets you trigger read-only skills and view results.

The Control Center is not a cloud website. It works only while the local dashboard server is running on your Windows PC.

## Start it

From the repository folder:

```powershell
cd "E:\LinkedIn Automation"
.\.venv\Scripts\Activate.ps1
python -m app dashboard
```

Then open:

```
http://127.0.0.1:8765
```

On Windows you can also double-click:

```
scripts\start-dashboard.cmd
```

That launcher starts the dashboard and opens the browser automatically.

## What to click

### Quick actions

These are read-only skills:

- **Find Power BI jobs** — searches the configured LinkedIn job workflow.
- **Read my profile** — reads your LinkedIn profile.
- **Find Power BI posts** — reads matching posts.
- **Find recruiters** — reads people/search results.
- **Find companies** — reads company results.
- **Read saved items** — reads saved LinkedIn items.
- **Read notifications** — reads notifications.

The result appears in the **Skill result** panel.

### Run Agent Now

This is the complete scheduled discovery workflow. It performs the same governed read-only discovery cycle used by the Windows scheduler.

It does not automatically send messages, send connection requests, like/comment, publish, or submit applications.

### Pending approvals

This is where governed account-changing requests can be reviewed. Approval is separate from discovery.

## Important

If the browser says it cannot connect to `127.0.0.1:8765`, the dashboard server is not running (or another program has taken the port). The URL itself does not start the application.

The dashboard binds to localhost only, so it is intended for use on the same Windows PC.

## Recommended workflow for you

```
Start Dashboard
      ↓
Find Power BI jobs
      ↓
Review jobs
      ↓
Run Agent Now when you want the full discovery cycle
      ↓
Review drafts / approvals
      ↓
You decide what to apply for or send
```

The scheduled Windows agent can continue running separately every two hours. The dashboard is simply your manual control and visibility layer.
