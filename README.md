# sibils2bioc

A Python library for converting SIBiLS internal format to BioC format, supporting multiple document collections including PubMed Central (PMC), MEDLINE, Plazi, supplementary data, and Zenodo.

## Overview

The conversion preserves document metadata, text passages, annotations, and relationships, ensuring full fidelity during format transformation.

## Installation

### From source

```bash
pip install git+ssh://git@github.com/sibils/sibils2bioc.git
```

## API Reference

### Main Function

```python
from sibils2bioc import convert_to_BioC

def convert_to_BioC(sibils_doc: dict, collection: str) -> dict:
    """
    Convert a SIBiLS document to BioC format.

    Args:
        sibils_doc (dict): SIBiLS document in JSON format
        collection (str): Document collection type. Supported values:
            - "medline": MEDLINE/PubMed citations
            - "pmc": PubMed Central full-text articles
            - "plazi": Plazi taxonomic treatments
            - "suppdata": Supplementary data files
            - "zenodo": Zenodo research data

    Returns:
        dict: Document in BioC format with the following structure:
            - id: Document identifier
            - infons: Document metadata
            - passages: Text passages with annotations
            - relations: Relationships between entities
    """
```

## Usage Examples

### Basic Usage

```python
import json
from sibils2bioc import convert_to_BioC

# Load a SIBiLS document
with open("sibils_document.json", "r") as f:
    sibils_doc = json.load(f)

# Convert to BioC format
bioc_doc = convert_to_BioC(sibils_doc, "medline")

# Save the result
with open("bioc_document.json", "w") as f:
    json.dump(bioc_doc, f, indent=2)
```
