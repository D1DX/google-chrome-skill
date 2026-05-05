# google-chrome-skill

Claude Code skill for operating Google Chrome on macOS.

Covers:

- Profile discovery (mapping `Profile N` folders → display names)
- Bookmarks JSON structure and a safe edit pattern (quit → edit → relaunch)
- AppleScript tab/window control
- UI-scripting limits of the bookmark bubble
- Extension paths
- **Cookie extraction** for authenticated calls to internal web APIs when an MCP is unavailable or lacks the needed action

See [`SKILL.md`](./SKILL.md) for the full reference and [`extract.py`](./extract.py) for the cookie extractor.

macOS only.
