"""Unit tests for the assistant: understanding questions, recognising projects and people, help
topics, and the wording of answers."""
from datetime import date, timedelta

import pytest

from core.assistant import (
    classify, match_help, match_person, match_project, status_answer, suggestions, when, workload_answer,
)

TODAY = date(2026, 10, 14)
PROJECTS = [{"id": 1, "name": "Mobile Banking Refresh"}, {"id": 2, "name": "Branch Kiosk Rollout"},
            {"id": 3, "name": "Real-Time Fraud Alerts"}]


@pytest.mark.parametrize("question, intent", [
    ("Which projects are at risk?", "risks"),
    ("Who's overbooked?", "workload"),
    ("Is Ravi free next week?", "workload"),
    ("What's overdue?", "overdue"),
    ("What's due this week?", "due_soon"),
    ("What's blocking the kiosk rollout?", "blocked"),
    ("How's the budget on mobile banking?", "budget"),
    ("What should I work on?", "my_work"),
    ("How do I reschedule a milestone?", "help"),
    ("Why can't I assign Ravi?", "help"),
    ("How is the kiosk project doing?", "status"),
    ("Who is on the team?", "team"),
    ("hi", "greeting"),
    ("Hey, what's overdue?", "overdue"),
    ("thanks!", "thanks"),
    ("purple elephants", None),
])
def test_questions_map_to_intents(question, intent):
    assert classify(question) == intent


def test_projects_are_recognised_by_their_distinctive_words():
    assert match_project("what's blocking the kiosks?", PROJECTS)["id"] == 2
    assert match_project("How is Mobile Banking Refresh doing", PROJECTS)["id"] == 1
    assert match_project("anything on fraud alerts", PROJECTS)["id"] == 3


def test_common_words_do_not_pick_a_project_by_accident():
    assert match_project("is everything on time this week?", PROJECTS) is None


def test_people_are_recognised_by_first_name():
    people = [{"name": "Ravi Shah"}, {"name": "Leo Martins"}]
    assert match_person("is ravi free?", people)["name"] == "Ravi Shah"
    assert match_person("who's overbooked?", people) is None


def test_help_picks_the_most_relevant_topic():
    assert match_help("How do I reschedule a milestone?")["title"] == "Rescheduling a milestone"
    assert match_help("Why can't I assign Ravi?")["title"].startswith("Assigning people")
    assert match_help("How do I restore an archived project?")["title"] == "Archiving and restoring"
    assert match_help("gibberish words") is None


def test_dates_are_written_relative_to_today():
    assert when(TODAY, TODAY) == "Oct 14 (today)"
    assert when(TODAY + timedelta(days=1), TODAY) == "Oct 15 (tomorrow)"
    assert when(TODAY - timedelta(days=11), TODAY) == "Oct 3 (11 days ago)"


def test_status_answer_reads_like_a_briefing():
    project = {"name": "Branch Kiosk Rollout", "health": "at_risk", "progress": 52, "time_elapsed_pct": 87,
               "end_date": TODAY + timedelta(days=11), "risk_reasons": ["Behind schedule: 52% done", "Over budget by $5,000"]}
    text = status_answer(project, "manager", TODAY, {"name": "Install", "end_date": TODAY + timedelta(days=7)},
                         {"status": "late", "projected_end": TODAY + timedelta(days=57), "days_late": 46}, 0,
                         {"title": "Vendor slips", "level": "high", "score": 16})
    assert "**Branch Kiosk Rollout** is **at risk**" in text
    assert "46 days late" in text and "no buffer" in text and "Vendor slips" in text and "$5,000" in text
    assert "$5,000" not in status_answer(project, "employee", TODAY)


def test_workload_answer_flags_overload_and_finds_room():
    people = [{"name": "Ravi Shah", "peak": 10.0, "day": TODAY}, {"name": "Leo Martins", "peak": 8.0, "day": TODAY},
              {"name": "Diego Alvarez", "peak": 3.0, "day": TODAY}]
    text = workload_answer(people, TODAY)
    assert "1 person over-allocated" in text and "Ravi Shah" in text
    assert "Fully booked" in text and "Diego Alvarez (5h free)" in text
    assert "5 hours free" in workload_answer(people, TODAY, {"name": "Diego Alvarez"})


def test_suggestions_fit_the_role_and_the_project():
    assert "Who's overbooked?" in suggestions("manager")
    assert "What should I work on?" in suggestions("employee")
    assert suggestions("manager", {"name": "Branch Kiosk Rollout"})[0] == "How is Branch Kiosk Rollout doing?"