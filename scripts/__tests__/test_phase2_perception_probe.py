from pathlib import Path

from scripts import phase2_perception_probe as probe


def test_main_closes_grader_and_removes_temp_directory(monkeypatch):
    events = []
    captured = {}

    class FakeGrader:
        def __init__(self, config, rubric_loader):
            assert isinstance(config, dict)
            assert rubric_loader is None

        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, exc_type, exc, traceback):
            events.append("exit")

    def run_probe(grader, temp_dir):
        assert isinstance(grader, FakeGrader)
        assert temp_dir.is_dir()
        captured["temp_dir"] = temp_dir
        return 0

    monkeypatch.chdir(probe.BR)
    monkeypatch.setattr(probe, "Grader", FakeGrader)
    monkeypatch.setattr(probe, "_run_probe", run_probe)

    assert probe.main() == 0
    assert events == ["enter", "exit"]
    assert not Path(captured["temp_dir"]).exists()
