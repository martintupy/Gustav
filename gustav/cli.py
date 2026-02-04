import click
from pydantic import ValidationError

from gustav.commands.cache import cache
from gustav.commands.commit import commit
from gustav.commands.init import init
from gustav.commands.pull_request import pull_request
from gustav.commands.report import report
from gustav.commands.status import status
from gustav.logging import setup_logging
from gustav.settings import load_settings, settings_exist

COMMANDS_REQUIRING_SETTINGS = {"commit", "report", "pr"}


@click.group()
@click.pass_context
def main(ctx: click.Context):
    """AI-powered Git/GitHub tools"""
    setup_logging()
    ctx.ensure_object(dict)

    invoked = ctx.invoked_subcommand
    if invoked in COMMANDS_REQUIRING_SETTINGS:
        if not settings_exist():
            raise click.ClickException("Settings not found. Run 'gus init' first.")

        try:
            ctx.obj = load_settings()
        except FileNotFoundError as e:
            raise click.ClickException(str(e)) from None
        except ValidationError as e:
            raise click.ClickException(f"Invalid settings: {e}") from None
        except ValueError as e:
            raise click.ClickException(str(e)) from None


main.add_command(init)
main.add_command(status)
main.add_command(cache)
main.add_command(commit)
main.add_command(report)
main.add_command(pull_request, name="pr")


if __name__ == "__main__":
    main()
