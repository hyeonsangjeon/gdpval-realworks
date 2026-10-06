# Latest task result

## Corrected retained-result readout integrated with accepted main

The leader reviewed readout source
`4e9529b60c6edec14c252972e4d31c461ed16834`, tree
`29fcc47c196e247d9823a1c600e7b7b03a6fc961`, in review `5435153879`.
It is integrated with accepted native/allocator main
`1e4519d71a6cead3a2dd8de7e60d884a21ba954d`, tree
`9464969952af79c359e5c4236692f0dc4ca844e3`. All non-document changes are
disjoint and retain their exact reviewed source/workflow/test blobs.
Only CHANGELOG, LATEST and README require reconciliation.

The readout's only production correction after its original proof sets
`Accept-Encoding: identity` on the scoped session before the metadata GET.
Both permitted requests now match the identity-only response guard. The
immutable target/result binding, byte/time limits, safe projection, existing
credential scope and workflow are unchanged.

The three-case proof at `7a64df827012e57ad7391daf77b3c24688c43324`, tree
`cc9cba829a2e1f9981911c32231fd9cfe30ad144`, reported **3 passed in 2.55s**,
exit 0, with a 2.977388s wrapper. It verifies both identity headers,
uncompressed success and refusal of gzip metadata/result responses after
exactly one/two GETs, without retry or private-body output. The separate
original proof remains **21 passed in 7.95s**, with an 8.412420s wrapper.
The [immutable readout record][readout] retains exact commands and artifact
hashes. No local selector was repeated for integration.

Readout controller C remains distinct from original result source R. A
leader-verified completion inside the independent digest-bound request
supplies the original request/claim association; neither claim nor original
request is downloaded by the reader. The existing private target and exact
immutable object are read under one 60-second bound, with no OIDC, Azure,
storage write, provider call or grading. Only validated typed fields and
aggregate deliverable metadata may leave the process.

The combined HEAD requires review and ordinary CI before delivery, followed
by a separately recorded request naming accepted C and its actual run
number. No actual private result has been fetched by this task. Source
acceptance and a successful synthetic projection do not authorize a model
attempt, grader, retry or historical-state adoption.

Task3 run `37524773961` remains consumed with a canonical error, terminal
reason `failed`, confirmed cleanup and reported usage of 2913 input and 326
output tokens. Output commit `2460c45c3896371b011624f13fc7817d5f670969`
contains its 6632-byte result, SHA256
`a2f21666eb53542ead8b780404fd241056d3cc129167f6e7b1be36c6b64160f7`,
fingerprint `0374270431f6352211715da432d886f8557514324c89d60c230f81f65a2a5b61`.
Its private error/model-binding fields have not yet been read. Reported
tokens are not a bill, model-call count or quality score. Task1 and Task2
remain consumed and uncertain; no Task1-Task3 replay, Task4 or grade is granted.

The [accepted main record][main] preserves the native callable and cleanup
CI evidence. Frozen F, the twenty-observation study, source/input/host guards
and 1200+20 limits remain unchanged.

[readout]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4e9529b60c6edec14c252972e4d31c461ed16834/tasks/LATEST_TASK_RESULT/README.md
[main]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/1e4519d71a6cead3a2dd8de7e60d884a21ba954d/tasks/LATEST_TASK_RESULT/README.md
