export interface ScenarioTissue {
  id: string;
  name: string;
  t1: number;
  t2: number;
  t2s?: number;
  pd: number;
  desc: string;
}

export interface ScenarioSpec {
  id: string;
  recipeId: string;
  name: string;
  category: "Neuro" | "Cardiac" | "Body" | "MSK" | "Vascular" | "Spectroscopy";
  seqType: "TSE" | "GRE" | "SE" | "CEST";
  anatomy: string;
  scanPlane: "AXIAL" | "CORONAL" | "SAGITTAL" | "SHORT AXIS" | "VOXEL";
  weightingName: string;
  clinicalQuestion: string;
  tissues: ScenarioTissue[];
  /** Imaging FA/TE/TR/geometry. Omit on spectroscopy scenarios — they are not spin-echo products. */
  defaultParams?: {
    fa: number;
    te: number;
    tr: number;
    fov: number;
    matrix: number;
    sliceThick: number;
    sliceCount: number;
    sliceGap: number;
    isInterleaved: boolean;
    flipAngleGRE?: number;
  };
}

export const CLINICAL_SCENARIOS: Record<string, ScenarioSpec> = {
  cest_amide: {
    id: "cest_amide", recipeId: "cest_amide_z_spectrum",
    name: "Physics — Two-pool amide CEST Z-spectrum", category: "Spectroscopy", seqType: "CEST",
    anatomy: "Single voxel", scanPlane: "VOXEL", weightingName: "Z(Δ) spectrum experiment",
    clinicalQuestion: "How does exchanging amide saturation alter the backend-computed water Z-spectrum?",
    tissues: [
      { id: "water", name: "Water", t1: 1000, t2: 80, pd: .9, desc: "0 ppm reference liquid" },
      { id: "amide", name: "Amide solute", t1: 1000, t2: 10, pd: .1, desc: "+3.5 ppm exchanging liquid" },
    ],
  },
  ms_brain: {
    id: "ms_brain",
    recipeId: "brain_t2_tse",
    name: "Brain & Neuro — MS Plaque Demarcation",
    category: "Neuro",
    seqType: "TSE",
    anatomy: "Brain",
    scanPlane: "AXIAL",
    weightingName: "T2 TSE",
    clinicalQuestion: "Why does high-TE TSE maximize lesion-WM contrast without CSF blooming?",
    tissues: [
      { id: "lesion", name: "MS Lesion Plaque", t1: 1400, t2: 120, t2s: 80, pd: 0.95, desc: "Hyperintense / Prolonged T2" },
      { id: "wm", name: "Normal White Matter", t1: 900, t2: 80, t2s: 60, pd: 0.70, desc: "Reference Base (Suppressed)" },
      { id: "gm", name: "Cortical Gray Matter", t1: 1300, t2: 100, t2s: 75, pd: 0.85, desc: "Intermediate Brain Parenchyma" },
      { id: "csf", name: "Ventricular CSF", t1: 4000, t2: 2000, t2s: 500, pd: 1.00, desc: "Free Fluid / Long T1/T2" },
      { id: "fat", name: "Scalp Subcutaneous Fat", t1: 250, t2: 70, t2s: 50, pd: 0.90, desc: "Short T1 Hyperintense" }
    ],
    defaultParams: { fa: 150, te: 100, tr: 3000, fov: 230, matrix: 256, sliceThick: 4.0, sliceCount: 20, sliceGap: 1.0, isInterleaved: true, flipAngleGRE: 90 }
  },
  cardiac_darkblood: {
    id: "cardiac_darkblood",
    recipeId: "dark_blood_vessel_wall_tse",
    name: "Cardiovascular — Short-Axis Dark Blood Wall",
    category: "Cardiac",
    seqType: "TSE",
    anatomy: "Heart",
    scanPlane: "SHORT AXIS",
    weightingName: "DIR T2 TSE",
    clinicalQuestion: "How does Double Inversion Recovery (DIR) void blood pool to visualize thin endocardium?",
    tissues: [
      { id: "myo", name: "Left Ventricle Myocardium", t1: 1050, t2: 50, t2s: 40, pd: 0.75, desc: "Target Heart Muscle Wall" },
      { id: "blood", name: "Flowing Cavity Blood", t1: 1600, t2: 180, t2s: 100, pd: 0.95, desc: "Flow Dephased / Black Cavity" },
      { id: "endo", name: "Subendocardial Border", t1: 1100, t2: 65, t2s: 45, pd: 0.80, desc: "Inner Plaque/Ischemia Margin" },
      { id: "fat", name: "Pericardial Fat", t1: 260, t2: 60, t2s: 50, pd: 0.85, desc: "Bright Epicardial Fat Ring" }
    ],
    defaultParams: { fa: 140, te: 60, tr: 1200, fov: 320, matrix: 224, sliceThick: 6.0, sliceCount: 12, sliceGap: 2.0, isInterleaved: true, flipAngleGRE: 90 }
  },
  abdomen_dixon: {
    id: "abdomen_dixon",
    recipeId: "abdomen_dixon_gre",
    name: "Abdominal — Liver Steatosis & Dixon Fat Sep",
    category: "Body",
    seqType: "GRE",
    anatomy: "Abdomen",
    scanPlane: "CORONAL",
    weightingName: "T1 In/Out Phase GRE",
    clinicalQuestion: "How does low-flip-angle fast GRE separate fat/water phase with minimal T1 bias?",
    tissues: [
      { id: "liver", name: "Hepatic Parenchyma", t1: 800, t2: 45, t2s: 30, pd: 0.70, desc: "Normal Liver Tissue" },
      { id: "fatty_lesion", name: "Focal Hepatic Steatosis", t1: 450, t2: 65, t2s: 40, pd: 0.85, desc: "Fat Infiltrated Liver Zone" },
      { id: "spleen", name: "Splenic Tissue", t1: 1100, t2: 80, t2s: 55, pd: 0.85, desc: "Reference Parenchyma" },
      { id: "vessel", name: "Portal Vein / IVC", t1: 1500, t2: 150, t2s: 90, pd: 0.90, desc: "Vascular Luminal Signal" },
      { id: "subq_fat", name: "Retroperitoneal Fat", t1: 260, t2: 70, t2s: 50, pd: 0.90, desc: "Subcutaneous Pure Fat" }
    ],
    defaultParams: { fa: 12, te: 2.3, tr: 150, fov: 380, matrix: 256, sliceThick: 5.0, sliceCount: 24, sliceGap: 1.0, isInterleaved: false, flipAngleGRE: 12 }
  },
  msk_knee: {
    id: "msk_knee",
    recipeId: "msk_knee_tse",
    name: "MSK — Knee Meniscus & Cartilage Fissure",
    category: "MSK",
    seqType: "TSE",
    anatomy: "Knee Joint",
    scanPlane: "SAGITTAL",
    weightingName: "PD FatSat TSE",
    clinicalQuestion: "How does Intermediate-weighted TSE / PD with FatSat delineate thin collagen cartilage vs joint fluid?",
    tissues: [
      { id: "cartilage", name: "Articular Hyaline Cartilage", t1: 1200, t2: 40, t2s: 25, pd: 0.80, desc: "Superficial / Deep Collagen" },
      { id: "tear", name: "Meniscal Tear / Fissure", t1: 1500, t2: 90, t2s: 60, pd: 0.95, desc: "Hyperintense Fluid Infiltration" },
      { id: "meniscus", name: "Fibrocartilage Meniscus", t1: 900, t2: 15, t2s: 10, pd: 0.50, desc: "Ultra-Short T2 Dark Triangle" },
      { id: "synovial_fluid", name: "Joint Synovial Fluid", t1: 3800, t2: 1500, t2s: 400, pd: 1.00, desc: "Bright Effusion Signal" },
      { id: "bone_marrow", name: "Subchondral Bone Marrow", t1: 300, t2: 60, t2s: 40, pd: 0.85, desc: "Fatty Marrow Signal" }
    ],
    defaultParams: { fa: 140, te: 45, tr: 2500, fov: 160, matrix: 288, sliceThick: 3.0, sliceCount: 18, sliceGap: 0.5, isInterleaved: true, flipAngleGRE: 90 }
  },
  angio_tof: {
    id: "angio_tof",
    recipeId: "angio_tof_gre",
    name: "Angiography — 3D TOF Intracranial MRA",
    category: "Vascular",
    seqType: "GRE",
    anatomy: "Circle of Willis",
    scanPlane: "AXIAL",
    weightingName: "3D TOF Flash",
    clinicalQuestion: "How does 3D Flash/GRE with short TR/TE saturate static brain tissue while fresh inflow blood remains bright?",
    tissues: [
      { id: "inflow_artery", name: "Inflow Arterial Blood (ICA/MCA)", t1: 1600, t2: 180, t2s: 120, pd: 1.00, desc: "Fresh Unsaturated Inflow (Bright)" },
      { id: "aneurysm", name: "Aneurysmal Sac Inflow", t1: 1600, t2: 160, t2s: 110, pd: 1.00, desc: "Turbulent Inflow Focus" },
      { id: "static_brain", name: "Saturated Brain Parenchyma", t1: 1000, t2: 80, t2s: 50, pd: 0.70, desc: "Repeated RF Saturated (Suppressed)" },
      { id: "skull_base_fat", name: "Skull Base Fat", t1: 250, t2: 60, t2s: 40, pd: 0.80, desc: "Short T1 Background" }
    ],
    defaultParams: { fa: 20, te: 3.5, tr: 25, fov: 200, matrix: 320, sliceThick: 1.0, sliceCount: 60, sliceGap: 0.0, isInterleaved: false, flipAngleGRE: 20 }
  }
};
