"""Round 6 rule order, roles L/cols, _pick and the new apps' wiring (ARCHITECTURE.md "Round 6: detection", "request flow")."""
import io
import re

import pytest
from pptx import Presentation

from app import apps, catalog, config, main, xlsx


def _ids(client):
    return {d["path"]: d["id"] for d in client.get("/api/datasets").json()}


def _app(client, name, query=""):
    return client.get(f"/api/datasets/{_ids(client)[name]}/app{query}").json()


def _detect(make_client, folder, name):
    make_client(folder)
    d = next(d for d in catalog.scan(config.get().data).datasets if d.path == name)
    _, mapping, typed, _ = main._base(d)
    return apps.detect(d.columns, mapping, typed)


def test_rules_and_names_order():
    assert [(r, a) for r, a, _ in apps.RULES] == [("R1", "map"), ("R5", "survey"), ("R2", "business"),
                                                  ("R4", "monitoring"), ("R3", "explorer")]
    assert apps.NAMES["monitoring"] == "Monitoring" and apps.NAMES["survey"] == "Survey"


@pytest.mark.parametrize("name, app, rule, qualifies", [
    ("monitor.csv", "monitoring", "R4", ["monitoring", "explorer"]),
    ("quiet.csv", "monitoring", "R4", ["monitoring", "explorer"]),
    ("survey.csv", "survey", "R5", ["survey", "business", "explorer"]),
    ("orders.csv", "explorer", "R3", ["explorer"]),
])
def test_app_route_round6_fixtures(make_client, round6_dir, name, app, rule, qualifies):
    got = _app(make_client(round6_dir), name)
    assert (got["app"], got["rule"], got["qualifies"], got["shown"]) == (app, rule, qualifies, app)


def test_round5_fixtures_keep_their_app(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    got = {n: (_app(client, n)["app"], _app(client, n)["rule"]) for n in _ids(client)}
    assert got == {"shop.csv": ("business", "R2"), "places.csv": ("map", "R1"), "measures.csv": ("explorer", "R3"),
                   "sparse.csv": ("explorer", "R3")}


def test_data_dir_and_big_files_keep_their_app(make_client, data_dir):
    client = make_client(data_dir)
    for d in client.get("/api/datasets").json():
        assert _app(client, d["path"])["app"] in ("business", "map", "explorer")  # never Survey or Monitoring


def test_roles_l_cols_and_guard():
    cols = ["a", "b", "c", "d"]
    mapping = dict.fromkeys(cols, "numerical")
    typed = [[1.0, 7.0, 8.0, None], [5.0, 3.0, 2.0, None]]
    r = apps.roles(cols, mapping, typed)
    assert (r["L"], r["cols"]) == ([0, 1], 4)  # c holds 8; d has no value
    mapping["c"] = "numerical"
    cols2 = ["a", "b", "revenue", "d"]
    assert apps.roles(cols2, dict.fromkeys(cols2, "numerical"), typed)["L"] == []  # amount guard


def test_survey_without_date_still_r5(make_client, tmp_path):
    (tmp_path / "s.csv").write_text("id,q1,q2,q3,q4\n" + "".join(
        f"{i},{('a', 'b')[i % 2]},{('x', 'y', 'z')[i % 3]},{('u', 'v')[i % 2]},{i % 5 + 1}\n" for i in range(30)))
    got = _detect(make_client, tmp_path, "s.csv")
    assert (got["app"], got["rule"]) == ("survey", "R5")


def test_four_categoricals_among_seven_columns_is_not_r5(make_client, tmp_path):
    (tmp_path / "s.csv").write_text("a,b,c,d,x,y,z\n" + "".join(
        f"{('p', 'q')[i % 2]},{('r', 's')[i % 3 % 2]},{('t', 'u')[i % 2]},{('v', 'w', 'k')[i % 3]},{i * 31},{i * 17},{i * 5}\n"
        for i in range(30)))
    assert _detect(make_client, tmp_path, "s.csv")["rule"] == "R3"


def test_shop_without_revenue_is_r5(make_client, tmp_path):
    """shop.csv's units run 1..7: only the revenue column (amount guard) keeps it Business."""
    make_client(tmp_path)
    rows = [("date", "store", "channel", "product", "units")]
    rows += [(f"2024-0{1 + i % 6}-01", ("N", "S")[i % 2], ("web", "shop")[i % 3 % 2], ("p", "q", "r")[i % 3], 1 + i % 7)
             for i in range(24)]
    (tmp_path / "shop.csv").write_text("\n".join(",".join(map(str, r)) for r in rows) + "\n")
    got = _detect(make_client, tmp_path, "shop.csv")
    assert (got["app"], got["rule"]) == ("survey", "R5")


def test_badges(make_client, round6_dir):
    client = make_client(round6_dir)
    ids = _ids(client)
    assert "App: Monitoring (rule R4)" in client.get(f"/datasets/{ids['monitor.csv']}").text
    assert "App: Survey (rule R5)" in client.get(f"/datasets/{ids['survey.csv']}").text


def test_pick_validates_period_and_pair(make_client, round6_dir):
    make_client(round6_dir)
    ds = {d.path: d for d in catalog.scan(config.get().data).datasets}
    mon, sur = ds["monitor.csv"], ds["survey.csv"]
    assert [main._pick(mon, "monitoring", {"period": p}) for p in ("7", "30", "90", "all", "5", None)] == [
        "7", "30", "90", "all", "30", "30"]
    assert main._pick(sur, "survey", {}) == ("gender", "region")
    assert main._pick(sur, "survey", {"row": "q_easy", "col": "city"}) == ("q_easy", "city")
    assert main._pick(sur, "survey", {"row": "q_easy", "col": "age"}) == ("gender", "region")  # age is no question
    assert main._pick(sur, "survey", {"row": "city"}) == ("gender", "region")  # both or neither
    assert main._pick(mon, "explorer", {"period": "7"}) is None
    hash(main._pick(sur, "survey", {}))


def test_period_changes_the_app_payload(make_client, round6_dir):
    client = make_client(round6_dir)
    a, b, bad = (_app(client, "monitor.csv", q) for q in ("?period=7", "?period=90", "?period=zzz"))
    assert (a["period"], b["period"], bad["period"]) == ("7", "90", "30")
    assert a["charts"][0]["data"]["x"] != b["charts"][0]["data"]["x"]


def test_survey_cross_tab_pick_in_payload(make_client, round6_dir):
    client = make_client(round6_dir)
    assert _app(client, "survey.csv")["pick"] == ["gender", "region"]
    assert _app(client, "survey.csv", "?row=q_easy&col=region")["pick"] == ["q_easy", "region"]


def test_pickq_in_links_only_when_in_url(make_client, round6_dir):
    client = make_client(round6_dir)
    mid = _ids(client)["monitor.csv"]
    plain = client.get(f"/datasets/{mid}?f.nothing=1&from=2024-04-01").text
    assert "period=" not in re.sub(r'<nav class="periods".*?</nav>', "", plain, flags=re.S)  # the period links carry one by design
    page = client.get(f"/datasets/{mid}?from=2024-04-01&period=7").text
    assert "export.xlsx?from=2024-04-01&amp;period=7" in page and "export.pptx?from=2024-04-01&amp;period=7" in page
    sid = _ids(client)["survey.csv"]
    page = client.get(f"/datasets/{sid}?row=q_easy&col=city&app=survey").text
    assert "export.xlsx?app=survey&amp;row=q_easy&amp;col=city" in page
    assert main._pickq("survey", {"row": "q_easy", "col": "city", "x": "1"}) == (("row", "q_easy"), ("col", "city"))
    assert main._pickq("explorer", {"period": "7"}) == () and main._pickq("monitoring", {}) == ()  # chips/form use this
    assert "View as" in page and "period=" not in page


def _get(client, name, kind, query=""):
    r = client.get(f"/datasets/{_ids(client)[name]}/export.{kind}{query}")
    assert r.status_code == 200
    return io.BytesIO(r.content)


def test_monitoring_exports(make_client, round6_dir):
    client = make_client(round6_dir)
    got = _get(client, "monitor.csv", "xlsx")
    assert xlsx.sheet_names(got) == ["Data", "chart-1 table", "chart-2 line", "Summary"]
    assert xlsx.read_sheet(got, "Summary")[0] == ["Monitoring overview"]
    slides = list(Presentation(_get(client, "monitor.csv", "pptx")).slides)
    assert slides[0].shapes[0].text_frame.text == "Monitoring overview"
    assert sum(s.has_chart for sl in slides for s in sl.shapes) == 1


def test_survey_exports(make_client, round6_dir):
    client = make_client(round6_dir)
    got = _get(client, "survey.csv", "xlsx")
    names = xlsx.sheet_names(got)
    assert names[0] == "Data" and names[-1] == "Summary"
    assert sum(n.endswith(" bar") for n in names) == 7  # one bar sheet per question
    assert xlsx.read_sheet(got, "Summary")[0] == ["Survey overview"]
    slides = list(Presentation(_get(client, "survey.csv", "pptx")).slides)
    assert slides[0].shapes[0].text_frame.text == "Survey overview"
    assert sum(s.has_chart for sl in slides for s in sl.shapes) >= 7
