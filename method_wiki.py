import re
import unicodedata
from typing import Dict, List, Optional, Tuple

try:
    from supabase import create_client
except Exception:
    create_client = None


FACET_DEFINITIONS = {
    "purpose": {
        "label_ko": "목적",
        "label_en": "Purpose",
        "values": {
            "detect_quantify": ("검출·정량", "Detect / quantify"),
            "visualize_localize": ("시각화·위치 확인", "Visualize / localize"),
            "profile_expression": ("발현·분자 프로파일링", "Expression / molecular profiling"),
            "cell_identity": ("세포 분류·표현형", "Cell identity / phenotype"),
            "proliferation_viability": ("세포 증식·생존", "Proliferation / viability"),
            "interaction_binding": ("분자 상호작용", "Molecular interaction"),
            "perturb_edit": ("유전자·기능 조작", "Perturb / edit"),
            "chromatin_regulation": ("염색질·조절 분석", "Chromatin / regulation"),
            "functional_response": ("기능·반응 측정", "Functional response"),
            "morphology_tissue": ("조직·형태 분석", "Morphology / tissue"),
        },
    },
    "material": {
        "label_ko": "대상",
        "label_en": "Material",
        "values": {
            "dna": ("DNA", "DNA"),
            "rna": ("RNA", "RNA"),
            "protein": ("단백질", "Protein"),
            "cell": ("세포", "Cell"),
            "tissue": ("조직", "Tissue"),
            "chromatin": ("Chromatin", "Chromatin"),
            "secreted_factor": ("분비 단백질·cytokine", "Secreted factor / cytokine"),
            "reporter": ("Reporter", "Reporter"),
        },
    },
    "principle": {
        "label_ko": "원리",
        "label_en": "Principle",
        "values": {
            "antibody": ("항체 기반", "Antibody-based"),
            "fluorescence": ("형광 기반", "Fluorescence"),
            "microscopy": ("Microscopy", "Microscopy"),
            "cytometry": ("Cytometry", "Cytometry"),
            "amplification": ("핵산 증폭", "Nucleic-acid amplification"),
            "sequencing": ("Sequencing", "Sequencing"),
            "hybridization": ("Hybridization", "Hybridization"),
            "electrophoresis": ("Electrophoresis", "Electrophoresis"),
            "immunoprecipitation": ("Immunoprecipitation", "Immunoprecipitation"),
            "reporter_assay": ("Reporter assay", "Reporter assay"),
            "genome_editing": ("Genome editing", "Genome editing"),
            "cell_based_assay": ("Cell-based assay", "Cell-based assay"),
            "histology": ("Histology", "Histology"),
        },
    },
    "output": {
        "label_ko": "결과",
        "label_en": "Output",
        "values": {
            "abundance": ("양·발현량", "Abundance / expression"),
            "localization": ("세포·조직 내 위치", "Localization"),
            "population_frequency": ("세포 집단·빈도", "Population / frequency"),
            "expression_matrix": ("발현 matrix", "Expression matrix"),
            "sequence_accessibility": ("Sequence·accessibility", "Sequence / accessibility"),
            "interaction": ("결합·상호작용", "Interaction / binding"),
            "morphology": ("형태·조직 구조", "Morphology / tissue structure"),
            "viability_function": ("생존·기능 readout", "Viability / functional readout"),
        },
    },
}


def normalize_method_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.casefold().strip()
    value = re.sub(r"[\s_\-/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _haystack(profile: Dict) -> str:
    bits = [
        profile.get("name", ""),
        profile.get("category", ""),
        profile.get("parent_method", ""),
        " ".join(profile.get("aliases", []) or []),
        " ".join(profile.get("submethods", []) or []),
    ]
    return " ".join(str(v) for v in bits).casefold()


def infer_facets(profile: Dict) -> Dict[str, List[str]]:
    """
    Deterministic starter taxonomy so category browsing works immediately,
    even before the method encyclopedia table has been populated.

    The DB may later store curated facets for a method; those take precedence.
    """
    text = _haystack(profile)
    name = str(profile.get("name", "")).casefold()

    facets = {
        "purpose": set(),
        "material": set(),
        "principle": set(),
        "output": set(),
    }

    def has(*terms):
        return any(term.casefold() in text for term in terms)

    # Material
    if has("rna", "transcript", "nanostring"):
        facets["material"].add("rna")
    if has("dna", "pcr", "crispr", "atac", "chip", "chromatin"):
        facets["material"].add("dna")
    if has("protein", "western", "elisa", "co-ip", "immunoprecip", "ihc", "if", "flow", "facs", "cytometry"):
        facets["material"].add("protein")
    if has("cell", "flow", "facs", "cytometry", "viability", "cytotoxic", "culture", "single-cell", "scrna"):
        facets["material"].add("cell")
    if has("tissue", "histology", "ihc", "immunohist"):
        facets["material"].add("tissue")
    if has("atac", "chip", "chromatin"):
        facets["material"].add("chromatin")
    if has("elisa", "cytokine", "secreted"):
        facets["material"].add("secreted_factor")
    if has("luciferase", "reporter"):
        facets["material"].add("reporter")

    # Principle
    if has("western", "elisa", "co-ip", "immunoprecip", "ihc", "immunofluorescence", "flow", "facs", "cytometry"):
        facets["principle"].add("antibody")
    if has("fluorescence", "confocal", "if", "flow", "facs", "cytometry"):
        facets["principle"].add("fluorescence")
    if has("confocal", "microscopy", "imaging", "immunofluorescence", "histology"):
        facets["principle"].add("microscopy")
    if has("flow", "facs", "cytometry"):
        facets["principle"].add("cytometry")
    if has("pcr", "qpcr"):
        facets["principle"].add("amplification")
    if has("sequencing", "rna-seq", "scrna", "bulk rna", "atac-seq", "chip-seq"):
        facets["principle"].add("sequencing")
    if has("nanostring", "hybridization"):
        facets["principle"].add("hybridization")
    if has("western", "gel electrophoresis", "electrophoresis"):
        facets["principle"].add("electrophoresis")
    if has("co-ip", "immunoprecip"):
        facets["principle"].add("immunoprecipitation")
    if has("luciferase", "reporter"):
        facets["principle"].add("reporter_assay")
    if has("crispr"):
        facets["principle"].add("genome_editing")
    if has("viability", "cytotoxic", "culture"):
        facets["principle"].add("cell_based_assay")
    if has("histology", "ihc"):
        facets["principle"].add("histology")

    # Purpose / Output
    if has("pcr", "qpcr", "western", "elisa", "nanostring"):
        facets["purpose"].add("detect_quantify")
        facets["output"].add("abundance")
    if has("confocal", "immunofluorescence", "ihc", "imaging"):
        facets["purpose"].add("visualize_localize")
        facets["output"].add("localization")
    if has("rna-seq", "sequencing", "nanostring", "transcript"):
        facets["purpose"].add("profile_expression")
        facets["output"].add("expression_matrix")
    if has("flow", "facs", "cytometry"):
        facets["purpose"].add("cell_identity")
        facets["output"].add("population_frequency")
    if has("viability", "prolifer", "cell growth", "culture"):
        facets["purpose"].add("proliferation_viability")
        facets["output"].add("viability_function")
    if has("co-ip", "immunoprecip", "pull-down", "binding"):
        facets["purpose"].add("interaction_binding")
        facets["output"].add("interaction")
    if has("crispr", "knockout", "knockdown"):
        facets["purpose"].add("perturb_edit")
        facets["output"].add("viability_function")
    if has("atac", "chip", "chromatin"):
        facets["purpose"].add("chromatin_regulation")
        facets["output"].add("sequence_accessibility")
    if has("luciferase", "cytotoxic", "functional assay"):
        facets["purpose"].add("functional_response")
        facets["output"].add("viability_function")
    if has("histology", "morphology"):
        facets["purpose"].add("morphology_tissue")
        facets["output"].add("morphology")

    # Generic fallback based on the original ontology category.
    if not facets["purpose"]:
        facets["purpose"].add("detect_quantify")

    return {
        key: sorted(values)
        for key, values in facets.items()
    }


def facet_label(facet: str, key: str, lang: str = "ko") -> str:
    spec = FACET_DEFINITIONS.get(facet, {})
    value = spec.get("values", {}).get(key)
    if not value:
        return key
    return value[0] if lang == "ko" else value[1]


def facet_title(facet: str, lang: str = "ko") -> str:
    spec = FACET_DEFINITIONS.get(facet, {})
    return spec.get("label_ko" if lang == "ko" else "label_en", facet)


class MethodWikiStore:
    def __init__(self, url: str, secret_key: str):
        if create_client is None:
            raise RuntimeError("The `supabase` Python package is not installed.")
        if not url or not secret_key:
            raise ValueError("Supabase URL/secret key is missing.")
        self.client = create_client(url, secret_key)

    def ping(self) -> bool:
        response = (
            self.client
            .table("method_encyclopedia")
            .select("canonical_name")
            .limit(1)
            .execute()
        )
        return response is not None

    def get(self, canonical_name: str, increment_hit: bool = True) -> Optional[Dict]:
        response = (
            self.client
            .table("method_encyclopedia")
            .select("*")
            .eq("normalized_name", normalize_method_name(canonical_name))
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None

        row = rows[0]
        if increment_hit:
            try:
                self.client.rpc(
                    "method_encyclopedia_increment_hit",
                    {"p_normalized_name": row["normalized_name"]},
                ).execute()
            except Exception:
                pass
        return row

    def list_entries(self) -> List[Dict]:
        response = (
            self.client
            .table("method_encyclopedia")
            .select(
                "canonical_name,normalized_name,facets,quality_status,updated_at"
            )
            .execute()
        )
        return response.data or []

    def upsert(self, payload: Dict):
        clean = dict(payload)
        clean["normalized_name"] = normalize_method_name(
            clean.get("canonical_name", "")
        )
        return (
            self.client
            .table("method_encyclopedia")
            .upsert(clean, on_conflict="normalized_name")
            .execute()
        )
