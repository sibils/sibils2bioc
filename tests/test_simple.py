from pathlib import Path
import json
from sibils2bioc import convert_to_BioC

import pytest

@pytest.mark.parametrize('collection, sibils_filename, bioc_filename', [
    ("medline", "sibils_38531008.json", "bioc_38531008.json"),
    ("plazi", "sibils_0046F48C89D29359E1EED032C4FCDC81.json", "bioc_0046F48C89D29359E1EED032C4FCDC81.json"),
    ("pmc",  "sibils_PMC10967677.json", "bioc_PMC10967677.json"),
    ("suppdata",  "sibils_PMC8365339_DataSheet_1.docx.json", "bioc_PMC8365339_DataSheet_1.docx.json"),
])
def test_simple(collection, sibils_filename, bioc_filename):
    sibils_filepath = Path(__file__).parent / "assets" / collection / sibils_filename
    bioc_filepath = Path(__file__).parent / "assets" / collection / bioc_filename
    with open(sibils_filepath, "rt", encoding="utf-8") as f:
        sibils_doc = json.load(f)
    with open(bioc_filepath, "rt", encoding="utf-8") as f:
        expected_bioc_doc = json.load(f)
    bioc_doc = convert_to_BioC(sibils_doc, collection)
    assert bioc_doc == expected_bioc_doc
