from app.cli import app


def test_smoke_command_registered():
    names = {command.name for command in app.registered_commands}
    assert "smoke-test" in names
