"""The emergency gate sees all and only owner-authored text."""

from backend.questions import STANDARD_QUESTIONS
from backend.schemas import AdaptiveDecision, TurnRequest
from backend.workflow import run_turn
from conftest import FakeChains, FakeSearcher, history, intake, ready_history


def test_warning_sign_in_a_standard_answer_is_caught() -> None:
    chains = FakeChains()
    searcher = FakeSearcher()
    request = TurnRequest(
        intake=intake("My dog seems quieter."),
        history=history((STANDARD_QUESTIONS[0].text, "She collapsed this morning.")),
    )

    result = run_turn(request, chains, searcher)

    assert result.kind == "emergency_notice"
    assert chains.adaptive_calls == []


def test_assistant_warning_wording_is_not_scanned_when_owner_denies_it() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    request = TurnRequest(
        intake=intake(),
        history=ready_history(("Is she struggling to breathe?", "No")),
    )

    result = run_turn(request, chains, FakeSearcher())

    assert result.kind == "assessment"


def test_search_and_synthesis_text_never_enter_the_emergency_matcher() -> None:
    chains = FakeChains(adaptive=[AdaptiveDecision(kind="ready_for_search")])
    searcher = FakeSearcher()
    searcher.results[0] = searcher.results[0].model_copy(
        update={"excerpt": "Difficulty breathing and collapse are emergency signs."}
    )

    result = run_turn(
        TurnRequest(
            intake=intake(),
            history=ready_history(("Anything else?", "No")),
        ),
        chains,
        searcher,
    )

    assert result.kind == "assessment"
