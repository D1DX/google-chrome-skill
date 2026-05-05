---
name: google-chrome
description: Google Chrome on macOS — profile discovery, Bookmarks JSON structure, safe edit patterns (quit-restart), AppleScript tab/window control, UI-scripting limits of the bookmark bubble, extension paths, sessions, and cross-references to chrome-cookies. Auto-triggers on "chrome bookmarks", "chrome profile", "open chrome tab", "chrome extension", "edit chrome bookmarks", "chrome applescript".
---

# Google Chrome Skill

macOS-only. Operate Google Chrome programmatically: discover profiles, read/write the Bookmarks JSON, control tabs and windows via AppleScript, and understand the limits of UI scripting.

> Sister skill: `chrome-cookies` — extract live session cookies from a logged-in Chrome profile. Use that for cookie work; this skill covers everything else.

---

## 1. Profile discovery

Chrome stores each profile under its own folder. Folder names are stable (`Default`, `Profile 1`, `Profile 2`, …) but the **display name** lives inside `Preferences`.

```bash
ROOT="$HOME/Library/Application Support/Google/Chrome"
ls "$ROOT/" | grep -iE '^(default|profile)'
# Default
# Profile 1
# Profile 3
# ...
```

Map folder → display name:

```bash
for p in "$ROOT"/Default "$ROOT"/Profile\ *; do
  [ -f "$p/Preferences" ] || continue
  name=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('profile',{}).get('name','?'))" "$p/Preferences")
  printf '%s → %s\n' "$(basename "$p")" "$name"
done
```

The Chrome window title also exposes the profile in parentheses: `LinkedIn - Google Chrome - Daniel (.D1DX)` → profile name is `.D1DX`.

---

## 2. Bookmarks JSON

### Location

```
$ROOT/<Profile>/Bookmarks         # canonical
$ROOT/<Profile>/Bookmarks.bak     # Chrome's automatic backup
```

### Top-level structure

```json
{
  "checksum": "32-char-md5-hex",
  "roots": {
    "bookmark_bar":      { "id": "1", "type": "folder", "name": "Bookmarks Bar", "children": [ ... ] },
    "other":             { "id": "2", "type": "folder", "name": "Other Bookmarks", "children": [ ... ] },
    "synced":            { "id": "3", "type": "folder", "name": "Mobile Bookmarks", "children": [ ... ] }
  },
  "sync_metadata": "...",
  "version": 1
}
```

### Node shapes

```json
// URL bookmark
{ "id": "2472", "type": "url",
  "name": "Some Page",
  "url":  "https://example.com/...",
  "date_added": "13371234567890" }

// Folder
{ "id": "2471", "type": "folder",
  "name": "MyFolder",
  "children": [ ... ] }
```

`date_added` is microseconds since 1601-01-01 UTC (Windows FILETIME epoch). Most edits can leave it as a recent value or copy from a sibling.

### `checksum` field

MD5 over a recursive walk of the bookmark tree (id, name, type, url). When you edit the file externally, **drop the `checksum` field** — Chrome recomputes it on the next save and doesn't reject the file. Don't try to recompute it yourself unless you're matching the exact Chromium algorithm.

---

## 3. Safe edit pattern (quit → edit → relaunch)

**Chrome holds bookmarks in memory and overwrites the file** on its own schedule. External edits while Chrome is running on that profile WILL be lost. The reliable pattern:

```bash
PROFILE="Profile 4"
BMK="$ROOT/$PROFILE/Bookmarks"

# 1. Quit Chrome cleanly (preserves session restore)
osascript -e 'tell application "Google Chrome" to quit'
for i in $(seq 1 10); do
  pgrep -x "Google Chrome" >/dev/null || break
  sleep 1
done

# 2. Backup
cp "$BMK" "/tmp/bookmarks-backup-$(date +%s).json"

# 3. Edit (Python preserves JSON shape better than jq for nested mutations)
python3 - <<PY
import json
p = "$BMK"
d = json.load(open(p))
# ... mutate d["roots"]["bookmark_bar"]["children"] ...
d.pop("checksum", None)
json.dump(d, open(p, "w"), indent=3, ensure_ascii=False)
PY

# 4. Relaunch — Chrome restores tabs via session restore
open -a "Google Chrome"
```

**Why session restore preserves tabs:** Chrome reads `Sessions/Session_*` and `Last Session` on launch, which were written before the quit. A clean `quit` (vs a kill -9) flushes session state.

**Don't** edit `Bookmarks.bak` instead — Chrome only consults it when the main file is missing or unparseable, and your changes won't load.

### Example: move a bookmark to bookmark_bar root

```python
target_id = "2472"
extracted = {"obj": None}

def remove_from(n):
    if "children" not in n: return
    new = []
    for c in n["children"]:
        if c.get("id") == target_id:
            extracted["obj"] = c
        else:
            new.append(c)
            remove_from(c)
    n["children"] = new

for root in d["roots"].values():
    remove_from(root)

d["roots"]["bookmark_bar"]["children"].append(extracted["obj"])
d.pop("checksum", None)
```

---

## 4. AppleScript — tab and window control

Chrome's AppleScript dictionary is small but enough for tab orchestration.

### Open URL in a new tab (or focus existing tab with that URL)

```applescript
tell application "Google Chrome"
  activate
  set found to false
  repeat with w in windows
    set tabIdx to 0
    repeat with t in tabs of w
      set tabIdx to tabIdx + 1
      if (URL of t as string) contains "linkedin.com/posts/michael" then
        set active tab index of w to tabIdx
        set index of w to 1
        set found to true
        exit repeat
      end if
    end repeat
    if found then exit repeat
  end repeat
  if not found then open location "https://example.com"
end tell
```

### Read current tab URL / title

```applescript
tell application "Google Chrome"
  set u to URL of active tab of front window
  set t to title of active tab of front window
end tell
```

### Execute JavaScript in the active tab

Requires "Allow JavaScript from Apple Events" in Chrome's View → Developer menu (off by default).

```applescript
tell application "Google Chrome"
  tell active tab of front window
    execute javascript "document.title"
  end tell
end tell
```

---

## 5. UI-scripting limits — the bookmark bubble

The `Cmd+D` "Bookmark added" popover is rendered in Chrome's internal Views toolkit and **doesn't expose its children to macOS Accessibility**. `entire contents of` returns the popover window but its inputs/buttons are invisible — you can't reliably:

- Read or click the Folder dropdown
- Read or click the "Done" / "Edit…" / "Remove" buttons
- Confirm what folder a `Cmd+D` + `Return` actually picks

The popover's keyboard navigation works (`Tab` from Name → Folder dropdown → Edit/Done), but the dropdown's open menu is also invisible to Accessibility, so verification requires reading the file afterward.

**Do not** invest in UI scripting for bookmark folder selection. Use the JSON edit pattern instead. The reliable pattern when you only need a "save this URL" with no folder control:

```applescript
keystroke "d" using command down
delay 1
keystroke return
```

Then read `Bookmarks` to see where it landed (Chrome saves to the last-used folder), and JSON-edit-with-restart to move it if needed.

---

## 6. Extensions

Extensions live at:

```
$ROOT/<Profile>/Extensions/<ext-id>/<version>/
```

Manifest is the canonical source for permissions and content scripts:

```bash
jq '{name, version, permissions, host_permissions, content_scripts}' \
  "$ROOT/Profile 4/Extensions/<id>/<version>/manifest.json"
```

Per-profile extension state (enabled, install time):

```bash
jq '.extensions.settings | to_entries[] | {id: .key, name: .value.manifest.name, state: .value.state}' \
  "$ROOT/Profile 4/Preferences"
```

Don't disable/enable extensions by hand-editing `Preferences` while Chrome is running — same overwrite hazard as Bookmarks. Use the `chrome://extensions` UI or the same quit→edit→relaunch pattern.

---

## 7. Cookies

→ Use the `chrome-cookies` skill. It encapsulates `browser_cookie3`, profile selection, and the inline-substitution-only pattern for safely passing extracted cookies into a `curl` without echoing them to stdout.

---

## 8. Common gotchas

- **Profile-folder display name ≠ folder name.** Always read `Preferences.profile.name` to identify the right profile. `Profile 4` could be Daniel's `.D1DX` or anything else.
- **Multiple Chrome windows ≠ multiple profiles.** A single profile can have many windows; each profile launches its own browser process. Use `osascript` to enumerate windows and check titles for the profile suffix.
- **`Bookmarks.bak` will trip you up.** If you delete `Bookmarks` (or corrupt it badly) and Chrome sees the .bak with old data, it'll restore stale state silently. When in doubt, check both files.
- **Sync.** If Chrome Sync is on, your external bookmark edit will be propagated to other devices on the next sync. That's usually what you want — but it also means a bad edit is harder to take back.
- **iCloud-synced Chrome data: not a thing.** Chrome's app support folder is in `~/Library/Application Support/`, NOT `~/Library/Mobile Documents/`. Safe to edit.
- **Quitting Chrome via `kill -9`** skips session save. Tabs may not restore. Always `osascript -e 'tell application "Google Chrome" to quit'`.
- **Hebrew/RTL bookmark names** survive a JSON round-trip iff you use `ensure_ascii=False` and UTF-8 in `json.dump` / `json.load`.

---

## Do NOT

- Don't edit `Bookmarks` while Chrome is running on that profile — your changes will be overwritten silently
- Don't try to recompute the `checksum` field — drop it instead and let Chrome regenerate
- Don't use UI scripting for the bookmark bubble's folder selection — it's not exposed to Accessibility
- Don't `kill -9` Chrome to "speed up" a quit — it skips session save
- Don't put a Chrome profile folder in iCloud-synced space — performance and corruption risk
- Don't manually edit `Bookmarks.bak` to "make sure" — Chrome only reads it on fallback
