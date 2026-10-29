"""Survey figures (SU1): questions, scales, bars, Likert, cross-tab, Respondents, export (ARCHITECTURE.md "Round 6: Survey app")."""
from collections import Counter
from types import SimpleNamespace

from app import survey
from app.rules import typed as to_typed
from tests.conftest import survey_rows

COLS = ["submitted", "respondent_id", "age", "gender", "region", "city", "q_service", "q_easy", "q_visits", "q_score"]
MAP = {"submitted": "temporal", "respondent_id": "numerical", "age": "numerical", "gender": "categorical",
       "region": "categorical", "city": "categorical", "q_service": "categorical", "q_easy": "categorical",
       "q_visits": "categorical", "q_score": "numerical"}
SET = SimpleNamespace(chart_cap=500)
ROWS = survey_rows()
TYPED = to_typed(COLS, [list(map(str, r)) for r in ROWS], MAP)


def _view(rows=TYPED, chosen=None):
    return survey.view(COLS, rows, MAP, TYPED, chosen, SET)


def _chart(v, title):
    return next(c for c in v["charts"] if c["title"] == title)


def _count(i):
    return Counter(r[i] for r in ROWS)


def test_questions_are_categorical_plus_answer_columns_in_order():
    assert survey.questions(COLS, MAP, TYPED) == ["gender", "region", "city", "q_service", "q_easy", "q_visits", "q_score"]


def test_amount_named_column_drops_the_one_to_seven_answers():
    cols = ["store", "units", "revenue"]
    m = {"store": "categorical", "units": "numerical", "revenue": "numerical"}
    rows = [["a", 3.0, 1000.0], ["b", 5.0, 20.0]]
    assert survey.questions(cols, m, rows) == ["store"]
    assert survey.questions(cols[:2], m, [r[:2] for r in rows]) == ["store", "units"]


def test_scale_known_cases_and_none():
    levels, neutral = survey.scale(["Agree", "neutral"])
    assert levels == ["strongly disagree", "disagree", "neutral", "Agree", "strongly agree"] and neutral == 2
    assert survey.scale([1, 3, 7]) == ([1, 2, 3, 4, 5, 6, 7], 3)
    assert survey.scale([1.0, 5.0])[0] == [1, 2, 3, 4, 5]
    assert survey.scale(["Never", "Often"])[0] == ["Never", "rarely", "sometimes", "Often", "always"]
    assert survey.scale(["yes", "no"]) is None
    assert survey.scale(["Agree", "Agree"]) is None
    assert survey.scale(["Agree", "Satisfied"]) is None


def test_bars_hand_values():
    v = _view()
    city = _chart(v, "city")
    assert city["kind"] == "bar" and city["orientation"] == "h" and city["other"] is True and "drill" not in city
    assert city["data"]["x"] == [f"city{k:02d}" for k in range(10)] + ["Other"]
    assert city["data"]["y"] == [4] * 4 + [3] * 6 + [6]
    gender = _chart(v, "gender")
    assert (gender["data"]["x"], gender["data"]["y"], gender["other"]) == (["female", "male", "other"], [14, 13, 13], False)


def test_likert_hand_values():
    v = _view()
    s = _chart(v, "q_service")
    assert s["kind"] == "likert" and s["data"]["levels"][0] == "Very dissatisfied" and s["data"]["neutral"] == 2
    assert s["data"]["counts"] == [6, 6, 6, 16, 6] and s["data"]["pct"] == [15, 15, 15, 40, 15]
    assert _chart(v, "q_visits")["data"]["counts"] == [9, 9, 9, 9, 4]
    score = _chart(v, "q_score")["data"]
    assert score["levels"] == [1, 2, 3, 4, 5] and score["counts"] == [5, 5, 5, 15, 10]
    for c in v["charts"]:
        if c["kind"] == "likert":
            assert abs(sum(c["data"]["pct"]) - 100) < 1e-9


def test_filtered_rows_keep_all_levels_with_zero_counts():
    only = [r for r in TYPED if r[COLS.index("q_visits")] == "Never"]
    d = _chart(_view(only), "q_visits")["data"]
    assert d["levels"] == ["Never", "Rarely", "Sometimes", "Often", "Always"] and d["counts"] == [9, 0, 0, 0, 0]


def test_pick_and_crosstab():
    qs = survey.questions(COLS, MAP, TYPED)
    assert survey.pick(qs, "q_easy", "gender") == ("q_easy", "gender")
    assert survey.pick(qs, "age", "gender") == ("gender", "region")
    assert survey.pick(qs, None, None) == ("gender", "region")
    v = _view()
    assert v["pick"] == ["gender", "region"] and v["questions"] == qs
    ct = _chart(v, "gender by region")
    assert ct["kind"] == "crosstab"
    assert ct["data"]["x"] == ["East", "North", "South", "West"] and ct["data"]["y"] == ["female", "male", "other"]
    assert ct["data"]["z"] == [[3, 4, 3, 4], [3, 3, 4, 3], [4, 3, 3, 3]]
    assert [round(p, 1) for p in ct["data"]["pct"][0]] == [21.4, 28.6, 21.4, 28.6]
    assert [round(p, 1) for p in ct["data"]["pct"][1]] == [23.1, 23.1, 30.8, 23.1]
    assert all(abs(sum(r) - 100) < 1e-9 for r in ct["data"]["pct"])


def test_crosstab_likert_levels_in_scale_order():
    v = _view(chosen=("q_visits", "q_easy"))
    d = _chart(v, "q_visits by q_easy")["data"]
    assert d["y"] == ["Never", "Rarely", "Sometimes", "Often", "Always"]
    assert d["x"] == ["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"]


def test_respondents_are_age_only_and_ids_in_order():
    v = _view()
    kinds = [c["kind"] for c in v["charts"]]
    assert kinds == ["bar"] * 3 + ["likert"] * 4 + ["crosstab", "histogram"]
    assert v["charts"][-1]["x_label"] == "age"
    assert [c["id"] for c in v["charts"]] == [f"chart-{i}" for i in range(1, 10)]


def test_export_list():
    out = survey.export(_view())
    assert [c["kind"] for c in out] == ["bar"] * 7 + ["table", "histogram"]
    assert [c["id"] for c in out] == [f"chart-{i}" for i in range(1, 10)]
    assert out[3]["data"] == {"x": _chart(_view(), "q_service")["data"]["levels"], "y": [6, 6, 6, 16, 6]}
    t = out[7]["data"]
    assert t["head"] == ["gender", "East", "North", "South", "West"] and t["rows"][0] == ["female", 3, 4, 3, 4]


def test_counts_match_survey_rows():
    v = _view()
    assert _chart(v, "region")["data"]["y"] == [_count(4)[k] for k in ("East", "North", "South", "West")]
