"""Capture what each run place really sent, and compare that — not the config.

Why the capture, and not a config comparison
--------------------------------------------
The defect this suite guards is one where every config file already agreed. The
three run places were pointed at the same experiment, the same model and the
same task list, and still sent three different texts, because the prompt each
one used was chosen inside its own runner class from its own ``DEFAULT_PROMPT``
and never appeared in any config. A test that compared config strings would have
passed on the broken code. So these tests hold a fake client in the position the
real provider client occupies, let the whole runner run, and read the request
out of the call the runner actually made.

Two things are asserted, and they are different things:

* the three requests are byte-identical where they can be — the system text and
  the user text, and the fingerprint recorded from them;
* what the capture still shows as different is exactly what
  ``core.shared_first_request.UNCONTROLLED_DIFFERENCES`` already declares. A
  difference visible at the wire and missing from that tuple fails here, because
  the tuple is what a report reads when it states what the comparison does not
  control.
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.executor import TaskExecutor
from core.execution_environment_readiness import (
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
)
from core.execution_envelope_observed import (
    check_observations_agree,
    observed_from_record,
)
from core.shared_first_request import (
    SHARED_PROMPT_NAME,
    build_shared_task_text,
    first_request_fingerprint,
    residual_differences_for,
)


TASK_PROMPT = (
    "Read the quarterly figures and produce a one-page summary workbook "
    "with a chart of revenue by region."
)
OCCUPATION = "financial analyst"
MODEL = "gpt-5.2-chat"

#: One of the five the comparison is pre-registered on. The executor writes it
#: onto the request record, because the runner is never told which task it was
#: handed and a record with no task on it is read downstream as "cannot be shown
#: to have run the same work".
TASK_ID = "02aa1805-c658-4069-8a6a-02dec146063a"

#: Code the fake model "returns". It has to really run: the host process and
#: the container execute it, and a run that fails there retries with a repair
#: reflection, which would put a second, different request in the capture. One
#: successful attempt keeps the comparison about the first request.
CANNED_ANSWER = """Here is the summary.

```python
from pathlib import Path

Path("summary.txt").write_text("revenue by region", encoding="utf-8")
```
"""


# ── the fakes that stand where a provider client stands ──────────────────


# Standing for "this fake was not told to answer with anything in particular,
# so it echoes the model back as a provider does". Distinct from ``None``,
# which a test uses to mean "the provider named no model at all".
_ECHO = object()

#: What the real ``openai.AzureOpenAI`` exposes and this repository's code
#: reads off it: a public ``base_url`` naming the resource the request goes to,
#: and the API version, which the SDK keeps privately. A double that left these
#: out would be testing against a client shape that does not exist.
FAKE_BASE_URL = "https://fake-resource.openai.azure.com/openai/"
FAKE_API_VERSION = "2025-03-01-preview"


class _ChatCapture:
    """A client shaped like the chat-completions clients ``complete`` accepts."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.answers_with = _ECHO
        self.base_url = FAKE_BASE_URL
        self._api_version = FAKE_API_VERSION
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        message = SimpleNamespace(content=CANNED_ANSWER)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=None,
            model=(
                kwargs.get("model")
                if self.answers_with is _ECHO
                else self.answers_with
            ),
        )

    def close(self) -> None:  # pragma: no cover - parity with real clients
        pass


class _ResponsesCapture:
    """A client shaped like the Azure client ``CodeInterpreterRunner`` needs.

    Every attribute path ``core.azure_ai_client.validate_client_capabilities``
    checks for the code-interpreter workload is present, because the runner
    refuses a client that is missing one and the refusal would otherwise be
    mistaken here for the request never being built.
    """

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self._next_file_id = 0
        self.answers_with = _ECHO
        self.base_url = FAKE_BASE_URL
        self._api_version = FAKE_API_VERSION
        self.responses = SimpleNamespace(create=self._create)
        self.files = SimpleNamespace(
            create=self._files_create,
            delete=lambda *_a, **_k: None,
            content=lambda *_a, **_k: SimpleNamespace(read=lambda: b""),
        )
        self.containers = SimpleNamespace(
            create=lambda *_a, **_k: SimpleNamespace(id="container-fake"),
            files=SimpleNamespace(
                list=lambda *_a, **_k: SimpleNamespace(data=[]),
                content=SimpleNamespace(
                    retrieve=lambda *_a, **_k: SimpleNamespace(read=lambda: b"")
                ),
            ),
        )

    def _files_create(self, **_kwargs):
        self._next_file_id += 1
        return SimpleNamespace(id=f"file-fake-{self._next_file_id}")

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            output=[],
            output_text=CANNED_ANSWER,
            model=(
                kwargs.get("model")
                if self.answers_with is _ECHO
                else self.answers_with
            ),
        )

    def close(self) -> None:  # pragma: no cover - parity with real clients
        pass


# ── the inputs all three run places are given ────────────────────────────


@pytest.fixture
def reference_files(tmp_path: Path) -> list[str]:
    """Two real files on disk, because the previews read their bytes."""
    csv_path = tmp_path / "quarterly_revenue.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "quarter", "revenue"])
        writer.writerow(["north", "Q1", "1200"])
        writer.writerow(["south", "Q1", "900"])
    notes_path = tmp_path / "analyst_notes.txt"
    notes_path.write_text(
        "North outperformed on the enterprise renewal cycle.\n",
        encoding="utf-8",
    )
    return [str(csv_path), str(notes_path)]


def _first_request_texts(requests: list[dict], run_place: str) -> tuple[str, str]:
    """The system text and the user text of the first captured request.

    Fails rather than returns a default when nothing was captured.
    ``TaskExecutor.execute`` turns an exception into an error dict, so a runner
    that never reached its provider call would otherwise look here like a run
    place that agreed with the others by sending nothing.
    """
    assert requests, f"{run_place} never reached its provider call"
    request = requests[0]
    if "messages" in request:
        by_role = {msg["role"]: msg["content"] for msg in request["messages"]}
        return by_role["system"], by_role["user"]
    return request["instructions"], request["input"]


def _capture_host(reference_files: list[str]) -> _ChatCapture:
    client = _ChatCapture()
    executor = TaskExecutor(
        mode="subprocess",
        llm_client=client,
        shared_first_request=True,
    )
    # Kept on the fake so the tests below can read either half — what left the
    # process, and what the run place wrote down about having sent it — without
    # every existing caller having to unpack a pair.
    client.executor_result = executor.execute(
        task_prompt=TASK_PROMPT,
        model=MODEL,
        reference_files=reference_files,
        occupation=OCCUPATION,
        task_id=TASK_ID,
    )
    return client


def _capture_container(reference_files: list[str]) -> _ChatCapture:
    client = _ChatCapture()
    executor = TaskExecutor(
        mode="sandbox",
        llm_client=client,
        shared_first_request=True,
        # The comparison's own settings, copied from exp031's sandbox block: no
        # Docker daemon is assumed in a unit test, the Skills toolkit is off
        # because it is a block only the container can build, and the repair
        # round is off because it would give this run place a second go at the
        # model that the other two never get.
        sandbox_options={
            "use_docker": "never",
            "max_skills": 0,
            "repair": {"enabled": False, "max_attempts": 0},
        },
    )
    client.executor_result = executor.execute(
        task_prompt=TASK_PROMPT,
        model=MODEL,
        reference_files=reference_files,
        occupation=OCCUPATION,
        task_id=TASK_ID,
    )
    return client


def _capture_azure(reference_files: list[str]) -> _ResponsesCapture:
    client = _ResponsesCapture()
    executor = TaskExecutor(
        mode="code_interpreter",
        code_interpreter_client=client,
        shared_first_request=True,
    )
    client.executor_result = executor.execute(
        task_prompt=TASK_PROMPT,
        model=MODEL,
        reference_files=reference_files,
        occupation=OCCUPATION,
        task_id=TASK_ID,
    )
    return client


# ── the comparison itself ────────────────────────────────────────────────


def test_the_three_run_places_send_the_same_two_texts(reference_files):
    host = _first_request_texts(_capture_host(reference_files).requests, "host")
    container = _first_request_texts(
        _capture_container(reference_files).requests, "container"
    )
    azure = _first_request_texts(_capture_azure(reference_files).requests, "azure")

    assert host == container, (
        "the host process and the container sent different text. These two use "
        "the same API and the same prompt file, so there is nothing here that "
        "cannot be made equal"
    )
    assert host == azure, (
        "Azure sent different text. The envelope differs by product and is "
        "declared as uncontrolled; the two texts inside it are not"
    )


def test_the_recorded_fingerprint_is_the_same_number_for_all_three(reference_files):
    """The digest a run records is the digest of what it really sent.

    The fingerprint is what a finished run's record carries, so a report can be
    checked after the fact rather than only before it by re-reading the same
    files the run read. It is only worth carrying if it is computed from the
    wire text, which is what this asserts.
    """
    fingerprints = {
        run_place: first_request_fingerprint(*texts)
        for run_place, texts in {
            "host_python_process": _first_request_texts(
                _capture_host(reference_files).requests, "host"
            ),
            "docker_container": _first_request_texts(
                _capture_container(reference_files).requests, "container"
            ),
            "azure_code_interpreter": _first_request_texts(
                _capture_azure(reference_files).requests, "azure"
            ),
        }.items()
    }

    assert len(set(fingerprints.values())) == 1, fingerprints


def test_the_sent_text_is_the_text_the_shared_builder_produces(reference_files):
    """No run place adds anything after the shared builder returns.

    Equality among the three would also hold if all three appended the same
    extra block, which would make the comparison agree with itself while the
    text stopped being the one the shared definition describes. This pins the
    sent text to that definition.
    """
    _, user_text = _first_request_texts(
        _capture_container(reference_files).requests, "container"
    )
    expected_task_text = build_shared_task_text(
        task_prompt=TASK_PROMPT,
        reference_files=reference_files,
    )

    assert expected_task_text in user_text
    # The task's own words appear once. The container used to carry them again
    # inside its contract block, and a second copy is how a "shared" prompt
    # quietly regains a run-place-specific width.
    assert user_text.count(TASK_PROMPT) == 1


def test_the_container_no_longer_adds_its_own_sections(reference_files):
    """The width gap that the section list caused is gone, measured at the wire.

    The container's ``_augment_prompt`` reads its section order out of the prompt
    file. Pointing it at the shared file is what removes the extra blocks; this
    checks the removal on the sent bytes rather than on the file.
    """
    host_system, host_user = _first_request_texts(
        _capture_host(reference_files).requests, "host"
    )
    container_system, container_user = _first_request_texts(
        _capture_container(reference_files).requests, "container"
    )

    assert len(container_system) == len(host_system)
    assert len(container_user) == len(host_user)
    # The named blocks the container used to add, checked by their own wording
    # so that a rename in the container's default prompt cannot make this pass.
    for container_only in ("Available skills", "pip install", "Deliverable contract"):
        assert container_only not in container_user


def test_what_is_still_different_at_the_wire_is_what_the_module_declares(
    reference_files,
):
    """Every difference the capture shows must already be written down.

    This is the test that stops "the texts matched" from being read as "the run
    places were equal". It looks at what the requests still disagree about and
    requires a declared entry for each — so the report that prints those entries
    is printing the whole list, not a convenient part of it.
    """
    host_request = _capture_host(reference_files).requests[0]
    container_request = _capture_container(reference_files).requests[0]
    azure_request = _capture_azure(reference_files).requests[0]

    declared = residual_differences_for(
        ("host_python_process", "docker_container", "azure_code_interpreter")
    )
    declared_what = {entry.what for entry in declared}

    # 1. A different API family: two send messages, one sends instructions+input.
    assert "messages" in host_request and "messages" in container_request
    assert "messages" not in azure_request
    assert {"instructions", "input"} <= set(azure_request)
    assert "the API the request is sent on" in declared_what

    # 2. A tool declaration only Azure sends.
    assert "tools" not in host_request and "tools" not in container_request
    assert [tool["type"] for tool in azure_request["tools"]] == ["code_interpreter"]
    assert "a tool declaration only one run place sends" in declared_what

    # 3. The reference files reach Azure as uploaded ids, and the other two off
    #    disk. The ids are in the request; the disk paths are not.
    container_cfg = azure_request["tools"][0]["container"]
    assert container_cfg["file_ids"], "Azure sent no uploaded reference files"
    assert "how the reference files arrive" in declared_what

    # Nothing else in the request differs by key. A new key on one side is a new
    # difference, and it has to be declared before this test will accept it.
    comparable = {"model", "messages", "instructions", "input", "tools"}
    host_only = set(host_request) - set(azure_request) - comparable
    azure_only = set(azure_request) - set(host_request) - comparable
    budget_keys = {"max_completion_tokens", "max_output_tokens", "include"}
    assert host_only - budget_keys == set(), host_only
    assert azure_only - budget_keys == set(), azure_only


def test_every_run_place_loaded_the_shared_prompt_file(reference_files):
    """The one file, named once, is the file all three really loaded."""
    executors = [
        TaskExecutor(
            mode="subprocess", llm_client=_ChatCapture(), shared_first_request=True
        ),
        TaskExecutor(
            mode="sandbox",
            llm_client=_ChatCapture(),
            shared_first_request=True,
            sandbox_options={"use_docker": "never", "max_skills": 0},
        ),
        TaskExecutor(
            mode="code_interpreter",
            code_interpreter_client=_ResponsesCapture(),
            shared_first_request=True,
        ),
    ]
    for executor in executors:
        assert executor.runner.prompt_name == SHARED_PROMPT_NAME


# ── what each run place wrote down about the request it sent ─────────────


def _observations(reference_files: list[str]) -> list:
    """One :class:`ObservedRunPlace` per run place, read from its own result.

    Nothing here is constructed by the test. Each record is what the runner
    itself attached to the result it returned, so a runner that recorded
    nothing fails below rather than being filled in from the plan.
    """
    observed = []
    for capture in (_capture_host, _capture_container, _capture_azure):
        client = capture(reference_files)
        result = client.executor_result
        record = result.get("first_request_observation")
        assert record, (
            f"a run place returned {sorted(result)} and no "
            "first_request_observation, so there is nothing to check it by"
        )
        observed.append(observed_from_record(record["run_place"], record))
    return observed


def test_each_run_place_names_itself_as_the_plan_names_it(reference_files):
    """A record filed under a name the plan does not use checks nothing."""
    names = {place.run_place for place in _observations(reference_files)}
    assert names == {
        ENVIRONMENT_HOST_PYTHON_PROCESS,
        ENVIRONMENT_DOCKER_CONTAINER,
        ENVIRONMENT_AZURE_CODE_INTERPRETER,
    }


def test_the_three_records_agree_on_everything_that_must_be_equal(reference_files):
    """The identity check, run over three records from three real requests.

    This is the check instruction 2 asks for, done the way instruction 1 asks
    for it: the model name, the prompt file, the first-request digest, the token
    cap, the timeout and the attempt count all come from a request that was
    really assembled and a response that really came back.
    """
    assert check_observations_agree(_observations(reference_files)) == []


def test_the_recorded_digest_is_the_digest_of_what_left_the_process(
    reference_files,
):
    """The record must not be a second, independent rendering of the prompt.

    A fingerprint computed from the plan, or from a re-render, would agree
    across the three run places whatever they actually sent. So it is checked
    against the captured request rather than against the other records.
    """
    for capture, run_place in (
        (_capture_host, ENVIRONMENT_HOST_PYTHON_PROCESS),
        (_capture_container, ENVIRONMENT_DOCKER_CONTAINER),
        (_capture_azure, ENVIRONMENT_AZURE_CODE_INTERPRETER),
    ):
        client = capture(reference_files)
        system_text, user_text = _first_request_texts(client.requests, run_place)
        record = client.executor_result["first_request_observation"]
        assert record["first_request_fingerprint"] == first_request_fingerprint(
            system_text, user_text
        )


def test_the_model_recorded_is_the_one_the_provider_answered_with(
    reference_files,
):
    """Not the one that was asked for.

    The two fakes echo the model back, as a provider does. Here one of them is
    made to answer with something else, and the record has to follow the
    answer — otherwise a substitution would be invisible, which is the whole
    reason this field is recorded separately from ``requested_model``.
    """
    client = _ChatCapture()
    client.answers_with = "gpt-5.1-chat-2025-11-02"
    executor = TaskExecutor(
        mode="subprocess", llm_client=client, shared_first_request=True
    )
    result = executor.execute(
        task_prompt=TASK_PROMPT,
        model=MODEL,
        reference_files=reference_files,
        occupation=OCCUPATION,
    )
    record = result["first_request_observation"]

    assert record["requested_model"] == MODEL
    assert record["answering_model"] == "gpt-5.1-chat-2025-11-02"

    swapped = observed_from_record(record["run_place"], record)
    honest = [
        place
        for place in _observations(reference_files)
        if place.run_place != ENVIRONMENT_HOST_PYTHON_PROCESS
    ]
    problems = check_observations_agree([swapped, *honest])
    assert any("answering_model" in problem for problem in problems), problems


def test_a_provider_that_names_no_model_is_recorded_as_unread_not_as_asked(
    reference_files,
):
    """Fail closed: silence about which model answered is not confirmation."""
    client = _ChatCapture()
    client.answers_with = None
    executor = TaskExecutor(
        mode="subprocess", llm_client=client, shared_first_request=True
    )
    result = executor.execute(
        task_prompt=TASK_PROMPT,
        model=MODEL,
        reference_files=reference_files,
        occupation=OCCUPATION,
    )
    record = result["first_request_observation"]

    assert "answering_model" not in record
    assert "answering_model" in record["unreadable"]
    assert MODEL not in record["unreadable"]["answering_model"]


def test_the_reference_files_are_recorded_by_content_not_by_name(
    reference_files, tmp_path
):
    """Two run places given files with the same names but different bytes.

    The names would match and the run would look controlled. The digests are
    what shows it was not.
    """
    honest = _observations(reference_files)[0]

    edited = []
    for path in reference_files:
        copy = tmp_path / "edited" / Path(path).name
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_text(
            Path(path).read_text(encoding="utf-8") + "south,Q2,950\n",
            encoding="utf-8",
        )
        edited.append(str(copy))

    client = _capture_container(edited)
    other = observed_from_record(
        client.executor_result["first_request_observation"]["run_place"],
        client.executor_result["first_request_observation"],
    )

    assert set(honest.input_file_versions) == set(other.input_file_versions)
    problems = check_observations_agree([honest, other])
    assert any("did not read the same" in problem for problem in problems), problems


def test_the_container_reports_its_attempt_count_in_requests(reference_files):
    """One repair round means the model can be asked twice, and it says two.

    ``repair.max_attempts`` counts the *extra* goes, and the other two run
    places count requests. A record that mixed the two units would compare a 1
    against a 1 that meant 2.
    """
    client = _ChatCapture()
    executor = TaskExecutor(
        mode="sandbox",
        llm_client=client,
        shared_first_request=True,
        sandbox_options={
            "use_docker": "never",
            "max_skills": 0,
            "repair": {"enabled": True, "max_attempts": 1},
        },
    )
    result = executor.execute(
        task_prompt=TASK_PROMPT,
        model=MODEL,
        reference_files=reference_files,
        occupation=OCCUPATION,
    )
    assert result["first_request_observation"]["max_attempts"] == 2
