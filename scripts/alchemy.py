import json
import os
import subprocess
import time

import requests
from colorama import Fore, Style
from pyfiglet import figlet_format


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
        self.display_logo()
        self.get_pr_number()

    def display_logo(self):
        print("="*100)
        print(Fore.GREEN)
        name = "  GirishCodeAlchemy"
        formatted_text = figlet_format(name, font="standard", width=100)
        for line in formatted_text.splitlines():
            print(Fore.GREEN + Style.BRIGHT + line)
        print(Fore.RESET)
        print("="*100)

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

    def fetch_user_login_from_events(self):
        print("Fetching user info from events...")
        with open(self.github_event_path, "r") as f:
            data = json.load(f)
            self.user_login = data.get("comment", {}).get("user", {}).get("login")
            if self.user_login is None:
                self.user_login = data.get("pull_request", {}).get("user", {}).get("login")

    def get_comment_body(self):
        print("Getting comment body...")
        response = requests.get(
            f"{self.uri}/repos/{self.github_repository}/issues/{self.pr_number}/comments",
            headers={"Authorization": f"Bearer {self.github_token}"}
        )
        self.comment_body = response.json()[-1]["body"]
        return self.comment_body

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

    def get_user_info(self):
        print("Getting user info...")
        response = requests.get(
            f"{self.uri}/users/{self.user_login}",
            headers=self.header
        )
        data = response.json()
        user = data.get("name", self.user_login)
        user_email = data.get("email", f"{self.user_login}@users.noreply.github.com")
        if user_email is None:
            user_email = f"{self.user_login}@users.noreply.github.com"
        return user, user_email

    def git_config(self, user, user_email, head_repo):
        print("Configuring git...")
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/github/workspace"])
        subprocess.run(["git", "remote", "set-url", "origin", f"https://x-access-token:{self.github_token}@github.com/{self.github_repository}.git"])
        subprocess.run(["git", "config", "--global", "user.email", str(user_email)])
        subprocess.run(["git", "config", "--global", "user.name", str(user)])
        subprocess.run(["git", "remote", "add", "fork", f"https://x-access-token:{self.github_token}@github.com/{head_repo}.git"])

    def autosquash(self, base_branch, head_branch):
        print("Autosquashing commits...")
        subprocess.run(["git", "fetch", "fork", head_branch], check=True, text=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", f"{head_branch}", f"fork/{head_branch}"], check=True, text=True, capture_output=True)
        try:
            # env = os.environ.copy()
            # env["GIT_SEQUENCE_EDITOR"] = ":"
            subprocess.run(["git", "commit", "--amend", "-m", "squash!"], check=True, text=True, capture_output=True)
            squash_output = subprocess.run(["GIT_SEQUENCE_EDITOR=true","git", "rebase", "-i", "--autosquash", f"origin/{base_branch}"], check=True, text=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            error_message = f"Error during Autosquash. Return code: {e.returncode}"
            error_message += f"\n\nstdout:\n{e.stdout}"
            error_message += f"\nstderr:\n{e.stderr}"
            error_lines = error_message.splitlines()
            formatted_error = "\n".join([f"{Fore.RED}{Style.BRIGHT}{line}{Style.RESET_ALL}" for line in error_lines])
            print(formatted_error)
            exit(1)
        print(f"{Fore.GREEN}{Style.BRIGHT}Autosquash Output:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{squash_output.stdout}{Style.RESET_ALL}")
        print(f"{Fore.RED}{squash_output.stderr}{Style.RESET_ALL}")

        subprocess.run(["git", "status"], check=True, text=True, capture_output=True)
        subprocess.run(["git", "push", "--force-with-lease", "fork", f"fork/{head_branch}:{head_branch}"], check=True, text=True, capture_output=True)

    def rebase(self, base_branch, head_branch, autosquash):
        print(f"Performing git {self.comment_body}...")
        subprocess.run(["git", "fetch", "origin", base_branch], check=True, text=True, capture_output=True)
        subprocess.run(["git", "fetch", "fork", head_branch], check=True, text=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", f"fork/{head_branch}", f"fork/{head_branch}"], check=True, text=True, capture_output=True)

        if autosquash:
            rebase_output = subprocess.run(["git", "rebase", "-i", "--autosquash", f"origin/{base_branch}"], text=True, capture_output=True)
        rebase_output = subprocess.run(["git", "rebase", f"origin/{base_branch}"], text=True, capture_output=True)

        if rebase_output.returncode != 0:
            error_message = f"Error during rebase. Return code: {rebase_output.returncode}"
            error_message += f"\n\nstdout:\n{rebase_output.stdout}"
            error_message += f"\nstderr:\n{rebase_output.stderr}"
            error_lines = error_message.splitlines()
            formatted_error = "\n".join([f"{Fore.RED}{Style.BRIGHT}{line}{Style.RESET_ALL}" for line in error_lines])
            print(formatted_error)
            exit(1)

        else:
            print(f"{Fore.GREEN}{Style.BRIGHT}Rebase Output:{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{rebase_output.stdout}{Style.RESET_ALL}")
            print(f"{Fore.RED}{rebase_output.stderr}{Style.RESET_ALL}")

        subprocess.run(["git", "status"], check=True, text=True, capture_output=True)
        subprocess.run(["git", "push", "--force-with-lease", "fork", f"fork/{head_branch}:{head_branch}"], check=True, text=True, capture_output=True)

    def run(self, autosquash=False):
        print("Running GitHubAdhocAction...")
        pr_info = self.get_pr_info()
        base_repo = pr_info["base"]["repo"]["full_name"]
        base_branch = pr_info["base"]["ref"]
        self.fetch_user_login_from_events()
        user, user_email = self.get_user_info()
        head_repo = pr_info["head"]["repo"]["full_name"]
        head_branch = pr_info["head"]["ref"]
        print(f"---> Base repo: {base_repo}")
        print(f"---> Base branch: {base_branch}")
        print(f"---> User login: {self.user_login}")
        print(f"---> User: {user}")
        print(f"---> User email: {user_email}")
        print(f"---> Head repo: {head_repo}")
        print(f"---> Head branch: {head_branch}")
        self.git_config(user, user_email, head_repo)
        if self.comment_body == "/autosquash":
            self.autosquash(base_branch, head_branch)
        else:
            self.rebase(base_branch, head_branch, autosquash)


if __name__ == '__main__':
    adhoc_action = GitHubAdhocAction()
    comment_body = adhoc_action.get_comment_body()
    print(f"---> Comment body {comment_body}")
    autosquash = False
    if "autosquash" in comment_body:
        autosquash = True
    if comment_body in ["/autosquash", "/rebase", "/rebase-autosquash"]:
        adhoc_action.run(autosquash)
    else:
        print(f"{Fore.RED}{Style.BRIGHT}Invalid comment body. Exiting....{Style.RESET_ALL}")
        exit(1)