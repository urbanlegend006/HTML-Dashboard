---
name: tosca-test-gate
description: "Use for the TOSCA DI Report Dashboard project when implementing features. Follow this gated process: implement with tests, run tests 2x, self-score >=95%, loop until passing, update docs, commit all together, push once."
---

# TOSCA Feature Implementation Process

## Core Rules

1. **Push to current branch only** — always run `git branch --show-current` to
   determine the target. Never hardcode a branch name. Never merge into main.
2. **Every implementation needs tests** — any new element (button, header, label,
   section, function, behavior) must have at least one Playwright test validating
   its existence, placement, and behavior. Tests go in `tests/test_dashboard.py`.
3. **Sync documentation** — every feature change must also update
   `tosca_unified_dashboard_features-v2.md` with new/changed features, test
   counts, changelog entry, and any spec changes.

## Gate 1 — Implement

1. Make code changes in `tosca_di_report_dashboard.py`
2. Regenerate: `python tosca_di_report_dashboard.py`
3. Verify the feature works manually in browser
4. **Write tests** for every visible/behavioral change:
   - Element exists -> `expect(locator).to_be_visible()`
   - Element positioned correctly -> DOM order checks via `page.evaluate()`
   - Element has correct text/style -> attribute/content assertions
   - Feature behavior -> interaction + assertion (e.g. download content)
   - Content validation -> openpyxl for downloaded XLSX, etc.

## Gate 2 — Run Tests (Pass 1)

```bash
python -m pytest tests/test_dashboard.py -v --browser firefox
```

Known exception: `test_copy_to_clipboard` fails on Firefox (clipboard-read
unsupported by Playwright). All other tests must pass.

## Gate 3 — Run Tests (Pass 2)

Run the same command again. Results must be consistent (no flaky tests).

## Gate 4 — Self-Score >= 95%

| Criterion | Weight |
|---|---|
| Feature implemented per spec | 30% |
| Every change has a corresponding test | 15% |
| All new tests pass | 15% |
| All existing tests pass (minus known) | 15% |
| Consistent across 2 test runs | 10% |
| Code quality (no regressions, clean style) | 15% |

If < 95%: diagnose -> fix -> regenerate -> re-test -> re-score. Loop until passing.

## Gate 5 — Update Doc, Commit & Push

**One commit. One push. All files together.**

### Step 1: Update Feature Reference Doc

Update `tosca_unified_dashboard_features-v2.md`:

1. Add new feature descriptions under the relevant section (e.g., section 3 for
   sidebar changes, section 7 for matrix changes, section 8 for exports, etc.)
2. Add new test cases to the test suite table in section 9
3. Update the test count references (header row + quick-start section)
4. Add a changelog entry with date, version, short name, and details
5. Remove any duplicate content if present

### Step 2: Stage All Changed Files

```bash
git add tosca_di_report_dashboard.py tests/test_dashboard.py tosca_unified_dashboard_features-v2.md
```

### Step 3: Commit With Comprehensive Message

```bash
git commit -m "type: concise summary

Body with detailed per-file breakdown of changes and rationale."
```

### Step 4: Push to Current Branch (Never Main)

```bash
git push
```

To check current branch: `git branch --show-current`

Base directory for this skill: file:///S:/AI%20Learning%20Projects/TOSCA%20DI%20Report%20Dashboard/.opencode/skills/tosca-test-gate
Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.
Note: file list is sampled.
