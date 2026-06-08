from qa_agent_app.github_collector import GitHubRepositoryCollector, parse_github_repo_url


def test_parse_github_repo_url_variants():
    assert parse_github_repo_url("https://github.com/srsran/srsRAN_Project") == ("srsran", "srsRAN_Project")
    assert parse_github_repo_url("git@github.com:srsran/srsRAN_Project.git") == ("srsran", "srsRAN_Project")
    assert parse_github_repo_url("https://api.github.com/repos/srsran/srsRAN_Project") == ("srsran", "srsRAN_Project")


def test_collect_writes_repo_issues_and_pulls(tmp_path, monkeypatch):
    class FakeCollector(GitHubRepositoryCollector):
        def _request_json(self, path, params=None, default=None):
            if path == "/repos/acme/repo":
                return {
                    "full_name": "acme/repo",
                    "description": "Test repo",
                    "archived": False,
                    "fork": False,
                    "default_branch": "main",
                    "stargazers_count": 5,
                    "open_issues_count": 1,
                    "homepage": "",
                    "html_url": "https://github.com/acme/repo",
                }
            if path == "/repos/acme/repo/languages":
                return {"Python": 1000}
            if path == "/repos/acme/repo/readme":
                return {"name": "README.md", "html_url": "https://github.com/acme/repo/blob/main/README.md"}
            if path == "/repos/acme/repo/pulls/2":
                return {
                    "number": 2,
                    "title": "Improve docs",
                    "state": "closed",
                    "merged": True,
                    "user": {"login": "dev"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                    "html_url": "https://github.com/acme/repo/pull/2",
                    "base": {"ref": "main"},
                    "head": {"ref": "docs"},
                    "body": "PR body",
                }
            return default

        def _request_pages(self, path, params=None):
            if path == "/repos/acme/repo/issues":
                return [
                    {
                        "number": 1,
                        "title": "Bug report",
                        "state": "open",
                        "user": {"login": "user"},
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-02T00:00:00Z",
                        "html_url": "https://github.com/acme/repo/issues/1",
                        "labels": [{"name": "bug"}],
                        "body": "Issue body",
                    },
                    {"number": 2, "pull_request": {}},
                ]
            if path == "/repos/acme/repo/pulls":
                return [{"number": 2}]
            if path == "/repos/acme/repo/issues/1/comments":
                return [{"user": {"login": "reviewer"}, "created_at": "2026-01-03T00:00:00Z", "body": "Issue comment"}]
            if path == "/repos/acme/repo/issues/2/comments":
                return []
            if path == "/repos/acme/repo/pulls/2/comments":
                return [{"user": {"login": "reviewer"}, "created_at": "2026-01-03T00:00:00Z", "body": "Review comment"}]
            if path == "/repos/acme/repo/pulls/2/reviews":
                return [{"state": "APPROVED", "user": {"login": "lead"}, "submitted_at": "2026-01-04T00:00:00Z", "body": "LGTM"}]
            if path == "/repos/acme/repo/pulls/2/files":
                return [{"filename": "README.md", "status": "modified", "additions": 2, "deletions": 1, "patch": "@@ docs"}]
            return []

        def _clone_wiki(self, repo_url, github_dir):
            (github_dir / "wiki.md").write_text("# Wiki\n\nSkipped in test.", encoding="utf-8")

    collector = FakeCollector()
    collector.collect("https://github.com/acme/repo", tmp_path)

    assert "Test repo" in (tmp_path / "_github" / "repository.md").read_text(encoding="utf-8")
    assert "Bug report" in (tmp_path / "_github" / "issues.md").read_text(encoding="utf-8")
    pulls = (tmp_path / "_github" / "pull_requests.md").read_text(encoding="utf-8")
    assert "Improve docs" in pulls
    assert "README.md" in pulls
    assert "GitHub Discussions require GITHUB_TOKEN" in (tmp_path / "_github" / "discussions.md").read_text(encoding="utf-8")
