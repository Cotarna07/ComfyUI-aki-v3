# Tooling Reference

Quick reference for all GitHub operations used in this skill.

**Primary tool: `gh` CLI.** Always set `GH_PAGER=cat` to prevent interactive pagers from blocking execution.

---

## Labels

```sh
GH_PAGER=cat gh label create "<name>" --color "<hex>" --description "<text>"
GH_PAGER=cat gh label delete "<name>" --yes
GH_PAGER=cat gh label list
```

## Issues

```sh
GH_PAGER=cat gh issue create --title "<title>" --body "<body>" --label "<l1>,<l2>" --milestone "<name>"
GH_PAGER=cat gh issue list --milestone "<name>" --state open --label "<label>"
GH_PAGER=cat gh issue list --state open --milestone "" --json number,title,labels -q '.[] | "#\(.number) \(.title)"'
GH_PAGER=cat gh issue edit <number> --add-label "<label>" --remove-label "<label>"
GH_PAGER=cat gh issue edit <number> --milestone "<name>"
GH_PAGER=cat gh issue close <number> --comment "<reason>"
GH_PAGER=cat gh issue view <number>
GH_PAGER=cat gh issue pin <number>
```

## Pull Requests

```sh
GH_PAGER=cat gh pr create --title "<title>" --body "<body>" --base main --head <branch>
GH_PAGER=cat gh pr list --state open
GH_PAGER=cat gh pr merge <number> --squash --delete-branch
GH_PAGER=cat gh pr view <number>
GH_PAGER=cat gh pr edit <number> --add-label "<label>" --remove-label "<label>"
```

## Milestones (via API)

```sh
# List milestones
GH_PAGER=cat gh api repos/{owner}/{repo}/milestones \
  --jq '.[] | "\(.number): \(.title) (due: \(.due_on | split("T")[0]))"'

# Create milestone
GH_PAGER=cat gh api repos/{owner}/{repo}/milestones --method POST \
  --field title="Sprint N" \
  --field description="Sprint Goal: ..." \
  --field due_on="2026-03-06T23:59:59Z"

# Close milestone
GH_PAGER=cat gh api repos/{owner}/{repo}/milestones/<number> \
  --method PATCH --field state="closed"

# Update milestone
GH_PAGER=cat gh api repos/{owner}/{repo}/milestones/<number> \
  --method PATCH --field description="Updated goal"
```

## Releases

```sh
GH_PAGER=cat gh release create v<version> --title "<title>" --notes "<markdown>"
GH_PAGER=cat gh release list
```
