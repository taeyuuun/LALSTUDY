"""LALSTUDY Method Taxonomy V2.

Standalone on purpose:
Method Explorer imports this module directly so an older cached/deployed
`method_wiki.py` cannot cause KeyError for new facet names.
"""

from __future__ import annotations

from typing import Dict, List


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
    "core_principle": {
        "label_ko": "핵심 원리",
        "label_en": "Core principle",
        "values": {
            "cytometry": ("Cytometry", "Cytometry"),
            "amplification": ("핵산 증폭", "Nucleic-acid amplification"),
            "sequencing": ("Sequencing", "Sequencing"),
            "hybridization": ("Hybridization", "Hybridization"),
            "electrophoretic_separation": ("전기영동 분리", "Electrophoretic separation"),
            "affinity_binding": ("Affinity binding", "Affinity binding"),
            "immunoprecipitation": ("Immunoprecipitation", "Immunoprecipitation"),
            "microscopy": ("Microscopy", "Microscopy"),
            "histology": ("Histology", "Histology"),
            "reporter_assay": ("Reporter assay", "Reporter assay"),
            "genome_editing": ("Genome editing", "Genome editing"),
            "cell_based_assay": ("Cell-based assay", "Cell-based assay"),
        },
    },
    "detection": {
        "label_ko": "검출 방식",
        "label_en": "Detection",
        "values": {
            "light_scatter": ("Light scatter", "Light scatter"),
            "fluorescence": ("형광", "Fluorescence"),
            "chemiluminescence": ("Chemiluminescence", "Chemiluminescence"),
            "colorimetric": ("Colorimetric", "Colorimetric"),
            "absorbance": ("Absorbance", "Absorbance"),
            "sequencing_readout": ("Sequence readout", "Sequence readout"),
            "electrical": ("전기적 신호", "Electrical signal"),
            "imaging": ("Image readout", "Image readout"),
        },
    },
    "labeling": {
        "label_ko": "표지 방식",
        "label_en": "Labeling",
        "values": {
            "label_free": ("Label-free", "Label-free"),
            "antibody": ("항체", "Antibody"),
            "fluorescent_dye": ("형광 dye", "Fluorescent dye"),
            "fluorescent_protein": ("형광 단백질", "Fluorescent protein"),
            "nucleic_acid_probe": ("핵산 probe", "Nucleic-acid probe"),
            "enzyme_conjugate": ("효소 conjugate", "Enzyme conjugate"),
            "reporter_construct": ("Reporter construct", "Reporter construct"),
        },
    },
    "output": {
        "label_ko": "결과",
        "label_en": "Output",
        "values": {
            "abundance": ("양·발현량", "Abundance / expression"),
            "localization": ("세포·조직 내 위치", "Localization"),
            "population_frequency": ("세포 집단·빈도", "Population / frequency"),
            "single_cell_signal": ("Single-cell signal", "Single-cell signal"),
            "expression_matrix": ("발현 matrix", "Expression matrix"),
            "sequence_accessibility": ("Sequence·accessibility", "Sequence / accessibility"),
            "interaction": ("결합·상호작용", "Interaction / binding"),
            "morphology": ("형태·조직 구조", "Morphology / tissue structure"),
            "viability_function": ("생존·기능 readout", "Viability / functional readout"),
        },
    },
}


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
    text = _haystack(profile)

    facets = {
        "purpose": set(),
        "material": set(),
        "core_principle": set(),
        "detection": set(),
        "labeling": set(),
        "output": set(),
    }

    def has(*terms):
        return any(term.casefold() in text for term in terms)

    # Flow cytometry / FACS
    if has("flow cytometry", "facs", "flow cytometric"):
        facets["purpose"].add("cell_identity")
        facets["material"].add("cell")
        facets["core_principle"].add("cytometry")
        facets["detection"].update({"light_scatter", "fluorescence"})
        facets["labeling"].update({
            "label_free",
            "antibody",
            "fluorescent_dye",
            "fluorescent_protein",
        })
        facets["output"].update({
            "population_frequency",
            "single_cell_signal",
        })

    # Mass cytometry / CyTOF
    if has("mass cytometry", "cytof"):
        facets["purpose"].add("cell_identity")
        facets["material"].add("cell")
        facets["core_principle"].add("cytometry")
        facets["labeling"].add("antibody")
        facets["output"].update({
            "population_frequency",
            "single_cell_signal",
        })

    # qPCR
    if has("qpcr", "quantitative pcr", "real-time pcr"):
        facets["purpose"].add("detect_quantify")
        facets["material"].add("dna")
        if has("rt-qpcr", "reverse transcription", "gene expression"):
            facets["material"].add("rna")
        facets["core_principle"].add("amplification")
        facets["detection"].add("fluorescence")
        facets["labeling"].update({"fluorescent_dye", "nucleic_acid_probe"})
        facets["output"].add("abundance")
    elif has("pcr"):
        facets["purpose"].add("detect_quantify")
        facets["material"].add("dna")
        facets["core_principle"].add("amplification")
        facets["output"].add("abundance")

    # RNA sequencing
    if has("rna sequencing", "rna-seq", "bulk rna", "scrna", "single-cell rna"):
        facets["purpose"].add("profile_expression")
        facets["material"].add("rna")
        if has("scrna", "single-cell"):
            facets["material"].add("cell")
        facets["core_principle"].add("sequencing")
        facets["detection"].add("sequencing_readout")
        facets["output"].add("expression_matrix")

    # ATAC-seq
    if has("atac-seq", "atac seq", "atac"):
        facets["purpose"].add("chromatin_regulation")
        facets["material"].update({"dna", "chromatin"})
        facets["core_principle"].add("sequencing")
        facets["detection"].add("sequencing_readout")
        facets["output"].add("sequence_accessibility")

    # ChIP-seq
    if has("chip-seq", "chip seq", "chromatin immunoprecipitation"):
        facets["purpose"].add("chromatin_regulation")
        facets["material"].update({"dna", "chromatin", "protein"})
        facets["core_principle"].update({"immunoprecipitation", "sequencing"})
        facets["labeling"].add("antibody")
        facets["detection"].add("sequencing_readout")
        facets["output"].add("sequence_accessibility")

    # Western blot
    if has("western blot", "western blotting"):
        facets["purpose"].add("detect_quantify")
        facets["material"].add("protein")
        facets["core_principle"].add("electrophoretic_separation")
        facets["labeling"].update({"antibody", "enzyme_conjugate"})
        facets["detection"].update({"chemiluminescence", "fluorescence"})
        facets["output"].add("abundance")

    # ELISA
    if has("elisa"):
        facets["purpose"].add("detect_quantify")
        facets["material"].update({"protein", "secreted_factor"})
        facets["core_principle"].add("affinity_binding")
        facets["labeling"].update({"antibody", "enzyme_conjugate"})
        facets["detection"].update({"colorimetric", "absorbance"})
        facets["output"].add("abundance")

    # Co-IP / IP
    if has("co-ip", "coimmunoprecip", "co-immunoprecip", "immunoprecipitation"):
        facets["purpose"].add("interaction_binding")
        facets["material"].add("protein")
        facets["core_principle"].add("immunoprecipitation")
        facets["labeling"].add("antibody")
        facets["output"].add("interaction")

    # IF / confocal
    if has("immunofluorescence", "confocal", "fluorescence microscopy"):
        facets["purpose"].add("visualize_localize")
        facets["material"].update({"cell", "protein"})
        facets["core_principle"].add("microscopy")
        facets["detection"].update({"fluorescence", "imaging"})
        facets["labeling"].update({
            "antibody",
            "fluorescent_dye",
            "fluorescent_protein",
        })
        facets["output"].add("localization")

    # IHC / histology
    if has("ihc", "immunohistochemistry", "histology"):
        facets["purpose"].add("morphology_tissue")
        facets["material"].update({"tissue", "protein"})
        facets["core_principle"].add("histology")
        facets["labeling"].add("antibody")
        facets["detection"].update({"colorimetric", "imaging"})
        facets["output"].update({"localization", "morphology"})

    # CRISPR
    if has("crispr"):
        facets["purpose"].add("perturb_edit")
        facets["material"].add("dna")
        facets["core_principle"].add("genome_editing")
        facets["output"].add("viability_function")

    # Luciferase / reporter
    if has("luciferase", "reporter assay", "reporter"):
        facets["purpose"].add("functional_response")
        facets["material"].add("reporter")
        facets["core_principle"].add("reporter_assay")
        facets["labeling"].add("reporter_construct")
        facets["detection"].add("chemiluminescence")
        facets["output"].add("viability_function")

    # Cell viability
    if has("cell viability", "cytotoxicity", "viability assay"):
        facets["purpose"].add("proliferation_viability")
        facets["material"].add("cell")
        facets["core_principle"].add("cell_based_assay")
        facets["detection"].update({"colorimetric", "fluorescence", "absorbance"})
        facets["output"].add("viability_function")

    # NanoString
    if has("nanostring"):
        facets["purpose"].add("profile_expression")
        facets["material"].add("rna")
        facets["core_principle"].add("hybridization")
        facets["labeling"].add("nucleic_acid_probe")
        facets["output"].add("expression_matrix")

    if not facets["material"]:
        if has("rna"):
            facets["material"].add("rna")
        elif has("dna"):
            facets["material"].add("dna")
        elif has("protein"):
            facets["material"].add("protein")
        elif has("cell"):
            facets["material"].add("cell")

    if not facets["purpose"]:
        facets["purpose"].add("detect_quantify")

    return {
        **{
            key: sorted(values)
            for key, values in facets.items()
        },
        "_taxonomy_version": 2,
    }


def facet_label(facet: str, key: str, lang: str = "ko") -> str:
    spec = FACET_DEFINITIONS.get(facet, {})
    value = spec.get("values", {}).get(key)

    if not value:
        return key

    return value[0] if lang == "ko" else value[1]


def facet_title(facet: str, lang: str = "ko") -> str:
    spec = FACET_DEFINITIONS.get(facet, {})

    return spec.get(
        "label_ko" if lang == "ko" else "label_en",
        facet,
    )


def merged_facets(profile: Dict, db_entry: Dict | None = None) -> Dict:
    local = infer_facets(profile)

    if not db_entry:
        return local

    db_facets = (db_entry.get("facets", {}) or {})

    # Never trust old v1 single-principle facets.
    if db_facets.get("_taxonomy_version") != 2:
        return local

    output = {"_taxonomy_version": 2}

    for facet in (
        "purpose",
        "material",
        "core_principle",
        "detection",
        "labeling",
        "output",
    ):
        values = db_facets.get(facet)

        output[facet] = (
            values
            if isinstance(values, list) and values
            else local.get(facet, [])
        )

    return output
