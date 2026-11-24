"""Unit tests for table-to-BioC conversion and the PMC passage order."""

import json
from pathlib import Path

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
                "sentence": "jpg 5 707 606 48.62%",
                "sentence_length": 20,
                "sentence_number": 2,
                "content_id": "t1",
            },
            {
                "sentence": "Second sentence.",
                "sentence_length": 16,
                "sentence_number": 3,
                "content_id": "p2",
            },
        ],
        "annotations": [],
        "relations": [],
    }


def test_table_interleaved_between_paragraphs():
    """Table passage must appear between the two paragraph passages, after its own sentence."""
    table = {**TABLE_FULL, "id": "t1"}
    contents = [
        {"tag": "p", "id": "p1"},
        {"tag": "table", **table},
        {"tag": "p", "id": "p2"},
    ]
    doc = _make_pmc_doc(contents)
    result = convert_to_BioC(doc, collection="pmc")

    passages = result["passages"]
    assert len(passages) == 4

    assert passages[0]["text"] == "First sentence."
    assert passages[1]["text"] == "jpg 5 707 606 48.62%"
    assert passages[2]["infons"]["section_type"] == "TABLE"
    assert passages[3]["text"] == "Second sentence."


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


# ---------------------------------------------------------------------------
# PMC passage order, on a document shaped like the ones SIBiLS stores: the title,
# abstract and affiliations carry content_id "0", a section title carries the
# section id, every other sentence the id of its content item (a table's caption,
# column and value sentences the table id), in the order body, back, float.
# ---------------------------------------------------------------------------

def _sentence(number, field, tag, content_id, text):
    return {
        "field": field,
        "tag": tag,
        "content_id": content_id,
        "sentence_number": number,
        "sentence": text,
        "sentence_length": len(text),
    }


def _table_without_sentences(content_id, xref_id):
    """A table with no caption, footer, columns or values (only its xml): SIBiLS gives it no sentences."""
    return {
        "tag": "table", "id": content_id, "xref_id": xref_id, "xml": "<table/>",
        "label": "", "caption": "", "footer": "", "table_columns": [], "table_values": [],
    }


BODY_TABLE = {**TABLE_FULL, "id": "3.3", "xref_id": "T1"}            # caption, column and value sentences
BODY_TABLE_NO_SENTENCES = _table_without_sentences("3.4", "T2")
BACK_TABLE_NO_SENTENCES = _table_without_sentences("4.1", "T3")      # e.g. a supplementary data table
FLOAT_TABLE = {**TABLE_NO_COLUMNS, "id": "6.2", "xref_id": "T4"}      # value sentences only, no caption


def _real_pmc_doc():
    return {
        "_id": "PMC_TEST",
        "document": {
            "body_sections": [
                {"id": "1", "title": "Title", "contents": [{"id": "1.1", "tag": "p"}]},
                {"id": "2", "title": "Abstract", "contents": [{"id": "2.1", "tag": "p"}]},
                {"id": "3", "title": "Results", "contents": [
                    {"id": "3.1", "tag": "p"},
                    {"id": "3.2", "tag": "fig"},
                    BODY_TABLE,
                    BODY_TABLE_NO_SENTENCES,
                    {"id": "3.5", "tag": "p"},
                ]},
            ],
            "back_sections": [
                {"id": "4", "title": "Supplementary data", "contents": [BACK_TABLE_NO_SENTENCES]},
                {"id": "5", "title": "References", "contents": [{"id": "5.1", "tag": "ref"}]},
            ],
            "float_sections": [
                {"id": "6", "title": "", "contents": [{"id": "6.1", "tag": "fig"}, FLOAT_TABLE]},
            ],
        },
        "sentences": [
            _sentence(1, "title", None, "0", "Tables in BioC."),
            _sentence(2, "abstract", None, "0", "We place each table."),
            _sentence(3, "affiliations", None, "0", "SIB, Geneva."),
            _sentence(4, "section_title", "sec", "1", "Title"),
            _sentence(5, "text", "p", "1.1", "Tables in BioC."),
            _sentence(6, "section_title", "sec", "2", "Abstract"),
            _sentence(7, "text", "p", "2.1", "We place each table."),
            _sentence(8, "section_title", "sec", "3", "Results"),
            _sentence(9, "text", "p", "3.1", "See Table 1."),
            _sentence(10, "fig_caption", "fig", "3.2", "A figure."),
            _sentence(11, "table_caption", "table", "3.3", "For each file type, the number of files."),
            _sentence(12, "table_column", "table", "3.3", "File type"),
            _sentence(13, "table_value", "table", "3.3", "jpg 5 707 606 48.62%"),
            _sentence(14, "text", "p", "3.5", "After the tables."),
            _sentence(15, "section_title", "sec", "4", "Supplementary data"),
            _sentence(16, "section_title", "sec", "5", "References"),
            _sentence(17, "fig_caption", "fig", "6.1", "A floating figure."),
            _sentence(18, "table_value", "table", "6.2", "pdf 1 658 182 14.13%"),
        ],
        "annotations": [],
        "relations": [],
    }


def _key(passage):
    """A sentence passage by its sentence_number, a table passage by its table_id."""
    if passage["infons"].get("section_type") == "TABLE":
        return passage["infons"]["table_id"]
    return passage["infons"]["sentence_number"]


def test_pmc_passage_order():
    passages = convert_to_BioC(_real_pmc_doc(), collection="pmc")["passages"]
    assert [_key(p) for p in passages] == [
        1, 2, 3,                    # title, abstract, affiliations (content_id "0") first
        4, 5, 6, 7,                 # sections Title and Abstract, each title before its text
        8, 9, 10,                   # section Results: title, paragraph, figure caption
        11, 12, 13, "T1",           # a table after its caption, column and value sentences
        14,                         # T2, a table without sentences: no passage
        15,                         # T3, the same in back_sections
        16,
        17, 18, "T4",               # float_sections after back_sections; a table without caption
    ]


def test_pmc_sentences_keep_their_stored_order():
    doc = _real_pmc_doc()
    passages = convert_to_BioC(doc, collection="pmc")["passages"]
    sentence_passages = [p for p in passages if "section_type" not in p["infons"]]
    assert [p["text"] for p in sentence_passages] == [s["sentence"] for s in doc["sentences"]]
    assert [p["infons"]["content_id"] for p in sentence_passages] == [s["content_id"] for s in doc["sentences"]]


def test_pmc_one_passage_per_table_with_sentences():
    passages = convert_to_BioC(_real_pmc_doc(), collection="pmc")["passages"]
    tables = [p for p in passages if p["infons"].get("section_type") == "TABLE"]
    assert [p["infons"]["table_id"] for p in tables] == ["T1", "T4"]


def test_pmc_offsets_and_annotations_across_tables():
    doc = _real_pmc_doc()
    doc["annotations"] = [
        {"sentence_number": 1, "start_index": 0, "concept_length": 6, "concept_form": "Tables"},
        {"sentence_number": 13, "start_index": 0, "concept_length": 3, "concept_form": "jpg"},
        {"sentence_number": 14, "start_index": 10, "concept_length": 6, "concept_form": "tables"},
        {"sentence_number": 18, "start_index": 0, "concept_length": 3, "concept_form": "pdf"},
    ]
    passages = convert_to_BioC(doc, collection="pmc")["passages"]

    expected_offset = 0
    for p in passages:
        assert p["offset"] == expected_offset
        expected_offset += len(p["text"])

    placed = [(p, a) for p in passages for a in p["annotations"]]
    assert [p["infons"]["sentence_number"] for p, _ in placed] == [1, 13, 14, 18]
    for p, a in placed:
        [location] = a["locations"]
        start = location["offset"] - p["offset"]
        assert p["text"][start:start + location["length"]] == a["text"]


def test_pmc_document_without_tables_converts_like_any_collection():
    doc = _real_pmc_doc()
    for kind in ("body_sections", "back_sections", "float_sections"):
        for section in doc["document"][kind]:
            section["contents"] = [c for c in section["contents"] if c["tag"] != "table"]
    assert convert_to_BioC(doc, collection="pmc") == convert_to_BioC(doc, collection="medline")


def test_pmc_asset_keeps_sentence_order_and_places_its_table():
    with open(Path(__file__).parent / "assets" / "pmc" / "sibils_PMC10967677.json", encoding="utf-8") as f:
        doc = json.load(f)
    passages = convert_to_BioC(doc, collection="pmc")["passages"]

    sentence_passages = [p for p in passages if "section_type" not in p["infons"]]
    assert [p["infons"]["sentence_number"] for p in sentence_passages] == [
        s["sentence_number"] for s in doc["sentences"]
    ]
    assert passages[0]["infons"]["field"] == "title"

    # its one table, 3.2.3.2, has sentences 98 (caption) to 109 (values)
    [i] = [i for i, p in enumerate(passages) if p["infons"].get("section_type") == "TABLE"]
    assert passages[i - 1]["infons"]["sentence_number"] == 109
    assert passages[i + 1]["infons"]["sentence_number"] == 110
