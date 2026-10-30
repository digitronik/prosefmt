"""Command-line interface — the user-facing shell of prosefmt.

Usage examples:
    prosefmt "some text with erors"              Fix grammar (default mode)
    prosefmt -m professional -s -n               Rewrite highlighted text
    echo "text" | prosefmt -m casual             Pipe + mode
    prosefmt menu --system --notify              Open mode picker
    prosefmt list                                Show available modes
    prosefmt undo                                Undo last rewrite
    prosefmt config init                         Create default config file
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from prosefmt import __version__
from prosefmt.config import Config

if TYPE_CHECKING:
    from prosefmt.config import ModeConfig


# ---------------------------------------------------------------------------
# Custom Click Group — routes unknown subcommands to hidden 'run' command
# ---------------------------------------------------------------------------


class ProsefmtCLI(click.Group):
    """Dispatch to the hidden ``run`` command when the first arg is not
    a recognised subcommand.

    This lets users type ``prosefmt "text"`` or ``prosefmt -m fix "text"``
    instead of ``prosefmt run -m fix "text"``.

    ``ignore_unknown_options`` prevents the group-level parser from
    rejecting flags that belong to the ``run`` command (``-m``, ``-s``,
    ``-n``, ``-p``, ``--model``).
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.ignore_unknown_options = True

    # -- Arg routing -------------------------------------------------------

    _GROUP_FLAGS = frozenset({"--help", "-h", "--version", "--config-path"})

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args:
            args = ["run"]
        elif args[0] not in self.commands and args[0] not in self._GROUP_FLAGS:
            args = ["run", *args]
        return super().parse_args(ctx, args)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            cmd = super().get_command(ctx, "run")
            if cmd is not None:
                return "run", cmd, list(args)
            raise

    # -- Custom help output ------------------------------------------------

    def format_usage(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        formatter.write("Usage: prosefmt [OPTIONS] [TEXT]\n")
        formatter.write("       prosefmt COMMAND [ARGS]...\n")

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        self.format_usage(ctx, formatter)
        formatter.write_paragraph()
        formatter.write(
            "AI-powered text formatting for your terminal.\n"
            "Highlight text, press a hotkey, get polished prose back.\n"
        )

        # Rewrite options (pulled from the hidden 'run' command)
        run_cmd = self.get_command(ctx, "run")
        if run_cmd:
            with formatter.section("Rewrite options"):
                records: list[tuple[str, str]] = [
                    ("TEXT", "Text to rewrite (or pipe via stdin)"),
                ]
                for param in run_cmd.params:
                    if isinstance(param, click.Option):
                        rec = param.get_help_record(ctx)
                        if rec:
                            records.append(rec)
                formatter.write_dl(records)

        # Global options
        with formatter.section("Global options"):
            opts = []
            for param in self.params:
                rec = param.get_help_record(ctx)
                if rec:
                    opts.append(rec)
            formatter.write_dl(opts)

        # Subcommands
        cmds = []
        for name in self.list_commands(ctx):
            cmd = self.get_command(ctx, name)
            if cmd is None or cmd.hidden:
                continue
            cmds.append((name, cmd.get_short_help_str(limit=50)))
        if cmds:
            with formatter.section("Commands"):
                formatter.write_dl(cmds)

        # Examples
        formatter.write("\n")
        with formatter.section("Examples"):
            formatter.write(
                '  prosefmt "text with erors"       '
                " Fix grammar (default mode)\n"
                "  prosefmt -m professional -s -n   "
                " Rewrite highlighted text\n"
                "  echo text | prosefmt -m casual   "
                " Pipe + mode\n"
                "  prosefmt menu -s -n              "
                " Open mode picker\n"
                "  prosefmt list                    "
                " Show all modes\n"
            )

        # Available modes
        try:
            config = (ctx.obj or {}).get("config") or Config.load()
            if config and config.modes:
                with formatter.section("Available modes"):
                    rows = []
                    for name, m in config.modes.items():
                        short = m.prompt[:55] + "…" if len(m.prompt) > 55 else m.prompt
                        rows.append((name, short))
                    formatter.write_dl(rows)
        except Exception:
            pass

        formatter.write("\n")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_input(text: str | None, clipboard: bool, system: bool) -> str:
    """Figure out where the input text comes from.

    ``--system``    reads the **primary** selection (highlighted text).
    ``--clipboard`` reads the **clipboard** selection (Ctrl+C buffer).
    On macOS / Windows both resolve to the single system clipboard.
    """
    if text:
        return text

    if system:
        from prosefmt.clipboard import clipboard_read

        return clipboard_read(selection="primary")

    if clipboard:
        from prosefmt.clipboard import clipboard_read

        return clipboard_read(selection="clipboard")

    if not sys.stdin.isatty():
        return sys.stdin.read()

    return ""


def _no_input_error(system: bool, show_notify: bool) -> None:
    """Print / notify an error when no input text is available, then exit."""
    from prosefmt.notify import notify

    msg = (
        "No text selected — highlight text before pressing the hotkey"
        if system
        else "No text provided — pass as argument, pipe via stdin, or use --clipboard / --system"
    )
    if show_notify:
        notify("prosefmt", f"✗ {msg}", urgency="critical")
    click.echo(f"Error: {msg}", err=True)
    raise SystemExit(1)


def _run_rewrite(
    ctx: click.Context,
    mode_name: str,
    input_text: str,
    *,
    system: bool = False,
    clipboard: bool = False,
    provider_name: str | None = None,
    model_override: str | None = None,
    show_notify: bool = False,
    mode_override: ModeConfig | None = None,
) -> None:
    """Rewrite *input_text* and deliver the result.

    The caller is responsible for resolving input (via ``_resolve_input``).
    Output routing uses the mode's ``default_output`` field, overridden by
    ``system`` / ``clipboard`` flags when appropriate.
    """
    from dataclasses import replace

    from prosefmt.core import ProsefmtError, rewrite, save_undo
    from prosefmt.notify import notify
    from prosefmt.providers import ProviderError, get_provider

    config: Config = ctx.obj.get("config") or Config.load()

    # Resolve mode
    mode = mode_override or config.modes.get(mode_name)
    if mode is None:
        click.echo(f"Error: unknown mode '{mode_name}'", err=True)
        raise SystemExit(1)

    # Provider: CLI flag > mode config > global default
    pname = provider_name or mode.provider or config.default_provider
    pconfig = config.providers.get(pname)
    if pconfig is None:
        click.echo(f"Error: unknown provider '{pname}'", err=True)
        raise SystemExit(1)

    # Model: CLI flag > mode config > provider default
    effective_model = model_override or mode.model
    if effective_model:
        pconfig = replace(pconfig, model=effective_model)

    if show_notify:
        notify(
            "prosefmt",
            f"✦ {mode.label or mode_name}…",
            timeout_ms=30000,
        )

    try:
        prov = get_provider(pname, pconfig)
        result = rewrite(input_text, mode, provider=prov, config=config)
    except (ProviderError, ProsefmtError) as exc:
        if show_notify:
            notify("prosefmt", f"✗ {exc}", urgency="critical")
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from None

    save_undo(input_text, config.undo_file)

    # ------------------------------------------------------------------
    # Output routing
    #
    # Priority: explicit CLI flags  >  mode.default_output  >  stdout
    #
    # When --system is used the *input* always comes from primary selection.
    # The *output* destination is decided by the mode's default_output
    # ("replace" means paste back, "popup" / "clipboard" will be handled
    # once those modules land in Phase 2).
    # ------------------------------------------------------------------
    if system:
        output = mode.default_output  # "replace" | "popup" | "clipboard"
    elif clipboard:
        output = "clipboard"
    else:
        output = "stdout"

    if output == "replace":
        from prosefmt.clipboard import (
            clipboard_write,
            paste_to_active_window,
            preserve_clipboard,
        )

        with preserve_clipboard():
            clipboard_write(result)
            paste_to_active_window()
        if show_notify:
            notify("prosefmt", f"✓ {mode.label or mode_name}")

    elif output == "popup":
        # Phase 2 — popup.py not yet implemented; fall back to stdout
        click.echo(result)
        if show_notify:
            notify("prosefmt", f"✓ {mode.label or mode_name}")

    elif output == "clipboard":
        from prosefmt.clipboard import clipboard_write

        clipboard_write(result)
        if show_notify:
            notify("prosefmt", f"✓ {mode.label or mode_name}")
        click.echo(result)

    else:
        # stdout (terminal use)
        click.echo(result)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.group(cls=ProsefmtCLI, invoke_without_command=True)
@click.version_option(__version__, prog_name="prosefmt")
@click.option(
    "--config-path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to config file.",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None) -> None:
    """prosefmt — AI-powered text formatting for your terminal."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(config_path)


# ---------------------------------------------------------------------------
# Default command — rewrite text
# ---------------------------------------------------------------------------


@cli.command("run", hidden=True)
@click.argument("text", required=False)
@click.option(
    "--mode",
    "-m",
    default=None,
    help="Rewrite mode (default: from config, usually 'fix').",
)
@click.option(
    "--system",
    "-s",
    is_flag=True,
    help="Read highlighted text, paste result back.",
)
@click.option(
    "--clipboard",
    "-c",
    is_flag=True,
    help="Read from and write to clipboard.",
)
@click.option(
    "--notify",
    "-n",
    is_flag=True,
    help="Show desktop notification.",
)
@click.option(
    "--provider",
    "-p",
    default=None,
    help="Override AI provider for this run.",
)
@click.option("--model", default=None, help="Override AI model for this run.")
@click.pass_context
def run(
    ctx: click.Context,
    text: str | None,
    mode: str | None,
    system: bool,
    clipboard: bool,
    notify: bool,
    provider: str | None,
    model: str | None,
) -> None:
    """Rewrite text using an AI mode (default command)."""
    config: Config = ctx.obj.get("config") or Config.load()
    mode_name = mode or config.default_mode

    input_text = _resolve_input(text, clipboard, system)
    if not input_text:
        # Truly no input and nothing requested → show help
        if not mode and not system and not clipboard:
            help_ctx = ctx.parent if ctx.parent else ctx
            click.echo(help_ctx.get_help())
            return
        _no_input_error(system, notify)

    _run_rewrite(
        ctx,
        mode_name,
        input_text,
        system=system,
        clipboard=clipboard,
        provider_name=provider,
        model_override=model,
        show_notify=notify,
    )


# ---------------------------------------------------------------------------
# menu — interactive mode picker
# ---------------------------------------------------------------------------


@cli.command("menu")
@click.argument("text", required=False)
@click.option(
    "--system",
    "-s",
    is_flag=True,
    help="Read highlighted text, paste result back.",
)
@click.option(
    "--clipboard",
    "-c",
    is_flag=True,
    help="Read from and write to clipboard.",
)
@click.option(
    "--notify",
    "-n",
    is_flag=True,
    help="Show desktop notification.",
)
@click.option(
    "--provider",
    "-p",
    default=None,
    help="Override AI provider for this run.",
)
@click.option("--model", default=None, help="Override AI model for this run.")
@click.pass_context
def menu(
    ctx: click.Context,
    text: str | None,
    system: bool,
    clipboard: bool,
    notify: bool,
    provider: str | None,
    model: str | None,
) -> None:
    """Open the mode picker, then rewrite the selected text.

    \b
    Typical hotkey bindings:
      i3 / Sway:  bindsym $mod+Shift+g exec prosefmt menu -s -n
      Hyprland:   bind = $mainMod SHIFT, G, exec, prosefmt menu -s -n
    """
    from prosefmt.picker import best_picker, install_hints_picker, pick

    config: Config = ctx.obj.get("config") or Config.load()

    # Fail early if no picker tool is installed
    if best_picker() is None:
        hints = install_hints_picker()
        click.echo(
            "Error: no picker tool found (need rofi, wofi, fuzzel, dmenu, zenity, or fzf)",
            err=True,
        )
        for line in hints:
            click.echo(line, err=True)
        raise SystemExit(1)

    # Read input BEFORE opening the picker so the primary selection is
    # guaranteed to be intact (opening rofi/wofi can shift focus).
    input_text = _resolve_input(text, clipboard, system)
    if not input_text:
        _no_input_error(system, notify)

    # Show the picker
    choice = pick(list(config.modes.keys()))
    if not choice:
        raise SystemExit(0)  # user cancelled — silent exit

    if choice in config.modes:
        _run_rewrite(
            ctx,
            choice,
            input_text,
            system=system,
            clipboard=clipboard,
            provider_name=provider,
            model_override=model,
            show_notify=notify,
        )
    else:
        # Free-form custom prompt typed by the user
        from prosefmt.config import ModeConfig

        adhoc = ModeConfig(name="custom", prompt=choice, label=f"✦ {choice[:40]}")
        _run_rewrite(
            ctx,
            "custom",
            input_text,
            system=system,
            clipboard=clipboard,
            provider_name=provider,
            model_override=model,
            show_notify=notify,
            mode_override=adhoc,
        )


# ---------------------------------------------------------------------------
# list — show available modes
# ---------------------------------------------------------------------------


@cli.command("list")
@click.option(
    "--names",
    "-n",
    is_flag=True,
    help="Print mode names only (one per line).",
)
@click.pass_context
def list_modes(ctx: click.Context, names: bool) -> None:
    """List all available rewrite modes."""
    config: Config = ctx.obj["config"]

    if names:
        for name in config.modes:
            click.echo(name)
        return

    max_name = max(len(n) for n in config.modes)

    for name, mode in config.modes.items():
        label = mode.label or name
        click.echo(f"  {name:<{max_name}}  {label}: {mode.prompt}")


# ---------------------------------------------------------------------------
# undo — restore original text
# ---------------------------------------------------------------------------


@cli.command("undo")
@click.option(
    "--clipboard",
    "-c",
    is_flag=True,
    help="Write undo text to clipboard.",
)
@click.option(
    "--system",
    "-s",
    is_flag=True,
    help="Paste undo text back to active window.",
)
@click.pass_context
def undo(ctx: click.Context, clipboard: bool, system: bool) -> None:
    """Undo the last rewrite — restore the original text."""
    from prosefmt.core import load_undo
    from prosefmt.notify import notify

    config: Config = ctx.obj["config"]
    original = load_undo(config.undo_file)

    if original is None:
        click.echo("Nothing to undo.", err=True)
        raise SystemExit(1)

    if system:
        from prosefmt.clipboard import (
            clipboard_write,
            paste_to_active_window,
            preserve_clipboard,
        )

        with preserve_clipboard():
            clipboard_write(original)
            paste_to_active_window()

        notify("prosefmt", "↩ Reverted to original")
    elif clipboard:
        from prosefmt.clipboard import clipboard_write

        clipboard_write(original)
        notify("prosefmt", "↩ Reverted to original (clipboard)")
        click.echo(original)
    else:
        click.echo(original)


# ---------------------------------------------------------------------------
# config — manage configuration
# ---------------------------------------------------------------------------


@cli.group("config")
def config_group() -> None:
    """Manage prosefmt configuration."""


@config_group.command("init")
def config_init() -> None:
    """Create a default configuration file and check system dependencies."""
    from prosefmt.clipboard import check_clipboard_tools, install_hints
    from prosefmt.config import init_config

    path = init_config()
    click.echo(f"✓ Config file ready: {path}")
    click.echo("  Edit it to set your provider, model, and custom modes.\n")

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
        click.echo("\n  (Pipe mode — echo 'text' | prosefmt — works without these tools.)")
    else:
        click.echo("✓ Clipboard tools installed")


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show the active configuration."""
    config: Config = ctx.obj["config"]
    click.echo(f"Mode:      {config.default_mode}")
    click.echo(f"Provider:  {config.default_provider}")

    pconfig = config.providers.get(config.default_provider)
    if pconfig:
        click.echo(f"  URL:     {pconfig.url}")
        click.echo(f"  Model:   {pconfig.model}")
        click.echo(f"  API Key: {'***' if pconfig.api_key else '(not set)'}")

    click.echo(f"\nModes ({len(config.modes)}):")
    for name in config.modes:
        click.echo(f"  - {name}")


# ---------------------------------------------------------------------------
# check — verify system readiness
# ---------------------------------------------------------------------------


@cli.command("check")
@click.pass_context
def check(ctx: click.Context) -> None:
    """Verify clipboard tools, picker, and AI provider are ready."""
    from prosefmt.clipboard import check_clipboard_tools, install_hints
    from prosefmt.picker import (
        best_picker,
        check_picker_tools,
        install_hints_picker,
    )
    from prosefmt.providers import get_provider

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

    # --- Picker ---
    picker = best_picker()
    if picker:
        click.echo(f"✓ Picker: {picker}  (for 'prosefmt menu')")
    else:
        status = check_picker_tools()
        found = [t for t, v in status.items() if v]
        if not found:
            click.echo("⚠  No picker tool found  (needed for 'prosefmt menu')")
            for line in install_hints_picker():
                click.echo(line)
        else:
            click.echo(f"✓ Picker: {found[0]}")

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
                    "openai-compat": "PROSEFMT_COMPAT_API_KEY",
                }.get(pname, "API key env var")
                click.echo(
                    f"✗ Provider '{pname}' is not reachable\n"
                    f"  Make sure {env_var} is set in your environment."
                )
            else:
                click.echo(f"✗ Provider '{pname}' is not reachable")
            ok = False
    else:
        click.echo(f"✗ Provider '{pname}' not configured — run: prosefmt config init")
        ok = False

    raise SystemExit(0 if ok else 1)
