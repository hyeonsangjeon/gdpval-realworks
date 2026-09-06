"""What the run actually did, held against what the plan said it would.

Why a second check
------------------
``core/execution_environment_readiness.py`` already holds every run place to one
set of ``model_run_conditions``: one provider, one resource, one deployment, one
resolved model, one API version, one task list, one set of input file versions,
one token cap, one timeout, one retry policy. That check reads the plan.

Reading the plan is not the same as reading the run. Two of those fields were
shown to be unreadable in exactly that way: ``system_instruction`` and
``task_instruction`` are single values written once under
``model_run_conditions.shared``, inherited by every place, and compared against
themselves — and ``core/prompt_loader.py`` lets a committed prompt file's own
``system_message`` win over the first of them, so the field the plan compared was
wording no model ever read. A plan can be internally perfect and describe a run
that did not happen.

This module is the other half. It takes what a finished attempt recorded —
which model answered, on which API version, from which prompt file, with which
first-request fingerprint, under which token, time and retry settings — and holds
it against the plan's claims and against the other run places.

Fail closed
-----------
A field that could not be read is never filled in with a default, a zero or the
planned value. :class:`ObservedRunPlace` carries it in ``unreadable`` and every
check turns it into a problem. "The provider did not tell us which model
answered" and "the provider answered with the planned model" are different
findings, and only one of them is evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

from core.execution_environment_readiness import ENVIRONMENT_AZURE_CODE_INTERPRETER


#: Which API family a run place sent its request on. Recorded rather than
#: derived from the mode name, because it is the thing the two families are told
#: apart by in ``core/shared_first_request.py``'s uncontrolled-difference list,
#: and a comparison that guessed it from a label could not notice a run place
#: quietly changing products.
API_FAMILY_CHAT_COMPLETIONS = "chat_completions"
API_FAMILY_RESPONSES = "responses"
KNOWN_API_FAMILIES = frozenset({API_FAMILY_CHAT_COMPLETIONS, API_FAMILY_RESPONSES})


#: What every run place in one comparison must agree on, and why.
#:
#: Split out from the checking code so that a report can list what was held to
#: and a reader can see the list without reading the function. Each entry is an
#: attribute of :class:`ObservedRunPlace`.
MUST_AGREE_ACROSS_RUN_PLACES: Mapping[str, str] = {
    "provider": "a different provider is a different model vendor",
    "deployment": (
        "two deployments of one model name can sit on different capacity, "
        "different content filters and different versions"
    ),
    "answering_model": (
        "the name the provider echoed back. A request for one model that is "
        "served by another is the one substitution no plan can catch by "
        "reading itself"
    ),
    "prompt_name": (
        "three run places sending three differently named prompt files are not "
        "being asked one question, whatever the files come to"
    ),
    "first_request_fingerprint": (
        "the digest of the system text and the user text that really left the "
        "process. This is the field the plan's own system_instruction and "
        "task_instruction could not stand in for"
    ),
    "max_completion_tokens": (
        "a smaller cap truncates a longer answer, and a run place that was cut "
        "off did not do worse at the task"
    ),
    "per_task_timeout_seconds": (
        "a shorter timeout fails a slower task, which is a property of the "
        "settings rather than of the run place"
    ),
    "max_attempts": (
        "more tries at the same task is more chances to succeed, so an "
        "unequal count reads as an unequal run place"
    ),
}


#: What is allowed to differ, and the entry in
#: ``core.shared_first_request.UNCONTROLLED_DIFFERENCES`` that already says so.
#:
#: Kept here rather than left implicit, so that a field is either held to or
#: named as uncontrolled. A third state — differs, and nobody said anything —
#: is what this module exists to make impossible.
MAY_DIFFER_AND_IS_DECLARED: Mapping[str, str] = {
    "api_family": "the API the request is sent on",
    "api_version": "the API the request is sent on",
}


#: Fields a named run place has no setting for, and the declared difference
#: that says so.
#:
#: Narrower than :data:`MAY_DIFFER_AND_IS_DECLARED`: those fields are allowed to
#: hold *different values*; these are allowed to hold *no value*, and only in
#: the run place named. The Azure code interpreter is the case. Nothing in this
#: repository sets a per-task time limit on it — ``CodeInterpreterRunner`` takes
#: no timeout and ``TaskExecutor`` passes it none — because the service governs
#: its own container's lifetime and documents that it reclaims an idle one after
#: about twenty minutes. Writing 1200 into the record because the experiment
#: file says 1200 would be recording the plan as an observation, which is the
#: substitution this module exists to prevent.
#:
#: An exemption here excuses silence and nothing else. A run place that records
#: an actual value still has it compared, so a real disagreement is still a
#: problem. The value is the ``what`` of the
#: ``core.shared_first_request.UNCONTROLLED_DIFFERENCES`` entry that carries the
#: reasoning, and a test holds the two together.
DECLARED_ABSENT_BY_RUN_PLACE: Mapping[str, Mapping[str, str]] = {
    ENVIRONMENT_AZURE_CODE_INTERPRETER: {
        "per_task_timeout_seconds": "the per-task time limit",
    },
}


@dataclass(frozen=True)
class ObservedRunPlace:
    """What one run place recorded about the request it really sent.

    Every field is ``None`` when it could not be read, and the reason goes in
    ``unreadable``. Nothing here is defaulted: a token cap of 0 and a token cap
    nobody recorded are different facts, and only the first is a fact.
    """

    run_place: str
    provider: Optional[str] = None
    deployment: Optional[str] = None
    requested_model: Optional[str] = None
    answering_model: Optional[str] = None
    api_family: Optional[str] = None
    api_version: Optional[str] = None
    prompt_name: Optional[str] = None
    first_request_fingerprint: Optional[str] = None
    max_completion_tokens: Optional[int] = None
    per_task_timeout_seconds: Optional[int] = None
    max_attempts: Optional[int] = None
    task_ids: tuple[str, ...] = ()
    input_file_versions: Mapping[str, str] = field(default_factory=dict)
    unreadable: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.api_family is not None and self.api_family not in KNOWN_API_FAMILIES:
            raise ValueError(
                f"{self.run_place} recorded api_family={self.api_family!r}, "
                f"which is not one of {sorted(KNOWN_API_FAMILIES)}. A family "
                "this repository does not know is not a family whose "
                "differences it can say it accounted for"
            )
        both = sorted(set(self.unreadable) & {
            name
            for name in MUST_AGREE_ACROSS_RUN_PLACES
            if getattr(self, name, None) is not None
        })
        if both:
            raise ValueError(
                f"{self.run_place} recorded a value for {', '.join(both)} and "
                "also gave a reason it could not be read. One of the two is "
                "wrong, and a record that says both cannot be checked"
            )


def observed_from_record(
    run_place: str, record: Mapping[str, Any]
) -> ObservedRunPlace:
    """Read one run place's observations out of a run record.

    A key that is absent, or present and empty, becomes an entry in
    ``unreadable`` naming the key — not a ``None`` that later reads as
    agreement. Callers that have a genuine reason ("the provider does not
    return a model name on this API") pass it in ``unreadable`` themselves.
    """
    unreadable = dict(record.get("unreadable") or {})
    values: dict[str, Any] = {}
    for name in (
        "provider",
        "deployment",
        "requested_model",
        "answering_model",
        "api_family",
        "api_version",
        "prompt_name",
        "first_request_fingerprint",
    ):
        raw = record.get(name)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            unreadable.setdefault(
                name, f"the run record has no usable {name}"
            )
        else:
            values[name] = str(raw)
    for name in (
        "max_completion_tokens",
        "per_task_timeout_seconds",
        "max_attempts",
    ):
        raw = record.get(name)
        if isinstance(raw, bool) or not isinstance(raw, int):
            unreadable.setdefault(
                name,
                f"the run record's {name} is {raw!r}, which is not a whole "
                "number, so it cannot be compared",
            )
        else:
            values[name] = raw
    return ObservedRunPlace(
        run_place=run_place,
        task_ids=tuple(str(value) for value in (record.get("task_ids") or ())),
        input_file_versions={
            str(key): str(value)
            for key, value in dict(record.get("input_file_versions") or {}).items()
        },
        unreadable=unreadable,
        **values,
    )


def check_observations_agree(
    observed: Sequence[ObservedRunPlace],
) -> list[str]:
    """Hold the run places to each other on everything that must be equal.

    Returns one problem per disagreement, and one per field nobody could read.
    An empty list means the run places agreed on every field in
    :data:`MUST_AGREE_ACROSS_RUN_PLACES` — which is not the same as the run
    places being equal; see ``core.shared_first_request.UNCONTROLLED_DIFFERENCES``.
    """
    problems: list[str] = []
    if len(observed) < 2:
        # One run place on its own is a measurement, not a comparison. Saying
        # "they all agree" about a single record would be true and useless, and
        # a caller reading it as a passed comparison would be wrong.
        problems.append(
            f"{len(observed)} run place(s) recorded observations; a comparison "
            "needs at least two, and a single record cannot be held against "
            "anything"
        )
        return problems

    for place in sorted(observed, key=lambda entry: entry.run_place):
        for name, why in sorted(place.unreadable.items()):
            if name not in MUST_AGREE_ACROSS_RUN_PLACES:
                continue
            if name in DECLARED_ABSENT_BY_RUN_PLACE.get(place.run_place, ()):
                # Not a reading failure: this run place has no such setting to
                # read, and that is already written down as something the
                # comparison does not control. It stays out of the problem list
                # and stays in the report, which is where a reader meets it.
                continue
            problems.append(
                f"{place.run_place} could not record {name}, which every run "
                f"place must agree on because {MUST_AGREE_ACROSS_RUN_PLACES[name]}"
                f". {why}"
            )

    for name, why in MUST_AGREE_ACROSS_RUN_PLACES.items():
        seen: dict[Any, list[str]] = {}
        for place in observed:
            value = getattr(place, name)
            if value is None:
                continue
            seen.setdefault(value, []).append(place.run_place)
        if len(seen) <= 1:
            continue
        said = "; ".join(
            f"{value!r} in {', '.join(sorted(places))}"
            for value, places in sorted(seen.items(), key=lambda pair: str(pair[0]))
        )
        problems.append(
            f"the run places disagree on {name}: {said}. They must agree "
            f"because {why}"
        )

    problems.extend(_check_the_same_work_was_done(observed))
    return problems


def _check_the_same_work_was_done(
    observed: Sequence[ObservedRunPlace],
) -> list[str]:
    """The task list and the input file fingerprints, held place against place.

    Kept apart from the loop above because these two are not single values: a
    task list differs by *which* tasks, and an input file set by *which file*,
    and a problem that does not name them is not actionable.
    """
    problems: list[str] = []
    by_place = {place.run_place: place for place in observed}
    reference = sorted(by_place)[0]
    base = by_place[reference]

    for run_place in sorted(by_place):
        if run_place == reference:
            continue
        other = by_place[run_place]
        if not base.task_ids or not other.task_ids:
            missing = [
                name
                for name, place in ((reference, base), (run_place, other))
                if not place.task_ids
            ]
            problems.append(
                f"{' and '.join(missing)} recorded no task list, so whether "
                "the run places ran the same tasks cannot be worked out. An "
                "empty list is not a match"
            )
            # Falls through rather than moving on: which files were read is a
            # separate fact from which tasks were run, and an unknown task list
            # is no reason to stop reporting a known file mismatch.
        elif tuple(base.task_ids) != tuple(other.task_ids):
            only_base = [t for t in base.task_ids if t not in set(other.task_ids)]
            only_other = [t for t in other.task_ids if t not in set(base.task_ids)]
            detail = []
            if only_base:
                detail.append(f"{reference} alone ran {', '.join(only_base)}")
            if only_other:
                detail.append(f"{run_place} alone ran {', '.join(only_other)}")
            if not detail:
                detail.append("the same tasks were run in a different order")
            problems.append(
                f"{reference} and {run_place} did not run the same task list: "
                + "; ".join(detail)
            )

        for name in sorted(set(base.input_file_versions) | set(other.input_file_versions)):
            here = base.input_file_versions.get(name)
            there = other.input_file_versions.get(name)
            if here is None or there is None:
                absent = reference if here is None else run_place
                problems.append(
                    f"{absent} recorded no version for the input file {name}, "
                    "so the two run places cannot be shown to have read the "
                    "same bytes"
                )
                continue
            if here != there:
                problems.append(
                    f"{reference} read {name} at {here} and {run_place} read "
                    f"it at {there}; the two run places did not read the same "
                    "file"
                )
    return problems


def check_observations_match_the_plan(
    observed: Sequence[ObservedRunPlace],
    planned: Mapping[str, Any],
) -> list[str]:
    """Hold what each run place did against what the plan said it would do.

    ``planned`` is one run place's ``model_run_conditions`` as a mapping — the
    same shape ``core.execution_environment_readiness.ModelRunConditions``
    parses. Only the fields a run can observe are compared; a plan field with no
    observable counterpart is left to the readiness check that already reads it.

    The comparison that matters most here is ``resolved_model`` against
    ``answering_model``. The plan states which model the run place is pinned to;
    the provider states which model answered. Nothing but this pair can catch a
    request that was quietly served by something else.
    """
    problems: list[str] = []
    pairs = (
        ("provider", "provider"),
        ("deployment", "deployment"),
        ("resolved_model", "answering_model"),
        ("api_version", "api_version"),
        ("max_output_tokens", "max_completion_tokens"),
        ("per_task_timeout_seconds", "per_task_timeout_seconds"),
    )
    for place in sorted(observed, key=lambda entry: entry.run_place):
        for plan_field, observed_field in pairs:
            if plan_field not in planned:
                continue
            actual = getattr(place, observed_field)
            if actual is None:
                problems.append(
                    f"the plan pins {plan_field} to "
                    f"{planned[plan_field]!r} for {place.run_place}, and the run "
                    f"recorded no {observed_field}, so the pin was not checked "
                    "against anything"
                )
                continue
            expected = planned[plan_field]
            if isinstance(expected, int) and not isinstance(expected, bool):
                matches = actual == expected
            else:
                matches = str(actual) == str(expected)
            if not matches:
                problems.append(
                    f"{place.run_place}: the plan pins {plan_field} to "
                    f"{expected!r} and the run recorded {observed_field}="
                    f"{actual!r}"
                )
    return problems


def describe_observations(observed: Iterable[ObservedRunPlace]) -> list[str]:
    """One readable line per run place, saying what it recorded and what it did not."""
    lines: list[str] = []
    for place in sorted(observed, key=lambda entry: entry.run_place):
        answered = place.answering_model or "an unrecorded model"
        lines.append(
            f"{place.run_place}: {answered} answered on "
            f"{place.api_family or 'an unrecorded API'} "
            f"{place.api_version or '(version unrecorded)'}, from "
            f"prompts/{place.prompt_name or '?'}.yaml, first request "
            f"{place.first_request_fingerprint or 'unfingerprinted'}, "
            f"{place.max_completion_tokens if place.max_completion_tokens is not None else '?'}"
            " token cap, "
            f"{place.max_attempts if place.max_attempts is not None else '?'} "
            "attempt(s)"
        )
        for name, why in sorted(place.unreadable.items()):
            lines.append(f"    {name} was not recorded: {why}")
    return lines


# ─── writing the record, at the point the request is sent ────────────────────


#: Host suffixes that name a vendor, and the name. Matched against the base URL
#: the client is really configured with, because where the request went is a
#: fact about the run; the vendor named in a settings file is a claim about it,
#: and this module exists to hold the second against the first.
VENDOR_BY_HOST_SUFFIX: Mapping[str, str] = {
    ".openai.azure.com": "azure",
    ".cognitiveservices.azure.com": "azure",
    ".services.ai.azure.com": "azure",
    ".inference.ai.azure.com": "azure",
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
}


def provider_of_client(client: Any) -> tuple[Optional[str], Optional[str]]:
    """Name the vendor a client really points at, or say why it could not be.

    Returns ``(provider, None)`` or ``(None, reason)``. Read from the base URL
    first — that is where the request actually goes — and from the class only
    for the wrappers in this repository that keep no URL of their own.

    A host this module does not recognise is a reason, never a guess. Naming
    the wrong vendor would make two run places agree on a field that is the
    first thing a reader checks.
    """
    base_url = getattr(client, "base_url", None)
    if base_url is not None:
        host = str(getattr(base_url, "host", "") or "")
        if not host:
            from urllib.parse import urlsplit

            host = urlsplit(str(base_url)).hostname or ""
        host = host.lower()
        if host:
            for suffix, vendor in VENDOR_BY_HOST_SUFFIX.items():
                if host == suffix.lstrip(".") or host.endswith(suffix):
                    return vendor, None
            return None, (
                f"the client points at {host}, which this module has no vendor "
                "name for; naming one would be a guess about who answered"
            )

    for base in type(client).__mro__:
        if base.__name__ in ("AnthropicClient", "Anthropic"):
            return "anthropic", None
        if base.__name__ == "ManagedAzureAIClient":
            return "azure", None

    inner = getattr(client, "client", None)
    if inner is not None and inner is not client:
        return provider_of_client(inner)

    return None, (
        f"a {type(client).__name__} exposes no base_url and is not a wrapper "
        "this module knows, so where the request went was not recorded"
    )


def api_version_of_client(client: Any) -> tuple[Optional[str], Optional[str]]:
    """Read the API version a client is really configured with, or say why not.

    The openai SDK keeps it on a private attribute, so this can stop working
    without warning on an upgrade. When it does, the answer is a reason, never
    the version the plan asked for — a plan's own value cannot be evidence that
    the plan was followed.
    """
    for attribute in ("_api_version", "api_version"):
        value = getattr(client, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip(), None
    inner = getattr(client, "client", None)
    if inner is not None and inner is not client:
        return api_version_of_client(inner)
    return None, (
        f"a {type(client).__name__} exposes no api_version; the openai SDK "
        "keeps it privately and may have moved it, and the planned version "
        "cannot stand in for the one really used"
    )


def observation_from_a_sent_request(
    *,
    run_place: str,
    client: Any,
    requested_model: str,
    api_family: str,
    system_message: str,
    user_prompt: str,
    prompt_name: str,
    max_completion_tokens: Optional[int],
    per_task_timeout_seconds: Optional[int],
    max_attempts: Optional[int],
    response: Any,
    reference_files: Optional[Sequence[str]] = None,
    task_ids: Sequence[str] = (),
    api_version: Optional[str] = None,
) -> dict:
    """Build one run place's record from a request that was really sent.

    Called at the point the two texts have been assembled and the provider has
    answered, so the fingerprint is of the characters that left the process and
    ``answering_model`` is what came back — not what was asked for.

    ``deployment`` is the model argument itself on Azure, where the model name
    in a request *is* the deployment name. On any other vendor there is no
    deployment, and the record says that rather than repeating the model name
    into a field that would then compare equal for the wrong reason.
    """
    from core.shared_first_request import first_request_fingerprint

    unreadable: dict[str, str] = {}
    provider, why = provider_of_client(client)
    if why:
        unreadable["provider"] = why

    if api_version is None:
        api_version, why = api_version_of_client(client)
        if why:
            unreadable["api_version"] = why

    deployment: Optional[str] = None
    if provider == "azure":
        deployment = requested_model
    elif provider is not None:
        unreadable["deployment"] = (
            f"{provider} has no deployment layer; the model name is the whole "
            "address, and copying it here would make two run places compare "
            "equal on a field neither of them has"
        )

    answering_model = getattr(response, "model", None)
    if not isinstance(answering_model, str) or not answering_model.strip():
        unreadable["answering_model"] = (
            "the provider's response carried no model name, so which model "
            "answered is not known — only which one was asked for"
        )
        answering_model = None

    record: dict[str, Any] = {
        "provider": provider,
        "deployment": deployment,
        "requested_model": requested_model,
        "answering_model": answering_model,
        "api_family": api_family,
        "api_version": api_version,
        "prompt_name": prompt_name,
        "first_request_fingerprint": first_request_fingerprint(
            system_message, user_prompt
        ),
        "max_completion_tokens": max_completion_tokens,
        "per_task_timeout_seconds": per_task_timeout_seconds,
        "max_attempts": max_attempts,
        "task_ids": list(task_ids),
        "input_file_versions": _versions_of(reference_files or ()),
        "unreadable": unreadable,
    }
    return {
        "run_place": run_place,
        **{name: value for name, value in record.items() if value is not None},
    }


def _versions_of(paths: Iterable[str]) -> dict[str, str]:
    """Digest each reference file as it sits on disk at request time.

    A file that cannot be read gets a value naming the failure rather than
    being left out: an absent entry means "this run place did not have this
    file", which is a different finding from "it had it and could not read it",
    and the agreement check reports both.
    """
    import hashlib
    import os

    versions: dict[str, str] = {}
    for path in paths:
        name = os.path.basename(str(path))
        try:
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            versions[name] = f"sha256:{digest}"
        except OSError as error:
            versions[name] = f"unreadable:{type(error).__name__}"
    return versions


class RecordsItsFirstRequest:
    """Keeps what a runner's first request really was, on the shared path only.

    Mixed into the three runners so that one comparison run leaves three records
    the checks above can be run over. It writes nothing at all unless
    ``self.shared_first_request`` is on, because the ordinary experiments'
    recorded output has to stay exactly what it was — a comparison feature that
    changed every other run's result files would be paid for by every other run.

    Each runner supplies the three facts only it knows through the small hooks
    below. A hook that cannot answer returns ``None``, and the reading side
    turns that into "not recorded" rather than into a number.
    """

    #: Which API family this run place sends on. Overridden by the run place
    #: that does not use chat completions.
    OBSERVED_API_FAMILY: str = API_FAMILY_CHAT_COMPLETIONS

    #: The name this run place is known by in the comparison plan. Left empty
    #: here on purpose: a runner that forgot to set it records an empty name,
    #: which the agreement check reports, rather than silently borrowing a
    #: neighbour's.
    OBSERVED_RUN_PLACE: str = ""

    last_first_request_observation: Optional[dict] = None

    def _observed_max_attempts(self) -> Optional[int]:
        """How many times this run place may ask the model about one task."""
        return 1

    def _observed_timeout_seconds(self) -> Optional[int]:
        timeout = getattr(self, "timeout", None)
        return timeout if isinstance(timeout, int) and not isinstance(timeout, bool) else None

    def _observed_api_version(self) -> Optional[str]:
        """The version this run place was constructed with, if it holds one.

        ``None`` sends the reader to the client itself, which is the better
        source anyway; it is only overridden where the runner is the only thing
        that knows.
        """
        version = getattr(self, "api_version", None)
        return version if isinstance(version, str) and version.strip() else None

    def _record_first_request(
        self,
        *,
        client: Any,
        requested_model: str,
        system_message: str,
        user_prompt: str,
        response: Any,
        reference_files: Optional[Sequence[str]] = None,
    ) -> None:
        if not getattr(self, "shared_first_request", False):
            return
        self.last_first_request_observation = observation_from_a_sent_request(
            run_place=self.OBSERVED_RUN_PLACE,
            client=client,
            requested_model=requested_model,
            api_family=self.OBSERVED_API_FAMILY,
            system_message=system_message,
            user_prompt=user_prompt,
            prompt_name=str(getattr(self, "prompt_name", "") or ""),
            max_completion_tokens=getattr(self, "max_completion_tokens", None),
            per_task_timeout_seconds=self._observed_timeout_seconds(),
            max_attempts=self._observed_max_attempts(),
            response=response,
            reference_files=reference_files,
            api_version=self._observed_api_version(),
        )

    def _with_observation(self, result: dict) -> dict:
        """Add the record to a result, or hand the result back untouched.

        Untouched is the default and the common case: nothing is added on the
        ordinary path, so an experiment that does not ask for the shared first
        request writes exactly the keys it wrote before.
        """
        if self.last_first_request_observation is None:
            return result
        return {**result, "first_request_observation": self.last_first_request_observation}


