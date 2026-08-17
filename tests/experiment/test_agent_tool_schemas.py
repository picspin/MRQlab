import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_agent_schema_names_tools_and_graph_contract():
    schema = json.loads((ROOT / "docs/agent-tools/experiment-tools.schema.json").read_text())
    names = {item["allOf"][1]["properties"]["name"]["const"] for item in schema["oneOf"]}
    assert names == {
        "inspect_experiment", "inspect_signal", "compare_tissues", "run_simulation",
        "run_optimization", "explain_epg_pathway", "suggest_parameters", "find_failure_mode",
    }
    assert schema["$defs"]["experimentGraph"]["properties"]["schema_version"]["const"] == "1.0"
