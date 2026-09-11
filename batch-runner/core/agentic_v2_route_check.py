"""Whether the route a client resolved is the one the plan approved.

Moved out of ``scripts/run_agentic_stage_a_probe.py`` unchanged, because a
second caller arrived. Stage A asks one task and a stage run asks up to 220, and
the question they both have to answer first is identical: *did the client that
was just built reach the account, project and profile the plan fixed?* Two
copies of that check would be two things to keep right, and the copy that
drifted would be the one guarding the larger spend.

Nothing here builds a client, reads the environment or spends anything. It is
handed a resolved route and the plan's own ``azure_connection`` block and
returns the ways they disagree.
"""

from __future__ import annotations

from typing import Any, Mapping


def check_route_is_the_one_the_plan_fixed(
    route: Any,
    connection: Mapping[str, Any],
    *,
    settings: Any = None,
) -> list[str]:
    """Every way the resolved route could differ from what was approved.

    The plan fixes an account, a project and a route profile. A run that
    reached a real model over some other route would have proved something
    about a different environment than the one stage one is being priced for,
    and it would have cost the same to prove it. Checked after the client is
    built, because until then the route is a request rather than a fact.

    All three collected rather than the first returned, so a reader fixing a
    misconfigured dispatch sees the whole of it at once.

    The project needs its own paragraph, because the route selected for
    inference under ``project-ci`` does not carry one. That profile derives an
    account-scoped ``direct-v1`` URL from the configured project endpoint and
    sends inference over it, so the selected endpoint has an account and a
    ``project`` of ``None`` — while the project it was derived from is still
    the fact being checked. Where it is, the project endpoint says so, and that
    is read here rather than assumed away. If neither the selection nor the
    settings names a project, the run is refused: an unconfirmable project is
    the case a silent skip would hide.
    """
    problems: list[str] = []
    account = str(connection.get("account") or "")
    project = connection.get("project")
    profile = connection.get("route_profile")

    if account and route.endpoint.account != account:
        problems.append(
            f"the route resolves to account {route.endpoint.account!r}, but "
            f"the plan fixes {account!r}"
        )
    if project:
        configured = getattr(getattr(settings, "project", None), "project", None)
        found = route.endpoint.project or configured
        if found is None:
            problems.append(
                f"the plan fixes project {project!r}, but neither the route "
                "that was selected nor the endpoints it was built from names "
                "a project, so there is nothing to check it against"
            )
        elif found != project:
            problems.append(
                f"the route resolves to project {found!r}, but the plan "
                f"fixes {project!r}"
            )
    if profile and str(route.profile.value) != str(profile):
        problems.append(
            f"the route profile is {route.profile.value!r}, but the plan "
            f"fixes {profile!r}"
        )
    return problems


__all__ = ["check_route_is_the_one_the_plan_fixed"]
