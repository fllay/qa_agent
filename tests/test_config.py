from qa_agent_app.config import resolve_graphify_bin


def test_resolve_graphify_bin_keeps_explicit_command():
    assert resolve_graphify_bin("/opt/bin/graphify") == "/opt/bin/graphify"


def test_resolve_graphify_bin_auto_uses_path(monkeypatch):
    monkeypatch.setattr("qa_agent_app.config.shutil.which", lambda command: "/usr/local/bin/graphify")

    assert resolve_graphify_bin("auto") == "/usr/local/bin/graphify"


def test_resolve_graphify_bin_auto_uses_windows_user_site(monkeypatch, tmp_path):
    graphify = tmp_path / "Python" / "Python314" / "Scripts" / "graphify.exe"
    graphify.parent.mkdir(parents=True)
    graphify.write_text("", encoding="utf-8")
    monkeypatch.setattr("qa_agent_app.config.shutil.which", lambda command: None)
    monkeypatch.setattr("qa_agent_app.config.os.name", "nt")
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert resolve_graphify_bin("auto") == str(graphify)


def test_resolve_graphify_bin_auto_falls_back_to_command(monkeypatch):
    monkeypatch.setattr("qa_agent_app.config.shutil.which", lambda command: None)
    monkeypatch.setattr("qa_agent_app.config.os.name", "posix")

    assert resolve_graphify_bin("auto") == "graphify"
