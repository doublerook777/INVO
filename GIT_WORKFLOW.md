# Git workflow

Two people, one repo, ~6 hours. This is not a process for a real team — it's
the minimum needed so neither of us loses work or blocks the other.

---

## 0. One-time setup

Repo: `git@github.com:ayushrai-10/invo.git` (private).

- Dev A (Ayush) adds Dev B as a collaborator: repo → Settings → Collaborators → Add.
- Dev B accepts the invite, then clones:
  ```bash
  git clone git@github.com:ayushrai-10/invo.git
  ```
- Both run `git config pull.rebase true` once, so every future `git pull`
  rebases instead of creating a merge commit. Merge commits make a 6-hour
  history unreadable and conflict more often than a clean rebase does.

---

## 1. No branches. Commit to `main`.

A branch-per-feature workflow needs someone to review and merge it. Neither
of us has time to review the other's PR mid-build. Both commit straight to
`main`, in small pieces, and lean on **file ownership** (below) to avoid
stepping on each other.

If you're about to do something you're not sure will work (ripping out a
library, a big refactor), branch for that one thing and merge it back
yourself within the hour. Don't let a branch outlive your lunch break.

---

## 2. File ownership is the real conflict-avoidance

`IMPLEMENTATION.md` already tags every file `[A]` or `[B]`. That tagging
exists for this reason: **if you own a file, you're the only one editing it.**
Two people never touch the same lines, so there's almost nothing to conflict.

- Dev A: `db.py`, `seed.py`, `units.py`, `inventory.py`, `extract.py`,
  `resolver.py`, `reorder.py`, `reply.py`, `pipeline.py`, `routes/inventory.py`.
- Dev B: `frontend/*`, `asr.py`, `ocr.py`, `routes/whatsapp.py`.

**If you need a change in the other person's file, don't just make it.**
Message them (WhatsApp/Slack, whatever's fastest) and let them make the
edit, or get an explicit "go ahead" first. A thirty-second message beats a
conflict resolved under time pressure.

### Shared files (both touch these — read the rule for each)

| File | Rule |
|---|---|
| `routes/chat.py` | Dev A wrote it first; it should rarely need to change again. If you think it does, say so before editing — this file is the one place a silent conflict would actually break the contract both of you depend on. |
| `docs/api-contract.md` | Frozen at T+0:30. After that, no field renames or shape changes without telling the other dev **first**, not after. Adding a new documented error case or clarifying a line is fine solo. |
| `PROGRESS.md` | See section 3 — this is the one file both of us edit constantly, so it gets its own rule. |

---

## 3. `PROGRESS.md`: append, never rewrite

This file updates every few minutes from both sides, so it's the one place
conflicts are likely. The fix isn't a process, it's a habit:

- **Checklists**: only flip `[ ]` → `[x]`/`[~]` on your own rows, or add a new
  row. Don't reformat, reorder, or reword someone else's row.
- **Log at the bottom**: only append a new line with a timestamp. Never edit
  a line someone else already wrote.
- **Commit `PROGRESS.md` by itself**, not bundled into a code commit. A
  one-line status update shouldn't conflict with a code change, and if it
  ever does, the fix is trivial: keep both lines, you're not editing the
  same fact.

If you do hit a conflict here, it's almost always "we both appended at the
same time" — open the file, keep both blocks, done. It is never worth a
`git rebase --abort` and a redo.

---

## 4. The loop

Every 15–30 minutes, or whenever you finish something that runs:

```bash
git add <your files>        # not -A -- see the note below
git commit -m "[A] extract.py: wire gemini call"   # prefix with who
git pull                    # rebases (see setup) -- resolve anything small
git push
```

- **Prefix commit messages with `[A]` or `[B]`.** Running `git log --oneline`
  should tell you what the other person just did without opening a diff.
- **Don't push code that doesn't run.** One curl command or one click in the
  browser before you push. A broken `main` blocks the other person, and
  neither of us has slack to debug someone else's half-finished commit.
- **Don't use `git add -A` / `git add .` out of habit** — check `git status`
  first. It's easy to accidentally stage a stray `.env`, a test DB file, or
  scratch output. Both are already gitignored, but a new one you create by
  hand might not be.

---

## 5. If something actually breaks

- **Never `git push --force` to `main`.** If you've made a mess locally, fix
  it locally and make a normal commit — don't rewrite history the other
  person has already pulled.
- **Never `git reset --hard`** without checking `git status` first and
  confirming with the other dev if it touches anything beyond your own
  uncommitted mess.
- If `main` is broken and blocking you, the fastest fix is usually a new
  commit that fixes it forward, not an archaeology project. Revert only if
  you can't tell what's wrong in under five minutes.

---

## 6. Last 30–45 minutes: freeze

Stop pushing new logic. Only:
- Take the three screenshots (`docs/demo-script.md`).
- Fix something that's visibly broken for the demo.
- Fill in the PPT.

A late push that breaks the one thing you need to screenshot is the single
most avoidable way to lose points on Round 1.
