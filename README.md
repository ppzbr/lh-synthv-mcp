# lh-synthv-mcp

Give a program — not a person — control of the **already open** project in
**Synthesizer V Studio**: read its tracks, add and edit notes, set lyrics, pitch,
phonemes and timing, and run the transport. Nothing is clicked or typed to make
that happen.

Synthesizer V is the one editor here that ships a scripting API: the host loads
`.lua` files and hands them the `SV`, `Project` and `Editor` objects. So the
in-editor half of this bridge is **a resident Lua agent the editor itself loads** —
no DLL, no injection, no memory reading, no UI automation, no vendor patch.

Lua has no sockets. The agent therefore talks to Python through folders: it polls a
command folder and answers into a result folder. The **MCP server is the Python
side** (`lhai-mcp`), which turns those folder round-trips into typed tools.

```
 MCP client  <-->  lhai-mcp (Python)  <-->  folder IPC  <-->  LHai Agent (Lua, in the editor)
```

## Requirements

* Windows.
* **Synthesizer V Studio 1.x and/or 2.x.** Both are supported; they are separate
  products with separate script folders, separate Lua hosts and separate processes,
  and the installer writes into every generation it finds.
* Python 3.10+.

The client is stdlib at import time. The only installed dependencies are the `mcp`
transport and `comtypes`.

## Install

```powershell
git clone https://github.com/ppzbr/lh-synthv-mcp
cd lh-synthv-mcp
python -m pip install -e ".[mcp]"
```

Then, from an MCP client (or in plain Python — `from lhai.live import synthv_live`;
every `foo()` below is `synthv_live.foo()`):

```python
synthv_live_status()      # read this first
synthv_live_install()     # writes the agent into every generation found
```

**One click is not automatable, and asking for it is not a workaround.** A SynthV
script has no programmatic entry point: the host runs one only from its *Scripts*
menu. So ask the human to start it — *Scripts → Start Script → LHai Agent* — once
per generation per install. Everything after that click is programmatic.

```python
synthv_live_status()      # the agent now answers
synthv_live_version()     # host identity, generation, editor version
synthv_live_probe()       # which API calls this build answers, and how they were found
```

The agent is idempotent: a second start replaces the previous instance itself. Five
measured starts produced five `# agent started` lines and one live agent.

## Driving it

```python
synthv_live_state(group=1)                  # what the open project holds
synthv_live_cmd(["VERSION", "TRACKS"])      # a batch of verbs, applied in order
synthv_live_cmd([...], edition="sv1")       # pick a generation when both are open
synthv_live_push(project="song.svp")        # push a project file's track into the editor
```

`synthv_live_cmd` takes a list of verbs — the agent's own command language:

| verb | does |
|---|---|
| `VERSION`, `PROBE` | identity, and which host calls this build answers |
| `TRACKS`, `TRACKSEL` | list tracks / select one (`TRACKSEL` is handed the editor's own object, not an index) |
| `GROUP` | group operations |
| `NOTE`, `LYRIC`, `PITCH`, `PHONEME`, `TIMESHIFT`, `DEL` | note-level editing |
| `STATE` | read the current track back |
| `CLEAR` | clear the current track |
| `SEEK`, `PLAY`, `STOP` | transport |
| `UNDO`, `REDO`, `SAVE` | **absent from the vendor API** — see below |

## What is verified, and what is not

* **Synthesizer V Studio 2** — live-verified end to end: the agent loaded by the
  editor, commands round-tripped, notes edited in the open project. Everything in
  the tables above is measured, not inferred.
* **Synthesizer V Studio 1.x** — the hard part was finding the script folder, and
  that is root-caused: `HKCU\Software\Dreamtonics\Synthesizer V Studio\DataLocation`
  is routinely **stale** (on the development machine it pointed at a folder nothing
  had written to in a month). The status tool therefore weighs every candidate and
  picks the one holding the newest content; `editions[].roots` shows all of them,
  best first. SV1 was not driven end to end in that session, so treat SV1 as
  *installable and instrumented*, not *proven*.
* **`UNDO` / `REDO` / `SAVE` are not in the vendor's Lua API.** They are not
  omitted here by laziness; there is no call to make. The agent refuses them rather
  than pretending.

## Traps this repository already handles

* **Lua indexes from 1.** Converted in one helper, so the Python side can keep
  thinking in the editor's own numbering.
* **There is no `newUndoBlock`.** It is `Project.newUndoRecord()`.
* **Each generation gets its own folder** (`ipc/sv1`, `ipc/sv2`), so two running
  editors cannot claim the same batch and apply it twice. A batch file is removed as
  it is read.

## When something looks wrong

| symptom | cause |
|---|---|
| the menu has no `LHai Agent` | the folder written to is not the folder the editor scans — compare `editions[].root` with what the editor's own *Scripts* menu lists, and read `roots` |
| every built-in appears twice in the menu | the script folder contains a nested copy; the scan is recursive — remove the duplicate, do not assume two installs |
| installed, but never answers | the editor was already running when it was installed: rescan or restart |
| answers with old behaviour | a stale agent from an earlier build is still running: **Stop all running scripts**, then start again |

## Layout

| path | what |
|---|---|
| `prompt.md` | the paste-ready brief: the whole install-and-drive story for an agent that has never seen this repository |
| `lhai/live/` | the client: `synthv_live.py`, the Lua template `synthv_lua.py`, the folder IPC, and the shared live layer |
| `lhai/mcp/` | the MCP server that exposes the above as tools |
| `docs/mcp-engine-bridge.md` | the contract every bridge in this family follows: transport, tool vocabulary, diagnostics |
| `docs/live-control.md`, `docs/mcp-singing.md` | the live layer and the singing-model background |
| `tests/` | `test_synthv_lua_host.py` runs the Lua generation against a host stub; the rest is the client's own suite |
| `MANIFEST.txt` | sha256 of every tracked file; `python tools/make-manifest.py --check` re-derives it |

This repository also carries the client's adapters for the other editors in the
family (`lhai/mcp/engines/`). They are inert here: nothing in them runs unless that
editor is the target. The tree is shipped whole so that one client has one copy and
one test suite, rather than a fork per engine.

## Tests

```powershell
python -m pip install -e .
python -m pytest
```

## Licence

MIT. See `LICENSE`.
