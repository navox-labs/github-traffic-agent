"""Git operations for committing and pushing data."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def git_run(*args: str, cwd: str | None = None) -> str:
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
    git_run("config", "user.name", "github-traffic-agent[bot]", cwd=cwd)
    git_run("config", "user.email", "traffic-agent@users.noreply.github.com", cwd=cwd)


def commit_and_push(
    files: list[str],
    message: str,
    branch: str = "",
    cwd: str | None = None,
) -> bool:
    """Stage files, commit, and push. Returns True if changes were committed."""
    configure_git(cwd=cwd)

    for f in files:
        git_run("add", f, cwd=cwd)

    # Check if there are staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=cwd,
        check=False,
    )
    if result.returncode == 0:
        logger.info("No changes to commit")
        return False

    git_run("commit", "-m", message, cwd=cwd)

    push_args = ["push"]
    if branch:
        push_args.extend(["origin", branch])
    else:
        push_args.append("origin")

    git_run(*push_args, cwd=cwd)
    logger.info("Changes committed and pushed: %s", message)
    return True
