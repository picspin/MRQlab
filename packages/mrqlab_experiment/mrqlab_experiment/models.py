from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from mrqlab_sequence import SequenceIR

from .disturbances import DisturbanceStack
from .objectives import ObjectiveFunction

ActiveNodeKind = Literal["RF", "GRADIENT", "DELAY", "ADC", "READOUT", "LOOP"]
ReservedNodeKind = Literal["PREPARATION", "EXCHANGE", "FLOW", "DIFFUSION", "INJECTION"]
NodeKind = ActiveNodeKind | ReservedNodeKind
EdgeKind = Literal["TEMPORAL", "DEPENDENCY", "STATE_TRANSITION"]


class ExperimentNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExperimentEdge(BaseModel):
    source: str
    target: str
    kind: EdgeKind = "TEMPORAL"


class TemplateRef(BaseModel):
    template: Literal["SE", "GRE", "TSE"]
    params: dict[str, float | int] = Field(default_factory=dict)


class SampleSpec(BaseModel):
    t1: float = Field(default=1.0, gt=0)
    t2: float = Field(default=0.1, gt=0)
    proton_density: float = Field(default=1.0, ge=0)
    off_resonance_hz: float = 0.0
    # Keep nested phantom fields so /simulate adapter can round-trip payloads.
    isochromats: tuple[dict[str, Any], ...] = ()
    pools: tuple[dict[str, Any], ...] = ()


class TissueModel(BaseModel):
    t1: float = Field(default=1.0, gt=0)
    t2: float = Field(default=0.1, gt=0)
    t2_star: float | None = Field(default=None, gt=0)
    proton_density: float = Field(default=1.0, ge=0)
    flow_velocity_mps: float = Field(default=0.0)
    exchange_rate_hz: float = Field(default=0.0, ge=0)
    pool_fraction: float = Field(default=1.0, ge=0, le=1.0)
    diffusion_adc_mm2_s: float | None = Field(default=None, ge=0)


class PhysiologyModel(BaseModel):
    cardiac_phase: float = Field(default=0.0, ge=0.0, le=1.0)
    rr_interval_s: float = Field(default=1.0, gt=0)
    respiratory_phase: float = Field(default=0.0, ge=0.0, le=1.0)
    flow_waveform: tuple[float, ...] = ()
    contrast_agent_concentration: float = Field(default=0.0, ge=0)


class ScannerSpec(BaseModel):
    b0_t: float = Field(default=1.5, gt=0)
    gradient_scale: float = Field(default=1.0, ge=0)


class ScannerModel(BaseModel):
    b0_t: float = Field(default=1.5, gt=0)
    gradient_scale: float = Field(default=1.0, ge=0)
    max_gradient_mt_m: float = Field(default=40.0, gt=0)
    max_slew_rate_t_m_s: float = Field(default=150.0, gt=0)
    adc_bandwidth_hz: float = Field(default=50000.0, gt=0)


class DisturbanceModel(BaseModel):
    kind: str
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)



class EngineRef(BaseModel):
    preferred: str | None = None
    required_capabilities: frozenset[str] = frozenset()
    options: dict[str, Any] = Field(default_factory=dict)


class ReadoutSpec(BaseModel):
    products: tuple[str, ...] = ("signal", "k_trajectory", "image")


class ConstraintSet(BaseModel):
    max_work: int = Field(default=2_000_000, ge=1)
    matrix: int = Field(default=32, ge=1)


class ProvenanceHints(BaseModel):
    seed: int = 0
    tags: tuple[str, ...] = ()


class ExperimentGraph(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    name: str
    intent: Literal["teaching", "clinical_contrast", "physics", "custom"]
    nodes: tuple[ExperimentNode, ...]
    edges: tuple[ExperimentEdge, ...]
    sequence: SequenceIR | TemplateRef
    sample: SampleSpec = Field(default_factory=SampleSpec)
    scanner: ScannerSpec = Field(default_factory=ScannerSpec)
    engine: EngineRef = Field(default_factory=EngineRef)
    objective: ObjectiveFunction | None = None
    readout: ReadoutSpec = Field(default_factory=ReadoutSpec)
    constraints: ConstraintSet = Field(default_factory=ConstraintSet)
    disturbances: DisturbanceStack = Field(default_factory=DisturbanceStack)
    provenance: ProvenanceHints = Field(default_factory=ProvenanceHints)

    @model_validator(mode="after")
    def edges_reference_nodes(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("experiment node ids must be unique")
        if any(edge.source not in ids or edge.target not in ids for edge in self.edges):
            raise ValueError("experiment edges must reference existing nodes")
        return self
