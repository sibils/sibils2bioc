"""
sibils2bioc
===========
Converts SIBiLS internal document format to BioC JSON format.

BioC DTD reference: https://github.com/2mh/PyBioC/blob/master/BioC.dtd

Document structure produced:
  {
    "id": str,
    "infons": { key: value, ... },   # document-level metadata
    "passages": [                     # one passage per sentence
      {
        "offset": int,               # character offset in document (required by DTD)
        "text": str,
        "infons": { ... },           # sentence metadata (field, tag, sentence_number, …)
        "annotations": [ ... ],
        "relations": []
      }
    ],
    "relations": [ ... ]             # document-level relations
  }

Annotation offsets (location.offset) are document-level offsets, as required by the
BioC DTD. They are computed as: passage_offset + annotation.start_index.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# When a metadata field contains a list of dicts, we look for these keys (in
# order) to extract a human-readable string per item.
_NAME_CANDIDATES = ["name", "text", "term", "label", "value"]


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
        Collection name (e.g. 'pmc', 'medline', …). Currently unused in the
        generic conversion but kept for API compatibility and future use.

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
    # Annotation offsets in SIBiLS are relative to the sentence (start_index).
    # BioC requires offsets relative to the whole document, so we add the
    # cumulative passage offset when building each passage below.
    annotations_per_sentence: dict[int, list] = {}
    for ia, a in enumerate(sibils_doc.get("annotations", [])):
        annotation = {
            "id": str(ia),
            "infons": {},
            "text": a.get("concept_form", ""),
            # offset will be corrected to document-level when building the passage
            "_sentence_start_index": a.get("start_index", 0),
            "locations": [
                {
                    "offset": a.get("start_index", 0),   # placeholder, fixed below
                    "length": a.get("concept_length", 0),
                }
            ],
        }
        for f in (
            "type", "concept_source", "version", "concept_id",
            "preferred_term", "nature", "evidence_code",
            "provenance", "provider", "score", "attributes",
        ):
            if f in a:
                annotation["infons"][f] = a[f]

        sn = a.get("sentence_number")
        annotations_per_sentence.setdefault(sn, []).append(annotation)

    # --- Build passages (one per sentence) -----------------------------------
    doc_offset = 0  # running character offset across the whole document

    for s in sibils_doc.get("sentences", []):
        sentence_length = s.get("sentence_length", 0)

        passage = {
            "offset": doc_offset,          # required top-level field in BioC
            "text": s.get("sentence", ""),
            "infons": {},
            "annotations": [],
            "relations": [],
        }

        for f in ("field", "tag", "content_id", "sentence_number", "sentence_length"):
            if f in s:
                passage["infons"][f] = s[f]

        # Fix annotation offsets to document-level and attach to passage
        sn = s.get("sentence_number")
        for annotation in annotations_per_sentence.get(sn, []):
            doc_level_offset = doc_offset + annotation.pop("_sentence_start_index")
            annotation["locations"][0]["offset"] = doc_level_offset
            passage["annotations"].append(annotation)

        bioc_doc["passages"].append(passage)
        doc_offset += sentence_length

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