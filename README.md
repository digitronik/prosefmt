<p align="center">
  <h1 align="center">prosefmt</h1>
  <p align="center">
    <strong>AI-powered text rewriting — system-wide, from any app, with a single hotkey.</strong>
  </p>
  <p align="center">
    <a href="https://github.com/digitronik/prosefmt/actions/workflows/ci.yml"><img src="https://github.com/digitronik/prosefmt/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://pypi.org/project/prosefmt/"><img src="https://img.shields.io/pypi/v/prosefmt" alt="PyPI"></a>
    <a href="https://pypi.org/project/prosefmt/"><img src="https://img.shields.io/pypi/pyversions/prosefmt" alt="Python"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  </p>
</p>

<!-- TODO: Add demo.gif — screen recording of: highlight text → press Mod+G → text rewrites in place -->

Highlight text in **any application** — browser, email, Slack, VS Code, terminal — press your
hotkey, and prosefmt rewrites it in place. Grammar fixed, tone shifted, translated, summarized —
all without leaving the app you're in.

```
$ prosefmt "i can haz good grammer?"
I can have good grammar.

$ echo "this sentense has a typo" | prosefmt
This sentence has a typo.

$ prosefmt -m professional "lets meet tmrw and discuss"
Let's meet tomorrow to discuss.

$ prosefmt menu -s -n    # highlight text → picker → rewrite → paste back
```

---

## Table of Contents

- [Why prosefmt?](#why-prosefmt)
- [Quick Start (2 minutes)](#quick-start)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Setup Guide](#setup-guide)
  - [1. Clipboard tools](#1-clipboard-tools)
  - [2. AI provider](#2-ai-provider)
  - [3. Config file](#3-config-file)
  - [4. Picker tool](#4-picker-tool-optional)
  - [5. Verify](#5-verify)
- [Usage](#usage)
  - [Basic](#basic-usage)
  - [System-wide rewriting](#system-wide-rewriting)
  - [Mode picker](#mode-picker)
  - [Diff output](#diff-output)
  - [Popup output](#popup-output)
  - [Undo](#undo)
- [Built-in Modes](#built-in-modes)
- [Custom Modes](#custom-modes)
  - [Translation workflow](#real-world-example-translation-workflow)
  - [Per-mode provider and model](#per-mode-provider-and-model)
  - [Output routing](#controlling-output-per-mode)
- [System-Wide Hotkeys](#system-wide-hotkeys)
  - [i3 / Sway](#linux--i3-wm--sway)
  - [Hyprland](#linux--hyprland)
  - [GNOME / KDE](#linux--gnome--kde)
  - [macOS](#macos)
  - [Windows](#windows)
- [Architecture](#architecture)
- [Configuration Reference](#configuration-reference)
- [CLI Reference](#cli-reference)
- [FAQ](#faq)
- [Development](#development)

---

## Why prosefmt?

Every other AI writing tool is a GUI desktop app — Electron, PyQt5, or Tauri.
They weigh 100–200 MB, can't be scripted, and most are broken on Wayland.

prosefmt is different:

| | **prosefmt** | GUI writing tools |
|---|---|---|
| **Architecture** | CLI — 2 Python deps, ~15 KB | Electron/PyQt GUI, 100–200 MB |
| **Install** | `pip install prosefmt` | Download installer or clone repo |
| **Composability** | Pipes, scripts, shell automation | Click through menus |
| **Works on Wayland** | Yes — native `wl-clipboard` + `wtype` | Usually broken |
| **AI providers** | Ollama, OpenAI, Anthropic, any OpenAI-compat | Varies, often 1–2 |
| **Modes/prompts** | User-editable TOML — you own every prompt | Hardcoded, fork to change |
| **Offline** | Ollama (local, private) is the default | Cloud-only or optional |
| **Mode picker** | Built-in (`prosefmt menu`) | Their own UI or none |
| **Per-mode model** | Yes — route tasks to different AI models | No |

```
prosefmt is to AI text tools what ripgrep is to grep —
fast, composable, Unix-native, and built for power users.
```

---

## Quick Start

Get running in 2 minutes with Ollama (free, local, no API key):

```bash
# 1. Install prosefmt
pip install prosefmt          # or: uv tool install prosefmt

# 2. Install & start Ollama (https://ollama.com)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:1.5b
ollama serve                  # keep running in background

# 3. Create config + check everything works
prosefmt config init
prosefmt check

# 4. Try it!
prosefmt "me and him went to store yesterday"
```

That's it. For system-wide hotkeys, jump to [System-Wide Hotkeys](#system-wide-hotkeys).

---

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                        INPUT                                 │
│                                                              │
│  Highlight text + hotkey (--system)                          │
│  Clipboard content (--clipboard)                             │
│  CLI argument: prosefmt "text"                               │
│  Pipe: echo "text" | prosefmt                                │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    PICKER (optional)                         │
│                                                              │
│  prosefmt menu  →  rofi / wofi / fuzzel / dmenu / fzf        │
│  Choose a mode or type a free-form custom instruction        │
└─────────────────────────┬────────────────────────────────────┘
                          │ mode name (or custom prompt)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    PROCESSING                                │
│                                                              │
│  config.toml        →  system_prompt + mode.prompt           │
│  AI provider        →  Ollama / OpenAI / Anthropic / compat  │
│  List preservation  →  bullets & numbered lists kept intact  │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                      OUTPUT                                  │
│                                                              │
│  "replace"    →  paste rewritten text back in-place          │
│  "popup"      →  show in a desktop popup (original untouched)│
│  "clipboard"  →  write to clipboard                          │
│  "stdout"     →  print to terminal                           │
│  "--diff"     →  show what changed (red/green diff)          │
└──────────────────────────────────────────────────────────────┘
```

### Module Overview

```
src/prosefmt/
├── cli.py              CLI entry point (Click) — subcommands, flags, routing
├── config.py           TOML config loading — modes, providers, system prompt
├── core.py             Rewrite engine — prompt assembly, list preservation
├── modes.py            Built-in mode definitions + list-structure helpers
├── clipboard.py        Cross-platform clipboard (X11, Wayland, macOS, Windows)
├── picker.py           Mode picker UI (rofi, wofi, fuzzel, dmenu, zenity, fzf)
├── popup.py            Result display popup (zenity, yad, kdialog, rofi)
├── diff.py             Text diff formatting (unified + inline, ANSI colour)
├── notify.py           Desktop notifications (notify-send, osascript, toast)
└── providers/
    ├── base.py         Provider protocol
    ├── ollama.py       Ollama (local, default)
    ├── openai_compat.py OpenAI / Groq / Together / LM Studio / vLLM
    └── anthropic.py    Anthropic Claude
```

**Design principles:**
- **Config owns all prompts** — zero prompts hardcoded in Python. Every instruction sent to
  the AI lives in `config.toml` and is user-editable.
- **Platform tools, not Python deps** — clipboard, picker, popup, notifications are all
  subprocess calls to native OS tools. No PyQt, no Tkinter, no heavy GUI libraries.
- **Two runtime dependencies** — `click` (CLI framework) and `httpx` (HTTP client). That's it.

---

## Installation

### Recommended: uv (isolated tool install)

```bash
uv tool install prosefmt
```

> **New to uv?** Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### With pip

```bash
pip install prosefmt
```

### From source

```bash
git clone https://github.com/digitronik/prosefmt.git
cd prosefmt
uv sync --extra dev
```

---

## Setup Guide

One-time setup — takes about 5 minutes.

### 1. Clipboard tools

prosefmt uses native OS clipboard tools. **macOS and Windows users can skip this step.**

<details>
<summary><strong>Linux (X11)</strong> — GNOME, KDE, i3, XFCE, etc.</summary>

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

</details>

<details>
<summary><strong>Linux (Wayland)</strong> — GNOME on Wayland, Sway, Hyprland, etc.</summary>

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

</details>

> **Not sure?** Run `echo $XDG_SESSION_TYPE` — it prints `x11` or `wayland`.

### 2. AI provider

Pick one. You can always switch or add more later.

<details open>
<summary><strong>Option A — Ollama</strong> (local, free, private — recommended)</summary>

No API key needed. Runs entirely on your machine.

```bash
# Install Ollama → https://ollama.com/download
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (qwen2.5:1.5b is fast, works on CPU)
ollama pull qwen2.5:1.5b

# Start the server (keep running)
ollama serve
```

Other good models: `llama3.2:3b`, `mistral:7b`, `phi3:mini`

</details>

<details>
<summary><strong>Option B — OpenAI</strong></summary>

```bash
export OPENAI_API_KEY="sk-..."
# Add to ~/.bashrc or ~/.zshrc so it persists
```

</details>

<details>
<summary><strong>Option C — Anthropic (Claude)</strong></summary>

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# Add to ~/.bashrc or ~/.zshrc so it persists
```

</details>

<details>
<summary><strong>Option D — Any OpenAI-compatible endpoint</strong></summary>

Works with Groq, Together AI, LM Studio, vLLM, and anything that speaks `/v1/chat/completions`.

Configure the URL and model in your config file (next step).

</details>

### 3. Config file

```bash
prosefmt config init
```

This creates `~/.config/prosefmt/config.toml` with all modes, providers, and prompts
ready to edit. It also checks your clipboard tools and tells you what's missing.

Open and edit:

```bash
nano ~/.config/prosefmt/config.toml    # or: vim, code, etc.
```

The minimum config for Ollama (the defaults already cover this):

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
model = "gpt-4o-mini"    # API key from OPENAI_API_KEY env var
```

### 4. Picker tool (optional)

The `prosefmt menu` command opens an interactive mode picker. Install any one of these:

```bash
sudo dnf install rofi       # Fedora  (works on X11 + Wayland)
sudo apt install rofi       # Ubuntu/Debian
sudo pacman -S rofi         # Arch

# Or any of: wofi, fuzzel, dmenu, zenity, fzf
# prosefmt auto-detects the best one available
```

> Skip this if you only use `prosefmt -s -n` (direct rewriting without a picker).

### 5. Verify

```bash
prosefmt check
```

```
✓ Clipboard tools installed
✓ Picker: rofi  (for 'prosefmt menu')
✓ Popup: zenity  (for --popup / default_output = "popup")
✓ Provider 'ollama' is reachable  (model: qwen2.5:1.5b)
```

If anything is missing, `prosefmt check` prints the exact command to fix it.

---

## Usage

### Basic usage

```bash
# Pass text as an argument (default mode: fix grammar)
prosefmt "me and him went to the store yesterday"

# Use a specific mode
prosefmt -m professional "lets meet tmrw and discuss"

# Pipe from stdin
echo "this sentense has a typo" | prosefmt

# Read from clipboard, print the result
prosefmt --clipboard

# Override provider/model for one run
prosefmt -p openai --model gpt-4o "some text here"
```

### System-wide rewriting

The killer feature. Highlight text in **any app**, press your hotkey, and the rewritten
text replaces the original — without switching windows or touching the mouse.

```bash
# Read highlighted text → rewrite → paste back in-place
prosefmt --system --notify

# With a specific mode
prosefmt -m professional -s -n

# Short form for hotkey bindings
prosefmt -s -n
```

How `--system` works:

1. Reads the highlighted text (primary selection on Linux, clipboard on macOS/Windows)
2. Sends it to the AI with the selected mode's prompt
3. Saves the original for undo
4. Writes the result to clipboard
5. Simulates Ctrl+V / Cmd+V to paste it back
6. Restores your previous clipboard content

> **Clipboard safety:** Your Ctrl+C buffer is automatically saved before pasting and
> restored afterwards. prosefmt never destroys your clipboard.

### Mode picker

`prosefmt menu` opens an interactive mode picker — no shell scripting required.

```bash
# Highlight text → pick a mode → rewrite → paste back
prosefmt menu -s -n

# Read from clipboard → pick a mode → rewrite
prosefmt menu -c
```

The picker auto-detects the best installed tool: **rofi → wofi → fuzzel → dmenu → zenity → fzf**.

#### Free-form prompts

Type anything into the picker that isn't a mode name, and prosefmt treats it as a
one-shot custom instruction:

```
┌────────────────────────────────┐
│  ✎ prosefmt                    │
│  fix                           │
│  professional                  │
│  casual                        │
│  rephrase                      │
│  > translate to French    ←────│── typed freely, runs as ad-hoc prompt
│  > make this sound excited ←───│── also works
└────────────────────────────────┘
```

No config changes needed for one-off instructions.

### Diff output

See exactly what changed — a unique feature no competitor offers:

```bash
# Show a diff of original vs. result
prosefmt --diff "Their were a few things we didnt finish"
```

```diff
--- original
+++ rewritten
-Their were a few things we didnt finish
+There were a few things we didn't finish.
```

```bash
# Diff in a popup window
prosefmt --diff --popup -s

# Diff works with any mode
prosefmt --diff -m professional "text here"
```

### Popup output

Show the result in a desktop popup window instead of replacing the original text.
Perfect for translations and summaries where you want to **read** the result, not paste it.

```bash
# Show rewrite in a popup
prosefmt --popup -s -m summarize

# Popup auto-detects: zenity → yad → kdialog → rofi → notify-send
```

Popup tools can be checked with `prosefmt check`.

### Undo

Every rewrite saves the original text. One-step undo:

```bash
# Print the original text
prosefmt undo

# Paste it back to the active window
prosefmt undo -s

# Write to clipboard
prosefmt undo -c
```

---

## Built-in Modes

prosefmt ships with 8 modes. All prompts are user-editable in `config.toml`.

| Mode | What it does | Example |
|:---|:---|:---|
| **`fix`** | Fix grammar, spelling, punctuation | `"me and him went"` → `"He and I went"` |
| **`professional`** | Polished workplace tone | `"lets meet tmrw"` → `"Let's meet tomorrow."` |
| **`casual`** | Friendly, conversational | `"Please advise on the matter"` → `"What do you think?"` |
| **`rephrase`** | Improve clarity, keep meaning | Better flow, different words |
| **`concise`** | Same meaning, fewer words | Removes filler and redundancy |
| **`expand`** | Add detail and explanation | Fills in context and nuance |
| **`summarize`** | Key points only | Condenses to 2–3 sentences |
| **`email`** | Professional email format | Adds greeting and sign-off |

```bash
# List all modes (built-in + custom)
prosefmt list

# Mode names only (useful for scripts)
prosefmt list --names
```

---

## Custom Modes

Add any number of custom modes in `config.toml`. All prompts are yours to edit —
nothing is hardcoded.

```toml
# ~/.config/prosefmt/config.toml

[modes.translate-spanish]
prompt = "Translate to Spanish. Keep technical terms in English."
label  = "🇪🇸 Spanish"

[modes.slack]
prompt = "Rewrite for Slack: brief, friendly, one or two sentences max."
label  = "Slack-ready"

[modes.eli5]
prompt = "Explain this like I'm five — simple words, short sentences, no jargon."
label  = "Simplified"

[modes.code-comments]
prompt             = "Add clear, concise comments to this code. Do not change any code."
label              = "Comments added"
preserve_structure = false
```

Use them exactly like built-in modes:

```bash
prosefmt -m translate-spanish "Good morning, how are you?"
prosefmt -m slack "Please review the pull request I opened for the auth refactor."
```

Custom modes appear automatically in `prosefmt menu` — no config changes to your
hotkey bindings needed.

### Changing the default mode

Set `default_mode` so pressing your hotkey (without a picker) uses a different mode:

```toml
default_mode = "professional"
```

Now `prosefmt -s -n` rewrites in professional tone instead of fixing grammar.

### Real-world example: translation workflow

You receive a message in Czech. You want to read it in English, write your reply,
then send it back as Czech — all without switching apps.

**Config:**

```toml
[modes.translate-english]
prompt         = "Translate to English. Keep technical terms as-is."
label          = "→ English"
default_output = "popup"      # show translation in popup — don't replace original

[modes.translate-czech]
prompt         = "Translate to Czech. Keep technical terms in English."
label          = "→ Czech"
default_output = "replace"    # replace English with Czech in-place
```

**Workflow:**

```
1. Highlight Czech message → Mod+Shift+G → pick "translate-english"
   → popup shows English translation (Czech text untouched)

2. Read the popup, type your English reply

3. Highlight English reply → Mod+Shift+G → pick "translate-czech"
   → English replaced with Czech → hit send
```

The same pattern works for any language pair — Hindi, French, Spanish, Japanese.

### Per-mode provider and model

Route different tasks to different AI models — fast local model for grammar,
powerful cloud model for complex rewrites:

```toml
[modes.fix]
prompt   = "Fix grammar, spelling, and punctuation."
provider = "ollama"
model    = "qwen2.5:1.5b"   # fast, local, CPU-friendly

[modes.review]
prompt   = "Review this text for clarity, tone, and impact."
provider = "openai"
model    = "gpt-4o"          # complex task → cloud model
```

CLI flags `--provider` and `--model` always override the mode config for that run.

### Controlling output per mode

The `default_output` field decides what happens when a mode is used via `--system`:

| Value | Behaviour |
|:---|:---|
| `"replace"` | Paste result back in-place (default) |
| `"popup"` | Show in a popup window — original text untouched |
| `"clipboard"` | Write to clipboard only, don't paste |

```toml
[modes.summarize]
prompt         = "Summarize concisely. Key points only."
default_output = "popup"      # show summary, don't replace original

[modes.translate-czech]
prompt         = "Translate to Czech."
default_output = "replace"    # paste translation, replacing original
```

---

## System-Wide Hotkeys

Two hotkey bindings give you the full prosefmt experience:

| Hotkey | Action | Command |
|:---|:---|:---|
| `Mod+G` | Instant grammar fix (default mode) | `prosefmt -s -n` |
| `Mod+Shift+G` | Open mode picker → choose any mode | `prosefmt menu -s -n` |

### Linux — i3wm / Sway

Add to `~/.config/i3/config` (or `~/.config/sway/config`):

```
bindsym $mod+g       exec --no-startup-id prosefmt -s -n
bindsym $mod+Shift+g exec --no-startup-id prosefmt menu -s -n
```

Reload with `Mod+Shift+C`.

### Linux — Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```
bind = $mainMod,       G, exec, prosefmt -s -n
bind = $mainMod SHIFT, G, exec, prosefmt menu -s -n
```

### Linux — GNOME / KDE

Add custom shortcuts in **Settings → Keyboard → Custom Shortcuts**:

| Name | Command | Shortcut |
|:---|:---|:---|
| prosefmt fix | `prosefmt -s -n` | `Super+G` |
| prosefmt menu | `prosefmt menu -s -n` | `Super+Shift+G` |

### macOS

<details>
<summary><strong>Hammerspoon</strong> (recommended)</summary>

Install [Hammerspoon](https://www.hammerspoon.org), then add to `~/.hammerspoon/init.lua`:

```lua
-- Cmd+G → grammar fix
hs.hotkey.bind({"cmd"}, "g", function()
  hs.task.new("/usr/local/bin/prosefmt", nil, {"--system", "--notify"}):start()
end)

-- Cmd+Shift+G → mode picker (uses Hammerspoon's native chooser)
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

Reload from the Hammerspoon menu bar icon.

</details>

<details>
<summary><strong>Automator / Shortcuts</strong> (simpler, fix-only)</summary>

Create a Quick Action in Automator that runs:

```bash
/usr/local/bin/prosefmt --system --notify
```

Assign a shortcut in **System Settings → Keyboard → Keyboard Shortcuts → Services**.

</details>

### Windows

<details>
<summary><strong>AutoHotkey v2</strong></summary>

Create `prosefmt-menu.ps1`:

```powershell
$modes = (& prosefmt list --names) -split "`n" | Where-Object { $_ }
$mode  = $modes | Out-GridView -Title "prosefmt — choose a mode" -PassThru
if ($mode) { & prosefmt -m $mode --system --notify }
```

AutoHotkey script:

```ahk
#g::  Run "prosefmt --system --notify",, "Hide"
#+g:: Run 'powershell -WindowStyle Hidden -File "%USERPROFILE%\prosefmt-menu.ps1"',, "Hide"
```

</details>

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       config.toml                            │
│  Single source of truth for all prompts, modes, providers    │
│  Python code NEVER references specific mode names            │
└─────────────────────────────┬────────────────────────────────┘
                              │
          ┌───────────────────▼────────────────────┐
          │            prosefmt CLI                 │
          │     Prompt-agnostic orchestrator        │
          │  (Click commands, input/output routing) │
          └───────────────────┬────────────────────┘
                              │
     ┌────────────────────────┼─────────────────────────┐
     │                        │                         │
     ▼                        ▼                         ▼
┌─────────┐          ┌──────────────┐          ┌──────────────┐
│Providers│          │  Core Engine │          │   Platform   │
│         │          │              │          │   Backends   │
│ Ollama  │          │ Prompt       │          │              │
│ OpenAI  │◄────────►│ assembly     │────────► │ Clipboard    │
│Anthropic│          │ List         │          │ Picker       │
│ Compat  │          │ preservation │          │ Popup        │
│         │          │ Undo         │          │ Notify       │
└─────────┘          └──────────────┘          │ Diff         │
                                               └──────────────┘
                                               All via subprocess
                                               to native OS tools
                                               Zero GUI dependencies
```

### Key Design Decisions

1. **Config-driven** — The Python code never contains the string `"fix"`, `"professional"`,
   or any mode name. All modes and prompts live in `config.toml`. Users can edit, reorder,
   add, or delete any mode without touching code.

2. **List-structure preservation** — When rewriting bulleted or numbered lists, prosefmt
   strips the prefixes before sending to the AI (so the model doesn't lose or mangle them),
   then re-attaches them to the result.

3. **Clipboard save/restore** — The `--system` flag wraps the paste operation in a context
   manager that saves your Ctrl+C clipboard, pastes the result, then restores the original
   clipboard content.

4. **Tool auto-detection** — The picker, popup, and notification systems each maintain a
   priority list of native tools. prosefmt picks the best available one at runtime:
   - **Picker:** rofi → wofi → fuzzel → dmenu → zenity → fzf
   - **Popup:** zenity → yad → kdialog → rofi → notify-send
   - **Notifications:** notify-send (Linux), osascript (macOS), PowerShell toast (Windows)

---

## Configuration Reference

Config file locations:

| OS | Path |
|:---|:---|
| Linux / macOS | `~/.config/prosefmt/config.toml` |
| Linux (custom) | `$XDG_CONFIG_HOME/prosefmt/config.toml` |
| Windows | `%APPDATA%\prosefmt\config.toml` |

Create it: `prosefmt config init` · View it: `prosefmt config show`

### Top-level settings

| Key | Type | Default | Description |
|:---|:---|:---|:---|
| `default_mode` | string | `"fix"` | Mode used when `-m` is not specified |
| `default_provider` | string | `"ollama"` | Provider used when a mode has no `provider` override |
| `system_prompt` | string | built-in | System instruction prepended to every mode's prompt |

### Provider fields (`[providers.<name>]`)

| Field | Description |
|:---|:---|
| `url` | API endpoint URL |
| `model` | Default model name |

> **API keys** are set via environment variables — never put them in `config.toml`.

| Provider | Environment variable |
|:---|:---|
| OpenAI | `PROSEFMT_OPENAI_API_KEY` or `OPENAI_API_KEY` |
| Anthropic | `PROSEFMT_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY` |
| OpenAI-compat | `PROSEFMT_COMPAT_API_KEY` |

### Mode fields (`[modes.<name>]`)

| Field | Type | Default | Description |
|:---|:---|:---|:---|
| `prompt` | string | required | Instruction sent to the AI |
| `label` | string | mode name | Display name in notifications and picker |
| `preserve_structure` | bool | `true` | Re-attach bullet/number list prefixes after rewrite |
| `provider` | string | global default | Override provider for this mode |
| `model` | string | provider default | Override model for this mode |
| `default_output` | string | `"replace"` | Output routing: `"replace"`, `"popup"`, or `"clipboard"` |

### Full example config

```toml
# ~/.config/prosefmt/config.toml

default_mode     = "fix"
default_provider = "ollama"

system_prompt = """You are a text rewriter. Output ONLY the rewritten text.
No preamble, no explanation, no 'Here is'.
Keep technical terms, code, URLs, and formatting unchanged."""

# ── Providers ──────────────────────────────────────────────────

[providers.ollama]
url   = "http://localhost:11434"
model = "qwen2.5:1.5b"

[providers.openai]
model = "gpt-4o-mini"
# API key: OPENAI_API_KEY env var

[providers.anthropic]
model = "claude-haiku-4-5-20251001"
# API key: ANTHROPIC_API_KEY env var

# [providers.openai-compat]
# url   = "https://api.groq.com/openai/v1"
# model = "llama-3.3-70b-versatile"

# ── Modes ──────────────────────────────────────────────────────

[modes.fix]
prompt = "Fix grammar, spelling, and punctuation. Keep the same meaning."
label  = "Grammar fixed"

[modes.professional]
prompt = "Rewrite in a professional tone for work emails."
label  = "Made professional"

[modes.casual]
prompt = "Rewrite in a casual, friendly tone."
label  = "Made casual"

[modes.rephrase]
prompt = "Rephrase for better clarity. Keep the same meaning."
label  = "Rephrased"

[modes.concise]
prompt = "Make shorter. Remove unnecessary words. Same meaning."
label  = "Made concise"

[modes.expand]
prompt = "Expand with more detail and explanation."
label  = "Expanded"

[modes.email]
prompt             = "Rewrite as a professional email with greeting and sign-off."
label              = "Formatted as email"
preserve_structure = false

[modes.summarize]
prompt             = "Summarize concisely. Key points only. 2-3 sentences."
label              = "Summarized"
preserve_structure = false
default_output     = "popup"

# ── Custom examples (uncomment to enable) ──────────────────────

# [modes.translate-english]
# prompt         = "Translate to English. Output only the translation."
# label          = "→ English"
# default_output = "popup"
# model          = "qwen2.5:7b"

# [modes.explain]
# prompt         = "Explain this in simple terms. Be brief."
# label          = "Explained"
# default_output = "popup"
```

---

## CLI Reference

```
prosefmt [TEXT]                    Rewrite TEXT (default mode: fix)
prosefmt -m MODE [TEXT]            Rewrite with a specific mode
prosefmt -s / --system             Read highlighted text, paste result back
prosefmt -c / --clipboard          Read from clipboard
prosefmt -n / --notify             Show desktop notification when done
prosefmt --popup                   Show result in popup window
prosefmt --diff                    Show diff of original vs. result
prosefmt -p / --provider PROVIDER  Override AI provider
prosefmt --model MODEL             Override AI model

prosefmt menu                     Open mode picker, then rewrite
prosefmt menu -s -n               Highlight → picker → rewrite → paste back
prosefmt menu -c                  Clipboard → picker → rewrite

prosefmt list                     List all modes (human-readable)
prosefmt list --names             Mode names only (one per line)
prosefmt undo                     Print the original text from last rewrite
prosefmt undo -s                  Paste original back to active window
prosefmt check                    Verify clipboard, picker, popup, provider
prosefmt config init              Create config file
prosefmt config show              Show active configuration

prosefmt --version                Show version
prosefmt --help                   Show help
```

### Flag combinations cheatsheet

| Goal | Command |
|:---|:---|
| Fix grammar of highlighted text | `prosefmt -s -n` |
| Choose mode, rewrite highlighted text | `prosefmt menu -s -n` |
| Fix grammar from clipboard | `prosefmt -c` |
| Rewrite in professional tone | `prosefmt -m professional "text"` |
| See what changed | `prosefmt --diff "text with erors"` |
| Translate and show popup | `prosefmt --popup -m translate-english -s` |
| Use OpenAI for this one run | `prosefmt -p openai --model gpt-4o "text"` |
| Pipe through prosefmt | `cat draft.txt \| prosefmt -m concise` |

---

## FAQ

<details>
<summary><strong>What happens to my clipboard when using --system?</strong></summary>

prosefmt saves your current clipboard (Ctrl+C buffer) before pasting, then
restores it afterwards. Your clipboard is never destroyed.

</details>

<details>
<summary><strong>Can I use multiple AI providers at the same time?</strong></summary>

Yes. Configure all your providers in `config.toml`, then assign different modes to different
providers using the `provider` and `model` fields on each mode. For example, use Ollama for
quick grammar fixes and OpenAI for complex rewrites.

</details>

<details>
<summary><strong>Does it work offline?</strong></summary>

Yes, with Ollama. Once you've pulled a model (`ollama pull qwen2.5:1.5b`), everything
runs locally on your machine with no internet connection needed.

</details>

<details>
<summary><strong>How do I use it with LM Studio / vLLM / Groq / Together AI?</strong></summary>

Any service that speaks the OpenAI `/v1/chat/completions` format works out of the box:

```toml
[providers.openai-compat]
url   = "http://localhost:1234/v1"    # LM Studio default
model = "your-model-name"
```

Set `PROSEFMT_COMPAT_API_KEY` if the service requires authentication.

</details>

<details>
<summary><strong>I get garbage output for translations to Hindi / Chinese / Arabic</strong></summary>

Small language models (1.5B–3B parameters) struggle with non-Latin scripts.
Use a larger model for translation modes:

```toml
[modes.translate-hindi]
prompt = "Translate to Hindi. Keep technical terms in English."
model  = "qwen2.5:7b"    # needs a larger model
```

Or route translation to a cloud provider: `provider = "openai"`.

</details>

<details>
<summary><strong>Can I write prompts optimized for my specific model?</strong></summary>

Yes — that's the whole point. Every prompt in `config.toml` is yours to edit. Small local
models work best with short, direct, single-instruction prompts. Cloud models can handle
more nuanced instructions. The config file includes tips for prompt writing.

</details>

<details>
<summary><strong>How is prosefmt different from Writing Tools / AI Shortcuts?</strong></summary>

Those are GUI desktop apps (100–200 MB, Electron or PyQt5). They can't be piped, scripted,
or used from hotkeys without their own UI. Most are broken on Wayland. prosefmt is a 15 KB
CLI tool with 2 Python dependencies that composes with Unix pipes and works everywhere.

</details>

---

## Development

```bash
git clone https://github.com/digitronik/prosefmt.git
cd prosefmt
uv sync --extra dev

# Git hooks (ruff lint + format)
uv run pre-commit install
uv run pre-commit run --all-files

# Run tests
uv run pytest -v

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

CI runs lint + tests on Python 3.11–3.14 across Linux, macOS, and Windows on every push
and pull request.

Contributions welcome — open an issue or pull request on
[GitHub](https://github.com/digitronik/prosefmt).

---

## License

[MIT](LICENSE)
