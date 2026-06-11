"""Git operations for committing and pushing data."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile

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


def _encode_token(token: str) -> str:
    import base64

    return base64.b64encode(f"x-access-token:{token}".encode()).decode()


def configure_git(cwd: str | None = None) -> None:
    """Configure git identity and auth for the given working directory."""
    workspace = cwd or os.environ.get("GITHUB_WORKSPACE", "")
    if workspace:
        git_run("config", "--global", "safe.directory", workspace)

    git_run("config", "user.name", "github-traffic-agent[bot]", cwd=cwd)
    git_run("config", "user.email", "traffic-agent@users.noreply.github.com", cwd=cwd)

    token = os.environ.get("INPUT_TOKEN", "")
    if token:
        git_run(
            "config",
            "http.https://github.com/.extraheader",
            f"AUTHORIZATION: basic {_encode_token(token)}",
            cwd=cwd,
        )


def clone_data_repo(data_repo: str, branch: str = "") -> str:
    """Clone the data repo into a temp directory. Returns the clone path."""
    token = os.environ.get("INPUT_TOKEN", "")
    if token:
        repo_url = f"https://x-access-token:{token}@github.com/{data_repo}.git"
    else:
        repo_url = f"https://github.com/{data_repo}.git"

    clone_dir = tempfile.mkdtemp(prefix="traffic-data-")

    clone_args = ["clone", "--depth", "1"]
    if branch:
        clone_args.extend(["--branch", branch])
    clone_args.extend([repo_url, clone_dir])

    git_run(*clone_args, cwd="/tmp")
    git_run("config", "--global", "safe.directory", clone_dir)
    configure_git(cwd=clone_dir)

    logger.info("Cloned data repo %s to %s", data_repo, clone_dir)
    return clone_dir


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
        git_run("add", "-f", f, cwd=resolved_cwd)

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
