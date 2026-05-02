# GitHub Actions Workflows

Copy these files verbatim into `.github/workflows/` during project initialization.

---

## `labeler.yml` — Auto-label PRs by changed files

Uses `.github/labeler.yml` rules. See [templates.md](templates.md) for the labeler config.

```yaml
name: Labeler

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  labeler:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v5
        with:
          sync-labels: true
```

---

## `stale.yml` — Flag inactive backlog items

Marks issues inactive after 30 days. Does **not** auto-close — flags for review during refinement.

```yaml
name: Stale Issues

on:
  schedule:
    - cron: "0 9 * * 1" # Every Monday at 9:00 UTC

permissions:
  issues: write

jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v9
        with:
          stale-issue-message: >
            This issue has been inactive for 30 days.
            It will be reviewed in the next backlog refinement.
            If it's still relevant, remove the `stale` label.
          stale-issue-label: "stale"
          days-before-stale: 30
          days-before-close: -1 # Never auto-close
          exempt-issue-labels: "status:in-progress,status:blocked,mvp,priority:critical,priority:high"
          exempt-milestones: true # Don't mark sprint items as stale
```

---

## `release-drafter.yml` — Maintain a draft release

Auto-accumulates merged PRs into a draft release. Ready to publish at sprint end.

```yaml
name: Release Drafter

on:
  push:
    branches: [main, master]
  pull_request_target:
    types: [opened, reopened, synchronize, edited]

permissions:
  contents: write
  pull-requests: write

jobs:
  update-release-draft:
    runs-on: ubuntu-latest
    steps:
      - uses: release-drafter/release-drafter@v6
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## `auto-assign.yml` — Auto-assign PR creator

For solo/small teams, auto-assigns the PR creator as assignee.

```yaml
name: Auto Assign

on:
  pull_request:
    types: [opened]

permissions:
  pull-requests: write

jobs:
  assign:
    runs-on: ubuntu-latest
    steps:
      - uses: toshimaru/auto-author-assign@v2.1.1
```
