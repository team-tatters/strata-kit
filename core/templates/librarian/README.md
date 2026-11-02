# librarian daily job (macOS launchd)

The script `strata-librarian.sh` runs the librarian's daily work: vault pull, measurements per project, the project's
product-flow indicators (`kb indicators collect --write` — the read-only commands in its Tier P `indicators.yaml`),
the indicators that moved the worse way written as open signal notes (`kb signals candidates --write` — no
destination; a person chooses it, DEC-2026-11-01-14·17) and a `kb signals list` line per project in the log, a commit of the measurement
and signal files only, then the generated views. Each run writes `=== strata-librarian start … ===` and
`=== strata-librarian end … failed N ===` lines, and any failed step makes the run exit non-zero, so `tools/doctor.py`
can read the last run from the log and launchd's last exit code means what it says (DEC-2026-10-31-29).

Install or reinstall on a machine (replace the values; `{PROJECTS}` is space-separated `<vault project id>=<repo path>`):

```sh
K=$HOME/workspace/strata-kit
sed -e "s|{LABEL}|com.$USER.strata-librarian|" -e "s|{KIT}|$K|g" -e "s|{VAULT}|$HOME/workspace/vault|" \
    -e "s|{PYTHON}|$(command -v python3)|" -e "s|{LOG}|$HOME/Library/Logs/strata-librarian.log|g" \
    -e "s|{HOUR}|8|" -e "s|{MINUTE}|30|" \
    -e "s|{PROJECTS}|strata-kit=$K <project>=$HOME/workspace/projects/<project>|" \
    "$K/core/templates/librarian/strata-librarian.plist.template" > ~/Library/LaunchAgents/com.$USER.strata-librarian.plist
launchctl bootout gui/$(id -u)/com.$USER.strata-librarian 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.$USER.strata-librarian.plist
```

`STRATA_PYTHON` must be a python with PyYAML: launchd's shell does not load asdf or pyenv, and the first run on
2026-10-31 picked a python without it.
