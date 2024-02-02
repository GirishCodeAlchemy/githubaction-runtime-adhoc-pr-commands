# GithubAction Runtime Adhoc PR Commands

Automate custom commands on pull requests using GitHub Actions.

## Overview

This GitHub Action allows you to execute ad-hoc commands on pull requests dynamically in response to comments. It provides a flexible way to trigger specific tasks based on user interactions.

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

---

```mermaid
sequenceDiagram
    participant MainBranch as Main Branch
    participant NewBranch as New Branch
    participant User as User
    participant PullRequest as Pull Request

    MainBranch ->> NewBranch: Checkout new branch
    activate NewBranch
    User ->> NewBranch: Make changes
    User ->> NewBranch: Commit changes
    User ->> NewBranch: Push changes to remote
    deactivate NewBranch

    NewBranch ->> MainBranch: Create Pull Request (PR)
    activate PullRequest
    User ->> PullRequest: Add comment with /rebase, /autosquash, or /rebase-autosquash
    deactivate PullRequest

    note over MainBranch, PullRequest: Based on comment, perform corresponding action:
    note over NewBranch, PullRequest: Rebase:
    alt
      PullRequest ->> NewBranch: /rebase
      MainBranch ->> NewBranch: Rebased
    end
    note over NewBranch, PullRequest: Autosquash:
    alt
      PullRequest ->> NewBranch: /autosquash
      NewBranch ->> NewBranch: Autosquash
    end
    note over NewBranch, PullRequest: Rebase and Autosquash:
    alt
      PullRequest ->> NewBranch: /rebase-autosquash
      NewBranch ->> NewBranch: Autosquash
      MainBranch ->> NewBranch: Rebased
    end

```

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
        contains(github.event.comment.body, '/autosquash') ||
        contains(github.event.comment.body, '/rebase-autosquash')
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

## Sequence Diagram: Adhoc Commands Workflow

```mermaid
  sequenceDiagram
      participant User
      participant GitHubEvent
      participant GitHubActions
      participant CheckoutAction
      participant AdhocCommandsAction

      User->>GitHubEvent: Create PR Comment with /rebase or /autosquash or /rebase-autosquash
      GitHubEvent-->>GitHubActions: Trigger 'created' event on issue_comment

      alt Check if PR Comment triggers action
          GitHubActions-->>GitHubActions: Check if PR comment contains specific commands
          GitHubActions-->>CheckoutAction: Checkout the latest code
          CheckoutAction-->>AdhocCommandsAction: Running Adhoc commands
          AdhocCommandsAction-->>GitHubActions: Adhoc commands executed successfully
          GitHubActions-->>GitHubEvent: Complete Workflow
      else
          GitHubActions-->>GitHubEvent: Ignore event, no specific commands found
      end

```

### 1. Main Branch to New Branch: Checkout and Changes

- The main branch initiates the creation of a new branch.
- The user makes changes in the new branch, commits them, and pushes the changes to the remote repository.

### 2. New Branch to Main Branch: Create Pull Request

- A pull request is created from the new branch to the main branch.

### 3. User to Pull Request: Trigger Commands

- The user adds a comment to the pull request with one of the following commands: `/rebase`, `/autosquash`, or `/rebase-autosquash`.

### 4. Based on Comment: Rebase, Autosquash, or Both

- If the comment contains `/rebase`, the main branch rebases onto the new branch.
- If the comment contains `/autosquash`, autosquashing is performed in the new branch.
- If the comment contains `/rebase-autosquash`, both rebase and autosquash actions are executed.
