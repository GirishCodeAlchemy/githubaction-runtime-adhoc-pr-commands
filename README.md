# GithubAction Runtime Adhoc PR Commands

Automate custom commands on pull requests using GitHub Actions.

## Overview

This GitHub Action allows you to execute ad-hoc commands on pull requests dynamically in response to comments. It provides a flexible way to trigger specific tasks based on user interactions.

## Usage

### Workflow Setup

Create a GitHub Actions workflow YAML file, for example, `.github/workflows/adhoc_commands.yml`:

```yaml
name: PR Adhoc commands
on:
  issue_comment:
    types: [created]
jobs:
  build:
    name: PR-Adhoc-Commands
    runs-on: ubuntu-latest
    if: >-
      github.event.issue.pull_request != '' &&
      (
        contains(github.event.comment.body, '/rebase') ||
        contains(github.event.comment.body, '/autosquash')
      )
    steps:
      - name: Checkout the latest code
        uses: actions/checkout@v3
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - name: Running Adhoc commands
        uses: GirishCodeAlchemy/githubaction-runtime-adhoc-pr-commands@main
        with:
          autosquash: ${{ contains(github.event.comment.body, '/autosquash') || contains(github.event.comment.body, '/rebase-autosquash') }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

```mermaid
gitGraph
    commit "1"
    commit "2"
    branch develop
    commit "3"
    commit "4"
    commit "5"
    checkout main
    commit "6"
    commit "7"
    checkout develop
    commit "(rebase and squash here)"
    merge main
```
