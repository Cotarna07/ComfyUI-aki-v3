# GitHub Issue & PR Templates

Copy these files verbatim into `.github/` during project initialization.

---

## `.github/ISSUE_TEMPLATE/backlog-item.yml`

```yaml
name: Backlog Item
description: Add a new item to the Product Backlog
title: "[BACKLOG] "
labels: []
body:
  - type: markdown
    attributes:
      value: "## New Backlog Item"
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What needs to be done and why?
      placeholder: "As a user, I want to... so that..."
    validations:
      required: true
  - type: textarea
    id: acceptance-criteria
    attributes:
      label: Acceptance Criteria
      description: Conditions that must be true for this to be Done
      placeholder: |
        - [ ] Criterion 1
        - [ ] Criterion 2
    validations:
      required: true
  - type: dropdown
    id: type
    attributes:
      label: Type
      options:
        - feature
        - bug
        - chore
        - spike
        - docs
    validations:
      required: true
  - type: dropdown
    id: priority
    attributes:
      label: Priority
      options:
        - critical
        - high
        - medium
        - low
    validations:
      required: true
  - type: dropdown
    id: size
    attributes:
      label: Estimated Size
      options:
        - "xs (< 1 hour)"
        - "s (1-4 hours)"
        - "m (4-8 hours)"
        - "l (1-2 days)"
        - "xl (> 2 days — consider splitting)"
    validations:
      required: true
  - type: textarea
    id: notes
    attributes:
      label: Technical Notes
      description: Dependencies, constraints, implementation ideas
      placeholder: "Depends on #... / Blocked by... / Consider using..."
    validations:
      required: false
```

---

## `.github/ISSUE_TEMPLATE/bug-report.yml`

```yaml
name: Bug Report
description: Report something that isn't working correctly
title: "[BUG] "
labels: ["type:bug"]
body:
  - type: textarea
    id: description
    attributes:
      label: What happened?
      description: Clear description of the bug
      placeholder: "When I do X, Y happens instead of Z"
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Minimal steps to trigger the bug
      placeholder: |
        1. Go to...
        2. Click on...
        3. See error...
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What should happen instead?
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Environment / Context
      description: OS, browser, version, relevant config
      placeholder: "macOS 15, Node 22, Chrome 130"
    validations:
      required: false
  - type: dropdown
    id: priority
    attributes:
      label: Severity
      options:
        - "critical — app crashes or data loss"
        - "high — major feature broken, no workaround"
        - "medium — feature broken but workaround exists"
        - "low — cosmetic or minor annoyance"
    validations:
      required: true
```

---

## `.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## Summary

<!-- What does this PR do and why? Reference the issue: Closes #N -->

Closes #

## Definition of Done

- [ ] Code implemented and functional
- [ ] All acceptance criteria from the issue are met
- [ ] Tests written and passing (when applicable)
- [ ] No lint or compilation errors
- [ ] Self-reviewed (read your own diff)
- [ ] Documentation updated (if user-facing behavior changed)
```

---

## `.github/labeler.yml`

Rules for `actions/labeler` to auto-label PRs based on changed files.
**Adapt glob patterns to the project's actual directory structure.**

```yaml
"type:docs":
  - changed-files:
      - any-glob-to-any-file:
          - "**/*.md"
          - "docs/**"
          - "LICENSE*"
          - "CHANGELOG*"

"type:chore":
  - changed-files:
      - any-glob-to-any-file:
          - ".github/**"
          - "**/Dockerfile"
          - "**/.dockerignore"
          - "**/Makefile"
          - "**/.gitignore"
          - ".editorconfig"
          - ".prettierrc*"
          - ".eslintrc*"
          - "eslint.config.*"
          - "tsconfig*.json"
          - "biome.json"
          - "renovate.json"

# Adapt these to the project's source layout
"type:feature":
  - changed-files:
      - any-glob-to-any-file:
          - "src/**"
          - "lib/**"
          - "app/**"
          - "cmd/**"
          - "internal/**"
          - "pkg/**"
```

---

## `.github/release-drafter.yml`

Auto-generates release notes from merged PRs, categorized by Scrum labels.

```yaml
name-template: "v$RESOLVED_VERSION"
tag-template: "v$RESOLVED_VERSION"
template: |
  ## What's Changed

  $CHANGES

  **Full Changelog**: https://github.com/$OWNER/$REPOSITORY/compare/$PREVIOUS_TAG...v$RESOLVED_VERSION
categories:
  - title: "🚀 Features"
    labels:
      - "type:feature"
  - title: "🐛 Bug Fixes"
    labels:
      - "type:bug"
  - title: "🧰 Maintenance"
    labels:
      - "type:chore"
      - "tech-debt"
  - title: "📝 Documentation"
    labels:
      - "type:docs"
  - title: "🔬 Spikes & Research"
    labels:
      - "type:spike"
change-template: "- $TITLE (#$NUMBER) @$AUTHOR"
change-title-escapes: '\<*_&'
autolabeler:
  - label: "type:feature"
    title:
      - '/^feat(\(.+\))?!?:/i'
  - label: "type:bug"
    title:
      - '/^fix(\(.+\))?!?:/i'
  - label: "type:docs"
    title:
      - '/^docs(\(.+\))?!?:/i'
  - label: "type:chore"
    title:
      - '/^(chore|refactor|test|build|ci|perf|style)(\(.+\))?!?:/i'
  - label: "type:spike"
    title:
      - '/^spike(\(.+\))?!?:/i'
  - label: "breaking"
    title:
      - '/^[a-z]+(\(.+\))?!:/i'
version-resolver:
  major:
    labels:
      - "breaking"
  minor:
    labels:
      - "type:feature"
  patch:
    labels:
      - "type:bug"
      - "type:chore"
      - "type:docs"
  default: patch
```

> `autolabeler` labels PRs automatically from conventional commit prefixes in the title (`feat:` → `type:feature`, `fix:` → `type:bug`, etc.).
