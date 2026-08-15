from .models import ExperimentEdge, ExperimentGraph, ExperimentNode, TemplateRef

_PRESETS = {
    "spin-echo": ("SE", "Spin Echo", "teaching", ("RF", "RF", "READOUT")),
    "gradient-echo": ("GRE", "Gradient Echo", "teaching", ("RF", "GRADIENT", "READOUT")),
    "dark-blood-tse": ("TSE", "Dark Blood TSE", "clinical_contrast", ("RF", "LOOP", "READOUT")),
}


def build_preset(name: str, params: dict[str, float | int] | None = None) -> ExperimentGraph:
    try:
        template, title, intent, kinds = _PRESETS[name]
    except KeyError:
        raise ValueError(f"unknown experiment preset {name!r}") from None
    nodes = tuple(
        ExperimentNode(id=f"n{index}", kind=kind, label=f"{kind} {index}")
        for index, kind in enumerate(kinds)
    )
    edges = tuple(
        ExperimentEdge(source=nodes[index].id, target=nodes[index + 1].id)
        for index in range(len(nodes) - 1)
    )
    return ExperimentGraph(
        id=f"preset:{name}",
        name=title,
        intent=intent,
        nodes=nodes,
        edges=edges,
        sequence=TemplateRef(template=template, params=params or {}),
    )
