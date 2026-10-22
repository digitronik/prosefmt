"""Command-line interface — the user-facing shell of Reword.

Usage examples:
    reword fix "some text with erors"      # Fix grammar (stdout)
    reword professional --clipboard        # Read clipboard, rewrite, write back
    reword rephrase --system               # Read selection, rewrite, paste back in-place
    echo "text" | reword summarize         # Pipe mode
    reword list                            # Show available modes
    reword undo                            # Undo last rewrite
    reword config init                     # Create default config file
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from reword import __version__
from reword.config import Config


class RewordCLI(click.Group):
    """Custom Click group that treats unknown subcommands as mode names."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv

        config: Config = ctx.ensure_object(dict).get("config") or Config.load()
        if cmd_name in config.modes:
            return _make_mode_command(cmd_name)

        return None

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if args:
                return args[0], args[0], args[1:]
            raise

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        super().format_help(ctx, formatter)
        config = Config.load()
        formatter.write("\n")
        formatter.write_heading("Available modes")
        rows = [
            (name, m.prompt[:60] + "…" if len(m.prompt) > 60 else m.prompt)
            for name, m in config.modes.items()
        ]
        formatter.write_dl(rows)
        formatter.write("\n")


def _make_mode_command(mode_name: str) -> click.Command:
    """Dynamically create a Click command for a rewrite mode."""

    @click.command(name=mode_name, hidden=True)
    @click.argument("text", required=False)
    @click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard.")
    @click.option(
        "--system",
        "-s",
        is_flag=True,
        help="System-wide: read selection, rewrite, paste back in-place.",
    )
    @click.option("--provider", "-p", default=None, help="Override AI provider for this run.")
    @click.option("--model", "-m", default=None, help="Override model for this run.")
    @click.option("--notify", "-n", is_flag=True, help="Show desktop notifications.")
    @click.pass_context
    def mode_cmd(
        ctx: click.Context,
        text: str | None,
        clipboard: bool,
        system: bool,
        provider: str | None,
        model: str | None,
        notify: bool,
    ) -> None:
        _run_rewrite(ctx, mode_name, text, clipboard, system, provider, model, notify)

    return mode_cmd


def _run_rewrite(
    ctx: click.Context,
    mode_name: str,
    text: str | None,
    clipboard: bool,
    system: bool,
    provider_name: str | None,
    model_override: str | None,
    show_notify: bool,
) -> None:
    from reword.clipboard import clipboard_write, paste_to_active_window
    from reword.core import RewordError, rewrite, save_undo
    from reword.notify import notify
    from reword.providers import ProviderError, get_provider

    config: Config = ctx.obj.get("config") or Config.load()
    mode = config.modes.get(mode_name)
    if mode is None:
        click.echo(f"Error: unknown mode '{mode_name}'", err=True)
        raise SystemExit(1)

    pname = provider_name or config.default_provider
    pconfig = config.providers.get(pname)
    if pconfig is None:
        click.echo(f"Error: unknown provider '{pname}'", err=True)
        raise SystemExit(1)

    if model_override:
        pconfig.model = model_override

    input_text = _resolve_input(text, clipboard, system)
    if not input_text:
        click.echo(
            "Error: no text provided — pass as argument, pipe via stdin, "
            "or use --clipboard / --system",
            err=True,
        )
        raise SystemExit(1)

    if show_notify:
        notify("Reword", f"✦ {mode.label or mode_name}…", timeout_ms=30000)

    try:
        prov = get_provider(pname, pconfig)
        result = rewrite(input_text, mode, provider=prov, config=config)
    except (ProviderError, RewordError) as exc:
        if show_notify:
            notify("Reword", f"✗ {exc}", urgency="critical")
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from None

    save_undo(input_text, config.undo_file)

    if system:
        import time

        clipboard_write(result)
        time.sleep(0.1)
        paste_to_active_window()
        if show_notify:
            notify("Reword", f"✓ {mode.label or mode_name}")
    elif clipboard:
        clipboard_write(result)
        if show_notify:
            notify("Reword", f"✓ {mode.label or mode_name}")
        click.echo(result)
    else:
        click.echo(result)


def _resolve_input(text: str | None, clipboard: bool, system: bool) -> str:
    """Figure out where the input text comes from."""
    if text:
        return text

    if clipboard or system:
        from reword.clipboard import clipboard_read

        return clipboard_read()

    if not sys.stdin.isatty():
        return sys.stdin.read()

    return ""


@click.group(cls=RewordCLI, invoke_without_command=True)
@click.version_option(__version__, prog_name="reword")
@click.option(
    "--config-path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to config file.",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None) -> None:
    """Reword — AI-powered text rewriter for your terminal.

    \b
    Usage:
      reword fix "text with erors"          Fix grammar (print to stdout)
      reword professional --clipboard       Read clipboard, rewrite, write back
      reword rephrase --system              System-wide: rewrite selected text in-place
      echo "text" | reword summarize        Pipe mode
      reword list                           Show available modes
      reword undo                           Restore original text
      reword config init                    Create default config file
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(config_path)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("list")
@click.pass_context
def list_modes(ctx: click.Context) -> None:
    """List all available rewrite modes."""
    config: Config = ctx.obj["config"]
    max_name = max(len(n) for n in config.modes)

    for name, mode in config.modes.items():
        label = mode.label or name
        click.echo(f"  {name:<{max_name}}  {label}: {mode.prompt}")


@cli.command("undo")
@click.option("--clipboard", "-c", is_flag=True, help="Write undo text to clipboard.")
@click.option("--system", "-s", is_flag=True, help="Paste undo text back to active window.")
@click.pass_context
def undo(ctx: click.Context, clipboard: bool, system: bool) -> None:
    """Undo the last rewrite — restore the original text."""
    from reword.core import load_undo
    from reword.notify import notify

    config: Config = ctx.obj["config"]
    original = load_undo(config.undo_file)

    if original is None:
        click.echo("Nothing to undo.", err=True)
        raise SystemExit(1)

    if system:
        import time

        from reword.clipboard import clipboard_write, paste_to_active_window

        clipboard_write(original)
        time.sleep(0.1)
        paste_to_active_window()
        notify("Reword", "↩ Reverted to original")
    elif clipboard:
        from reword.clipboard import clipboard_write

        clipboard_write(original)
        notify("Reword", "↩ Reverted to original (clipboard)")
        click.echo(original)
    else:
        click.echo(original)


@cli.group("config")
def config_group() -> None:
    """Manage Reword configuration."""


@config_group.command("init")
def config_init() -> None:
    """Create a default configuration file and check system dependencies."""
    from reword.clipboard import check_clipboard_tools, install_hints
    from reword.config import init_config

    path = init_config()
    click.echo(f"✓ Config file ready: {path}")
    click.echo(f"  Edit it to set your provider, model, and custom modes.\n")

    missing = check_clipboard_tools()
    if missing:
        click.echo(
            "⚠  Missing clipboard tools (needed for --clipboard / --system):",
            err=False,
        )
        for tool in missing:
            click.echo(f"   • {tool}")
        hints = install_hints()
        if hints:
            click.echo("\n  Install with one of these commands:")
            for line in hints:
                click.echo(line)
        click.echo(
            "\n  (Pipe mode — echo 'text' | reword fix — works without these tools.)"
        )
    else:
        click.echo("✓ Clipboard tools installed")


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show the active configuration."""
    config: Config = ctx.obj["config"]
    click.echo(f"Provider:  {config.default_provider}")

    pconfig = config.providers.get(config.default_provider)
    if pconfig:
        click.echo(f"  URL:     {pconfig.url}")
        click.echo(f"  Model:   {pconfig.model}")
        click.echo(f"  API Key: {'***' if pconfig.api_key else '(not set)'}")

    click.echo(f"\nModes ({len(config.modes)}):")
    for name in config.modes:
        click.echo(f"  - {name}")


@cli.command("check")
@click.pass_context
def check(ctx: click.Context) -> None:
    """Verify clipboard tools are installed and the AI provider is reachable."""
    from reword.clipboard import check_clipboard_tools, install_hints
    from reword.providers import get_provider

    config: Config = ctx.obj["config"]
    ok = True

    # --- Clipboard tools ---
    missing = check_clipboard_tools()
    if missing:
        click.echo(f"✗ Missing clipboard tools: {', '.join(missing)}")
        hints = install_hints()
        if hints:
            click.echo("  Install with one of these commands:")
            for line in hints:
                click.echo(line)
        ok = False
    else:
        click.echo("✓ Clipboard tools installed")

    # --- AI provider ---
    pname = config.default_provider
    pconfig = config.providers.get(pname)
    if pconfig:
        prov = get_provider(pname, pconfig)
        if prov.check_health():
            click.echo(f"✓ Provider '{pname}' is reachable  (model: {pconfig.model})")
        else:
            if pname == "ollama":
                click.echo(
                    f"✗ Provider '{pname}' is not reachable\n"
                    "  Start Ollama:   ollama serve\n"
                    f"  Pull a model:   ollama pull {pconfig.model}"
                )
            elif pname in ("openai", "anthropic", "openai-compat"):
                env_var = {
                    "openai": "OPENAI_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "openai-compat": "REWORD_COMPAT_API_KEY",
                }.get(pname, "API key env var")
                click.echo(
                    f"✗ Provider '{pname}' is not reachable\n"
                    f"  Make sure {env_var} is set in your environment."
                )
            else:
                click.echo(f"✗ Provider '{pname}' is not reachable")
            ok = False
    else:
        click.echo(f"✗ Provider '{pname}' not configured — run: reword config init")
        ok = False

    raise SystemExit(0 if ok else 1)
