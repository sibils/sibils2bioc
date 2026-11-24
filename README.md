# sibils2bioc

A Python library for converting SIBiLS internal document format to [BioC JSON](https://github.com/2mh/PyBioC/blob/master/BioC.dtd) format.

## Overview

The conversion is generic and collection-agnostic: document metadata, text passages, annotations, and relations are all preserved. Document-level annotation offsets are computed as required by the BioC DTD (`passage_offset + annotation.start_index`).

## Installation

```bash
pip install git+ssh://git@github.com/sibils/sibils2bioc.git
```

## API Reference

```python
from sibils2bioc import convert_to_BioC

convert_to_BioC(sibils_doc: dict, collection: str = None) -> dict
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sibils_doc` | `dict` | A single SIBiLS document. Must contain `_id`, `document`, `sentences`, `annotations`, `relations`. |
| `collection` | `str` (optional) | Collection name (e.g. `"pmc"`, `"medline"`). Kept for API compatibility; not used in the conversion logic. |

**Returns** a BioC document dict:

```
{
  "id":       str,
  "infons":   { key: value, ... },   # all fields from document, flattened
  "passages": [                       # one passage per sentence
    {
      "offset":      int,             # document-level character offset
      "text":        str,
      "infons":      { field, tag, content_id, sentence_number, sentence_length },
      "annotations": [ ... ],
      "relations":   []
    }
  ],
  "relations": [ ... ]                # document-level relations
}
```

**Annotations**: one BioC annotation per SIBiLS annotation, in the passage of its sentence (an
annotation whose `sentence_number` names no sentence is left out):

```
{
  "id":        str,                   # position in sibils_doc["annotations"], named by relation nodes
  "text":      concept_form,
  "locations": [ { "offset": passage offset + start_index, "length": concept_length } ],
  "infons":    { ... }                # every other field of the annotation, as is (null kept)
}
```

`concept_form`, `start_index`, `end_index`, `concept_length`, `field` and `sentence_number` are not
repeated in the annotation `infons`: the BioC structure holds them. Every other field is copied, so
an annotation keeps whatever its producer gives it: `provenance` (`SIBILS`, or an external provider
such as `FairClinical`), `evidence_code`, and for an external provider's annotation its `category`
(e.g. `disease`, `pico_participant`) and `bioc_id` (the id of the annotation in the provider's own
BioC). An external annotation may have a null `preferred_term`, `version`, `category` or
`evidence_code`, and one without a concept a null `concept_source`, `concept_id` and `type`.

The annotation `id` is a handle that relation nodes name. It is unique within the document, as BioC
requires of ids at the level where the relations are, but it is not stable across releases. It is
never the provider's id, which goes in `infons.bioc_id`. To find a provider annotation in the
provider's original BioC, match the document `id`, `infons.provenance` and `infons.bioc_id` against
the original annotation's `id`. Several annotations can share a `bioc_id`, because SIBiLS serves a
provider annotation at every place it holds its text, such as a title or abstract held again in the
body text. Each of these is a BioC annotation of its own, with one location in its own passage.

**`infons` flattening rules** (applied to every field of `document`):

| Source value | Result in `infons` |
|---|---|
| `None` | `""` |
| scalar (`str`, `int`, …) | value as-is |
| list of scalars | `";"`-joined string |
| list of dicts | `";"`-joined string of the best name sub-field (`name`, `text`, `term`, `label`, `value`), deduped |
| anything else | `str()` |

## Usage

```python
import json
from sibils2bioc import convert_to_BioC

with open("sibils_document.json") as f:
    sibils_doc = json.load(f)

bioc_doc = convert_to_BioC(sibils_doc)

with open("bioc_document.json", "w") as f:
    json.dump(bioc_doc, f, indent=2)
```

Converting a batch (e.g. from the SIBiLS fetch API):

```python
bioc_articles = [convert_to_BioC(doc) for doc in response["sibils_article_set"]]
```
