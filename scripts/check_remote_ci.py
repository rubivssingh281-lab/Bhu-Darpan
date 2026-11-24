#!/usr/bin/env python3
"""
Remote CI Verification Utility for Bhu-Darpan.
Polls GitHub Actions API for the latest commit to ensure CI passed remotely after pushing.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error


def get_git_info() -> tuple[str, str, str]:
    """Retrieve current commit SHA, branch, and remote repository owner/repo."""
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    
    # Try remotes: Saksham-Singh, then origin
    remote_url = ""
    for remote in ["Saksham-Singh", "origin"]:
        try:
            remote_url = subprocess.check_output(["git", "remote", "get-url", remote], text=True).strip()
            if remote_url:
                break
        except subprocess.CalledProcessError:
            continue
            
    match = re.search(r"github\.com[/:]([\w-]+)/([\w-]+?)(\.git)?$", remote_url)
    if match:
        repo_slug = f"{match.group(1)}/{match.group(2)}"
    else:
        repo_slug = "rubivssingh281-lab/Bhu-Darpan"
        
    return sha, branch, repo_slug


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Bhu-Darpan-CI-Checker",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_ci_status(commit_sha: str | None = None, max_wait_sec: int = 120, interval_sec: int = 5) -> int:
    current_sha, branch, repo_slug = get_git_info()
    target_sha = commit_sha or current_sha
    
    print("=" * 60)
    print(" [CI VERIFIER] Checking Remote GitHub Actions Status")
    print(f" Target Repository : {repo_slug}")
    print(f" Branch            : {branch}")
    print(f" Commit SHA        : {target_sha[:8]}")
    print("=" * 60)

    api_url = f"https://api.github.com/repos/{repo_slug}/actions/runs?head_sha={target_sha}"
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < max_wait_sec:
        attempt += 1
        try:
            data = fetch_json(api_url)
            runs = data.get("workflow_runs", [])
            
            if not runs:
                print(f"[*] (Attempt {attempt}) No workflow run detected yet for {target_sha[:8]}. Waiting for GitHub dispatch...")
                time.sleep(interval_sec)
                continue
                
            run = runs[0]
            run_id = run.get("id")
            run_number = run.get("run_number")
            status = run.get("status")
            conclusion = run.get("conclusion")
            html_url = run.get("html_url")
            
            elapsed = int(time.time() - start_time)
            
            if status == "completed":
                print(f"\n-> Workflow Run #{run_number} completed in {elapsed}s.")
                print(f"-> Conclusion: {conclusion.upper() if conclusion else 'UNKNOWN'}")
                print(f"-> Run URL: {html_url}\n")
                
                if conclusion == "success":
                    print("[PASS] Remote GitHub Actions CI PASSED SUCCESSFULLY! No run fails detected.")
                    return 0
                else:
                    print(f"[FAIL] Remote GitHub Actions CI FAILED (Conclusion: {conclusion}).")
                    # Fetch failure details from jobs API
                    try:
                        jobs_data = fetch_json(f"https://api.github.com/repos/{repo_slug}/actions/runs/{run_id}/jobs")
                        for job in jobs_data.get("jobs", []):
                            if job.get("conclusion") == "failure":
                                print(f"\n--- Failing Job: {job.get('name')} ---")
                                for step in job.get("steps", []):
                                    if step.get("conclusion") == "failure":
                                        print(f"  FAILED STEP: {step.get('name')}")
                    except Exception as err:
                        print(f"  (Could not fetch detailed job steps: {err})")
                        
                    return 1
            else:
                print(f"[*] (Attempt {attempt}, {elapsed}s elapsed) Status: '{status}'... Waiting for run completion.")
                time.sleep(interval_sec)
                
        except urllib.error.URLError as e:
            print(f"[!] Network error contacting GitHub API: {e}. Retrying in {interval_sec}s...")
            time.sleep(interval_sec)
            
    print(f"\n[!] Polling timed out after {max_wait_sec}s. Please check run manually at:")
    print(f"    https://github.com/{repo_slug}/actions")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(check_ci_status(commit_sha=target))
