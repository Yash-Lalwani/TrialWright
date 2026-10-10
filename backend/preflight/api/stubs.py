import copy
import json
from pathlib import Path

_EXAMPLES = json.loads((Path(__file__).parent / "contract_examples.json").read_text())


def example(name: str):
    return copy.deepcopy(_EXAMPLES[name])
