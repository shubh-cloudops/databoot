from app import catalog


def test_scan_data_dir(make_client, data_dir):
    make_client(data_dir)  # clears the caches
    cat = catalog.scan(data_dir)
    assert [(d.path, d.sheet) for d in cat.datasets] == [
        ("notes.csv", None), ("points.tsv", None), ("sales.csv", None), ("sub/book.xlsx", "Revenue"),
        ("sub/book.xlsx", "Lookup"), ("sub/cities.geojson", None), ("sub/events.jsonl", None),
        ("sub/records.json", None)]
    by = {(d.path, d.sheet): d for d in cat.datasets}
    assert [by[k].rows for k in by] == [30, 4, 6, 6, 3, 4, 10, 3]
    assert by["sales.csv", None].columns == ["date", "region", "amount"]
    assert by["sub/book.xlsx", "Revenue"].columns == ["month", "team", "revenue"]
    assert by["sub/cities.geojson", None].columns == ["size", "longitude", "latitude"]
    assert len({d.id for d in cat.datasets}) == 8 and all(len(d.id) == 12 for d in cat.datasets)
    assert {(u.path, u.reason) for u in cat.unreadable} == {("empty.csv", "empty file"), ("broken.xlsx", "not a valid xlsx")}
    assert [(o.path, o.type, o.size) for o in cat.others] == [("manual.pdf", "pdf", 9)]
    assert len(cat.others[0].modified) == 10 and cat.others[0].modified[4] == "-"
    assert not any(".hidden" in d.path for d in cat.datasets)


def test_missing_folder_and_symlinks(make_client, tmp_path, data_dir):
    make_client(tmp_path)
    assert catalog.scan(tmp_path / "nope") == catalog.Catalog([], [], [])
    (tmp_path / "data" / "link").symlink_to(tmp_path / "data" / "sub", target_is_directory=True)
    (tmp_path / "data" / "alias.csv").symlink_to(tmp_path / "data" / "sales.csv")
    paths = {d.path for d in catalog.scan(data_dir).datasets}
    assert len(paths) == 7 and not any(p.startswith("link") or p == "alias.csv" for p in paths)


def test_load_caps_rows_and_caches(make_client, data_dir):
    make_client(data_dir)
    sales = catalog.scan(data_dir).datasets[2]
    assert catalog.load(sales, 2) == [["2024-01-01", "North", "10"], ["2024-01-02", "South", "20"]]
    assert len(catalog.load(sales, 100)) == 6
    assert catalog.load(sales, 2) is catalog.load(sales, 2)
    assert catalog.load.cache_info().maxsize == 4 and catalog.scan.cache_info().maxsize == 1
    rev = next(d for d in catalog.scan(data_dir).datasets if d.sheet == "Revenue")
    assert catalog.load(rev, 1)[0][1:] == ["A", 100]


def test_corrupt_file_does_not_stop_scan(make_client, tmp_path):
    root = tmp_path / "d"
    root.mkdir()
    (root / "a.json").write_text("{not json")
    (root / "b.csv").write_text("x\n1\n")
    make_client(root)
    cat = catalog.scan(root)
    assert [d.path for d in cat.datasets] == ["b.csv"]
    assert [u.path for u in cat.unreadable] == ["a.json"]
