import json
from mrqlab_sequence import SequenceIR
print(json.dumps(SequenceIR.model_json_schema(), indent=2))
