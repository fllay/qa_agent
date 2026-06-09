import shutil
import stat

from qa_agent_app.main import _handle_remove_readonly


def test_remove_readonly_handler_allows_rmtree(tmp_path):
    topic_dir = tmp_path / "topic"
    nested = topic_dir / ".git" / "objects" / "pack"
    nested.mkdir(parents=True)
    target = nested / "pack.idx"
    target.write_text("pack", encoding="utf-8")
    target.chmod(stat.S_IREAD)

    shutil.rmtree(topic_dir, onexc=_handle_remove_readonly)

    assert not topic_dir.exists()
