from mrqlab_sequence import SequenceIR, build_sequence

from .models import ExperimentGraph, TemplateRef

RESERVED = {"PREPARATION", "EXCHANGE", "FLOW", "DIFFUSION", "INJECTION"}


def compile_sequence(graph: ExperimentGraph) -> SequenceIR:
    for node in graph.nodes:
        if node.kind in RESERVED:
            raise ValueError(
                f"reserved node kind {node.kind} is not executable in schema {graph.schema_version}"
            )
    if isinstance(graph.sequence, SequenceIR):
        sequence = graph.sequence.model_copy(deep=True)
    elif isinstance(graph.sequence, TemplateRef):
        sequence = build_sequence(graph.sequence.template, graph.sequence.params)
    else:
        raise TypeError(f"unsupported sequence payload type {type(graph.sequence)!r}")
    sequence.metadata = {**sequence.metadata, "experiment_id": graph.id}
    return sequence
