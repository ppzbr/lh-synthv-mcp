"""Execute the installed Lua agent against a miniature Synthesizer V host.

Every other test of the agent reads its source.  That is what let the first
live version ship with two calls that do not exist - ``SV:setTimeout(callback,
ms)`` (the manual's order is the other way round) and ``editor:getProject()``
(``MainEditorView`` owns focus, not the document) - and the editor answered with
``attempt to call a nil value`` before the agent ever polled.

So this file runs the thing.  A small Lua prelude builds the objects the
scripting manual documents - ``SV``, ``MainEditorView``, ``Project``, ``Track``,
``NoteGroupReference``, ``NoteGroup``, ``Note``, ``PlaybackControl`` - and
deliberately leaves out everything the manual does not list.  A name the agent
invents then raises here, in a test, instead of in the editor.

The prelude also arms ``SV:setTimeout`` into a global so the harness can drive
the poll loop by hand, which exercises the real command/result files end to end.

Lupa is an optional extra (``pip install lupa``); without it these tests skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lhai.live import synthv_lua

lupa = pytest.importorskip("lupa", reason="pip install lupa to run the Lua agent")


#: The whole host, in Lua.  Methods are written exactly as the manual lists them
#: and nothing else is defined, so an unsupported call is an error here.
PRELUDE = r"""
-- ---------------------------------------------------------------- recording
__CALLS = {}
local function record(name) __CALLS[#__CALLS + 1] = name end

-- The real host counts arguments and refuses extras: `note:setLyrics(a, b)`
-- answers "expected 1 argument, got 2", which is how a missing pair of
-- parentheses around a string.gsub return value was found.  Lua itself ignores
-- extra arguments, so a permissive mock would have hidden exactly that bug.
-- The setters below are strict for this reason.
local function expect_args(wanted, got)
  if got ~= wanted then
    error(string.format("expected %d argument(s), got %d", wanted, got), 3)
  end
end

-- ---------------------------------------------------------------- Note
local Note = {}
Note.__index = Note
function Note.new()
  return setmetatable({ onset = 0, duration = 705600000, pitch = 60, lyrics = "" }, Note)
end
function Note:getOnset() return self.onset end
function Note:setOnset(...) expect_args(1, select("#", ...)) self.onset = (...) return true end
function Note:getDuration() return self.duration end
function Note:setDuration(...) expect_args(1, select("#", ...)) self.duration = (...) return true end
function Note:getEnd() return self.onset + self.duration end
function Note:getPitch() return self.pitch end
function Note:setPitch(...) expect_args(1, select("#", ...)) self.pitch = (...) return true end
function Note:getLyrics() return self.lyrics end
function Note:setLyrics(...) expect_args(1, select("#", ...)) self.lyrics = (...) return true end
function Note:getPhonemes() return self.phonemes or "" end
function Note:setPhonemes(...) expect_args(1, select("#", ...)) self.phonemes = (...) return true end
function Note:getDetune() return self.detune or 0 end
function Note:setDetune(...) expect_args(1, select("#", ...)) self.detune = (...) return true end
function Note:getLanguageOverride() return self.language or "" end
function Note:setLanguageOverride(...) expect_args(1, select("#", ...)) self.language = (...) return true end
function Note:getMusicalType() return "sing" end
function Note:setMusicalType(v) return true end
function Note:setTimeRange(a, b) return true end
function Note:getAttributes() return {} end
function Note:setAttributes(v) return true end
function Note:getRapAccent() return "" end
function Note:setRapAccent(v) return true end

-- ---------------------------------------------------------------- NoteGroup
local NoteGroup = {}
NoteGroup.__index = NoteGroup
function NoteGroup.new(name)
  return setmetatable({ notes = {}, name = name or "Lead" }, NoteGroup)
end
function NoteGroup:addNote(n) table.insert(self.notes, n) return true end
function NoteGroup:removeNote(i) table.remove(self.notes, i) return true end
function NoteGroup:getNote(i) return self.notes[i] end
function NoteGroup:getNumNotes() return #self.notes end
function NoteGroup:getUUID() return self.name .. "-uuid" end
function NoteGroup:getName() return self.name end
function NoteGroup:getParameter(t, n) return nil end
function NoteGroup:addPitchControl() return true end
function NoteGroup:getPitchControl(i) return nil end
function NoteGroup:getNumPitchControls() return 0 end
function NoteGroup:removePitchControl() return true end

-- ------------------------------------------------------- NoteGroupReference
-- A track holds references; the notes live in the group the reference targets.
local Ref = {}
Ref.__index = Ref
function Ref.new(group) return setmetatable({ group = group }, Ref) end
function Ref:getTarget() return self.group end
function Ref:getVoice() return nil end
function Ref:isMain() return true end
function Ref:isMuted() return false end

-- ---------------------------------------------------------------- Track
local Track = {}
Track.__index = Track
function Track.new(name, refs) return setmetatable({ name = name, refs = refs or {} }, Track) end
function Track:getName() return self.name end
function Track:getNumGroups() return #self.refs end
function Track:getGroupReference(i) return self.refs[i] end
function Track:addGroupReference(r) table.insert(self.refs, r) return true end
function Track:removeGroupReference(i) table.remove(self.refs, i) return true end
function Track:getDuration() return 705600000 end
function Track:getMixer() return nil end
function Track:getDisplayColor() return "ff0000" end
function Track:getDisplayOrder() return 0 end
function Track:isBounced() return false end

-- ---------------------------------------------------------------- Project
local TimeAxis = {}
function TimeAxis:getAllTempoMarks() return { 120 } end
function TimeAxis:getTempoMarkAt(b) return 120 end
function TimeAxis:getSecondsFromBlick(b) return b / 705600000 * 0.5 end
function TimeAxis:getBlickFromSeconds(s) return math.floor(s * 705600000 * 2) end

local Project = {}
Project.__index = Project
function Project.new()
  local self = setmetatable({ tracks = {} }, Project)
  self:addTrack("Lead", "Lead", "Harmony")
  self:addTrack("Backing", "Backing")
  return self
end
function Project:addTrack(name, ...)
  local refs = {}
  for _, group_name in ipairs({ ... }) do refs[#refs + 1] = Ref.new(NoteGroup.new(group_name)) end
  local track = Track.new(name, refs)
  table.insert(self.tracks, track)
  return track
end
function Project:getNumTracks() return #self.tracks end
function Project:getTrack(i) return self.tracks[i] end
function Project:getTimeAxis() return TimeAxis end
function Project:getFileName() return "mock.svp" end
function Project:getDuration() return 705600000 end
function Project:newUndoRecord() record("Project:newUndoRecord") return true end
function Project:removeTrack(i) table.remove(self.tracks, i) return true end
function Project:addNoteGroup() return NoteGroup.new() end
function Project:getNoteGroup(i) return nil end
function Project:getNumNoteGroupsInLibrary() return 0 end
function Project:removeNoteGroup() return true end

-- ---------------------------------------------------------------- selection
local Selection = {}
Selection.__index = Selection
function Selection:selectGroup(ref) __SELECTED = ref return true end
function Selection:unselectGroup(ref) return true end
function Selection:clearAll() return true end

-- ---------------------------------------------------------------- playback
local Playback = {}
Playback.__index = Playback
function Playback:play() record("playback:play") return true end
function Playback:pause() record("playback:pause") return true end
function Playback:stop() record("playback:stop") return true end
function Playback:seek(p) __PLAYHEAD = p return true end
function Playback:loop(a, b) return true end
function Playback:getPlayhead() return __PLAYHEAD or 0 end
function Playback:getStatus() return "stopped" end

__PLAYHEAD = 0
__PROJECT = Project.new()
__PLAYBACK = Playback

-- MainEditorView, exactly as the manual lists it: getCurrentTrack,
-- getCurrentGroup, getSelection, getNavigation.  No getProject, and no
-- setCurrentTrack - the first version called getProject here and died.
__EDITOR = {}
function __EDITOR:getCurrentTrack() return __PROJECT:getTrack(1) end
function __EDITOR:getCurrentGroup() return __PROJECT:getTrack(1):getGroupReference(1) end
function __EDITOR:getSelection() return Selection end
function __EDITOR:getNavigation() return {} end

__ARRANGEMENT = {}
function __ARRANGEMENT:getSelection() return Selection end

-- ---------------------------------------------------------------- SV
SV = {}
--: Published by the host; the agent is expected to prefer it over its literal.
SV.QUARTER = 705600000
function SV:getProject() return __PROJECT end
function SV:getMainEditor() return __EDITOR end
function SV:getPlayback() return __PLAYBACK end
function SV:getArrangement() return __ARRANGEMENT end
function SV:getHostInfo()
  return {
    osType = "Windows", osName = "Windows 11",
    hostName = "Synthesizer V Studio 2", hostVersion = "2.1.0",
    hostVersionNumber = 131072, languageCode = "en-US"
  }
end
function SV:create(kind)
  if kind == "Note" then return Note.new() end
  error("SV:create: unknown object '" .. tostring(kind) .. "'")
end
function SV:setTimeout(ms, cb) __TIMEOUT = { ms = ms, cb = cb } end
function SV:finish() __FINISHED = true __TIMEOUT = nil end
function SV:showMessageBox(title, text) __MESSAGE = { title = title, text = text } end

-- ------------------------------------------------------------------ binding
-- Synthesizer V hands its methods out as *callable userdata*, not as Lua
-- functions: `SV:getProject()` works while `type(SV.getProject)` is not
-- "function".  Lua cannot construct a real userdata, so the mock uses the
-- closest thing - a table with __call - which reproduces the trap exactly:
-- callable, but `type()` is not "function".  Binding SV and the editor this way
-- is the whole reason this harness exists, because a probe that tested
-- `type(fn) == "function"` passed against plain functions and then reported an
-- entirely empty API inside the real editor, and nothing caught it.
function __as_callable(fn)
  return setmetatable({}, { __call = function(_, self, ...) return fn(self, ...) end })
end

function __bind_as_callable(t)
  for name, fn in pairs(t) do
    if type(fn) == "function" then t[name] = __as_callable(fn) end
  end
  return t
end

__bind_as_callable(SV)
__bind_as_callable(__EDITOR)
"""


def _start(ipc_dir: Path, *, with_set_current_track: bool = False, extra: str = ""):
    """Load the mock host, then the real agent, and hand back the Lua runtime.

    ``extra`` is Lua run against the host between the two, for the variants that
    need a differently shaped host (one with an undo entry point, one with no
    selection).
    """
    lua = lupa.LuaRuntime()
    lua.execute(PRELUDE)
    if with_set_current_track:
        # A second dialect of the same host: some builds may hang the method off
        # the editor even though the manual does not list it.  Bound as userdata
        # here too, so the caller's existence test cannot rely on type().
        lua.execute(
            "function __EDITOR:setCurrentTrack(i) __CURRENT = i return true end\n"
            "__EDITOR.setCurrentTrack = __as_callable(__EDITOR.setCurrentTrack)"
        )
    if extra:
        lua.execute(extra)
    lua.execute(synthv_lua.source(ipc_dir))
    # The host calls the script's entry points; so does the mock, for the same
    # reason - a script that only works when main() is called by hand is not
    # installed correctly.
    lua.eval("main()")
    return lua


def _tick(lua) -> None:
    """Run one turn of the agent's poll loop."""
    lua.eval("__TIMEOUT").cb()


def _answers(ipc_dir: Path) -> dict[str, str]:
    """verb -> 'ok'/'err' from the result file the agent wrote."""
    path = ipc_dir / "synthv_result.txt"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("R "):
            continue
        body = line[2:]
        verb, _, rest = body.partition(" ")
        status = rest.partition(" ")[0]
        out[verb] = status
    return out


def _payloads(ipc_dir: Path) -> dict[str, str]:
    """verb -> the payload of its *last* reply, for the failure text."""
    path = ipc_dir / "synthv_result.txt"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("R "):
            continue
        # "R VERB ok payload"
        verb, _, tail = line[2:].partition(" ")
        _, _, payload = tail.partition(" ")
        out[verb] = payload
    return out


def _run(lua, ipc_dir: Path, commands: list[str]) -> dict[str, str]:
    ipc_dir.mkdir(parents=True, exist_ok=True)
    (ipc_dir / "synthv_cmd.txt").write_text(
        "\n".join([*commands, "END testtoken"]) + "\n", encoding="utf-8"
    )
    _tick(lua)
    return _answers(ipc_dir)


def _probe(lua, ipc_dir: Path) -> tuple[dict[str, str], str]:
    """PROBE's answer as name -> the type the host binds it as, plus the raw line."""
    _run(lua, ipc_dir, ["PROBE"])
    line = [
        item
        for item in (ipc_dir / "synthv_result.txt").read_text(encoding="utf-8").splitlines()
        if item.startswith("R PROBE ok ")
    ][0]
    payload = line.split(" ", 3)[3]
    return dict(item.split("=", 1) for item in payload.split(",") if "=" in item), payload


# --------------------------------------------------------------------------- #
# the host contract
# --------------------------------------------------------------------------- #
def test_client_info_is_the_shape_the_host_requires(tmp_path: Path) -> None:
    info = _start(tmp_path).eval("getClientInfo()")
    assert info["name"] == "LHai Agent"
    for key in ("category", "author", "versionNumber", "minEditorVersion"):
        assert info[key] is not None, key
    # 65536 is 1.0.0; anything above it would make the host refuse to load the
    # script on an older build.
    assert int(info["minEditorVersion"]) == 65536


def test_agent_starts_and_arms_a_non_blocking_timer(tmp_path: Path) -> None:
    """The exact failure Nono hit: main() must run without touching a nil value."""
    lua = _start(tmp_path)
    timeout = lua.eval("__TIMEOUT")
    assert timeout is not None, "the poll loop never armed SV:setTimeout"
    assert int(timeout["ms"]) == 250
    # And it must never have called SV.finish(), which would end the script.
    assert lua.eval("__MESSAGE") is None


def test_agent_only_polls_while_a_command_file_exists(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    _tick(lua)
    # A tick with nothing queued is a no-op, not an error.
    assert _answers(tmp_path) == {}
    assert lua.eval("__TIMEOUT") is not None


# --------------------------------------------------------------------------- #
# the wire protocol, end to end through the real files
# --------------------------------------------------------------------------- #
def test_a_batch_pushes_notes_and_reads_them_back(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    answers = _run(
        lua,
        tmp_path,
        ["GROUP 1", "CLEAR", "NOTE 0 705600000 64 la -", "NOTE 705600000 352800000 67 - zh", "STATE"],
    )
    assert answers["CLEAR"] == "ok"
    assert answers["NOTE"] == "ok"
    assert answers["STATE"] == "ok"

    # The notes really landed in the mock project's first group.
    notes = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget().notes")
    assert len(notes) == 2
    assert notes[1]["lyrics"] == "la"
    assert notes[2]["pitch"] == 67
    # A "-" language must stay unset rather than become the string "-".
    assert notes[2]["language"] == "zh"
    assert notes[1]["language"] is None


def test_group_index_selects_the_group_it_names(tmp_path: Path) -> None:
    """The first version ignored the index and always edited what was in focus."""
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["GROUP 2", "NOTE 0 705600000 60 do -"])
    assert answers["NOTE"] == "ok"

    first = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget():getNumNotes()")
    second = lua.eval("__PROJECT:getTrack(1):getGroupReference(2):getTarget():getNumNotes()")
    assert (first, second) == (0, 1)


def test_an_undocumented_call_is_reported_not_thrown(tmp_path: Path) -> None:
    """One bad command must not abort the batch before its RESULT line."""
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["SAVE C:\\nowhere\\x.svp", "GROUP 1", "STATE"])
    # SAVE has no documented entry point, so it reports err - and the batch
    # continues, which is what keeps the client from waiting out its timeout.
    assert answers["SAVE"] == "err"
    assert answers["STATE"] == "ok"
    assert "testtoken" in (tmp_path / "synthv_result.txt").read_text(encoding="utf-8")


def test_every_verb_answers(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    verbs = {
        "GROUP": ["GROUP 1"],
        "TRACKS": ["TRACKS"],
        "CLEAR": ["CLEAR"],
        "NOTE": ["NOTE 0 705600000 64 la -"],
        "STATE": ["STATE"],
        "LYRIC": ["LYRIC 0 la"],
        "PHONEME": ["PHONEME 0 l_a"],
        "PITCH": ["PITCH 1"],
        "TIMESHIFT": ["TIMESHIFT 10"],
        "DEL": ["DEL 0"],
        "PLAY": ["PLAY"],
        "STOP": ["STOP"],
        "SEEK": ["SEEK 100"],
        "UNDO": ["UNDO"],
        "REDO": ["REDO"],
        "SAVE": ["SAVE x.svp"],
        "VERSION": ["VERSION"],
        "PROBE": ["PROBE"],
        "TRACKSEL": ["TRACKSEL 1"],
    }
    for verb, commands in verbs.items():
        ipc = tmp_path / verb
        answers = _run(_start(ipc), ipc, commands)
        assert answers.get(verb) in {"ok", "err"}, f"{verb} never answered"


def test_unknown_verb_is_answered_rather_than_ignored(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["NOSUCHTHING 1", "GROUP 1"])
    assert answers["NOSUCHTHING"] == "err"
    assert answers["GROUP"] == "ok"


# --------------------------------------------------------------------------- #
# the calls the manual does promise
# --------------------------------------------------------------------------- #
def test_playback_goes_through_the_documented_control(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["PLAY", "SEEK 500", "STOP"])
    assert answers["PLAY"] == "ok"
    assert answers["SEEK"] == "ok"
    assert answers["STOP"] == "ok"
    assert lua.eval("__PLAYHEAD") == 500
    assert "playback:play" in list(lua.eval("__CALLS").values())


def test_tracks_reports_every_track_and_its_group_count(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    _run(lua, tmp_path, ["TRACKS"])
    line = [
        item
        for item in (tmp_path / "synthv_result.txt").read_text(encoding="utf-8").splitlines()
        if item.startswith("R TRACKS ")
    ][0]
    assert "T 0 2 Lead" in line
    assert "T 1 1 Backing" in line


def test_version_names_the_host_it_runs_in(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    _run(lua, tmp_path, ["VERSION"])
    line = [
        item
        for item in (tmp_path / "synthv_result.txt").read_text(encoding="utf-8").splitlines()
        if item.startswith("R VERSION ")
    ][0]
    assert "host=Synthesizer V Studio 2" in line
    assert "version=2.1.0" in line


def test_probe_reports_the_documented_surface(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    entries, payload = _probe(lua, tmp_path)
    # One name from each class the agent relies on, plus the host's own version.
    for name in (
        "sv:getProject",
        "sv:getMainEditor",
        "sv:create",
        "editor:getCurrentTrack",
        "arrangement:getSelection",
        "selection:selectGroup",
        "project:newUndoRecord",
        "track:getGroupReference",
        "note:setLyrics",
        "playback:seek",
    ):
        assert name in entries, name
    assert "hostVersionNumber:" in payload


def test_probe_finds_a_method_however_the_host_binds_it(tmp_path: Path) -> None:
    """The bug that only a live run could reveal.

    Synthesizer V hands methods out as callable userdata, so `type(SV.getProject)`
    is not "function" even though `SV:getProject()` works.  A probe that used the
    type as its existence test therefore reported an *empty* API in the editor
    while the agent's own poll loop was calling `SV:setTimeout` successfully.  The
    mock binds SV and the editor the same way (as a table with __call - Lua
    cannot build a real userdata) and leaves the rest as plain Lua functions, so
    the probe has to answer for both shapes.
    """
    lua = _start(tmp_path)
    entries, _ = _probe(lua, tmp_path)
    # Non-"function" is the whole point; "table" is just what a mock can make.
    assert entries["sv:getProject"] == "table"
    assert entries["editor:getCurrentTrack"] == "table"
    assert entries["sv:getProject"] != "function"
    # ...and the rest of the API is still ordinary functions, so the probe is
    # genuinely reporting what it found rather than a constant.
    assert entries["note:setLyrics"] == "function"
    assert entries["track:getGroupReference"] == "function"
    # Enumerated names carry a type too, which is why the payload grew a
    # marker for the owners the host listed itself.
    assert "note:setPhonemes" in entries


def _enumerated(payload: str) -> list[str]:
    """The owners PROBE says it listed from the host's own member list.

    The marker is one comma-separated entry that sorts into the middle of the
    payload, so it has to be fished out whole - taking everything after it gets a
    random alphabetical tail instead.
    """
    for item in payload.split(","):
        if item.startswith("enumerated="):
            return item.split("=", 1)[1].split("/")
    return []


def test_probe_reports_which_owners_the_host_enumerated(tmp_path: Path) -> None:
    """pairs() works in Synthesizer V, so the host answers "what do you have".

    That is what turned TRACKSEL around: the manual does not list
    ``editor:setCurrentTrack``, and a probe that only tested names it had thought
    of reported that absence as fact.
    """
    lua = _start(tmp_path)
    _, payload = _probe(lua, tmp_path)
    listed = _enumerated(payload)
    for owner in ("sv", "editor", "note", "selection"):
        assert owner in listed, (owner, listed)


def test_probe_finds_a_name_only_the_host_knows(tmp_path: Path) -> None:
    lua = _start(tmp_path, with_set_current_track=True)
    entries, _ = _probe(lua, tmp_path)
    assert "editor:setCurrentTrack" in entries
    # Not a Lua function - this mock, like the host, binds it as a callable.
    assert entries["editor:setCurrentTrack"] != "function"


def test_probe_does_not_claim_a_name_the_host_lacks(tmp_path: Path) -> None:
    """editor:setCurrentTrack is not in the manual, so the probe must not list it."""
    lua = _start(tmp_path)
    entries, _ = _probe(lua, tmp_path)
    assert "editor:setCurrentTrack" not in entries
    assert "project:writeFile" not in entries


def test_probe_falls_back_when_the_host_cannot_enumerate(tmp_path: Path) -> None:
    """Older hosts may not answer pairs(); the manual's names still stand.

    An empty own-table with everything behind __index is what a userdata without
    __pairs looks like from Lua - the members resolve, they just cannot be listed.
    """
    lua = _start(
        tmp_path,
        extra="__EDITOR = setmetatable({}, { __index = __EDITOR })",
    )
    entries, payload = _probe(lua, tmp_path)
    assert "editor:getCurrentTrack" in entries
    assert "editor" not in _enumerated(payload)
    # The other owners are untouched, so the marker is still there at all.
    assert _enumerated(payload)


def test_note_duration_default_comes_from_the_host(tmp_path: Path) -> None:
    """SV.QUARTER is published by the host; the literal is only the fallback."""
    lua = _start(tmp_path, extra="SV.QUARTER = 123456789")
    _run(lua, tmp_path, ["GROUP 1", "NOTE 0 - 60 la -"])
    notes = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget().notes")
    assert notes[1]["duration"] == 123456789


def test_note_duration_falls_back_when_the_host_hides_the_constant(
    tmp_path: Path,
) -> None:
    lua = _start(tmp_path, extra="SV.QUARTER = nil")
    _run(lua, tmp_path, ["GROUP 1", "NOTE 0 - 60 la -"])
    notes = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget().notes")
    assert notes[1]["duration"] == 705600000


def test_track_selection_falls_back_to_the_arrangement(tmp_path: Path) -> None:
    """When the editor cannot do it, the arrangement selection is the way in."""
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["TRACKSEL 1"])
    assert answers["TRACKSEL"] == "ok"
    assert lua.eval("__SELECTED") is not None
    assert _payloads(tmp_path)["TRACKSEL"] == "arrangement:selectGroup=1"


def test_track_selection_prefers_the_editor_when_the_build_has_it(tmp_path: Path) -> None:
    """editor:setCurrentTrack takes the Track *object*, not a wire index.

    Handing it the number is what made it raise in the live editor, which read as
    "this build has no way in" until the host's own member list said otherwise.
    """
    lua = _start(tmp_path, with_set_current_track=True)
    answers = _run(lua, tmp_path, ["TRACKSEL 1"])
    assert answers["TRACKSEL"] == "ok"
    assert _payloads(tmp_path)["TRACKSEL"] == "editor:setCurrentTrack=1"
    assert lua.eval("__CURRENT == __PROJECT:getTrack(2)") is True


def test_track_selection_uses_set_current_group_when_that_is_all_there_is(
    tmp_path: Path,
) -> None:
    lua = _start(
        tmp_path,
        extra=(
            "function __EDITOR:setCurrentGroup(ref) __CURRENT_GROUP = ref return true end\n"
            "__EDITOR.setCurrentGroup = __as_callable(__EDITOR.setCurrentGroup)"
        ),
    )
    answers = _run(lua, tmp_path, ["TRACKSEL 0"])
    assert answers["TRACKSEL"] == "ok"
    assert _payloads(tmp_path)["TRACKSEL"] == "editor:setCurrentGroup=0"
    assert lua.eval("__CURRENT_GROUP ~= nil") is True


def test_track_selection_reports_the_hosts_own_error(tmp_path: Path) -> None:
    """A bare "raised" hides the reason; the host's text is the diagnostic.

    Both paths have to fail for the payload to exist at all, so the arrangement
    is taken out too - and each failure is then named separately.
    """
    lua = _start(
        tmp_path,
        extra=(
            "function __EDITOR:setCurrentTrack(t) error('Track expected, got nil') end\n"
            "__EDITOR.setCurrentTrack = __as_callable(__EDITOR.setCurrentTrack)\n"
            "__ARRANGEMENT.getSelection = nil"
        ),
    )
    answers = _run(lua, tmp_path, ["TRACKSEL 0"])
    assert answers["TRACKSEL"] == "err"
    payload = _payloads(tmp_path)["TRACKSEL"]
    assert "editor.setCurrentTrack: " in payload
    assert "Track expected, got nil" in payload
    assert "arrangement has no getSelection" in payload


def test_track_selection_refuses_an_index_past_the_end(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["TRACKSEL 9"])
    assert answers["TRACKSEL"] == "err"


def test_track_selection_says_which_step_it_stopped_at(tmp_path: Path) -> None:
    """A flat "cannot select a track" is not actionable; the path is."""
    lua = _start(tmp_path, extra="__ARRANGEMENT.getSelection = nil")
    answers = _run(lua, tmp_path, ["TRACKSEL 0"])
    assert answers["TRACKSEL"] == "err"
    payload = _payloads(tmp_path)["TRACKSEL"]
    assert "arrangement has no getSelection" in payload
    assert "editor.setCurrentTrack: no such method" in payload
    assert "editor.setCurrentGroup: no such method" in payload


def test_undo_is_used_when_the_build_has_one(tmp_path: Path) -> None:
    """The manual documents no way back, so it is probed - and used if present."""
    lua = _start(
        tmp_path,
        extra=(
            "function __EDITOR:undo() __UNDONE = true return true end\n"
            "__EDITOR.undo = __as_callable(__EDITOR.undo)"
        ),
    )
    entries, _ = _probe(lua, tmp_path)
    assert entries["editor:undo"] != "function"  # callable, as this host delivers
    answers = _run(lua, tmp_path, ["UNDO"])
    assert answers["UNDO"] == "ok"
    assert lua.eval("__UNDONE") is True


def test_undo_absence_names_where_it_looked(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["UNDO"])
    assert answers["UNDO"] == "err"
    payload = _payloads(tmp_path)["UNDO"]
    assert "editor.undo" in payload
    assert "getNavigation().undo" in payload
    assert "newUndoRecord" in payload


def test_lyric_sets_exactly_one_value(tmp_path: Path) -> None:
    """``string.gsub`` returns the text *and* the replacement count.

    Both used to reach ``setLyrics`` because the call was not wrapped in
    parentheses, and the host answered "expected 1 argument, got 2".  The mock
    counts arguments like the host does, so an unwrapped gsub fails here.
    """
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["GROUP 1", "NOTE 0 705600000 64 la -", "LYRIC 0 fa"])
    assert answers["NOTE"] == "ok"
    assert answers["LYRIC"] == "ok"
    notes = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget().notes")
    assert notes[1]["lyrics"] == "fa"


def test_lyric_underscores_still_become_spaces(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    _run(lua, tmp_path, ["GROUP 1", "NOTE 0 705600000 64 la_la -", "LYRIC 0 do_re"])
    notes = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget().notes")
    assert notes[1]["lyrics"] == "do re"


def test_transport_answers_through_the_playback_control(tmp_path: Path) -> None:
    """The ex-type-gated verbs, live-broken once and now covered."""
    lua = _start(tmp_path)
    answers = _run(lua, tmp_path, ["SEEK 0", "PLAY", "STOP"])
    assert (answers["SEEK"], answers["PLAY"], answers["STOP"]) == ("ok", "ok", "ok")
    payloads = _payloads(tmp_path)
    assert payloads["PLAY"] == "playback:play"
    assert payloads["SEEK"] == "playback:seek=0"


def test_a_batch_is_one_undo_record(tmp_path: Path) -> None:
    lua = _start(tmp_path)
    _run(lua, tmp_path, ["CLEAR", "NOTE 0 705600000 64 la -"])
    calls = list(lua.eval("__CALLS").values())
    assert calls.count("Project:newUndoRecord") == 1


def test_lyric_underscores_become_spaces(tmp_path: Path) -> None:
    """A space cannot survive the whitespace-separated wire, so _ stands in."""
    lua = _start(tmp_path)
    _run(lua, tmp_path, ["NOTE 0 705600000 64 la_la -"])
    notes = lua.eval("__PROJECT:getTrack(1):getGroupReference(1):getTarget().notes")
    assert notes[1]["lyrics"] == "la la"


# --------------------------------------------------------------------------- #
# replacing a running instance
# --------------------------------------------------------------------------- #
def test_a_superseded_instance_retires(tmp_path: Path) -> None:
    """Running the script again must replace the running copy, not double it.

    Lua cannot be reloaded inside a live host, so without this an edit to the
    agent costs a restart of the whole editor.  Both instances share one
    directory here, exactly as they do in the host, and the older one has to
    notice the newer stamp and finish itself.
    """
    older = _start(tmp_path)
    newer = _start(tmp_path)  # claims the directory on start

    _tick(older)
    assert older.eval("__FINISHED") is True
    assert older.eval("__TIMEOUT") is None, "a retired instance must not re-arm its loop"

    _tick(newer)
    assert newer.eval("__FINISHED") is None, "the newcomer retired itself"
    assert newer.eval("__TIMEOUT") is not None
    # And it is still serving requests, which is the point of retiring the other.
    assert _run(newer, tmp_path, ["VERSION"])["VERSION"] == "ok"


def test_retirement_only_ever_goes_one_way(tmp_path: Path) -> None:
    """The newest stamp wins; an instance never retires on seeing its own."""
    lua = _start(tmp_path)
    for _ in range(3):
        _tick(lua)
    assert lua.eval("__FINISHED") is None
    assert lua.eval("__TIMEOUT") is not None


def test_a_missing_claim_file_does_not_retire_the_instance(tmp_path: Path) -> None:
    """Fail open: a lost marker must not silently stop the only agent."""
    lua = _start(tmp_path)
    (tmp_path / "synthv_agent.txt").unlink()
    _tick(lua)
    assert lua.eval("__FINISHED") is None
    assert lua.eval("__TIMEOUT") is not None

