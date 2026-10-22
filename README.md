# Reword

> AI-powered text rewriter for your terminal.  
> Fix grammar, rephrase, summarize — in any app, with one command.

[![CI](https://github.com/digitronik/reword/actions/workflows/ci.yml/badge.svg)](https://github.com/digitronik/reword/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/reword)](https://pypi.org/project/reword/)
[![Python](https://img.shields.io/pypi/pyversions/reword)](https://pypi.org/project/reword/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

```
$ reword fix "i can haz good grammer?"
I can have good grammar?

$ echo "This is a very long sentence that just keeps going" | reword concise
This sentence is too long.

$ reword professional --clipboard    # reads clipboard → rewrites → writes back
```

---

## Table of Contents

- [Why Reword?](#why-reword)
- [Installation](#installation)
- [Setup Guide](#setup-guide)
  - [Step 1 — Install clipboard tools](#step-1--install-clipboard-tools)
  - [Step 2 — Choose an AI provider](#step-2--choose-an-ai-provider)
  - [Step 3 — Create your config](#step-3--create-your-config)
  - [Step 4 — Verify everything works](#step-4--verify-everything-works)
  - [Step 5 — Try it out](#step-5--try-it-out)
- [Built-in Modes](#built-in-modes)
- [Configuration Reference](#configuration-reference)
- [Custom Modes](#custom-modes)
- [System-Wide Hotkeys](#system-wide-hotkeys)
- [Commands](#commands)
- [Development](#development)

---

## Why Reword?

Every existing tool in this space (WritingTools, GhostEdit, ZyntaxAI…) is a **GUI desktop app** — Electron, Tauri, or PyQt5. They're 100–200 MB, framework-dependent, and impossible to script.

Reword is a plain CLI tool: two dependencies, composes with pipes, works from hotkeys or scripts, and runs on every OS.

| | **Reword** | GUI tools |
|---|---|---|
| Size | ~2 Python deps | 100–200 MB runtime |
| Composability | Pipes, scripts, automation | GUI click-through only |
| Providers | Ollama, OpenAI, Anthropic, any OpenAI-compat | Varies |
| Custom modes | Add one line to a config file | Fork the source |
| Hotkey integration | Any window manager or OS shortcut | Their own UI |

---

## Installation

```bash
# Recommended — installs as an isolated tool
uv tool install reword

# Or with pip
pip install reword
```

> **New to uv?** Install it with: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Setup Guide

Follow these steps once after installing. This takes about 5 minutes.

### Step 1 — Install clipboard tools

Reword uses your system's clipboard to read and paste text. The tools needed
depend on your OS. **macOS and Windows users can skip this step** — everything
is built in.

**Linux (X11 — most desktops: GNOME, KDE, i3, XFCE, …)**

```bash
# Debian / Ubuntu / Mint / Pop!_OS
sudo apt install xclip xdotool

# Fedora / RHEL / CentOS / Rocky
sudo dnf install xclip xdotool

# Arch / Manjaro / EndeavourOS
sudo pacman -S xclip xdotool

# openSUSE
sudo zypper install xclip xdotool
```

**Linux (Wayland — GNOME on Wayland, KDE Wayland, Sway, Hyprland, …)**

```bash
# Debian / Ubuntu / Mint
sudo apt install wl-clipboard wtype

# Fedora / RHEL / CentOS
sudo dnf install wl-clipboard wtype

# Arch / Manjaro
sudo pacman -S wl-clipboard wtype

# openSUSE
sudo zypper install wl-clipboard wtype
```

> **Not sure if you're on X11 or Wayland?** Run `echo $XDG_SESSION_TYPE` — it
> prints `x11` or `wayland`.

**macOS** — nothing to install. `pbcopy`, `pbpaste`, and `osascript` are built in.

**Windows** — nothing to install. `clip.exe` and PowerShell are built in.

---

### Step 2 — Choose an AI provider

Pick one. You can always add more later.

#### Option A — Ollama (local, free, fully private — recommended for first-time setup)

No API key needed. Runs entirely on your machine.

```bash
# 1. Install Ollama  →  https://ollama.com/download
#    (macOS / Windows: download the installer; Linux: one-liner below)
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a model  (qwen2.5:1.5b is fast and small — great for CPU-only)
ollama pull qwen2.5:1.5b

# 3. Start the server (keep this running in the background)
ollama serve
```

Other good models to try: `llama3.2:3b`, `mistral:7b`, `phi3:mini`

#### Option B — OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`)
so it's always available:

```bash
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc
```

#### Option C — Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### Option D — Any OpenAI-compatible endpoint

Works with Groq, Together AI, LM Studio, vLLM, and any server that speaks
the `/v1/chat/completions` format. Configure the URL and model in your config
file (see [Step 3](#step-3--create-your-config)).

---

### Step 3 — Create your config

Run this once to create a ready-to-edit config file at
`~/.config/reword/config.toml`:

```bash
reword config init
```

It will also check whether your clipboard tools from Step 1 are installed and
tell you exactly what to run if anything is missing.

Open the file to set your default provider and model:

```bash
# Linux / macOS
nano ~/.config/reword/config.toml    # or: code, vim, whatever you prefer

# Windows
notepad %APPDATA%\reword\config.toml
```

The minimum config for Ollama looks like this — the defaults already cover it,
so you may not need to change anything:

```toml
default_provider = "ollama"

[providers.ollama]
url   = "http://localhost:11434"
model = "qwen2.5:1.5b"
```

For OpenAI:

```toml
default_provider = "openai"

[providers.openai]
model = "gpt-4o-mini"    # API key comes from OPENAI_API_KEY env var
```

---

### Step 4 — Verify everything works

```bash
reword check
```

Expected output:

```
✓ Clipboard tools installed
✓ Provider 'ollama' is reachable  (model: qwen2.5:1.5b)
```

If anything is wrong, `reword check` prints the exact command to fix it.

---

### Step 5 — Try it out

```bash
# Pass text directly
reword fix "me and him went to the store yesterday"

# Pipe from stdin
echo "this sentense has a typo" | reword fix

# Read from clipboard and print the result
reword fix --clipboard

# Read from clipboard, rewrite, and write the result back to clipboard
reword professional --clipboard

# System-wide: read selected text from any app, rewrite, paste back in-place
reword fix --system
```

---

## Built-in Modes

| Mode | What it does |
|:---|:---|
| `fix` | Fix grammar, spelling, and punctuation only |
| `professional` | Rewrite in a polished workplace tone |
| `casual` | Rewrite in a friendly, conversational tone |
| `rephrase` | Improve clarity and flow without changing the meaning |
| `concise` | Same meaning, fewer words |
| `expand` | Add more detail and explanation |
| `summarize` | Condense to the key points |
| `email` | Format as a professional email with greeting and sign-off |

Run `reword list` to see all modes including any custom ones you've added.

---

## Configuration Reference

Config file location:

| OS | Path |
|:---|:---|
| Linux / macOS | `~/.config/reword/config.toml` |
| Linux (custom) | `$XDG_CONFIG_HOME/reword/config.toml` |
| Windows | `%APPDATA%\reword\config.toml` |

Run `reword config init` to create it, `reword config show` to see active values.

### Full example

```toml
# ~/.config/reword/config.toml

# Which provider to use by default
default_provider = "ollama"

# System prompt applied to every rewrite mode.
# Uncomment and edit to change the AI's base behaviour.
# system_prompt = "You are a text editor. Output ONLY the rewritten text — no preamble."

# ── Providers ────────────────────────────────────────────────────────────────

[providers.ollama]
url   = "http://localhost:11434"
model = "qwen2.5:1.5b"          # any model you have pulled

[providers.openai]
# API key: set OPENAI_API_KEY or REWORD_OPENAI_API_KEY in your environment
model = "gpt-4o-mini"

[providers.anthropic]
# API key: set ANTHROPIC_API_KEY or REWORD_ANTHROPIC_API_KEY in your environment
model = "claude-haiku-4-5-20251001"

# Any OpenAI-compatible endpoint: Groq, Together AI, LM Studio, vLLM, etc.
# [providers.openai-compat]
# url   = "https://api.groq.com/openai/v1"
# model = "llama-3.3-70b-versatile"
# API key: set REWORD_COMPAT_API_KEY in your environment
```

### API keys — environment variables

**Never put API keys in the config file.** Set them as environment variables instead:

| Provider | Environment variable |
|:---|:---|
| OpenAI | `REWORD_OPENAI_API_KEY` or `OPENAI_API_KEY` |
| Anthropic | `REWORD_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY` |
| OpenAI-compat | `REWORD_COMPAT_API_KEY` |

Add them to your shell profile (`~/.bashrc`, `~/.zshrc`, `~/.config/fish/config.fish`)
so they load automatically in every session.

---

## Custom Modes

Add any number of custom modes to your config file:

```toml
# ~/.config/reword/config.toml

[modes.translate-spanish]
prompt = "Translate to Spanish. Keep technical terms in English."
label  = "Translated to Spanish"

[modes.code-comments]
prompt             = "Add clear, concise comments to this code. Do not change the code itself."
label              = "Comments added"
preserve_structure = false

[modes.slack]
prompt = "Rewrite for Slack: brief, friendly, one or two sentences max. No formal sign-off."
label  = "Slack-ready"

[modes.eli5]
prompt = "Explain this like I'm five — simple words, short sentences, no jargon."
label  = "Simplified"
```

Use them exactly like built-in modes:

```bash
reword translate-spanish "Good morning, how are you?"
reword slack "Please review the pull request I opened for the authentication refactor."
```

---

## System-Wide Hotkeys

The `--system` flag reads your selected text from any app, rewrites it, and
pastes the result back in-place. Bind it to a hotkey for a seamless workflow.

### Linux — i3wm / Sway

```
# ~/.config/i3/config (or ~/.config/sway/config)
bindsym $mod+g       exec --no-startup-id reword fix --system --notify
bindsym $mod+Shift+g exec --no-startup-id \
    reword list | rofi -dmenu -p "Reword mode" | xargs -r -I{} reword {} --system --notify
```

### Linux — Hyprland

```
# ~/.config/hypr/hyprland.conf
bind = $mainMod, G, exec, reword fix --system --notify
```

### Linux — GNOME / KDE (any desktop)

Go to **Settings → Keyboard → Custom Shortcuts** and add:

| Name | Command | Shortcut |
|:---|:---|:---|
| Reword Fix | `reword fix --system --notify` | `Super+G` |
| Reword Menu | `bash -c 'reword list \| rofi -dmenu -p Reword \| xargs -r reword --system --notify'` | `Super+Shift+G` |

### macOS — Hammerspoon

```lua
-- ~/.hammerspoon/init.lua
hs.hotkey.bind({"cmd"}, "g", function()
  hs.task.new("/usr/local/bin/reword", nil, {"fix", "--system", "--notify"}):start()
end)
```

### macOS — Automator / Shortcuts app

Create a **Quick Action** in Automator that runs a shell script:

```bash
/usr/local/bin/reword fix --system --notify
```

Assign it a keyboard shortcut in **System Settings → Keyboard → Keyboard Shortcuts → Services**.

### Windows — AutoHotkey v2

```ahk
; reword.ahk
#g:: {
    Run "reword fix --system --notify", , "Hide"
}
```

---

## Commands

```
reword <mode> [TEXT]         Rewrite TEXT (or stdin if omitted)
reword <mode> --clipboard    Read from clipboard, print result (also writes back)
reword <mode> --system       Read selected text, rewrite, paste back in-place
reword <mode> --provider P   Override the AI provider for this run
reword <mode> --model M      Override the model for this run
reword <mode> --notify       Show a desktop notification when done

reword list                  List all available modes
reword undo                  Restore the original text from the last rewrite
reword check                 Check clipboard tools and provider connectivity
reword config init           Create ~/.config/reword/config.toml
reword config show           Show the active configuration

reword --version             Show version
reword --help                Show help
```

---

## Development

```bash
git clone https://github.com/digitronik/reword.git
cd reword
uv sync --extra dev

# Run tests
uv run pytest -v

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

Contributions welcome — open an issue or pull request on GitHub.

---

## License

[MIT](LICENSE)
