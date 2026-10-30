# prosefmt

> Rewrite text in any app — press a hotkey, get polished prose back.

[![CI](https://github.com/digitronik/prosefmt/actions/workflows/ci.yml/badge.svg)](https://github.com/digitronik/prosefmt/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/prosefmt)](https://pypi.org/project/prosefmt/)
[![Python](https://img.shields.io/pypi/pyversions/prosefmt)](https://pypi.org/project/prosefmt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<!-- TODO: Add demo.gif here — screen recording of: highlight text in a browser/Slack/email → press Mod+G → text rewrites in place -->

Highlight text in any application — browser, email, Slack, VS Code, anything — press your hotkey,
and prosefmt silently rewrites it and pastes the result back. Grammar fixed, tone shifted, fully
rephrased: all without leaving the app you are in.

It also works as a standard CLI tool that composes with pipes and scripts.

```
$ prosefmt "i can haz good grammer?"
I can have good grammar?

$ echo "this sentense has a typo" | prosefmt
This sentence has a typo.

$ prosefmt -m professional --clipboard    # reads clipboard → rewrites → writes back

$ prosefmt menu -s -n                     # highlight text → picker → rewrite → paste back
```

→ **[Jump to hotkey setup ↓](#system-wide-hotkeys)**

---

## Table of Contents

- [Why prosefmt?](#why-prosefmt)
- [Installation](#installation)
- [Setup Guide](#setup-guide)
  - [Step 1 — Install clipboard tools](#step-1--install-clipboard-tools)
  - [Step 2 — Choose an AI provider](#step-2--choose-an-ai-provider)
  - [Step 3 — Create your config](#step-3--create-your-config)
  - [Step 4 — Install a picker tool](#step-4--install-a-picker-tool-for-prosefmt-menu)
  - [Step 5 — Verify everything works](#step-5--verify-everything-works)
  - [Step 6 — Try it out](#step-6--try-it-out)
- [System-Wide Hotkeys](#system-wide-hotkeys)
- [Built-in Modes](#built-in-modes)
- [Mode Picker](#mode-picker)
- [Custom Modes](#custom-modes)
- [Configuration Reference](#configuration-reference)
- [Commands](#commands)
- [Development](#development)

---

## Why prosefmt?

Every existing tool in this space is a **GUI desktop app** —
Electron, Tauri, or PyQt5. They are 100–200 MB, framework-dependent, and impossible to script.

prosefmt is a plain CLI tool: two Python dependencies, composes with pipes, works from hotkeys or
scripts, and runs on every OS.

| | **prosefmt** | GUI tools |
|---|---|---|
| Size | ~2 Python deps | 100–200 MB runtime |
| Composability | Pipes, scripts, automation | GUI click-through only |
| Providers | Ollama, OpenAI, Anthropic, any OpenAI-compat | Varies |
| Custom modes | One TOML block; all prompts user-editable | Fork the source |
| Mode picker | Built-in (`prosefmt menu`) — no shell script | Their own UI |
| Hotkey integration | Any window manager, two lines of config | Their own UI |
| Per-mode AI model | Yes — route tasks to different models | No |

---

## Installation

```bash
# Recommended — installs as an isolated tool
uv tool install prosefmt

# Or with pip
pip install prosefmt
```

> **New to uv?** Install it with: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Setup Guide

Follow these steps once after installing. This takes about 5 minutes.

### Step 1 — Install clipboard tools

prosefmt uses your system clipboard to read and paste text. The tools needed depend on your OS.
**macOS and Windows users can skip this step** — everything is built in.

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

> **Not sure if you are on X11 or Wayland?** Run `echo $XDG_SESSION_TYPE` — it prints `x11` or `wayland`.

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
so it is always available:

```bash
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc
```

#### Option C — Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### Option D — Any OpenAI-compatible endpoint

Works with Groq, Together AI, LM Studio, vLLM, and any server that speaks the
`/v1/chat/completions` format. Configure the URL and model in your config file
(see [Step 3](#step-3--create-your-config)).

---

### Step 3 — Create your config

Run this once to create a ready-to-edit config file:

```bash
prosefmt config init
```

It also checks whether your clipboard tools from Step 1 are installed and tells you exactly what
to run if anything is missing.

Open the file to set your default provider and model:

```bash
# Linux / macOS
nano ~/.config/prosefmt/config.toml    # or: code, vim, whatever you prefer

# Windows
notepad %APPDATA%\prosefmt\config.toml
```

The minimum config for Ollama — the defaults already cover this, so you may not need to change
anything:

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

### Step 4 — Install a picker tool (for `prosefmt menu`)

The `prosefmt menu` command opens a graphical mode picker — no shell scripting needed. Install any
one of these:

```bash
# Fedora
sudo dnf install rofi           # X11 / Wayland

# Debian / Ubuntu
sudo apt install rofi

# Arch / Manjaro
sudo pacman -S rofi

# Or any of: wofi, fuzzel, dmenu, zenity, fzf — prosefmt auto-detects the best one
```

> Skip this step if you only plan to use `prosefmt -s -n` (direct hotkey, no picker).

---

### Step 5 — Verify everything works

```bash
prosefmt check
```

Expected output:

```
✓ Clipboard tools installed
✓ Picker tool:  rofi
✓ Provider 'ollama' is reachable  (model: qwen2.5:1.5b)
```

If anything is wrong, `prosefmt check` prints the exact command to fix it.

---

### Step 6 — Try it out

```bash
# Pass text directly (default mode: fix)
prosefmt "me and him went to the store yesterday"

# Explicit mode
prosefmt -m professional "please review the attached document"

# Pipe from stdin
echo "this sentense has a typo" | prosefmt

# Read from clipboard and print the result
prosefmt --clipboard

# System-wide: read selected text from any app, rewrite, paste back in-place
prosefmt --system

# Open the mode picker, then rewrite selected text with the chosen mode
prosefmt menu -s -n
```

---

## System-Wide Hotkeys

The `--system` flag is what makes prosefmt useful beyond the terminal. Highlight any text, press
your hotkey, and the rewritten version is pasted back automatically — without touching the mouse
or switching windows.

Two bindings are recommended:

| Hotkey | Action |
|:---|:---|
| `Mod+G` | Fix grammar immediately (default mode, no picker) |
| `Mod+Shift+G` | Open the built-in mode picker — choose any mode interactively |

The mode picker (`prosefmt menu`) is built into the CLI — **no shell script required**. It
auto-detects the best available picker tool (rofi → wofi → fuzzel → dmenu → zenity → fzf) and
launches it. You can also type a free-form instruction directly into the picker to use it as a
one-shot custom prompt.

> **Clipboard safety:** `--system` reads your highlighted text via the *primary* selection and
> pastes the result back via a temporary clipboard write. Your previous Ctrl+C content is saved
> before the paste and automatically restored afterwards — so your clipboard is never destroyed.

---

### Linux — i3wm / Sway

Add to `~/.config/i3/config` (or `~/.config/sway/config`):

```
bindsym $mod+g       exec --no-startup-id prosefmt -s -n
bindsym $mod+Shift+g exec --no-startup-id prosefmt menu -s -n
```

Reload i3 with `Mod+Shift+C`.

That is all. prosefmt detects whichever picker you have installed — rofi, wofi, fuzzel, dmenu,
zenity, or fzf. Install any one:

```bash
sudo dnf install rofi   # Fedora
sudo apt install rofi   # Debian / Ubuntu
sudo pacman -S rofi     # Arch
```

Run `prosefmt check` to confirm your picker is detected.

---

### Linux — Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```
bind = $mainMod,       G, exec, prosefmt -s -n
bind = $mainMod SHIFT, G, exec, prosefmt menu -s -n
```

Install a Wayland-native picker if you do not have one:

```bash
sudo dnf install wofi   # Fedora — Wayland-native
sudo apt install wofi   # Debian / Ubuntu
sudo pacman -S wofi     # Arch
```

prosefmt also accepts rofi (Wayland mode), fuzzel, or fzf.

---

### Linux — GNOME / KDE (any desktop)

Add custom shortcuts in **Settings → Keyboard → Custom Shortcuts**:

| Name | Command | Shortcut |
|:---|:---|:---|
| prosefmt (default fix) | `prosefmt -s -n` | `Super+G` |
| prosefmt mode picker | `prosefmt menu -s -n` | `Super+Shift+G` |

Install a picker tool (rofi works on GNOME and KDE):

```bash
sudo dnf install rofi   # Fedora
sudo apt install rofi   # Debian / Ubuntu
sudo pacman -S rofi     # Arch
```

---

### macOS — Hammerspoon

[Hammerspoon](https://www.hammerspoon.org) provides both the hotkey binding and a built-in
chooser for the mode picker. Add to `~/.hammerspoon/init.lua`:

```lua
-- Grammar fix
hs.hotkey.bind({"cmd"}, "g", function()
  hs.task.new("/usr/local/bin/prosefmt", nil, {"--system", "--notify"}):start()
end)

-- Mode picker — opens Hammerspoon's native chooser
hs.hotkey.bind({"cmd", "shift"}, "g", function()
  hs.task.new("/usr/local/bin/prosefmt", function(_, stdout)
    local choices = {}
    for line in stdout:gmatch("[^\n]+") do
      table.insert(choices, { text = line })
    end
    local chooser = hs.chooser.new(function(choice)
      if choice then
        hs.task.new("/usr/local/bin/prosefmt", nil,
          {"-m", choice.text, "--system", "--notify"}):start()
      end
    end)
    chooser:choices(choices)
    chooser:show()
  end, {"list", "--names"}):start()
end)
```

Reload the Hammerspoon config from the menu bar icon.

> **Tip:** If you install `fzf` via Homebrew (`brew install fzf`), you can also use
> `prosefmt menu -s -n` directly — it opens fzf in a terminal window.

---

### macOS — Automator / Shortcuts app

For a fix-only binding without Hammerspoon, create a **Quick Action** in Automator that runs:

```bash
/usr/local/bin/prosefmt --system --notify
```

Assign it a keyboard shortcut in **System Settings → Keyboard → Keyboard Shortcuts → Services**.

---

### Windows — AutoHotkey v2

Create `prosefmt-menu.ps1` anywhere on your system (for example `%USERPROFILE%\prosefmt-menu.ps1`):

```powershell
# prosefmt-menu.ps1
$modes = (& prosefmt list --names) -split "`n" | Where-Object { $_ }
$mode  = $modes | Out-GridView -Title "prosefmt — choose a mode" -PassThru
if ($mode) { & prosefmt -m $mode --system --notify }
```

Add to your AutoHotkey v2 script:

```ahk
; prosefmt.ahk
#g::  Run "prosefmt --system --notify",, "Hide"
#+g:: Run 'powershell -WindowStyle Hidden -File "%USERPROFILE%\prosefmt-menu.ps1"',, "Hide"
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

Run `prosefmt list` to see all modes including any custom ones you have added.

---

## Mode Picker

`prosefmt menu` opens an interactive mode picker — no shell scripting required.

```bash
# Highlight text → picker → chosen mode rewrites and pastes back
prosefmt menu -s -n

# Or pick a mode and let it read from clipboard
prosefmt menu -c
```

prosefmt auto-detects the best installed picker in this order: **rofi → wofi → fuzzel → dmenu →
zenity → fzf**. Install any one of them (see [System-Wide Hotkeys](#system-wide-hotkeys) for
platform-specific install commands).

### Free-form prompts

You can type anything directly into the picker. If what you type is not a mode name, prosefmt
treats it as a one-shot custom instruction:

```
  fix
  professional
  casual
  translate to French        ← typed freely — runs as an ad-hoc prompt
  make this sound angrier    ← also works
```

No config file changes needed for one-off instructions.

### Check picker status

```bash
prosefmt check
```

```
✓ Clipboard tools installed
✓ Picker tool:  rofi
✓ Provider 'ollama' is reachable  (model: qwen2.5:1.5b)
```

If no picker is installed, `prosefmt check` suggests the install command for your distro.

---

## Custom Modes

Add any number of custom modes to your config file. All prompts live in `config.toml` — nothing
is hard-coded in prosefmt itself. You can also edit the built-in mode prompts.

```toml
# ~/.config/prosefmt/config.toml

[modes.translate-spanish]
prompt = "Translate to Spanish. Keep technical terms in English."
label  = "🇪🇸 Spanish"

[modes.translate-czech]
prompt = "Translate to Czech. Preserve meaning and tone."
label  = "🇨🇿 Czech"

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
prosefmt -m translate-spanish "Good morning, how are you?"
prosefmt -m slack "Please review the pull request I opened for the authentication refactor."
```

Custom modes appear automatically in `prosefmt menu` — no changes to your hotkey config needed.

### Making a custom mode the default

Set `default_mode` in your config so pressing `Mod+G` (the bare hotkey) uses a different mode:

```toml
# Bare hotkey fixes grammar for most work, but if you're a translator:
default_mode = "translate-czech"
```

Then `prosefmt -s -n` (your `Mod+G` binding) translates instead of fixing grammar.

### Real-world example: Czech ↔ English translation workflow

You receive a message in Czech. You want to read it in English, write your reply in English, then
send it back as Czech — all without switching apps.

**Config:**

```toml
[modes.translate-english]
prompt         = "Translate to English. Keep technical terms as-is."
label          = "→ English"
default_output = "popup"      # show translation — don't replace the Czech text

[modes.translate-czech]
prompt         = "Translate to Czech. Keep technical terms, code, and URLs in English."
label          = "→ Czech"
default_output = "replace"    # replace your English draft with Czech in-place
```

**Workflow:**

```
1. Highlight the Czech message → Mod+Shift+G → translate-english
   → popup shows the English translation (Czech text untouched)

2. Read the popup, type your English reply in the chat/email box

3. Highlight your English reply → Mod+Shift+G → translate-czech
   → English replaced with Czech in-place → hit send
```

The same pattern works for Hindi, French, Spanish, Japanese — one mode per language direction.

---

### Per-mode provider and model

Route specific modes to different AI providers or models — for example, use a fast local model
for quick fixes and a cloud model for deep rewrites:

```toml
[modes.fix]
prompt   = "Fix grammar, spelling, and punctuation. Output ONLY the corrected text."
provider = "ollama"
model    = "qwen2.5:1.5b"   # fast, local, CPU-friendly

[modes.review]
prompt   = "Review this text for clarity, tone, and impact. Suggest specific improvements."
provider = "anthropic"
model    = "claude-opus-4-5"  # heavy task → cloud model
```

CLI flags `--provider` and `--model` always override the mode config for that run.

### Controlling output

Every mode has a `default_output` field that decides what happens to the result:

| Value | Behaviour |
|:---|:---|
| `"replace"` | Paste result back in-place, replacing the original text (default) |
| `"clipboard"` | Write result to clipboard only (don't paste) |
| `"popup"` | Show result in a popup window — original text is untouched *(Phase 2)* |

```toml
[modes.translate-czech]
prompt         = "Translate to Czech. Keep technical terms in English."
default_output = "replace"    # paste the Czech translation back in-place

[modes.translate-english]
prompt         = "Translate to English."
default_output = "popup"      # show translation in popup — don't replace original
```

The `popup` display module is coming in Phase 2. Until then, popup modes fall back to stdout.

---

## Configuration Reference

Config file location:

| OS | Path |
|:---|:---|
| Linux / macOS | `~/.config/prosefmt/config.toml` |
| Linux (custom) | `$XDG_CONFIG_HOME/prosefmt/config.toml` |
| Windows | `%APPDATA%\prosefmt\config.toml` |

Run `prosefmt config init` to create it, `prosefmt config show` to see active values.

### Full example

```toml
# ~/.config/prosefmt/config.toml

# Default mode — used when running `prosefmt "text"` without -m.
# Change to any mode name you define (e.g. "professional", "translate-czech").
default_mode = "fix"

# Default AI provider (options: ollama, openai, anthropic, openai-compat)
default_provider = "ollama"

# System prompt applied to every rewrite mode.
# Uncomment and edit to change the AI's base behaviour.
# system_prompt = "You are a text editor. Output ONLY the rewritten text — no preamble, no quotes."

# ── Providers ────────────────────────────────────────────────────────────────

[providers.ollama]
url   = "http://localhost:11434"
model = "qwen2.5:1.5b"          # any model you have pulled

[providers.openai]
# API key: set OPENAI_API_KEY or PROSEFMT_OPENAI_API_KEY in your environment
model = "gpt-4o-mini"

[providers.anthropic]
# API key: set ANTHROPIC_API_KEY or PROSEFMT_ANTHROPIC_API_KEY in your environment
model = "claude-haiku-4-5-20251001"

# Any OpenAI-compatible endpoint: Groq, Together AI, LM Studio, vLLM, etc.
# [providers.openai-compat]
# url   = "https://api.groq.com/openai/v1"
# model = "llama-3.3-70b-versatile"
# API key: set PROSEFMT_COMPAT_API_KEY in your environment

# ── Modes ─────────────────────────────────────────────────────────────────────
# Every built-in mode can be edited here. `prosefmt config init` writes all of
# them out so you can see and change every default prompt.

# [modes.fix]
# prompt             = "Fix grammar, spelling, and punctuation only. Output ONLY the corrected text."
# label              = "Fix Grammar"
# preserve_structure = true     # keep bullet lists, numbered lists intact
# provider           = "ollama" # optional: override default_provider for this mode
# model              = "qwen2.5:1.5b"  # optional: override provider's default model
# default_output     = "replace"       # "replace" | "popup" | "clipboard"
```

### Top-level keys

| Key | Type | Default | Description |
|:---|:---|:---|:---|
| `default_mode` | string | `"fix"` | Mode used when `-m` is not specified |
| `default_provider` | string | `"ollama"` | Provider used when mode has no `provider` override |
| `system_prompt` | string | built-in | System instruction prepended to every mode |

### Mode fields

| Field | Type | Default | Description |
|:---|:---|:---|:---|
| `prompt` | string | required | The instruction sent to the AI |
| `label` | string | mode name | Display name shown in the picker |
| `preserve_structure` | bool | `true` | Re-attach bullet / numbered list markers after rewrite |
| `provider` | string | `default_provider` | Provider to use for this mode only |
| `model` | string | provider default | Model to use for this mode only |
| `default_output` | string | `"replace"` | What to do with the result: `replace`, `popup`, `clipboard` |

### API keys — environment variables

**Never put API keys in the config file.** Set them as environment variables instead:

| Provider | Environment variable |
|:---|:---|
| OpenAI | `PROSEFMT_OPENAI_API_KEY` or `OPENAI_API_KEY` |
| Anthropic | `PROSEFMT_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY` |
| OpenAI-compat | `PROSEFMT_COMPAT_API_KEY` |

Add them to your shell profile (`~/.bashrc`, `~/.zshrc`, `~/.config/fish/config.fish`) so they
load automatically in every session.

---

## Commands

```
prosefmt [TEXT]                Rewrite TEXT with default mode (or stdin if omitted)
prosefmt -m MODE [TEXT]        Rewrite with a specific mode
prosefmt -s / --system         Read highlighted text, paste result back in-place
prosefmt -c / --clipboard      Read from and write to clipboard
prosefmt -n / --notify         Show a desktop notification when done
prosefmt -p / --provider P     Override the AI provider for this run
prosefmt --model M             Override the model for this run

prosefmt menu                  Open the built-in mode picker, then rewrite
prosefmt menu -s -n            Highlight text → picker → rewrite → paste back
prosefmt menu -c               Read clipboard → picker → rewrite → write back
prosefmt menu -p P --model M   Override provider/model for this picker session

prosefmt list                  List all available modes (human-readable)
prosefmt list --names          Mode names only
prosefmt undo                  Restore the original text from the last rewrite
prosefmt check                 Check clipboard tools, picker, and provider connectivity
prosefmt config init           Create ~/.config/prosefmt/config.toml
prosefmt config show           Show the active configuration

prosefmt --version             Show version
prosefmt --help                Show help
```

---

## Development

```bash
git clone https://github.com/digitronik/prosefmt.git
cd prosefmt
uv sync --extra dev

# Git hooks (ruff + file hygiene) — uses .pre-commit-config.yaml
uv run pre-commit install
uv run pre-commit run --all-files   # once, to verify hooks

# Run tests
uv run pytest -v
```

Contributions welcome — open an issue or pull request on GitHub.

---

## License

[MIT](LICENSE)
