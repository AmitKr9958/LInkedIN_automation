import asyncio
import typer

from .config import settings
from .skill_registry import list_skills
from .workflows import login_check

app = typer.Typer(help="Local LinkedIn workflow assistant")

@app.command()
def status():
    result = asyncio.run(login_check())
    typer.echo(f"{result.action}: {result.status} - {result.details}")
    typer.echo(f"dry_run={settings.dry_run}, headless={settings.headless}")

@app.command()
def login():
    typer.echo("A visible browser will open. Log in manually; credentials are never stored by this application.")
    result = asyncio.run(login_check())
    typer.echo(f"{result.status}: {result.details}")

@app.command("skills")
def skills():
    for skill in list_skills():
        mode = "mutating" if skill.mutating else "read/draft"
        typer.echo(f"- {skill.name}: {skill.description} [{mode}]")

if __name__ == "__main__":
    app()
