# Golden IQ MUSIC Bot — Hardening & Rework Design

**Date:** 2026-08-13
**Status:** Approved (pending spec review)
**Scope:** Whole-bot audit, regression safety net, bug fixes, performance, decomposition

---

## 1. Problem statement

The bot works for a core happy path (boot, Lavalink connect, YouTube and
SoundCloud playback) but the owner reports frequent user-visible failures:
buttons that render a red error embed, controls that do nothing, and sluggish
response. The owner cannot reliably report these errors because the failures
are swallowed and surface only as a generic red embed.

This design fixes the reported symptoms and, more importantly, removes the
conditions that let them recur.

### 1.1 Evidence gathered (2026-08-13)

Reproduced against a live local boot with the real token and a local Lavalink
v4 node (`127.0.0.1:8090`), plus static analysis of the tree.

Source loading, via Lavalink REST `/v4/loadtracks`:

| Query | `loadType` | Result |
| --- | --- | --- |
| `ytsearch:never gonna give you up` | `search` | OK, 20 hits |
| `scsearch:daft punk` | `search` | OK, 10 hits |
| `https://youtube.com/watch?v=dQw4w9WgXcQ` | `track` | OK |
| `dzsearch:coldplay yellow` | `empty` | **Broken** — no results |
| `spsearch:adele hello` | `error` | **Broken** — `FriendlyException` |

Boot log also emits `Spotify: Ocorreu um erro ao obter token: Failed to get
client` — an untranslated Portuguese string from the upstream fork.

Static findings:

| Finding | Count / location | Consequence |
| --- | --- | --- |
| Bare `except:` | 320 across `modules/`, `utils/` | Errors vanish; owner cannot report them |
| `except` → `pass` | 370 | Silent wrong behavior instead of a fault |
| Test files | 0 (in 30,701 lines) | Nothing prevents regressions |
| ~~Blocking `requests.get()` in async paths~~ | `utils/client.py:614`, `utils/music/local_lavalink.py:19`, `utils/music/remote_lavalink_serverlist.py:51` | **Retracted 2026-08-13.** All three sit in plain `def` functions on the startup path, and the one reachable at runtime (`run_lavalink`) is invoked through `loop.run_in_executor`, so it runs on a thread. No blocking I/O reaches the event loop, directly or transitively — verified by AST scan over all 53 modules. The reported slowness has another cause; see §4.4. |
| `modules/music.py` | 7,929 lines | Unmaintainable; changes cause collateral breakage |
| Stale Discord CDN URL | `utils/music/ui/theme.py` `PREMIUM_DECORATIVE_BAR` | 2023 unsigned attachment link; now 404s — broken image in every player embed |
| Non-emoji glyphs in `STATUS_ICONS` | `utils/music/ui/theme.py:57` — exactly 3: `↻` U+21BB, `∞` U+221E, `✓` U+2713 | Latent trap, not a live bug: currently rendered as embed *text* (harmless), but Discord rejects them as component emoji. The module's own docstring warns about exactly this. `emoji_set._DEFAULTS` was checked and is entirely valid. |
| Empty Spotify credentials | `application.yml:73-74` with `spotify: true` | Lavalink Spotify source enabled but unauthenticated |
| Deezer disabled + no key | `application.yml:87-88` | `dzsearch` silently returns empty |
| `countryCode: "BR"` | `application.yml:75,79` | Brazil region leftover from upstream fork |
| Broken virtualenv | `venv/pyvenv.cfg` | Pointed at `C:\Python314` from another machine (`C:\Users\GoldenIQ\...`); repaired during audit to the local uv CPython 3.14.6 |
| `cp1252` stdout on Windows | runtime | `UnicodeEncodeError` when logging emoji |

### 1.2 Root cause

Two conditions produce every symptom above:

1. **No regression safety net.** With zero tests over 30k lines, each UI or
   feature change (the recent skin/emoji/Khmer-localization commits) can break
   unrelated surfaces with no signal until a user clicks a button.
2. **Errors are swallowed, not surfaced.** 320 bare handlers convert real
   faults into silent misbehavior or a generic red embed carrying no
   actionable detail.

Fixing individual bugs without addressing these two conditions returns the bot
to the same state within weeks.

---

## 2. Non-goals

- Rewriting the bot from scratch. Boot, node management, YouTube and SoundCloud
  playback demonstrably work; a rewrite would risk proven behavior.
- Changing the hosting model, the Lavalink version, or the database backend.
- Adding new user-facing features. This work is stability, correctness,
  performance, and maintainability only.
- Automating clicks in a live Discord client. Handler-level integration tests
  cover control behavior instead (§4.1.3).

---

## 3. Constraints and decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| UI language | Khmer + English side by side | Matches current bot; owner confirmed |
| Strategy | Test first → fix → refactor | Owner approved; protects working paths |
| Test approach | Offline harness + local live boot | Clicking in Discord is not automatable; handler tests give equivalent coverage |
| Python | 3.14.6 (local uv CPython) | Matches the cp314 wheels already in `venv` |
| Test framework | `pytest` + `pytest-asyncio` | Standard; no runtime dependency added to the bot |

---

## 4. Design

### 4.0 Phase 0 — Foundation

Make the environment reproducible and capable of running tests.

- Record the required Python version and document venv recreation. The audit
  repaired `venv/pyvenv.cfg` in place (original saved as `pyvenv.cfg.bak`);
  Phase 0 replaces that ad-hoc repair with a documented, repeatable setup.
- Force UTF-8 stdio at process start so emoji logging cannot raise
  `UnicodeEncodeError` on Windows consoles.
- Add `pytest` and `pytest-asyncio` as development-only dependencies, kept
  separate from the bot's runtime `requirements.txt`.

**Done when:** a clean checkout can install, boot, and run `pytest` on Windows
without manual intervention.

### 4.1 Phase 1 — Test harness (the safety net)

The central deliverable. Everything after this phase depends on it.

**Unit under test:** the bot's rendering and interaction layers, driven by
fabricated player/interaction objects rather than a live Discord gateway.

**Fixtures.** A `FakePlayer` exposing the attributes the skins read
(`current`, `queue`, `paused`, `volume`, `loop`, `autoplay`, `nightcore`,
`keep_connected`, `restrict_mode`, `mini_queue_enabled`, `command_log`, `node`,
`guild`, `bot`, …) and a `FakeInteraction` implementing the
`disnake.MessageInteraction` surface the handlers touch (`response.defer`,
`response.edit_message`, `send`, `author`, `guild_id`, `channel_id`,
`data.custom_id`, `values`, `message`). Fixtures cover several player states —
playing, paused, stopped, live stream, empty queue, long queue, autoplay,
missing artwork, very long titles, Khmer text — so a skin is exercised across
the state space that produces the reported failures.

**4.1.1 Skin render validation.** Render all 15 skins (10 normal, 5 static)
against every fixture state and assert the resulting payload satisfies Discord
API limits: embed total ≤ 6000 characters; description ≤ 4096; title ≤ 256;
field value ≤ 1024 with ≤ 25 fields; footer ≤ 2048; author name ≤ 256;
≤ 5 action rows; ≤ 5 buttons per row; ≤ 25 select options; component label
≤ 80; `custom_id` ≤ 100; select option description ≤ 100. Also assert every
embed image/thumbnail URL is well-formed and non-expiring.

**4.1.2 Emoji validation.** Assert every string used as `Button.emoji` or
`SelectOption.emoji` is either a real Unicode emoji (validated against the
`emoji` package already in `requirements.txt`) or a well-formed custom emoji
(`<:name:id>` / `<a:name:id>`). This catches the `∞` and `✓` class of defect
that produces the red error text, and enforces the rule the `emoji_set` module
already documents but does not check.

**4.1.3 Interaction handler coverage.** For each of the 30 `PlayerControls`
values, invoke `Music.player_controller()` with a fabricated interaction and
assert: no unhandled exception escapes; exactly one response path is taken
(`defer`, `send`, or `edit_message`); and any pre-response work stays inside
Discord's 3-second acknowledgement budget. This is the automated equivalent of
clicking every button.

**4.1.4 Command metadata validation.** Assert every slash command's name and
description satisfy Discord's limits — description ≤ 100 characters is the
binding constraint, and Khmer text overflows it easily, which fails command
sync for the whole bot. Also assert option names match Discord's pattern and
that localized strings are present for every command.

**4.1.5 Configuration validation.** Assert `application.yml` and `.env` agree:
a source enabled in `application.yml` must have credentials, and a source the
Python layer expects must be enabled in Lavalink. This test fails today on
Spotify and Deezer, encoding the §1.1 findings as executable checks.

**Done when:** `pytest` runs green except for tests that encode confirmed
current bugs, which are marked `xfail` and flipped to passing in Phase 2.

### 4.2 Phase 2 — Fix confirmed breakages

Each fix turns a Phase 1 `xfail` into a pass.

- **Spotify.** Two independent Spotify paths exist — Lavalink's `lavasrc`
  plugin and the Python `SpotifyClient` — and both fail. Consolidate on one
  (lavasrc, since track resolution already flows through Lavalink), populate
  its credentials from the values already present in `.env`, and remove or
  clearly demote the unused path so there is a single source of truth.
- **Deezer.** Either enable it with a working configuration or disable it
  coherently across both layers, so a Deezer query returns an explicit,
  user-legible "source unavailable" message instead of an empty result.
- **Region.** `countryCode: "BR"` → `"KH"`.
- **Decorative bar image.** Replace the expired CDN attachment URL with a
  stable asset or drop the element.
- **Component emoji.** Replace non-emoji glyphs flagged by 4.1.2.
- **Residual Portuguese strings.** Translate to Khmer + English.

**Done when:** all §1.1 reproduction queries succeed or degrade with a clear
message, and no Phase 1 test is `xfail`.

### 4.3 Phase 3 — Error visibility

Directly addresses the owner's inability to report faults.

- Replace bare `except:` handlers with specific exception types. Where a broad
  catch is genuinely correct (top-level task boundaries), it must log the full
  traceback rather than `pass`.
- Add rotating file logging capturing full tracebacks with context (guild,
  user, command/control, track).
- Assign each caught error a short **Error ID**, store the full traceback
  against it, and display that ID in the red embed. Reporting a problem then
  means quoting one short ID.
- The 320 handlers are triaged by risk (interaction and playback paths first),
  not converted blindly in one sweep.

**Done when:** every user-visible error carries an ID resolvable to a full
stored traceback, and no handler in the interaction or playback path discards
an exception silently.

### 4.4 Phase 4 — Performance

- ~~Convert the three blocking `requests.get()` calls in async paths to
  `aiohttp`.~~ **Retracted.** The premise was wrong: an AST scan of all 53
  modules found no blocking call inside a coroutine, and no coroutine calling
  a blocking helper without `run_in_executor`. `tests/test_async_hygiene.py`
  now enforces both properties so a future regression is caught, but there was
  nothing to convert. The slowness must be explained by the remaining items
  below, or by something not yet identified — it should not be claimed fixed
  without a measurement.
- Cache `guild_data`, currently re-read from MongoDB on essentially every
  interaction, with explicit invalidation on write.
- Review the player update path (`auto_update`, progress-bar re-render rate)
  and reduce redundant message edits, which also lowers rate-limit pressure.
- Measure before and after; report real numbers rather than asserting
  improvement.

**Done when:** no blocking I/O remains on the event loop in the interaction or
playback path, and measured interaction latency improves against a recorded
baseline.

### 4.5 Phase 5 — Decompose `modules/music.py`

With Phase 1 tests in place, split the 7,929-line module along its existing
seams — playback commands, queue management, the player-controller dispatcher,
search and track resolution, and the static-player lifecycle — into focused
modules with explicit interfaces. `utils/music/models.py` (3,833 lines) and
`utils/music/interactions.py` (3,349 lines) receive the same treatment if they
remain the largest remaining risks after the split.

Behavior must not change. The Phase 1 suite is the acceptance criterion: it
passes identically before and after each extraction.

**Done when:** no module exceeds roughly 1,500 lines, and the full suite passes
unchanged.

---

## 5. Testing strategy

Three layers, in decreasing breadth:

1. **Offline harness (Phase 1)** — deterministic, fast, runs on every change.
   Covers rendering, component validity, handler dispatch, command metadata,
   and configuration coherence.
2. **Local live boot** — starts the bot and a local Lavalink node, verifies
   startup, cog loading, node readiness, command sync, and real track
   resolution through the Lavalink REST API. Used at each phase boundary.
3. **Owner acceptance pass** — the owner exercises the bot in Discord at the
   end. By then the automated layers should have removed the defects that make
   such a pass frustrating.

Verification discipline: no phase is reported complete without showing the
command output that demonstrates it.

---

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| Fabricated fixtures drift from real disnake objects, so tests pass while production breaks | Validate payloads with disnake's own serialization rather than hand-rolled assertions; re-verify at each phase boundary with a live boot |
| Converting 320 `except:` handlers surfaces previously hidden faults, appearing to add bugs | Triage by risk, convert in reviewable batches, treat each newly surfaced fault as a finding rather than a regression |
| Decomposition of `music.py` introduces subtle behavior change | Phase 5 runs only after Phase 1 is green; the suite is the acceptance gate for every extraction |
| Live testing uses the production token and touches real guilds | Boots are short, owner-approved, and stopped immediately after; no destructive command is exercised |
| Deezer may not be fixable without a key the owner does not hold | Phase 2 explicitly permits coherent disabling as an acceptable outcome |

---

## 7. Open questions

None. Deezer's fix-or-disable ambiguity is resolved by §4.2 permitting either,
decided by whether a working key is available at implementation time.
