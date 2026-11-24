"""Unit tests for annotation infons: SIBiLS's own annotations and those of external providers."""

from sibils2bioc import convert_to_BioC


SENTENCE = "Acute median nerve palsy and Pain."

# A SIBiLS annotation, as /api/fetch serves it.
SIBILS = {
    "provenance": "SIBILS",
    "type": "mesh",
    "version": "2026",
    "evidence_code": "ECO_0000366",
    "concept_source": "mesh",
    "concept_id": "D008475",
    "concept_form": "median nerve",
    "preferred_term": "Median Nerve",
    "nature": "pref_term",
    "field": "title",
    "sentence_number": 1,
    "start_index": 6,
    "end_index": 18,
    "concept_length": 12,
    "score": 0.5,
    "attributes": None,
}

# An external provider's annotation without a concept (a PICO span): no concept_source,
# concept_id, preferred_term or version, but a category and the provider's own id.
PICO = {
    "provenance": "FairClinical",
    "type": None,
    "version": None,
    "evidence_code": "ECO_0000203",
    "concept_source": None,
    "concept_id": None,
    "concept_form": "Acute median nerve palsy",
    "preferred_term": None,
    "field": "title",
    "sentence_number": 1,
    "start_index": 0,
    "end_index": 24,
    "concept_length": 24,
    "score": None,
    "attributes": None,
    "category": "pico_participant",
    "bioc_id": "pico-423570",
}

# An external provider's annotation with a concept, served without a preferred term or version.
DISEASE = {
    **PICO,
    "type": "mesh",
    "concept_source": "mesh",
    "concept_id": "D001939",
    "concept_form": "Pain",
    "start_index": 29,
    "end_index": 33,
    "concept_length": 4,
    "category": "disease",
    "bioc_id": "dis-365970",
}

PLACEMENT_FIELDS = {"concept_form", "field", "sentence_number", "start_index", "end_index", "concept_length"}


def _doc(annotations, relations=()):
    return {
        "_id": "PMC_TEST",
        "document": {"title": SENTENCE},
        "sentences": [
            {"field": "title", "sentence_number": 0, "sentence": "First.", "sentence_length": 6},
            {"field": "title", "sentence_number": 1, "sentence": SENTENCE, "sentence_length": len(SENTENCE)},
        ],
        "annotations": list(annotations),
        "relations": list(relations),
    }


def _annotations(bioc):
    return [a for p in bioc["passages"] for a in p["annotations"]]


def test_external_annotation_keeps_its_category_and_bioc_id():
    [pico, disease] = _annotations(convert_to_BioC(_doc([PICO, DISEASE])))

    assert pico["infons"] == {k: v for k, v in PICO.items() if k not in PLACEMENT_FIELDS}
    assert pico["infons"]["category"] == "pico_participant"
    assert pico["infons"]["bioc_id"] == "pico-423570"
    assert pico["infons"]["concept_source"] is None
    assert pico["infons"]["preferred_term"] is None

    assert disease["infons"]["category"] == "disease"
    assert disease["infons"]["bioc_id"] == "dis-365970"
    assert disease["infons"]["concept_id"] == "D001939"
    assert disease["infons"]["preferred_term"] is None
    assert disease["infons"]["version"] is None


def test_sibils_annotation_infons_unchanged():
    [sibils] = _annotations(convert_to_BioC(_doc([SIBILS])))
    assert sibils["infons"] == {
        "provenance": "SIBILS",
        "type": "mesh",
        "version": "2026",
        "evidence_code": "ECO_0000366",
        "concept_source": "mesh",
        "concept_id": "D008475",
        "preferred_term": "Median Nerve",
        "nature": "pref_term",
        "score": 0.5,
        "attributes": None,
    }


def test_placement_fields_are_structure_not_infons():
    bioc = convert_to_BioC(_doc([SIBILS, PICO, DISEASE]))
    passage = bioc["passages"][1]
    assert len(passage["annotations"]) == 3
    for annotation, source in zip(passage["annotations"], (SIBILS, PICO, DISEASE)):
        assert not PLACEMENT_FIELDS & set(annotation["infons"])
        [location] = annotation["locations"]
        assert annotation["text"] == source["concept_form"]
        assert location == {"offset": passage["offset"] + source["start_index"], "length": source["concept_length"]}
        start = location["offset"] - passage["offset"]
        assert passage["text"][start:start + location["length"]] == annotation["text"]


def test_a_new_annotation_field_is_kept():
    [annotation] = _annotations(convert_to_BioC(_doc([{**PICO, "some_new_field": "x"}])))
    assert annotation["infons"]["some_new_field"] == "x"


def test_items_of_one_provider_annotation_keep_distinct_ids():
    # one provider annotation served as several items (one per concept or segment) shares its bioc_id
    second = {**PICO, "concept_source": "ncit", "concept_id": "C0000"}
    annotations = _annotations(convert_to_BioC(_doc([PICO, second])))
    assert [a["id"] for a in annotations] == ["0", "1"]
    assert [a["infons"]["bioc_id"] for a in annotations] == ["pico-423570", "pico-423570"]


def test_copies_of_one_provider_annotation_stay_apart():
    # SIBiLS holds the title twice (field title, then again in the body text) and serves the annotation at both places
    doc = _doc([PICO, {**PICO, "field": "text", "sentence_number": 2}])
    doc["sentences"].append({"field": "text", "sentence_number": 2, "sentence": SENTENCE, "sentence_length": len(SENTENCE)})
    bioc = convert_to_BioC(doc)
    placed = [(p["offset"], a) for p in bioc["passages"] for a in p["annotations"]]
    assert [a["id"] for _, a in placed] == ["0", "1"]
    assert [a["infons"]["bioc_id"] for _, a in placed] == ["pico-423570", "pico-423570"]
    assert [a["locations"] for _, a in placed] == [[{"offset": offset, "length": 24}] for offset, _ in placed]
    assert placed[0][0] != placed[1][0]


def test_relation_names_the_sibils_annotation_among_provider_ones():
    # /api/fetch serves relations as positions in the annotations it serves, provider ones included
    relation = {"type": "biotic_interactions", "concept1": [1], "concept2": [1]}
    bioc = convert_to_BioC(_doc([PICO, SIBILS, DISEASE], [relation]))
    by_id = {a["id"]: a for a in _annotations(bioc)}
    [r] = bioc["relations"]
    assert [by_id[n["refid"]]["infons"]["provenance"] for n in r["nodes"]] == ["SIBILS", "SIBILS"]
