# Operating model

The agent is designed as a local productivity assistant, not an unattended LinkedIn bot.

## Safe flow

1. Open the user's local persistent browser session.
2. The user logs into LinkedIn manually when needed.
3. Read-only planning/data preparation is separated from actions.
4. AI may draft job-search notes, recruiter messages, follow-ups and posts.
5. Actions remain behind the approval layer.
6. Activity is logged locally.

LinkedIn currently states that third-party software that scrapes or automates activity on its website is not allowed, and its User Agreement specifically prohibits unauthorized automated methods for activities such as adding contacts, messaging, posting, liking and sharing. The project therefore does not attempt to evade LinkedIn controls or automate those actions at scale.

For a production integration, prefer an officially supported LinkedIn API/product flow where the required capability is available.
