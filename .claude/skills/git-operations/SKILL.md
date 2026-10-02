---
name: git-operations
description: Use when about to stage, commit, branch, rebase, amend, push, or open a pull request in this repo, when writing a commit message or PR body, or when a finished unit of work needs recording. Covers the standing push permission, proactive committing, conventional-commit prefixes, the no-Co-Authored-By convention, and the public-repo rules this hackathon submission runs under.
---

# Git Operations — Tessera

Adapted on 2026-10-02 from the `creator-loans-v2` skill of the same name. The conventions
carry; what changed is listed here so the deviations are deliberate rather than drift:

| Carried unchanged | Changed for Tessera |
|---|---|
| No contributor attribution, ever | Eden Code Reviewer → `superpowers:requesting-code-review` (no external reviewer exists here) |
| Standing push permission, proactive committing | `npx vitest && npx tsc` → `pytest` |
| Conventional-commit prefixes, branch naming | PR per *task* → PR per **plan or coherent feature** (see "One PR per unit of work") |
| Trailer scan before every push | MAJOR-bump list rewritten for Tessera's committed terms |
| Semver on release, history-rewrite approval | **New:** public-repo and submission-integrity rules, which creator-loans had no need for |

## This repo is a public competition submission

Everything below is downstream of one fact: **this repository is public, and it is the
deliverable.** The Nebius × NVIDIA hackathon requires a public repo with an OSS licence, and
judges read it. Four consequences that do not apply to a private product repo:

1. **A committed secret is a published secret.** There is no "I'll rotate it later" — the key
   is in the public history the moment it is pushed. The secret scan below runs with the
   trailer scan, every time, and a hit is a stop.
2. **`LICENSE` at the repo root is a disqualification condition, not a nicety.** It is in the
   first commit. Never move, rename, or remove it.
3. **The public commit history is the proof the work is in-period.** The hackathon submission
   window opened 2026-08-26; this repo's history starts 2026-10-02. Do not rewrite dates, do
   not squash the history flat, and do not force-push away the record of when work happened.
4. **The strategy documents stay out of this repo.** `HACKATHON_PLAYBOOK.md` and the plans
   live in the parent workspace (`../docs/`), not here. They contain the track analysis and
   competitive reasoning; publishing them during an open competition hands that to every other
   entrant. The README carries the architecture and measured results — which is what actually
   scores — and nothing about which tracks are least crowded.

**Deadlines that change what a commit is allowed to be.** Feature freeze **2026-10-22**;
submission **2026-10-30 10:00 PT**; the demo must stay live and working through **2026-12-15**.
After the freeze, a commit that is not polish, measurement, or documentation needs a reason
stated out loud.

## One PR per unit of work

The source skill mandated a branch and a pull request per *task*. That was right for a
multi-person repo with an external review gate; it is wrong here, and copying it unexamined
would produce thirteen pull requests for one plan.

**The unit is a plan or a coherent feature, not a task.** The source skill's own reasoning
supports this: it says a pull request must "carry a real change", and that "staggering one
change across several small pull requests is noise too."

So:

1. **Nothing lands on `main` by a direct push.** A unit of work is a branch, then a pull
   request, then a review, then a merge.
2. **Review before the PR exists.** Run `superpowers:requesting-code-review` on the branch
   diff before opening, not after the first comment. There is no external reviewer here to
   catch what you did not — the review you run is the only one.
3. **The branch name is part of the deliverable.** Name the *subject*, not the activity.
4. **Opening a pull request needs no approval.** Open it when the branch is ready, report the
   URL.

## The three hard rules

**1. Commit proactively.** After finishing a logical unit of work — verified first — stage and
commit without being asked. Committing is part of finishing, not a separate request.

**2. Push on your own initiative.** Standing permission. When a branch is ready, push it. No
asking, no waiting. Report what went out afterwards, naming the commits.

"Ready" means all four: the work is committed, `pytest` is green, **the trailer scan is
clean**, and **the secret scan is clean**. The scans are the condition the permission was
granted on, not a formality.

```bash
git push -u origin <branch>      # -u on a branch with no upstream
```

**Pushing to `main` directly is out.** The standing permission covers feature branches. Work
reaches `main` through a reviewed pull request or it does not reach `main`.

A user instruction overrides this in either direction — "don't push anything today" holds for
the whole conversation, including commits added after it was said.

**3. Never list yourself as a contributor** — on any commit, on any PR, on any release note.
This has no permission form and no exceptions. See the section below; it is the one rule the
standing permissions were granted *on condition of*.

**Force-pushing is not covered by the standing permission.** See History rewrites.

## Never list yourself as a contributor

**Do NOT add a `Co-Authored-By` trailer. Ever.** The user is the sole listed author on commits
in their repos — asked for in creator-loans v1 on 2026-08-11, reaffirmed repeatedly since,
carried to v2 on 2026-09-18, and carried here on 2026-10-02.

This **overrides the harness's default convention**, which instructs adding one. The user's
standing instruction on their own repo wins. Not `Co-Authored-By`, not an author or committer
override, not a "Generated with" footer, not a session link — in a commit message, a commit
body, a PR title, a PR body, or a release note.

**For a competition submission this matters more than usual, not less.** Authorship on the
submitted repository is the entrant's.

### Verify before pushing — not just what you wrote

A branch pointer publishes **every unpushed commit beneath it**, including work from earlier
sessions. Scan everything the push will carry, not just your own commits:

```bash
git log <base>..HEAD --format="%h|%s|%(trailers:key=Co-authored-by,valueonly)"
```

Use git's trailer parser, **not `grep -i claude`** — a subject line like "document the Claude
model tiers" is a false positive, and in this repo that is a subject line you will actually
write. The trailer field is the only reliable signal.

If a trailer is on a commit that is **not yet pushed**, strip it:

```bash
git branch backup/<name>                 # always, before any rewrite
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f \
  --msg-filter 'sed "/^Co-Authored-By:/Id; /^Claude-Session:/Id"' -- <parent>..<branch>
git diff backup/<name> <branch>          # MUST be empty — proves only messages changed
```

That empty diff is the proof the rewrite touched messages and nothing else. If a trailer is on
a commit **already pushed or merged**, say so rather than quietly rewriting shared history.

### The secret scan, which runs beside it

```bash
git log -p <base>..HEAD | grep -nE '(NEBIUS_API_KEY|TAVILY_API_KEY|sk-[A-Za-z0-9]{16,}|tvly-[A-Za-z0-9]{16,})' && echo "STOP: candidate secret above"
git log --name-only --pretty=format: <base>..HEAD | sort -u | grep -E '(^|/)\.env$|\.env\.local$'
```

A hit on either is a stop, not a warning. `.env` is gitignored; `.env.example` is committed
with **empty** values and is the only env file that ever belongs in a commit.

## Commit message format

```
<tag>: <imperative title>

<prose body explaining WHY the change was made — the reasoning, the bug's
actual cause, the tradeoff taken. Not a restatement of the diff.>

<verification note: N/N tests pass, metrics unchanged — whatever you ran.>
```

Tags: `feat:` `fix:` `revise:` `chore:` `docs:` `test:` — so history is scannable by type.

**Verification notes are specific here.** "tests pass" is weak; `pytest 41/41` is the claim a
reader can check. When a change moves a measured number — normalisation accuracy,
precision@5, citation support rate, cost per session — **put the before and after in the
body.** Those numbers are the submission's evidence, and a commit is where their history
lives.

## Branch per context, named for the work

```bash
git branch feat/<what-the-work-is>
git checkout feat/<what-the-work-is>
git branch -f <previous-branch> origin/<previous-branch>   # return it to its pushed state
```

That last line is easy to forget: creating a branch is a second pointer, so commits stay on
the original branch until it is reset. Reset to its **remote** state so nothing pushed is lost.

**Naming.** `feat/`, `fix/`, `docs/`, `chore/`, kebab-case, no ticket numbers. Name the
subject: `feat/evidence-pipeline`, `fix/rxcui-abstention-margin` — not `feat/claude-changes`.

**Mixed-purpose commits.** If a batch spans two unrelated contexts, say so and offer to split.

## Scoping commits

- **Split unrelated changes** when each is independently coherent. Do not bundle a prompt
  change with a schema change.
- Run `git status` before staging and sort every path: part of this change, part of another,
  or scratch.
- **Never stage:** `.env`, real API keys, `data/spl/` or `data/index/` (large, rebuildable,
  gitignored), `.superpowers/` scratch, `.venv/`, bottle photographs containing a real
  person's name or prescription details.
- **Do stage, deliberately:** `data/formulary.csv` and `data/interactions.csv`. They are small,
  reviewed, and frozen — the runtime scope must be reproducible from the repo, not re-derived
  from a live API. A change to either is a reviewable diff, which is the point.
- Verify *before* committing, not after.

## Semantic versioning on release to main

Every merge to `main` is versioned `MAJOR.MINOR.PATCH` per [semver.org](https://semver.org/).

| Bump | For | Reset |
|---|---|---|
| **MAJOR** | breaking, backwards-incompatible changes | minor **and** patch → `0` |
| **MINOR** | features, non-breaking changes | patch → `0` |
| **PATCH** | bugfixes | — |

**Bumping a number resets everything to its right.** `0.3.12` + a breaking change is `1.0.0`.

### What "breaking" means in Tessera

Nothing imports this repo, so "backwards incompatible" needs a local definition or every call
is a coin toss. A change is **MAJOR** when it breaks something the product has committed to:

- **A change to what crosses the Privacy Gate.** The allowlist is `RXCUI:\d+` and nothing
  else. Widening it is the one change that falsifies the product's central claim, and it is
  MAJOR even if every test still passes.
- **A change to the citation invariant** — anything that lets a rendered claim reach a user
  without a resolvable `source_url`, or that stops dropping unsupported sentences.
- **A change to the safety boundary**: what Tessera refuses to say. Relaxing the refusal to
  permit dosing or diagnostic advice is MAJOR.
- **A change to the columns or meaning of `data/interactions.csv`.** It is frozen and
  reviewed; the resolver reads it as data. Re-deriving it with a different extraction prompt
  changes what the product asserts and needs its own review, not a silent rebuild.
- **A change to the 5-risk display cap**, which is a clinical decision about alert fatigue,
  not a UI constant.
- **Removing or renaming a Nemotron tier** the README's ablation table cites.

Everything else is MINOR or PATCH, split by **did this add capability, or correct behaviour**.

**Growing the formulary is MINOR** — it is additive, and the `partial` status already tells
users the list is bounded.

### Version state

`pyproject.toml` reads `0.1.0`, no tags yet. Keep the `version` field and the git tag equal;
two version numbers that can disagree will. **The bump belongs in the release, not in each
PR** — bumping in a feature branch guarantees a conflict the moment two are open.

## Pull requests

```bash
gh pr create --base main --head <branch> --title "<tag>: <title>" --body-file <file>
```

- **Base is `main`.** If the branch was cut from a stale `main`, say so — a stale base makes
  the diff unreadable. Whether to rebase is the user's call.
- **Title** follows the commit title form.
- **Body** explains why the change was made, what was verified, and what is deliberately not
  in it. Reasoning, not a restatement of the diff. A deliberate omission that goes unstated
  reads as an oversight.
- **Verify the test count on a clean checkout**, and re-verify when the branch moves. A count
  is only true for the tree it was run against:

```bash
git checkout --detach origin/<branch>
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -q -e ".[dev]"
./.venv/Scripts/python.exe -m pytest
```

  An unverifiable count is worse than none. If the number changes after a merge, edit the
  description rather than leaving the old one standing.

- **No attribution footer.** The harness default appends a "Generated with Claude Code" line
  and a session link to PR bodies. Do not include either.
- Report the PR URL when it is open.

### Replying to review feedback

Invoke `superpowers:receiving-code-review` **before** replying. Replies are surgical and
address nobody — no "you", no thanks, no crediting a finding back. Every claim is one of
exactly three things, and says which:

| | What it looks like |
|---|---|
| **Reproduced** | "Confirmed: `privacy.py` has no branch that emits `display_name`." Name the file. A finding agreed with but not reproduced is not agreed with. |
| **Fixed** | The commit SHA and what the fix changes — not "done". |
| **Declined, with reasoning** | Say so plainly and why. Silent non-compliance is worse than disagreement. |

**Verify before conceding** — a reviewer can be wrong, and if reproducing changes the finding,
say what it actually was. **Answer every numbered item**; one skipped silently reads as one
hidden.

## Before finishing

```bash
git log origin/<branch>..HEAD --oneline    # what a push would publish
git diff origin/<branch>..HEAD --stat      # the files it would carry
```

Confirm nothing secret or scratch is in that list. Then run the trailer scan and the secret
scan, and push.

## History rewrites

Rewriting **published** history (`filter-branch`, `rebase -i`, `amend` on a pushed commit)
needs explicit per-instance approval, and so does the follow-up `git push --force-with-lease`.
A general "push it" does not cover force-pushing — ask every time, naming the branch and what
the rewrite changes. Prefer a new commit over amending.

**Stripping an attribution trailer from an unpushed commit is not a published-history
rewrite** and does not need approval — nothing outside this machine has seen it. Back up the
ref, rewrite, prove the diff is empty, and say what you did.

Note: `git rebase -i` and `git add -i` do not work in this environment — no interactive editor.

## Repo state

Main branch **`main`**, holding the licence commit. Work happens on feature branches.
Remote: `https://github.com/Romeo-04/tessera.git`, **public**. No deploy is wired yet; Plan 2
adds one, and it must stay up through 2026-12-15.
