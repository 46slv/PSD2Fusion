#!/usr/bin/env python3
"""Inspection-only guard for proving a completed task is published remotely."""
import argparse, json, subprocess, sys

PASS, FAIL, BLOCKED = 0, 1, 2

def evaluate(snapshot):
    """Evaluate collected remote facts; returns a machine-readable result dict."""
    errors = list(snapshot.get("errors", []))
    if snapshot.get("blocked"):
        return {"status": "BLOCKED", "errors": errors or ["git/network unavailable"]}
    checks = snapshot.get("checks", {})
    for name in ("remote_branch_exists", "candidate_reachable", "state_reachable", "state_matches", "remote_expectations"):
        if not checks.get(name, False):
            errors.append(name)
    status = "PASS" if not errors else "FAIL"
    return {"status": status, "errors": errors, "remote": snapshot.get("remote", {})}

def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip() or "command failed")
    return p.stdout.strip()

def main(argv=None):
    ap = argparse.ArgumentParser(description="Remote completion guard (inspection only; offline check is not completion proof).")
    ap.add_argument("-TaskId", required=True); ap.add_argument("-ExpectedActiveTaskId", required=True)
    ap.add_argument("-ExpectedStatus", default="done"); ap.add_argument("-ExpectedVerification", default="pass")
    ap.add_argument("-Repo", default="."); ap.add_argument("-Remote", default="origin")
    a = ap.parse_args(argv)
    try:
        run(["git", "fetch", a.Remote], a.Repo)
        local = json.loads(open(a.Repo + "/.control/current.json", encoding="utf-8").read())
        remote_text = run(["git", "show", f"{a.Remote}/main:.control/current.json"], a.Repo)
        remote_state = json.loads(remote_text)
        task = next(t for t in local["tasks"] if t["id"] == a.TaskId)
        branch_ref = f"refs/heads/{task['branch']}"
        branch_sha = run(["git", "ls-remote", a.Remote, branch_ref], a.Repo).split()[0] if run(["git", "ls-remote", a.Remote, branch_ref], a.Repo) else ""
        candidate = task.get("commit") or ""
        state_commit = run(["git", "log", "-1", "--format=%H", "--", ".control/current.json"], a.Repo)
        def anc(commit, ref):
            return subprocess.run(["git", "merge-base", "--is-ancestor", commit, ref], cwd=a.Repo).returncode == 0
        remote_task_ref = f"{a.Remote}/{task['branch']}"
        checks = {"remote_branch_exists": bool(branch_sha), "candidate_reachable": bool(branch_sha) and anc(candidate, remote_task_ref), "state_reachable": anc(state_commit, f"{a.Remote}/main"), "state_matches": local == remote_state, "remote_expectations": remote_state.get("active_task_id") == a.ExpectedActiveTaskId and next((t for t in remote_state.get("tasks", []) if t.get("id") == a.TaskId), {}).get("status") == a.ExpectedStatus and next((t for t in remote_state.get("tasks", []) if t.get("id") == a.TaskId), {}).get("verification") == a.ExpectedVerification}
        result = evaluate({"checks": checks, "remote": {"main": run(["git", "rev-parse", f"{a.Remote}/main"], a.Repo), "branch": branch_sha, "candidate": candidate, "state_commit": state_commit}})
    except (OSError, ValueError, RuntimeError, StopIteration) as e:
        result = {"status": "BLOCKED", "errors": [str(e)]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return {"PASS": PASS, "FAIL": FAIL, "BLOCKED": BLOCKED}[result["status"]]

if __name__ == "__main__": sys.exit(main())
