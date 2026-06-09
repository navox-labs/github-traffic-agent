"""Git operations for committing and pushing data."""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def _resolve_cwd(cwd: str | None) -> str | None:
    if cwd:
        return cwd
    return os.environ.get("GITHUB_WORKSPACE") or None


def git_run(*args: str, cwd: str | None = None) -> str:
    cwd = _resolve_cwd(cwd)
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        logger.error("git %s failed: %s", " ".join(args), result.stderr.strip())
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def configure_git(cwd: str | None = None) -> None:
    # Mark workspace as safe (required when running as different user in Docker)
    workspace = cwd or os.environ.get("GITHUB_WORKSPACE", "")
    if workspace:
        git_run("config", "--global", "safe.directory", workspace)

    git_run("config", "user.name", "github-traffic-agent[bot]", cwd=cwd)
    git_run("config", "user.email", "traffic-agent@users.noreply.github.com", cwd=cwd)

    # Configure token-based auth for pushing from Docker container
    token = os.environ.get("INPUT_TOKEN", "")
    if token:
        git_run(
            "config",
            "http.https://github.com/.extraheader",
            f"AUTHORIZATION: basic {_encode_token(token)}",
            cwd=cwd,
        )


def _encode_token(token: str) -> str:
    import base64

    return base64.b64encode(f"x-access-token:{token}".encode()).decode()


def commit_and_push(
    files: list[str],
    message: str,
    branch: str = "",
    cwd: str | None = None,
) -> bool:
    """Stage files, commit, and push. Returns True if changes were committed."""
    resolved_cwd = _resolve_cwd(cwd)
    configure_git(cwd=resolved_cwd)

    for f in files:
        git_run("add", f, cwd=resolved_cwd)

    # Check if there are staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=resolved_cwd,
        check=False,
    )
    if result.returncode == 0:
        logger.info("No changes to commit")
        return False

    git_run("commit", "-m", message, cwd=resolved_cwd)

    push_args = ["push"]
    if branch:
        push_args.extend(["origin", branch])
    else:
        push_args.append("origin")

    git_run(*push_args, cwd=resolved_cwd)
    logger.info("Changes committed and pushed: %s", message)
    return True
