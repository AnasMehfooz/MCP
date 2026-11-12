"""Keeps scripts/sample_products.csv and its problem manifest in sync.

The sheet is the importer's test fixture: 30 products, 10 of them with a planted problem.
These checks only guard the fixture itself; the importer tests assert the actual handling.
"""

import csv
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load() -> tuple[list[dict[str, str]], dict]:
    with (SCRIPTS / "sample_products.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    manifest = json.loads((SCRIPTS / "sample_products.problems.json").read_text(encoding="utf-8"))
    return rows, manifest


def test_sheet_has_30_products_and_10_planted_problems():
    rows, manifest = _load()
    handles = {r["handle"] for r in rows}

    assert len(handles) == manifest["products"] == 30
    assert len(rows) == manifest["rows"]
    assert len(manifest["problems"]) == manifest["products_with_problems"] == 10
    assert len({p["handle"] for p in manifest["problems"]}) == 10  # one problem per product
    assert len({p["kind"] for p in manifest["problems"]}) == 10  # ten different kinds


def test_manifest_lines_point_at_real_rows():
    rows, manifest = _load()
    for problem in manifest["problems"]:
        # File line n is rows[n - 2]: the header is line 1 and lists are 0-based.
        referenced = [rows[line - 2]["handle"] for line in problem["lines"]]
        assert problem["handle"] in referenced, problem


def test_planted_values_are_still_in_the_sheet():
    rows, _ = _load()
    by_sku: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        by_sku.setdefault(r["sku"], []).append(r)

    assert by_sku["TOTE-NAT"][0]["price"] == ""
    assert {r["handle"] for r in by_sku["LOGO-MUG-WHT"]} == {"logo-mug", "linen-apron-olive"}
    assert by_sku["BEANIE-GRY"][0]["option1_value"] == by_sku["BEANIE-GRY-2"][0]["option1_value"] == "Grey"
    assert by_sku["SOCK3-3942"][0]["title"] == ""
    assert by_sku["PIN-SET-3"][0]["stock"] == "-4"
    assert by_sku["PLANT-S-WHT"][0]["price"] == "24,90 €"
    assert by_sku["STICKER-A5"][0]["price"] == "0.00"
    assert by_sku["TEE-WHT-M"][0]["material"] != by_sku["TEE-BLK-S"][0]["material"]
    assert by_sku["BLKT-GRY"][0]["stock"] == "in stock"
    assert by_sku["ZHOOD-GRY-L"][0]["option1_value"] == ""
