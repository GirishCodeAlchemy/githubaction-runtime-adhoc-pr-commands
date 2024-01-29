#!/bin/bash

set -e

echo "githubevent path: $GITHUB_EVENT_PATH"
if [ -z "$PR_NUMBER" ]; then
	PR_NUMBER=$(jq -r ".pull_request.number" "$GITHUB_EVENT_PATH")
	if [[ "$PR_NUMBER" == "null" ]]; then
		PR_NUMBER=$(jq -r ".issue.number" "$GITHUB_EVENT_PATH")
	fi
	if [[ "$PR_NUMBER" == "null" ]]; then
		echo "Failed to determine PR Number."
		exit 1
	fi
fi

echo "Collecting information about PR #$PR_NUMBER of $GITHUB_REPOSITORY..."

# echo all environment variables
echo "Environment variables:"
env | sort

if [[ -z "$GITHUB_TOKEN" ]]; then
	echo "Set the GITHUB_TOKEN env variable."
	exit 1
fi

# Fetch the comment body
COMMENT_BODY=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
    "https://api.github.com/repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" | \
    jq -r ".[] | select(.id == $GITHUB_EVENT_ID) | .body")

echo "Comment Body: $COMMENT_BODY"

URI=https://api.github.com
API_HEADER="Accept: application/vnd.github.v3+json"
AUTH_HEADER="Authorization: token $GITHUB_TOKEN"

MAX_RETRIES=${MAX_RETRIES:-6}
RETRY_INTERVAL=${RETRY_INTERVAL:-10}
REBASEABLE=""
pr_resp=""
for ((i = 0 ; i < $MAX_RETRIES ; i++)); do
	pr_resp=$(curl -X GET -s -H "${AUTH_HEADER}" -H "${API_HEADER}" \
		"${URI}/repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER")
    echo "--> pr_resp: $pr_resp"
	REBASEABLE=$(echo "$pr_resp" | jq -r .rebaseable)
	if [[ "$REBASEABLE" == "null" ]]; then
		echo "The PR is not ready to rebase, retry after $RETRY_INTERVAL seconds"
		sleep $RETRY_INTERVAL
		continue
	else
		break
	fi
done

if [[ "$REBASEABLE" != "true" ]] ; then
	echo "GitHub doesn't think that the PR is rebaseable!"
	exit 1
fi

BASE_REPO=$(echo "$pr_resp" | jq -r .base.repo.full_name)
BASE_BRANCH=$(echo "$pr_resp" | jq -r .base.ref)
echo "Base repo: $BASE_REPO"
echo "Base branch: $BASE_BRANCH"
USER_LOGIN=$(jq -r ".comment.user.login" "$GITHUB_EVENT_PATH")
echo "USER_LOGIN: $USER_LOGIN"

if [[ "$USER_LOGIN" == "null" ]]; then
	USER_LOGIN=$(jq -r ".pull_request.user.login" "$GITHUB_EVENT_PATH")
fi

user_resp=$(curl -X GET -s -H "${AUTH_HEADER}" -H "${API_HEADER}" \
	"${URI}/users/${USER_LOGIN}")

USER_NAME=$(echo "$user_resp" | jq -r ".name")
if [[ "$USER_NAME" == "null" ]]; then
	USER_NAME=$USER_LOGIN
fi
echo "USER_NAME: $USER_NAME"
USER_NAME="${USER_NAME} (Rebase PR Action)"

USER_EMAIL=$(echo "$user_resp" | jq -r ".email")
if [[ "$USER_EMAIL" == "null" ]]; then
	USER_EMAIL="$USER_LOGIN@users.noreply.github.com"
fi

echo "USER_NAME: $USER_NAME"
echo "USER_EMAIL: $USER_EMAIL"

if [[ -z "$BASE_BRANCH" ]]; then
	echo "Cannot get base branch information for PR #$PR_NUMBER!"
	exit 1
fi

HEAD_REPO=$(echo "$pr_resp" | jq -r .head.repo.full_name)
HEAD_BRANCH=$(echo "$pr_resp" | jq -r .head.ref)

echo "Head repo: $HEAD_REPO, HeadBranch : $HEAD_BRANCH"
echo "Base branch for PR #$PR_NUMBER is $BASE_BRANCH"

USER_TOKEN=${USER_LOGIN//-/_}_TOKEN
UNTRIMMED_COMMITTER_TOKEN=${!USER_TOKEN:-$GITHUB_TOKEN}
COMMITTER_TOKEN="$(echo -e "${UNTRIMMED_COMMITTER_TOKEN}" | tr -d '[:space:]')"

# See https://github.com/actions/checkout/issues/766 for motivation.
git config --global --add safe.directory /github/workspace

git remote set-url origin https://x-access-token:$COMMITTER_TOKEN@github.com/$GITHUB_REPOSITORY.git
git config --global user.email "$USER_EMAIL"
git config --global user.name "$USER_NAME"

git remote add fork https://x-access-token:$COMMITTER_TOKEN@github.com/$HEAD_REPO.git

set -o xtrace

# make sure branches are up-to-date
git fetch origin $BASE_BRANCH
git fetch fork $HEAD_BRANCH

# do the rebase
git checkout -b fork/$HEAD_BRANCH fork/$HEAD_BRANCH
if [[ $INPUT_AUTOSQUASH == 'true' ]]; then
	GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash origin/$BASE_BRANCH
else
	git rebase origin/$BASE_BRANCH
fi
git status

# push back
git push --force-with-lease fork fork/$HEAD_BRANCH:$HEAD_BRANCH