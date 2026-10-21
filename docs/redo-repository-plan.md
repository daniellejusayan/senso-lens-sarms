# Plan: recreate the GitHub repository with only team members as contributors

Goal: `github.com/daniellejusayan/senso-lens-sarms` lists only the four team members as
contributors — no Claude trailer, no `sarms` placeholder identity, no third-party account
anywhere in the history, now or later. At the moment of the re-push that means one
contributor (daniellejusayan, who made every commit so far); the other three join as they
commit under their own GitHub identities. Two ways to get there; A keeps the commit history, B starts a
fresh one. Both end with the same checks. Do everything in PowerShell from
`C:\senso-lens-sarms\sarms` unless a step says otherwise.

## Why the names appeared, so they cannot come back

| What GitHub showed | Where it came from | Rule from now on |
| --- | --- | --- |
| `claude` | a `Co-Authored-By: Claude …` trailer line in each commit message; GitHub counts trailer authors as contributors | commit messages carry no `Co-Authored-By:` or `Claude-Session:` lines — the check in step 3 greps for them |
| `sarms` (Mike Sarmiento) | commits authored as `sarms <sarms@users.noreply.github.com>`; `*@users.noreply.github.com` is GitHub's format for real accounts, and the handle `sarms` is taken | every commit is authored with your own identity (`git config user.name/email` below); any assistant-made commit is re-authored to you before it is pushed |

## Step 0 — before deleting anything on GitHub

1. Make sure the local clone is complete and clean:
   ```powershell
   git status            # nothing to commit
   git log --oneline | Measure-Object -Line   # 16 commits expected after step 1
   ```
2. Keep a safety copy: `Copy-Item -Recurse C:\senso-lens-sarms\sarms C:\senso-lens-sarms\sarms-backup-2026-10-22`.
   Delete it only after the new repository is pushed and checked.

## Step 1 — apply the last pending change (the graph report)

The commit "Report: the import graph drawn; render_graph tool; kedro HEAD vs 2020 figures" is in
`0001-Report-the-import-graph-drawn-….patch` beside the repository, already authored as you.
```powershell
git am ..\0001-Report-the-import-graph-drawn-render_graph-tool-kedr.patch
git log -1 --format='%an <%ae>'   # daniellejusayan <6731503051@lamduan.mfu.ac.th>
```

## Step 2 — set your identity for this repository, permanently

```powershell
git config user.name  "daniellejusayan"
git config user.email "6731503051@lamduan.mfu.ac.th"
git config commit.gpgsign false
```
(If you prefer the GitHub-private address, use `daniellejusayan@users.noreply.github.com` in both
places below instead; GitHub links either to your account.)

## Step 3 — make the history yours (choose A or B)

### A — keep the history, re-author it (recommended: the step-by-step commits stay readable)

The local history was already rewritten on 21 Oct (authors = you, trailers removed), so this is a
verification pass plus a safety net:
```powershell
git filter-branch -f --env-filter '
  export GIT_AUTHOR_NAME="daniellejusayan"; export GIT_AUTHOR_EMAIL="6731503051@lamduan.mfu.ac.th";
  export GIT_COMMITTER_NAME="daniellejusayan"; export GIT_COMMITTER_EMAIL="6731503051@lamduan.mfu.ac.th"' `
  --msg-filter 'grep -v -e "^Co-Authored-By:" -e "^Claude-Session:"' --tag-name-filter cat -- --all
Remove-Item -Recurse -Force .git\refs\original
git reflog expire --expire=now --all; git gc --prune=now
```
(`filter-branch` needs Git Bash's `grep`; Git for Windows ships it. If PowerShell complains about
the backtick continuation, put the whole command on one line.)

### B — fresh history: one commit per step, all yours

Use this if you would rather the repository start clean with hand-written messages.
```powershell
cd C:\senso-lens-sarms
git clone --no-local sarms sarms-fresh-src     # a scratch copy to read files from
mkdir sarms-fresh; cd sarms-fresh; git init -b main
git config user.name "daniellejusayan"; git config user.email "6731503051@lamduan.mfu.ac.th"
# copy everything except .git from ..\sarms into this folder (File Explorer or robocopy ..\sarms . /E /XD .git .venv data\raw)
git add -A
git commit -m "sarms v0.1: Steps 1 and 2 (criteria, subjects, baselines, specification)"
git tag -a v0.1-steps-1-2 -m "Steps 1 and 2 frozen"
```
One commit loses the step-by-step story (P0 → point 7 → P1 … P6) that the report refers to;
if you take B, say so in `reports/steps-1-2-report.md` § 9 in one line.

## Step 4 — check before pushing (this is the step that matters)

```powershell
git log --all --format='%an <%ae> | %cn <%ce>' | Sort-Object -Unique
#   -> exactly one line today: daniellejusayan <6731503051@lamduan.mfu.ac.th> | daniellejusayan <…>
#      (later: one line per team member, never anything else)
git log --all --format=%B | Select-String -Pattern 'Co-Authored|Claude|sarms@' | Measure-Object -Line
#   -> Lines : 0
git log --all --format='%(trailers)' | Where-Object { $_ } | Measure-Object -Line
#   -> Lines : 0  (no trailers of any kind)
Get-Content .git\config | Select-String 'trailer|template'      # nothing
git tag                                                          # v0.1-steps-1-2
```
If any check fails, stop and fix it locally; nothing has reached GitHub yet.

## Step 5 — delete the old repository and create the new one

1. GitHub → repository → Settings → scroll to Danger Zone → **Delete this repository**; type the
   name to confirm. (Alternative: rename it to `senso-lens-sarms-old` and make it private; the
   contributor cache of a deleted or renamed repository never carries over.)
2. GitHub → New repository → name `senso-lens-sarms`, owner `daniellejusayan`, **empty**: no
   README, no .gitignore, no licence (the clone has them).
3. Push:
   ```powershell
   git remote set-url origin https://github.com/daniellejusayan/senso-lens-sarms.git
   git push -u origin main
   git push origin v0.1-steps-1-2
   ```

## Step 6 — check on GitHub

- Code tab → the commit list shows only your avatar.
- Insights → Contributors → one contributor (the graph may take a few minutes to compute on a
  brand-new repository; it is not a cache of the old one).
- Actions tab → the CI run on the first push is green (ruff, pytest, lint-imports,
  validate_spec).
- Settings → Collaborators: add Eaindray, Kanthi Phoosorn and Withuwit Ninphan. Before their
  first commit each runs, inside the clone:
  ```powershell
  git config user.name  "<their GitHub username>"
  git config user.email "<their GitHub e-mail, or <username>@users.noreply.github.com>"
  ```
  so every commit maps to a real team account and the contributor list grows only by team
  members. The `attribution` job in CI (next section) fails any push that carries an assistant
  trailer or a placeholder author, whoever pushed it.
- Optional, Settings → Branches → protect `main`: require the `ci` checks to pass before
  merging, so a failed attribution check cannot land.

## From here on — the rule for all four members

- A commit is authored by the team member who made or asked for it, under their own GitHub
  identity. Commits made with the assistant are authored as the member who directed them
  (today: daniellejusayan). If the team later wants the system itself visible, it is
  `sensolens-sarms <sensolens-sarms@users.noreply.github.com>` only after that GitHub account
  exists and belongs to the team — never a placeholder handle, which is how `sarms` happened.
- No commit message carries a `Co-Authored-By:` or `Claude-Session:` line. Two guards: the
  step-4 grep before any push that includes commits you did not type yourself, and the
  `attribution` job in `.github/workflows/ci.yml`, which greps every pushed commit's author,
  committer and body for `Co-Authored-By: Claude`, `@anthropic.com`, `Claude-Session:` and
  `sarms@users.noreply` and fails the build if one appears. With `main` protected, such a
  commit cannot be merged.
- The paper's acknowledgement is where the assistant is named, not the git author field.
