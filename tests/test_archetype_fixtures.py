"""The round 5 archetype fixtures hold the column roles ARCHITECTURE.md "Round 5" builds on (types from profile)."""


def test_archetype_fixture_roles(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    ids = {d["path"]: d["id"] for d in client.get("/api/datasets").json()}

    def types(name):
        return client.get(f"/api/datasets/{ids[name]}/profile").json()

    assert types("shop.csv") == {"date": "temporal", "store": "categorical", "channel": "categorical",
                                 "product": "categorical", "units": "numerical", "revenue": "numerical"}
    assert types("places.csv") == {"lat": "geospatial", "lon": "geospatial", "country": "categorical", "pop": "numerical"}
    assert set(types("measures.csv").values()) == {"numerical"}
    assert types("sparse.csv") == {"lat": "geospatial", "lon": "geospatial", "a": "numerical", "b": "numerical",
                                   "c": "numerical"}


def test_round6_fixture_roles(make_client, round6_dir):
    """The round 6 fixtures hold the roles ARCHITECTURE.md "Round 6" builds on (R4, R5, AC-59)."""
    client = make_client(round6_dir)
    ids = {d["path"]: d["id"] for d in client.get("/api/datasets").json()}

    def types(name):
        return client.get(f"/api/datasets/{ids[name]}/profile").json()

    for name in ("monitor.csv", "quiet.csv"):
        assert types(name) == {"time": "temporal", "temperature": "numerical", "humidity": "numerical"}
    assert types("survey.csv") == {"submitted": "temporal", "respondent_id": "numerical", "age": "numerical",
                                   "gender": "categorical", "region": "categorical", "city": "categorical",
                                   "q_service": "categorical", "q_easy": "categorical", "q_visits": "categorical",
                                   "q_score": "numerical"}
    assert types("orders.csv") == {"order_id": "numerical", "year": "numerical", "region": "categorical",
                                   "amount": "numerical"}
