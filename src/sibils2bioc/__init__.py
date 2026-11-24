"""
sibils2bioc
===========
Converts SIBiLS internal document format to BioC JSON format.

BioC DTD reference: https://github.com/2mh/PyBioC/blob/master/BioC.dtd

Document structure produced:
  {
    "id": str,
    "infons": { key: value, ... },   # document-level metadata
    "passages": [                     # one passage per sentence or table
      {
        "offset": int,               # character offset in document (required by DTD)
        "text": str,
        "infons": { ... },           # sentence/table metadata
        "annotations": [ ... ],
        "relations": []
      }
    ],
    "relations": [ ... ]             # document-level relations
  }

Passages come in the stored order of the sentences, which SIBiLS keeps in document
order. A PMC document also gets one passage per table that has sentences, after them
(see _tables_after_sentences).

Annotation offsets (location.offset) are document-level offsets, as required by the
BioC DTD. They are computed as: passage_offset + annotation.start_index.

Annotation infons hold every field of the SIBiLS annotation except the ones the BioC
structure already holds (_ANNOTATION_PLACEMENT_FIELDS), so an annotation of an external
provider keeps its own fields (category, bioc_id) beside provenance and evidence_code.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# When a metadata field contains a list of dicts, we look for these keys (in
# order) to extract a human-readable string per item.
_NAME_CANDIDATES = ["name", "text", "term", "label", "value"]

# Fields of a SIBiLS annotation that the BioC annotation holds in its structure,
# so they are not repeated as infons: concept_form is its text, start_index,
# end_index and concept_length its location, field and sentence_number are the
# infons of its passage. Every other field is copied: a list of fields to keep
# would drop, silently, the fields a new provenance brings (category, bioc_id).
_ANNOTATION_PLACEMENT_FIELDS = frozenset((
    "concept_form", "start_index", "end_index", "concept_length",
    "field", "sentence_number",
))


def _document_to_infons(doc: dict) -> dict:
    """
    Generically convert all fields of a SIBiLS document dict into a flat
    BioC infons dict.

    Rules:
      - None              → ""
      - scalar            → value as-is
      - list of scalars   → ";"-joined string
      - list of dicts     → ";"-joined string of the best "name" sub-field,
                            deduped and preserving order; falls back to str()
                            if no known name key is found.
      - anything else     → str()
    """
    infons = {}
    for key, value in doc.items():
        if key == "_id":
            # _id is already used as the document id
            continue

        if value is None:
            infons[key] = ""

        elif isinstance(value, (str, int, float, bool)):
            infons[key] = value

        elif isinstance(value, list):
            if not value:
                infons[key] = ""
            elif all(isinstance(item, dict) for item in value):
                # List of dicts: find the best name key from the first item
                name_key = next(
                    (k for k in _NAME_CANDIDATES if k in value[0]), None
                )
                if name_key:
                    seen = []
                    for item in value:
                        v = item.get(name_key, "")
                        if v and v not in seen:
                            seen.append(str(v))
                    infons[key] = ";".join(seen)
                else:
                    # No known name key: serialize each dict as string
                    infons[key] = ";".join(str(item) for item in value)
            else:
                # List of scalars (str, int, …)
                infons[key] = ";".join(str(item) for item in value if item is not None)

        else:
            infons[key] = str(value)

    return infons


# ---------------------------------------------------------------------------
# Table helpers (PMC) — one BioC passage per table
# ---------------------------------------------------------------------------

def _table_to_passage(table: dict, offset: int) -> tuple[dict, int]:
    """
    Convert a SIBiLS table item to a single BioC passage.

    text  : header row (table_columns joined by \\t) + one row per
            table_values entry, each joined by \\t, all separated by \\n.
    infons: section_type + all non-empty metadata fields (table_id, label,
            caption, footer, xref_url, xml). Missing / empty fields are omitted.
    """
    # Build text
    lines = []
    columns = table.get("table_columns") or []
    if columns:
        lines.append("\t".join(str(c) for c in columns))
    for row in table.get("table_values") or []:
        lines.append("\t".join(str(c) for c in row))
    text = "\n".join(lines)
    if text:
        text += "\n"

    # Build infons — omit empty/absent fields
    infons: dict = {"section_type": "TABLE"}
    for src_key, dst_key in (
        ("xref_id",  "table_id"),
        ("label",    "label"),
        ("caption",  "caption"),
        ("footer",   "footer"),
        ("xref_url", "xref_url"),
        ("xml",      "xml"),
    ):
        val = (table.get(src_key) or "").strip()
        if val:
            infons[dst_key] = val

    passage = {
        "offset": offset,
        "text": text,
        "infons": infons,
        "annotations": [],
        "relations": [],
    }
    return passage, offset + len(text)


def _tables_after_sentences(sibils_doc: dict) -> dict[int, dict]:
    """
    Give each table item of a PMC document the sentence its passage follows:
    the last of the table's own sentences (table_caption, table_footer,
    table_column, table_value), which carry the table's id as content_id.

    A table without sentences has no caption, footer, columns or values, so it
    has no text and gets no passage.

    Returns {sentence index: table}.
    """
    last_sentence = {s.get("content_id"): i for i, s in enumerate(sibils_doc.get("sentences", []))}
    doc_inner = sibils_doc.get("document", {})
    tables_after = {}
    for section in (
        doc_inner.get("body_sections", [])
        + doc_inner.get("back_sections", [])
        + doc_inner.get("float_sections", [])
    ):
        for content in section.get("contents", []):
            if content.get("tag") == "table" and content.get("id") in last_sentence:
                tables_after[last_sentence[content["id"]]] = content
    return tables_after


# ---------------------------------------------------------------------------
# Sentence helper
# ---------------------------------------------------------------------------

def _sentence_passage(
    s: dict, doc_offset: int, annotations_per_sentence: dict
) -> tuple[dict, int]:
    """Build a BioC passage from a SIBiLS sentence dict."""
    sentence_length = s.get("sentence_length", 0)

    passage = {
        "offset": doc_offset,
        "text": s.get("sentence", ""),
        "infons": {},
        "annotations": [],
        "relations": [],
    }

    for f in ("field", "tag", "content_id", "sentence_number", "sentence_length"):
        if f in s:
            passage["infons"][f] = s[f]

    sn = s.get("sentence_number")
    for annotation in annotations_per_sentence.get(sn, []):
        doc_level_offset = doc_offset + annotation.pop("_sentence_start_index")
        annotation["locations"][0]["offset"] = doc_level_offset
        passage["annotations"].append(annotation)

    return passage, doc_offset + sentence_length


# ---------------------------------------------------------------------------
# Main conversion function
# ---------------------------------------------------------------------------

def convert_to_BioC(sibils_doc: dict, collection: str = None) -> dict:
    """
    Convert a single SIBiLS article to BioC JSON format.

    Parameters
    ----------
    sibils_doc : dict
        One element from sibils_article_set. Must contain at minimum:
        '_id', 'document', 'sentences', 'annotations', 'relations'.
    collection : str, optional
        Collection name (e.g. 'pmc', 'medline', …). 'pmc' adds one passage
        per table.

    Returns
    -------
    dict
        BioC document as a Python dict (serialisable to JSON).
    """

    # --- Document skeleton ---------------------------------------------------
    bioc_doc = {
        "id": sibils_doc["_id"],
        "infons": _document_to_infons(sibils_doc.get("document", {})),
        "passages": [],
        "relations": [],
    }

    # --- Pre-index annotations by sentence_number ----------------------------
    annotations_per_sentence: dict[int, list] = {}
    for ia, a in enumerate(sibils_doc.get("annotations", [])):
        annotation = {
            "id": str(ia),
            "infons": {
                k: v for k, v in a.items() if k not in _ANNOTATION_PLACEMENT_FIELDS
            },
            "text": a.get("concept_form", ""),
            "_sentence_start_index": a.get("start_index", 0),
            "locations": [
                {
                    "offset": a.get("start_index", 0),
                    "length": a.get("concept_length", 0),
                }
            ],
        }

        sn = a.get("sentence_number")
        annotations_per_sentence.setdefault(sn, []).append(annotation)

    # --- Build passages -------------------------------------------------------
    # One passage per sentence, in stored order; in a PMC document, each table
    # passage follows the last of the table's own sentences.
    tables_after = _tables_after_sentences(sibils_doc) if collection == "pmc" else {}
    doc_offset = 0

    for i, s in enumerate(sibils_doc.get("sentences", [])):
        passage, doc_offset = _sentence_passage(s, doc_offset, annotations_per_sentence)
        bioc_doc["passages"].append(passage)
        if i in tables_after:
            passage, doc_offset = _table_to_passage(tables_after[i], doc_offset)
            bioc_doc["passages"].append(passage)

    # --- Relations -----------------------------------------------------------
    ir = 0
    for ta in sibils_doc.get("relations", []):
        concept1_list = ta.get("concept1", [])
        concept2_list = ta.get("concept2", [])
        concept3_list = ta.get("concept3", [])

        for c1 in concept1_list:
            for c2 in concept2_list:
                if not concept3_list:
                    relation = {
                        "id": "R" + str(ir),
                        "infons": {"type": "biotic interaction"},
                        "nodes": [
                            {"refid": str(c1), "role": "species1"},
                            {"refid": str(c2), "role": "species2"},
                        ],
                    }
                    bioc_doc["relations"].append(relation)
                    ir += 1
                else:
                    for c3 in concept3_list:
                        relation = {
                            "id": "R" + str(ir),
                            "infons": {"type": "biotic interaction"},
                            "nodes": [
                                {"refid": str(c1), "role": "species1"},
                                {"refid": str(c2), "role": "species2"},
                                {"refid": str(c3), "role": "interaction"},
                            ],
                        }
                        bioc_doc["relations"].append(relation)
                        ir += 1

    return bioc_doc
