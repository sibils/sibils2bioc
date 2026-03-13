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
