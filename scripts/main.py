import json
import os
import subprocess
import time

import requests
from requests.auth import HTTPBasicAuth


class GitHubAdhocAction:
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("Set the GITHUB_TOKEN env variable.")

        self.github_repo = os.environ.get('GITHUB_REPOSITORY')
        self.pr_number = os.environ.get('PR_NUMBER')
        print(f'PR Number: {self.pr_number}')
        self.comment_body = None
        self.auth_header = {
            'Authorization': f'Bearer {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'}
        print(f"Collecting information about PR #{self.pr_number} of {self.github_repo} ...")
        self.extract_info_from_events()
        print(f'-->PR Number: {self.pr_number}')

    def extract_info_from_events(self):
        github_event_path = os.environ.get('GITHUB_EVENT_PATH')
        if github_event_path:
            with open(github_event_path, 'r') as file:
                event_data = json.load(file)
                if self.pr_number is None:
                    self.get_pr_number_from_event(event_data)
                self.user_login = self.fetch_user_login_from_events(event_data)

        print("Failed to determine PR Number and user_login.")
        exit(1)

    def get_pr_number_from_event(self, event_data):
        self.pr_number = event_data.get("pull_request", {}).get("number")
        if self.pr_number is None:
            self.pr_number = event_data.get("issue", {}).get("number")
        if self.pr_number is None:
            raise Exception("Failed to determine PR Number.")
        return self.pr_number

    def fetch_user_login_from_events(self, event_data):
        user_login = event_data.get("comment", {}).get("user", {}).get("login")
        if user_login is None:
            user_login = event_data.get("pull_request", {}).get("user", {}).get("login")
            return user_login
        else:
            return user_login

    def fetch_comment_body(self):
        url = f'https://api.github.com/repos/{self.github_repo}/issues/{self.pr_number}/comments'
        headers = {'Authorization': f'Bearer {self.github_token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        comments = response.json()
        self.comment_body = comments[-1]['body']
        print(f'Comment body: {self.comment_body}')
        return self.comment_body

    def rebase_pr(self):
        uri = 'https://api.github.com'
        max_retries = 6
        retry_interval = 10
        rebaseable = None

        for _ in range(max_retries):
            pr_resp = requests.get(
                f'{uri}/repos/{self.github_repo}/pulls/{self.pr_number}',
                headers=self.auth_header
            )
            pr_resp.raise_for_status()
            rebaseable = pr_resp.json().get('rebaseable')

            if rebaseable is None:
                print(f'The PR is not ready to rebase, retry after {retry_interval} seconds')
                time.sleep(retry_interval)
                continue
            else:
                break

        if rebaseable is not True:
            print('GitHub doesn\'t think that the PR is rebaseable!')
            exit(1)

        self.configure_git()

        head_repo, _ = self.fetch_head_repo_and_branch()
        subprocess.run(['git', 'remote', 'add', 'fork', f'https://x-access-token:{self.committer_token}@github.com/{head_repo}.git'])

        self.perform_rebase()

    def configure_git(self):
        user_resp = requests.get(
            f'https://api.github.com/users/{self.user_login}',
            headers=self.auth_header
        )
        user_resp.raise_for_status()
        user_data = user_resp.json()

        self.user_name = user_data.get('name') or self.user_login
        self.user_email = user_data.get('email') or f'{self.user_login}@users.noreply.github.com'

        self.user_token = os.environ.get(f'{self.user_login.upper()}_TOKEN', self.github_token)
        self.committer_token = self.user_token.replace(' ', '')

        subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
        subprocess.run(['git', 'remote', 'set-url', 'origin', f'https://x-access-token:{self.committer_token}@github.com/{self.github_repo}.git'])
        subprocess.run(['git', 'config', '--global', 'user.email', self.user_email])
        subprocess.run(['git', 'config', '--global', 'user.name', f'{self.user_name}'])

    def fetch_base_repo(self):
        pr_resp = self.fetch_pr_info()
        return pr_resp.json().get('base', {}).get('repo', {}).get('full_name')

    def fetch_user_login(self):
        user_login = self.comment_body.get('comment', {}).get('user', {}).get('login')
        if user_login is None:
            pr_resp = self.fetch_pr_info()
            user_login = pr_resp.json().get('pull_request', {}).get('user', {}).get('login')
        return user_login

    def fetch_base_branch(self):
        pr_resp = self.fetch_pr_info()
        return pr_resp.json().get('base', {}).get('ref')

    def fetch_head_repo_and_branch(self):
        pr_resp = self.fetch_pr_info()
        head_repo = pr_resp.json().get('head', {}).get('repo', {}).get('full_name')
        head_branch = pr_resp.json().get('head', {}).get('ref')
        return head_repo, head_branch

    def fetch_pr_info(self):
        uri = f'https://api.github.com/repos/{self.github_repo}/pulls/{self.pr_number}'

        pr_resp = requests.get(uri, headers=self.auth_header)
        pr_resp.raise_for_status()
        return pr_resp

    def perform_rebase(self):
        base_branch = self.fetch_base_branch()
        head_branch = self.fetch_head_repo_and_branch()[1]

        subprocess.run(['git', 'fetch', 'origin', base_branch])
        subprocess.run(['git', 'fetch', 'fork', head_branch])

        subprocess.run(['git', 'checkout', '-b', f'fork/{head_branch}', f'fork/{head_branch}'])

        if os.environ.get('INPUT_AUTOSQUASH') == 'true':
            subprocess.run(['git', 'rebase', '-i', '--autosquash', f'origin/{base_branch}'])
        else:
            subprocess.run(['git', 'rebase', f'origin/{base_branch}'])

        subprocess.run(['git', 'status'])
        subprocess.run(['git', 'push', '--force-with-lease', 'fork', f'fork/{head_branch}:{head_branch}'])


if __name__ == '__main__':
    adhoc_action = GitHubAdhocAction()
    comment_body = adhoc_action.fetch_comment_body()
    adhoc_action.rebase_pr()
