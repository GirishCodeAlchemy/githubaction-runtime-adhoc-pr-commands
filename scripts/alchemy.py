import json
import os
import subprocess
import time

import requests


class GitHubAdhocAction:
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("Set the GITHUB_TOKEN env variable.")
        self.github_repository = os.environ.get('GITHUB_REPOSITORY')
        self.pr_number = os.environ.get('PR_NUMBER')
        self.github_event_path = os.environ.get('GITHUB_EVENT_PATH')
        self.uri = "https://api.github.com"
        self.header = {
            'Authorization': f'Bearer {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'}
        self.max_retries = 6
        self.retry_interval = 10
        self.get_pr_number()

    def get_pr_number(self):
        print("Getting PR number...")
        if self.pr_number is None:
            with open(self.github_event_path, "r") as f:
                data = json.load(f)
                self.pr_number = data.get("pull_request", {}).get("number")
                if self.pr_number is None:
                    self.pr_number = data.get("issue", {}).get("number")
        if self.pr_number is None:
            raise Exception("Failed to determine PR Number.")
        print(f"PR_NUMBER: {self.pr_number}")
        return self.pr_number

    def get_comment_body(self):
        print("Getting comment body...")
        response = requests.get(
            f"{self.uri}/repos/{self.github_repository}/issues/{self.pr_number}/comments",
            headers={"Authorization": f"Bearer {self.github_token}"}
        )
        return response.json()[-1]["body"]

    def get_pr_info(self):
        print("Getting PR info...")
        for _ in range(self.max_retries):
            response = requests.get(
                f"{self.uri}/repos/{self.github_repository}/pulls/{self.pr_number}",
                headers=self.header
            )
            data = response.json()
            rebaseable = data.get("rebaseable")
            if rebaseable is None:
                print("The PR is not ready to rebase, retry after {} seconds".format(self.retry_interval))
                time.sleep(self.retry_interval)
                continue
            else:
                print("PR info retrieved successfully.")
                return data
        if rebaseable != "true":
            raise Exception("GitHub doesn't think that the PR is rebaseable!")

    def get_user_info(self, user_login):
        print("Getting user info...")
        response = requests.get(
            f"{self.uri}/users/{user_login}",
            headers=self.header
        )
        data = response.json()
        user = data.get("name", user_login)
        user_email = data.get("email", f"{user_login}@users.noreply.github.com")
        return user, user_email

    def git_config(self, user, user_email, head_repo):
        print("Configuring git...")
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/github/workspace"])
        subprocess.run(["git", "remote", "set-url", "origin", f"https://x-access-token:{self.github_token}@github.com/{self.github_repository}.git"])
        subprocess.run(["git", "config", "--global", "user.email", user_email])
        subprocess.run(["git", "config", "--global", "user.name", user])
        subprocess.run(["git", "remote", "add", "fork", f"https://x-access-token:{self.github_token}@github.com/{head_repo}.git"])

    def rebase(self, base_branch, head_branch, autosquash):
        print("Performing git rebase...")
        subprocess.run(["git", "fetch", "origin", base_branch])
        subprocess.run(["git", "fetch", "fork", head_branch])
        subprocess.run(["git", "checkout", "-b", f"fork/{head_branch}", f"fork/{head_branch}"])
        if autosquash:
            subprocess.run(["GIT_SEQUENCE_EDITOR=:", "git", "rebase", "-i", "--autosquash", f"origin/{base_branch}"])
        else:
            subprocess.run(["git", "rebase", f"origin/{base_branch}"])
        subprocess.run(["git", "status"])
        subprocess.run(["git", "push", "--force-with-lease", "fork", f"fork/{head_branch}:{head_branch}"])

    def run(self, autosquash=False):
        print("Running GitHubAdhocAction...")
        pr_info = self.get_pr_info()
        base_repo = pr_info["base"]["repo"]["full_name"]
        base_branch = pr_info["base"]["ref"]
        user_login = pr_info["user"]["login"]
        user, user_email = self.get_user_info(user_login)
        head_repo = pr_info["head"]["repo"]["full_name"]
        head_branch = pr_info["head"]["ref"]
        print(f"---> Base repo: {base_repo}")
        print(f"---> Base branch: {base_branch}")
        print(f"---> User login: {user_login}")
        print(f"---> User: {user}")
        print(f"---> User email: {user_email}")
        print(f"---> Head repo: {head_repo}")
        print(f"---> Head branch: {head_branch}")
        self.git_config(user, user_email, head_repo)
        self.rebase(base_branch, head_branch, autosquash)


if __name__ == '__main__':
    adhoc_action = GitHubAdhocAction()
    comment_body = adhoc_action.get_comment_body()
    print(f"---> Comment body {comment_body}")
    adhoc_action.run()