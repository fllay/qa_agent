import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class GitHubCollectError(RuntimeError):
    pass


class GitHubRepositoryCollector:
    def __init__(
        self,
        *,
        token: str | None = None,
        max_pages: int = 10,
        per_page: int = 100,
        patch_max_chars: int = 4000,
    ):
        self.token = token
        self.max_pages = max_pages
        self.per_page = per_page
        self.patch_max_chars = patch_max_chars

    def collect(self, repo_url: str, target_dir: Path) -> None:
        owner, repo = parse_github_repo_url(repo_url)
        github_dir = target_dir / "_github"
        github_dir.mkdir(parents=True, exist_ok=True)

        self._write_repo_metadata(owner, repo, github_dir)
        self._write_collection(
            github_dir / "issues.md",
            "Issues",
            self._collect_issues(owner, repo),
        )
        self._write_collection(
            github_dir / "pull_requests.md",
            "Pull Requests",
            self._collect_pull_requests(owner, repo),
        )
        self._write_collection(
            github_dir / "repository_activity.md",
            "Repository Activity",
            self._collect_activity(owner, repo),
        )
        self._write_collection(
            github_dir / "discussions.md",
            "Discussions",
            self._collect_discussions(owner, repo),
        )
        self._clone_wiki(repo_url, github_dir)

    def _write_repo_metadata(self, owner: str, repo: str, github_dir: Path) -> None:
        metadata = self._request_json(f"/repos/{owner}/{repo}")
        languages = self._request_json(f"/repos/{owner}/{repo}/languages", default={})
        readme = self._request_json(f"/repos/{owner}/{repo}/readme", default=None)
        lines = [
            "# Repository Metadata",
            "",
            f"- Full name: {metadata.get('full_name', f'{owner}/{repo}')}",
            f"- Description: {metadata.get('description') or 'None'}",
            f"- Archived: {metadata.get('archived')}",
            f"- Fork: {metadata.get('fork')}",
            f"- Default branch: {metadata.get('default_branch')}",
            f"- Stars: {metadata.get('stargazers_count')}",
            f"- Open issues count: {metadata.get('open_issues_count')}",
            f"- Homepage: {metadata.get('homepage') or 'None'}",
            f"- URL: {metadata.get('html_url')}",
            "",
            "## Languages",
            json.dumps(languages, indent=2, ensure_ascii=False),
        ]
        if readme:
            lines.extend(["", "## README", f"- Name: {readme.get('name')}", f"- URL: {readme.get('html_url')}"])
        (github_dir / "repository.md").write_text("\n".join(lines), encoding="utf-8")

    def _collect_issues(self, owner: str, repo: str) -> list[str]:
        issues = self._request_pages(f"/repos/{owner}/{repo}/issues", {"state": "all", "sort": "updated"})
        sections: list[str] = []
        for issue in issues:
            if issue.get("pull_request"):
                continue
            comments = self._request_pages(f"/repos/{owner}/{repo}/issues/{issue['number']}/comments")
            sections.append(self._format_issue_like("Issue", issue, comments))
        return sections

    def _collect_pull_requests(self, owner: str, repo: str) -> list[str]:
        pulls = self._request_pages(f"/repos/{owner}/{repo}/pulls", {"state": "all", "sort": "updated"})
        sections: list[str] = []
        for pull in pulls:
            number = pull["number"]
            detail = self._request_json(f"/repos/{owner}/{repo}/pulls/{number}", default=pull)
            comments = self._request_pages(f"/repos/{owner}/{repo}/issues/{number}/comments")
            review_comments = self._request_pages(f"/repos/{owner}/{repo}/pulls/{number}/comments")
            reviews = self._request_pages(f"/repos/{owner}/{repo}/pulls/{number}/reviews")
            files = self._request_pages(f"/repos/{owner}/{repo}/pulls/{number}/files")
            sections.append(self._format_pull_request(detail, comments, review_comments, reviews, files))
        return sections

    def _collect_activity(self, owner: str, repo: str) -> list[str]:
        collections = {
            "Branches": self._request_pages(f"/repos/{owner}/{repo}/branches"),
            "Tags": self._request_pages(f"/repos/{owner}/{repo}/tags"),
            "Releases": self._request_pages(f"/repos/{owner}/{repo}/releases"),
            "Contributors": self._request_pages(f"/repos/{owner}/{repo}/contributors"),
            "Labels": self._request_pages(f"/repos/{owner}/{repo}/labels"),
            "Milestones": self._request_pages(f"/repos/{owner}/{repo}/milestones", {"state": "all"}),
            "Workflows": self._request_json(f"/repos/{owner}/{repo}/actions/workflows", default={}).get("workflows", []),
        }
        sections: list[str] = []
        for title, items in collections.items():
            lines = [f"## {title}", ""]
            if not items:
                lines.append("No items found or endpoint unavailable.")
            for item in items:
                lines.append(json.dumps(_compact_json(item), ensure_ascii=False))
            sections.append("\n".join(lines))
        return sections

    def _collect_discussions(self, owner: str, repo: str) -> list[str]:
        if not self.token:
            return ["GitHub Discussions require GITHUB_TOKEN and repository Discussions API access."]
        query = """
        query($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) {
            discussions(first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
              nodes {
                number
                title
                body
                url
                createdAt
                updatedAt
                author { login }
                comments(first: 50) {
                  nodes {
                    body
                    createdAt
                    author { login }
                  }
                }
              }
            }
          }
        }
        """
        payload = self._graphql(query, {"owner": owner, "repo": repo}, default={})
        nodes = (
            payload.get("data", {})
            .get("repository", {})
            .get("discussions", {})
            .get("nodes", [])
        )
        sections: list[str] = []
        for discussion in nodes:
            lines = [
                f"## Discussion #{discussion.get('number')}: {discussion.get('title')}",
                "",
                f"- Author: {(discussion.get('author') or {}).get('login') or 'unknown'}",
                f"- Created: {discussion.get('createdAt')}",
                f"- Updated: {discussion.get('updatedAt')}",
                f"- URL: {discussion.get('url')}",
                "",
                "### Body",
                discussion.get("body") or "",
            ]
            comments = [
                {
                    "user": comment.get("author"),
                    "created_at": comment.get("createdAt"),
                    "body": comment.get("body"),
                }
                for comment in discussion.get("comments", {}).get("nodes", [])
            ]
            lines.extend(self._format_comments(comments, "Comments"))
            sections.append("\n".join(lines))
        return sections

    def _graphql(self, query: str, variables: dict[str, Any], default: Any = None) -> Any:
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            headers={**self._headers(), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError):
            if default is not None:
                return default
            raise

    def _clone_wiki(self, repo_url: str, github_dir: Path) -> None:
        wiki_url = repo_url.rstrip("/").removesuffix(".git") + ".wiki.git"
        wiki_dir = github_dir / "wiki"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", wiki_url, str(wiki_dir)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            (github_dir / "wiki.md").write_text(
                "# Wiki\n\nNo wiki repository was available or public for this repo.",
                encoding="utf-8",
            )

    def _request_pages(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            page_params = {"per_page": self.per_page, "page": page, **(params or {})}
            payload = self._request_json(path, page_params, default=[])
            if not payload:
                break
            if not isinstance(payload, list):
                break
            collected.extend(payload)
            if len(payload) < self.per_page:
                break
        return collected

    def _request_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        default: Any = None,
    ) -> Any:
        url = "https://api.github.com" + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if default is not None and exc.code in {403, 404, 410, 451}:
                return default
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubCollectError(f"GitHub API failed for {path}: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            if default is not None:
                return default
            raise GitHubCollectError(f"GitHub API unavailable for {path}: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "qa-agent-graph-ingestion",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _write_collection(self, path: Path, title: str, sections: list[str]) -> None:
        body = "\n\n".join(sections) if sections else "No items found or endpoint unavailable."
        path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")

    def _format_issue_like(self, label: str, item: dict[str, Any], comments: list[dict[str, Any]]) -> str:
        lines = [
            f"## {label} #{item.get('number')}: {item.get('title')}",
            "",
            f"- State: {item.get('state')}",
            f"- Author: {_login(item.get('user'))}",
            f"- Created: {item.get('created_at')}",
            f"- Updated: {item.get('updated_at')}",
            f"- URL: {item.get('html_url')}",
            f"- Labels: {', '.join(label.get('name', '') for label in item.get('labels', [])) or 'None'}",
            "",
            "### Body",
            item.get("body") or "",
        ]
        lines.extend(self._format_comments(comments, "Comments"))
        return "\n".join(lines)

    def _format_pull_request(
        self,
        pull: dict[str, Any],
        comments: list[dict[str, Any]],
        review_comments: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        files: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"## Pull Request #{pull.get('number')}: {pull.get('title')}",
            "",
            f"- State: {pull.get('state')}",
            f"- Merged: {pull.get('merged')}",
            f"- Author: {_login(pull.get('user'))}",
            f"- Created: {pull.get('created_at')}",
            f"- Updated: {pull.get('updated_at')}",
            f"- URL: {pull.get('html_url')}",
            f"- Base: {pull.get('base', {}).get('ref')}",
            f"- Head: {pull.get('head', {}).get('ref')}",
            "",
            "### Body",
            pull.get("body") or "",
            "",
            "### Changed Files",
        ]
        for file in files:
            patch = (file.get("patch") or "")[: self.patch_max_chars]
            lines.extend(
                [
                    f"- {file.get('filename')} ({file.get('status')}, +{file.get('additions')}/-{file.get('deletions')})",
                    patch,
                ]
            )
        lines.extend(self._format_comments(comments, "Issue Comments"))
        lines.extend(self._format_comments(review_comments, "Review Comments"))
        lines.extend(self._format_reviews(reviews))
        return "\n".join(lines)

    @staticmethod
    def _format_comments(comments: list[dict[str, Any]], title: str) -> list[str]:
        lines = ["", f"### {title}"]
        if not comments:
            lines.append("No comments.")
        for comment in comments:
            lines.extend(
                [
                    "",
                    f"- Author: {_login(comment.get('user'))}",
                    f"- Created: {comment.get('created_at')}",
                    comment.get("body") or "",
                ]
            )
        return lines

    @staticmethod
    def _format_reviews(reviews: list[dict[str, Any]]) -> list[str]:
        lines = ["", "### Reviews"]
        if not reviews:
            lines.append("No reviews.")
        for review in reviews:
            lines.extend(
                [
                    "",
                    f"- State: {review.get('state')}",
                    f"- Author: {_login(review.get('user'))}",
                    f"- Submitted: {review.get('submitted_at')}",
                    review.get("body") or "",
                ]
            )
        return lines


def parse_github_repo_url(url: str) -> tuple[str, str]:
    patterns = [
        r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$",
        r"api\.github\.com/repos/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group("owner"), match.group("repo").removesuffix(".git")
    raise ValueError("Expected a GitHub repository URL like https://github.com/owner/repo.")


def _login(user: dict[str, Any] | None) -> str:
    return (user or {}).get("login") or "unknown"


def _compact_json(value: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "name",
        "full_name",
        "login",
        "title",
        "state",
        "description",
        "html_url",
        "created_at",
        "updated_at",
        "pushed_at",
        "language",
        "stargazers_count",
        "forks_count",
        "open_issues_count",
        "default_branch",
        "workflow_runs_url",
        "badge_url",
        "total_count",
    }
    return {key: value.get(key) for key in keep if key in value}
