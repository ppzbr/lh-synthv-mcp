# Synthesizer V — install and drive

> Paste everything below the rule into an agent that has shell access to the Windows
> machine running Synthesizer V Studio. It is written to stand alone: the agent needs
> this repository and nothing else explained to it.

---

## Goal

Give a program — not a person — control of the **already open** project in
Synthesizer V Studio: read the tracks, add and edit notes, set lyrics, pitch,
phonemes and timing, and run the transport. Nothing may be clicked or typed to make
that happen.

**How it is done.** Synthesizer V is the only editor in this repository with a
vendor scripting API: the host loads `.lua` scripts and hands them the `SV`,
`Project` and `Editor` objects. So the bridge is a **resident Lua agent that the
editor itself loads** — no DLL, no injection, no memory reading, no UI automation.

**The one thing that cannot be automated.** A SynthV script has no programmatic
entry point. The host runs one only from its *Scripts* menu. Writing the file is
automated; the click that starts it is not. Ask the human for that click, once per
generation per install.

## Rules

1. Touch nothing outside this repository except the agent file written into the
   editor's own script folder.
2. Never kill the editor process.
3. Never substitute UI automation, keystrokes or clipboard for the one menu click.
4. If a step fails, stop at that step and report exactly what happened.
5. Work only inside this repository. Nothing else on the machine is yours to change.

## Step 0 — the repository

```powershell
git clone https://github.com/ppzbr/lh-synthv-mcp
cd lh-synthv-mcp
```

Every command below runs from the repository root.

## Step 1 — dependencies

```powershell
python -m pip install -e ".[mcp]"
python -m pip install comtypes
```

* `.[mcp]` brings the `mcp` transport and `comtypes` and nothing heavier: the client
  is stdlib at import time, on purpose, so this installs on a bare Python.
* `comtypes` is what `lhai/live/uia.py` and `lhai/live/cevio_com.py` import, and it is
  declared in the `[mcp]` extra, so the line above is enough. On a checkout older than
  that declaration, install it by hand: `python -m pip install comtypes`.

Start the MCP server (`lhai-mcp` for stdio, `lhai-mcp http` for streamable HTTP) and
call the tools below from your client. If you have no MCP client: the same functions
are plain Python, `from lhai.live import synthv_live`, and every `foo()` named here
is `synthv_live.foo()`.

## Step 2 — see what the code sees

```
synthv_live_status()
```

Read it before writing anything.

| field | meaning |
|---|---|
| `editions[]` | one row per generation found: `root`, `scripts`, `exe`, `data_location`, and **`roots`** — every candidate folder that was weighed, best first |
| `editions[].root` | the folder the editor is **actually writing to**, chosen by which candidate holds the newest content |
| `running_editions` | which generation is open right now |
| `stale_path` | `true` when the installed agent is older than the template in this repository |

Both generations are supported, and they are separate products with separate script
folders, separate Lua hosts and separate processes: **Synthesizer V Studio 1.x** and
**Synthesizer V Studio 2.x**. The installer writes into every generation it finds.

Two traps, both hit for real:

* **The registry is not the answer.** `HKCU\Software\Dreamtonics\Synthesizer V
  Studio\DataLocation` is routinely stale — on the machine this was written on it
  pointed at a folder nothing had written to in a month while the live folder was
  elsewhere. The code gathers every candidate (`%APPDATA%`, the Documents folder *as
  Windows defines it* — it is redirectable, and there it is `D:\文档` — and the
  recorded `DataLocation`) and takes the newest. `roots` shows what lost.
* **A 1.x path that is neither under `%APPDATA%` nor the recorded `DataLocation` is
  correct, not a bug.** Do not "fix" it.

## Step 3 — install the agent

```
synthv_live_install()
```

It writes the agent into each generation's live script folder, creates the IPC
folder up front (Lua cannot create directories), and returns the paths, a `source`
hash, whether an existing copy was `stale_path`, and a `next` string. **Hand `next`
to the human verbatim** — it is step 4.

## Step 4 — the human's one click, per running generation

1. **Scripts → Rescan** — *only* if the agent was installed while the editor was
   already running. The editor scans its script folder **once, at launch**, and does
   not watch it: a file written afterwards is invisible until a rescan or a restart.
2. **Scripts → Start Script → LHai Agent**.

Then verify:

```
synthv_live_status()     # the agent now answers
synthv_live_version()    # host identity, generation, editor version
synthv_live_probe()      # which API calls this build answers, and how they were found
```

If an older copy is already running it cannot retire itself — the host stops the
previous instance itself, and five measured starts produced five `# agent started`
lines and zero `# agent retired` lines:

> **Scripts → Stop all running scripts**, then start it once. That is the only
> reliable way back to a known state.

## Step 5 — drive it

```
synthv_live_state(group=1)                  # what the open project holds
synthv_live_cmd(["VERSION", "TRACKS"])      # a batch of verbs, applied in order
synthv_live_cmd([...], edition="sv1")       # choose a generation when both are open
synthv_live_push(project="song.svp")        # push a project file's track into the editor
```

`synthv_live_cmd` takes a list of verbs — the agent's own command language. Each verb
answers one line:

```
R <VERB> ok <payload>          or          R <VERB> err <reason>
```

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

A batch is handed over as a file that the reader removes as it takes it, so no batch
is ever applied twice. The reader takes its start offset from the result file's
current size and never truncates it, so earlier batches stay readable.

## Step 6 — what works, and what does not

**Works:** everything note-level, plus transport, on both generations.

**Does not, and refuses honestly:**

* `UNDO`, `REDO`, `SAVE` — the host's own objects have no such entry point. This was
  confirmed by enumerating the host's own member list, not assumed. The agent answers
  `err`. Saving the project stays with the human or the editor.
* Starting the script — see the one click above.
* Updating a running agent by installing again. Rescan or restart.

`PROBE` is the honest way to ask what a build supports: it merges the host's own
member list with the names the vendor manual documents, and reports how many owners
it enumerated. Enumeration is **tried, never required** — the older 1.x Lua engine
may not answer `pairs()`, and `PROBE` still works.

Never test for a method with `type(obj.name) == "function"`: this host binds methods
as *callable userdata*, so that test reports "no" for every method that exists. Ask
with `obj[name] ~= nil`, and let the call itself report failure.

## Step 7 — when it goes wrong

| symptom | cause |
|---|---|
| the menu has no `LHai Agent` | the folder written to is not the folder the editor scans — compare `editions[].root` with what the editor's own *Scripts* menu lists, and read `roots` |
| every built-in appears twice in the menu | the script folder contains a nested copy; the scan is recursive — remove the duplicate, do not assume two installs |
| installed, but never answers | the editor was already running when it was installed: rescan or restart |
| answers with old behaviour | a stale agent from an earlier build is still running: **Stop all running scripts**, then start again |

Stop at the first unexplained failure and report the text you saw. Do not restart or
kill the editor to "fix" a step: an editor holding work is not yours to close.
