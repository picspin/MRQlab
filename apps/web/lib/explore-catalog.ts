import { CLINICAL_SCENARIOS } from "./scenarios";

export type ExploreDifficulty = "Fundamental" | "Intermediate" | "Advanced";

export interface ExploreCase {
  id: string;
  title: string;
  anatomy: string;
  clinicalQuestion: string;
  keyPhysics: string;
  sequence: string;
  parameters: { fa: number; te: number; tr: number };
  difficulty: ExploreDifficulty;
  category: string;
  /** Canonical backend recipe id, or null when the card is not executable in v0.1. */
  recipeId: string | null;
  executable: boolean;
}

/**
 * Single Explore catalog. recipeId is the backend `_CLINICAL_RECIPES` key.
 * FLAIR / MOLLI / MESE stay visible but are not launchable — no invented engines.
 */
export const EXPLORE_CASES: ExploreCase[] = [
  {
    id: "cest-apt", title: "Amide CEST Z-spectrum", anatomy: "Single voxel / water reference",
    clinicalQuestion: "How does amide exchange create asymmetry in a backend-computed Z-spectrum?",
    keyPhysics: "Two-liquid-pool CW Bloch–McConnell saturation transfer",
    sequence: "EPG-X CEST offset sweep", parameters: { fa: 0, te: 0, tr: 2000 },
    difficulty: "Advanced", category: "Spectroscopy & Exchange",
    recipeId: "cest_amide_z_spectrum", executable: true,
  },
  {
    id: "mrs-1h", title: "¹H MR Spectroscopy", anatomy: "Spectral observation",
    clinicalQuestion: "Density-matrix engine unavailable", keyPhysics: "Not in v0.1",
    sequence: "Unavailable", parameters: { fa: 0, te: 0, tr: 0 }, difficulty: "Advanced",
    category: "Spectroscopy & Exchange", recipeId: null, executable: false,
  },
  {
    id: "x-nuclei", title: "X-nuclei Spectroscopy", anatomy: "Non-proton nuclei",
    clinicalQuestion: "X-nuclei engine unavailable", keyPhysics: "Not in v0.1",
    sequence: "Unavailable", parameters: { fa: 0, te: 0, tr: 0 }, difficulty: "Advanced",
    category: "Spectroscopy & Exchange", recipeId: null, executable: false,
  },
  {
    id: "ms-lesion-t2",
    title: "Multiple Sclerosis (MS) Plaque Contrast",
    anatomy: "Brain / White Matter",
    clinicalQuestion:
      "Why do demyelinating MS plaques appear hyperintense on T2 TSE while minimizing CSF partial volume artifacts?",
    keyPhysics:
      "T2 transverse relaxation differentiation + EPG stimulated echo preservation in TSE echo train",
    sequence: "Brain T2 Turbo Spin Echo (TSE)",
    parameters: { fa: 150, te: 100, tr: 3000 },
    difficulty: "Fundamental",
    category: "Brain & Neuro",
    recipeId: "brain_t2_tse",
    executable: true,
  },
  {
    id: "brain-flair",
    title: "FLAIR Free-Water Attenuation",
    anatomy: "Brain / Ventricles",
    clinicalQuestion: "How does Inversion Recovery null CSF signal to reveal periventricular lesions?",
    keyPhysics: "180° Inversion Recovery null-crossing timing $TI = T1 \\\\ln(2)$",
    sequence: "T2 Fluid Attenuated Inversion Recovery",
    parameters: { fa: 180, te: 120, tr: 8000 },
    difficulty: "Intermediate",
    category: "Brain & Neuro",
    recipeId: null,
    executable: false,
  },
  {
    id: "dark-blood-tse",
    title: "Dark Blood Vessel Wall Separation",
    anatomy: "Heart / Carotid Artery",
    clinicalQuestion:
      "How to completely suppress flowing luminal blood signal while preserving high SNR for carotid plaque wall?",
    keyPhysics: "Double Inversion Recovery (DIR) flow dephasing + slice selective re-inversion",
    sequence: "Dark Blood Turbo Spin Echo (Uses: TSE)",
    parameters: { fa: 140, te: 60, tr: 1200 },
    difficulty: "Advanced",
    category: "Cardiovascular",
    recipeId: "dark_blood_vessel_wall_tse",
    executable: true,
  },
  {
    id: "myocardial-t1-map",
    title: "Myocardial Fibrosis MOLLI T1 Mapping",
    anatomy: "Myocardium",
    clinicalQuestion: "How to quantify diffuse interstitial fibrosis via pixel-wise T1 relaxation fitting?",
    keyPhysics: "Look-Locker readout modification with modified EPG steady-state correction",
    sequence: "Modified Look-Locker Inversion (MOLLI)",
    parameters: { fa: 35, te: 1.5, tr: 3.0 },
    difficulty: "Advanced",
    category: "Cardiovascular",
    recipeId: null,
    executable: false,
  },
  {
    id: "dixon-fat-water",
    title: "Dixon Two-Point Water-Fat Separation",
    anatomy: "Abdomen / Liver",
    clinicalQuestion: "How does chemical shift phase cycling separate fat from water parenchymal signals?",
    keyPhysics: "3.5 ppm chemical shift $\\\\Delta f$ phase modulation between in-phase and out-of-phase echoes",
    sequence: "Dual-Echo Fast Gradient Echo (GRE)",
    parameters: { fa: 12, te: 2.3, tr: 150 },
    difficulty: "Intermediate",
    category: "Body & Musculoskeletal",
    recipeId: "abdomen_dixon_gre",
    executable: true,
  },
  {
    id: "knee-cartilage-t2",
    title: "Knee Articular Cartilage T2 Mapping",
    anatomy: "Musculoskeletal / Knee",
    clinicalQuestion: "How does collagen matrix degradation correlate with multi-echo T2 prolongation?",
    keyPhysics: "Multi-echo Spin Echo CPMG decay curve exponential non-linear regression",
    sequence: "Multi-Echo Spin Echo (MESE)",
    parameters: { fa: 180, te: 80, tr: 2000 },
    difficulty: "Fundamental",
    category: "Body & Musculoskeletal",
    recipeId: null,
    executable: false,
  },
];

/** recipe_id → workbench CLINICAL_SCENARIOS key. cardiac_cine_gre has no Explore/workbench card. */
export const RECIPE_TO_SCENARIO: Record<string, string> = Object.fromEntries(
  Object.entries(CLINICAL_SCENARIOS).map(([key, spec]) => [spec.recipeId, key])
);

export function scenarioKeyForRecipe(recipeId: string | null | undefined): string {
  if (recipeId === "cest_amide_z_spectrum") return "cest_amide";
  if (recipeId && RECIPE_TO_SCENARIO[recipeId]) return RECIPE_TO_SCENARIO[recipeId];
  return "ms_brain";
}

export function exploreCasesByCategory(): Record<string, ExploreCase[]> {
  return EXPLORE_CASES.reduce<Record<string, ExploreCase[]>>((acc, item) => {
    (acc[item.category] ||= []).push(item);
    return acc;
  }, {});
}
