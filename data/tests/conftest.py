"""Fakes shared by the tests.

Everything here runs offline. No Azure login, no warehouse, no database: the
suite has to pass in CI, on a laptop with no credentials, and in under a
second. What that buys you is a test you actually run before pushing.

The pattern throughout is the same. Each module that talks to the outside world
takes the thing that does the talking as an argument, defaulting to the real
one. Tests pass a fake instead. That is the whole trick, and it is why those
`opener=urllib.request.urlopen` arguments exist.
"""

import io
import json

import pytest


class FakeResponse(io.BytesIO):
    """What urlopen returns: readable, and usable as a context manager.

    BytesIO is already both, so there is nothing to add. It is named rather
    than used directly so the tests read as what they mean.
    """


def response(payload: dict) -> FakeResponse:
    return FakeResponse(json.dumps(payload).encode())


class RecordingOpener:
    """A urlopen stand-in that replays canned answers and records requests.

    Answers are consumed in order. Running out of them is a test failure with
    a useful message rather than a StopIteration from somewhere deep.
    """

    def __init__(self, answers: list[dict]) -> None:
        self.answers = list(answers)
        self.requests: list = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if not self.answers:
            raise AssertionError(f"no answer left for {getattr(request, 'full_url', request)}")
        return response(self.answers.pop(0))

    @property
    def urls(self) -> list[str]:
        return [request.full_url for request in self.requests]


class FakeWarehouse:
    """Records every statement and answers from a canned list.

    Statements are matched loosely, by a substring, because the tests care
    about which statement ran and in what order, not about whitespace.
    """

    def __init__(
        self, answers: dict[str, list[list]] | None = None, catalog: str = "team_x"
    ) -> None:
        self.catalog = catalog
        self.answers = answers or {}
        self.statements: list[str] = []

    def run(self, statement: str) -> list[list]:
        self.statements.append(statement)
        for fragment, rows in self.answers.items():
            if fragment in statement:
                return rows
        return []

    def query(self, statement: str):
        return [], self.run(statement)

    def ran(self, fragment: str) -> bool:
        return any(fragment in statement for statement in self.statements)

    def index_of(self, fragment: str) -> int:
        for position, statement in enumerate(self.statements):
            if fragment in statement:
                return position
        raise AssertionError(f"no statement contained {fragment!r}: {self.statements}")


@pytest.fixture
def warehouse() -> FakeWarehouse:
    return FakeWarehouse()
