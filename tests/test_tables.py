"""Unit tests for table-to-BioC conversion."""

from sibils2bioc import convert_to_BioC
from sibils2bioc import _table_to_passage


# ---------------------------------------------------------------------------
# _table_to_passage unit tests
# ---------------------------------------------------------------------------

TABLE_FULL = {
    "tag": "table",
    "xref_id": "vbaf155-T1",
    "xref_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12371329/table/vbaf155-T1",
    "label": "Table 1.",
    "caption": "For each file type, the table shows the number of files.",
    "footer": "a The success rate is defined as the proportion of files processed.",
    "table_columns": ["File type", "# files", "%"],
    "table_values": [
        ["jpg", "5 707 606", "48.62%"],
        ["pdf", "1 658 182", "14.13%"],
    ],
    "xml": "<table><tr><td>jpg</td></tr></table>",
    "id": "3.2.3.9",
}

TABLE_NO_FOOTER = {**TABLE_FULL, "footer": ""}
TABLE_NO_XML    = {**TABLE_FULL, "xml": None}
TABLE_NO_COLUMNS = {**TABLE_FULL, "table_columns": []}


def test_table_full():
    passage, new_offset = _table_to_passage(TABLE_FULL, offset=100)

    assert passage["offset"] == 100
    assert passage["annotations"] == []
    assert passage["relations"] == []

    infons = passage["infons"]
    assert infons["section_type"] == "TABLE"
    assert infons["table_id"] == "vbaf155-T1"
    assert infons["label"] == "Table 1."
    assert infons["caption"] == "For each file type, the table shows the number of files."
    assert infons["footer"] == "a The success rate is defined as the proportion of files processed."
    assert infons["xref_url"] == TABLE_FULL["xref_url"]
    assert infons["xml"] == TABLE_FULL["xml"]

    # text: header + 2 rows, each ending with \n
    expected_text = (
        "File type\t# files\t%\n"
        "jpg\t5 707 606\t48.62%\n"
        "pdf\t1 658 182\t14.13%\n"
    )
    assert passage["text"] == expected_text
    assert new_offset == 100 + len(expected_text)


def test_table_no_footer():
    passage, _ = _table_to_passage(TABLE_NO_FOOTER, offset=0)
    assert "footer" not in passage["infons"]
    assert "section_type" in passage["infons"]


def test_table_no_xml():
    passage, _ = _table_to_passage(TABLE_NO_XML, offset=0)
    assert "xml" not in passage["infons"]


def test_table_no_columns():
    passage, new_offset = _table_to_passage(TABLE_NO_COLUMNS, offset=0)
    # No header line — text starts directly with first data row
    expected_text = (
        "jpg\t5 707 606\t48.62%\n"
        "pdf\t1 658 182\t14.13%\n"
    )
    assert passage["text"] == expected_text
    assert new_offset == len(expected_text)


# ---------------------------------------------------------------------------
# Integration test: tables are interleaved with text passages in PMC documents
# ---------------------------------------------------------------------------

def _make_pmc_doc(body_contents):
    """Build a minimal SIBiLS PMC document with given body contents."""
    return {
        "_id": "PMC_TEST",
        "document": {
            "body_sections": [
                {"contents": body_contents}
            ],
            "back_sections": [],
            "float_sections": [],
        },
        "sentences": [
            {
                "sentence": "First sentence.",
                "sentence_length": 15,
                "sentence_number": 1,
                "content_id": "p1",
            },
            {
                "sentence": "Second sentence.",
                "sentence_length": 16,
                "sentence_number": 2,
                "content_id": "p2",
            },
        ],
        "annotations": [],
        "relations": [],
    }


def test_table_interleaved_between_paragraphs():
    """Table passage must appear between the two paragraph passages."""
    table = {**TABLE_FULL, "id": "t1"}
    contents = [
        {"tag": "p", "id": "p1"},
        {"tag": "table", **table},
        {"tag": "p", "id": "p2"},
    ]
    doc = _make_pmc_doc(contents)
    result = convert_to_BioC(doc, collection="pmc")

    passages = result["passages"]
    assert len(passages) == 3

    assert passages[0]["text"] == "First sentence."
    assert passages[1]["infons"]["section_type"] == "TABLE"
    assert passages[2]["text"] == "Second sentence."


def test_table_not_added_for_non_pmc():
    """Tables in document sections must be ignored for non-PMC collections."""
    table = {**TABLE_FULL, "id": "t1"}
    contents = [
        {"tag": "p", "id": "p1"},
        {"tag": "table", **table},
        {"tag": "p", "id": "p2"},
    ]
    doc = _make_pmc_doc(contents)
    result = convert_to_BioC(doc, collection="medline")

    # No table passages — only sentence passages (but content_ids won't match
    # since medline path ignores sections; sentences are emitted as-is)
    table_passages = [p for p in result["passages"] if p.get("infons", {}).get("section_type") == "TABLE"]
    assert table_passages == []


def test_offset_continuity():
    """Offsets must be contiguous across sentence and table passages."""
    table = {**TABLE_FULL, "id": "t1"}
    contents = [
        {"tag": "p", "id": "p1"},
        {"tag": "table", **table},
        {"tag": "p", "id": "p2"},
    ]
    doc = _make_pmc_doc(contents)
    result = convert_to_BioC(doc, collection="pmc")

    passages = result["passages"]
    expected_offset = 0
    for p in passages:
        assert p["offset"] == expected_offset
        expected_offset += len(p["text"])
