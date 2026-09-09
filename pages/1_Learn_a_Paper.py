
import io, json, re, html
from collections import Counter
from pathlib import Path

import streamlit as st
from pypdf import PdfReader

APP_VERSION = "v0.1.0-beta"
METHOD_PROFILE_FILE = Path("method_profiles.json")

st.set_page_config(page_title="LALSTUDY · Learn a Paper", page_icon="📄", layout="wide")

def clean_text(text):
    text = html.unescape(text or "")
    text = text.replace("\x00", " ")
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()

def sentence_split(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9αβγΔ])", clean_text(text)) if len(s.strip()) >= 25]

@st.cache_data
def load_profiles():
    if not METHOD_PROFILE_FILE.exists():
        return []
    return json.loads(METHOD_PROFILE_FILE.read_text(encoding="utf-8"))

profiles = load_profiles()
profile_by_name = {p["name"]: p for p in profiles}
method_terms = []
for p in profiles:
    for term in [p.get("name","")] + p.get("aliases", []):
        if term:
            method_terms.append((term, p["name"]))

def detect_methods(text):
    out = Counter()
    for term, canonical in method_terms:
        pat = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
        n = len(re.findall(pat, text, flags=re.I))
        if n:
            out[canonical] += n
    return out

CONCEPTS = {
    "T cell": {
        "aliases":["T cells","T-cell","T lymphocyte","T lymphocytes"],
        "level":1,"category":"Immunology",
        "short":"적응면역을 담당하는 림프구로, 항원을 인식한 뒤 다른 면역세포를 조절하거나 표적세포를 직접 제거합니다.",
        "detail":"TCR을 통해 peptide-MHC를 인식합니다. CD4 T cell은 주로 면역반응을 조절하고 CD8 T cell은 감염세포·종양세포 제거에 중요합니다.",
        "depends":["Adaptive immunity","MHC"]
    },
    "CD4 T cell": {
        "aliases":["CD4+ T cell","CD4 T cells","CD4+ T cells"],
        "level":2,"category":"Immunology",
        "short":"MHC class II에 제시된 항원을 인식하고 면역반응을 조절하는 T 세포 계열입니다.",
        "detail":"활성화 후 Th1, Th2, Th17, Tfh, Treg 등으로 분화하며 cytokine 환경과 전사인자에 따라 기능이 달라집니다.",
        "depends":["T cell","MHC"]
    },
    "CD8 T cell": {
        "aliases":["CD8+ T cell","CD8 T cells","CD8+ T cells"],
        "level":2,"category":"Immunology",
        "short":"MHC class I에 제시된 항원을 인식하고 표적세포를 사멸시키는 cytotoxic T cell 계열입니다.",
        "detail":"perforin/granzyme, Fas-FasL 등의 기전을 통해 표적세포를 제거하며 종양면역과 항바이러스 면역에서 중요합니다.",
        "depends":["T cell","MHC"]
    },
    "Treg": {
        "aliases":["regulatory T cell","regulatory T cells","Tregs","Treg cells"],
        "level":3,"category":"Immunology",
        "short":"과도한 면역반응과 자가면역을 억제하는 조절 T 세포입니다.",
        "detail":"대표적으로 CD4, CD25, FOXP3를 발현하며 IL-2 신호에 크게 의존합니다. CTLA-4, IL-10, TGF-β 등으로 억제 기능을 수행합니다.",
        "depends":["CD4 T cell","FOXP3","IL-2"]
    },
    "FOXP3": {
        "aliases":["Foxp3"],
        "level":3,"category":"Transcription factor",
        "short":"Treg의 정체성과 억제 기능 유지에 핵심적인 전사인자입니다.",
        "detail":"FOXP3 발현과 안정성은 Treg 기능과 밀접하며 IL-2–STAT5 signaling과 epigenetic state의 영향을 받습니다.",
        "depends":["Treg","IL-2","STAT5"]
    },
    "IL-2": {
        "aliases":["interleukin-2","interleukin 2"],
        "level":2,"category":"Cytokine",
        "short":"T 세포 증식과 생존, 특히 Treg 유지에 중요한 cytokine입니다.",
        "detail":"IL-2 receptor가 활성화되면 JAK1/JAK3–STAT5 축이 활성화됩니다. Treg는 CD25를 높게 발현해 낮은 IL-2에도 민감합니다.",
        "depends":["Cytokine","JAK-STAT signaling"]
    },
    "STAT5": {
        "aliases":["STAT5A","STAT5B","pSTAT5"],
        "level":3,"category":"Signal transduction",
        "short":"여러 cytokine receptor 하위에서 활성화되는 전사조절 단백질입니다.",
        "detail":"JAK에 의해 인산화된 STAT5는 dimer를 형성해 핵으로 이동하고 표적 유전자의 전사를 조절합니다.",
        "depends":["JAK-STAT signaling","Phosphorylation"]
    },
    "JAK-STAT signaling": {
        "aliases":["JAK/STAT","JAK STAT","JAK-STAT"],
        "level":2,"category":"Signal transduction",
        "short":"cytokine receptor 신호를 핵의 유전자 발현 변화로 전달하는 대표 signaling pathway입니다.",
        "detail":"ligand 결합 → JAK 활성화 → STAT 인산화 → dimerization → 핵 이동 → transcription 변화 순서로 이해하면 됩니다.",
        "depends":["Phosphorylation","Cytokine"]
    },
    "MHC": {
        "aliases":["major histocompatibility complex","HLA"],
        "level":1,"category":"Immunology",
        "short":"세포가 peptide antigen을 T 세포에 제시하는 분자 시스템입니다.",
        "detail":"MHC I은 CD8 T cell, MHC II는 주로 CD4 T cell과 연결됩니다.",
        "depends":["Antigen presentation"]
    },
    "Macrophage": {
        "aliases":["macrophages"],
        "level":1,"category":"Innate immunity",
        "short":"식균작용, cytokine 분비, 조직 항상성, 항원제시를 수행하는 선천면역 세포입니다.",
        "detail":"조직과 자극에 따라 매우 다양한 상태를 가지므로 실제 논문에서는 M1/M2 이분법만으로 설명하기 어려운 경우가 많습니다.",
        "depends":["Innate immunity"]
    },
    "Dendritic cell": {
        "aliases":["dendritic cells","DCs"],
        "level":2,"category":"Immunology",
        "short":"naive T cell을 활성화하는 능력이 뛰어난 전문 항원제시세포입니다.",
        "detail":"항원을 포획하고 lymph node로 이동한 뒤 peptide-MHC와 costimulation을 제공해 T-cell priming을 유도합니다.",
        "depends":["Antigen presentation","T cell"]
    },
    "Cytokine": {
        "aliases":["cytokines"],
        "level":1,"category":"Cell signaling",
        "short":"세포 간 신호를 전달하는 작은 분비성 단백질들의 총칭입니다.",
        "detail":"IL, IFN, TNF 계열 등이 있으며 농도, receptor 발현, 시간적 맥락에 따라 효과가 달라집니다.",
        "depends":[]
    },
    "Interferon": {
        "aliases":["interferon","IFN","IFN-γ","IFNγ","IFN-gamma"],
        "level":2,"category":"Cytokine",
        "short":"항바이러스 및 면역조절 반응을 유도하는 cytokine 계열입니다.",
        "detail":"Type I IFN과 Type II IFN은 receptor와 기능이 다르며 IFN-γ는 macrophage activation과 Th1 immunity에 중요합니다.",
        "depends":["Cytokine"]
    },
    "mTORC1": {
        "aliases":["mTOR complex 1"],
        "level":3,"category":"Cell signaling",
        "short":"영양상태와 성장신호를 감지해 단백질 합성·대사·성장을 조절하는 kinase complex입니다.",
        "detail":"amino acid, growth factor, energy state를 통합하며 면역세포 활성화와 분화에도 중요한 영향을 줍니다.",
        "depends":["Cell metabolism"]
    },
    "CRISPR": {
        "aliases":["CRISPR-Cas9","CRISPR Cas9","Cas9"],
        "level":2,"category":"Genetic manipulation",
        "short":"guide RNA를 이용해 특정 DNA 위치를 표적하는 유전자 편집 시스템입니다.",
        "detail":"knockout, knock-in, screening 등에 활용되며 특정 유전자 기능의 인과적 검증에 자주 사용됩니다.",
        "depends":["Gene editing"]
    },
    "Single-cell RNA sequencing": {
        "aliases":["scRNA-seq","single-cell RNA-seq","single cell RNA sequencing"],
        "level":3,"category":"Omics",
        "short":"개별 세포 수준에서 transcriptome을 측정해 세포군과 상태의 이질성을 분석합니다.",
        "detail":"세포별 barcode 후 QC, normalization, dimensionality reduction, clustering, marker identification 등을 수행합니다.",
        "depends":["RNA sequencing","UMAP"]
    },
    "RNA sequencing": {
        "aliases":["RNA-seq","RNA seq","transcriptome sequencing"],
        "level":2,"category":"Omics",
        "short":"RNA를 sequencing하여 유전자 발현량과 transcript 구성을 분석하는 기술입니다.",
        "detail":"read mapping/quantification 후 differential expression 등으로 조건 간 transcriptional 변화를 비교합니다.",
        "depends":["Gene expression"]
    },
    "UMAP": {
        "aliases":[],
        "level":3,"category":"Data analysis",
        "short":"고차원 데이터를 2D/3D로 시각화하는 dimensionality reduction 방법입니다.",
        "detail":"local structure를 보존하도록 배치하지만 UMAP에서 가까워 보인다는 것 자체가 생물학적 인과를 뜻하지는 않습니다.",
        "depends":["Dimensionality reduction"]
    },
    "Differential expression": {
        "aliases":["differentially expressed","DEGs"],
        "level":3,"category":"Bioinformatics",
        "short":"두 조건 사이에서 발현량이 통계적으로 달라진 유전자를 찾는 분석입니다.",
        "detail":"fold change와 통계적 유의성을 함께 고려하며 multiple testing correction이 중요합니다.",
        "depends":["RNA sequencing","Multiple testing"]
    },
    "Phosphorylation": {
        "aliases":["phosphorylated"],
        "level":1,"category":"Molecular biology",
        "short":"단백질에 phosphate group이 붙는 대표적인 post-translational modification입니다.",
        "detail":"kinase가 phosphate를 붙이고 phosphatase가 제거하며 signaling protein의 활성과 위치를 빠르게 조절합니다.",
        "depends":[]
    },
    "Gene expression": {
        "aliases":["transcriptional"],
        "level":1,"category":"Molecular biology",
        "short":"유전자 정보가 RNA 또는 단백질 수준의 기능적 산물로 나타나는 과정입니다.",
        "detail":"mRNA 증가가 반드시 protein 증가와 동일하지 않아 transcript와 protein을 별도로 측정하는 경우가 많습니다.",
        "depends":[]
    },
    "Adaptive immunity": {
        "aliases":["adaptive immune"],
        "level":1,"category":"Immunology",
        "short":"항원 특이성과 면역기억을 특징으로 하는 B/T 세포 중심의 면역반응입니다.",
        "detail":"antigen-specific receptor와 clonal expansion을 통해 정밀한 반응과 memory를 형성합니다.",
        "depends":[]
    },
    "Innate immunity": {
        "aliases":["innate immune"],
        "level":1,"category":"Immunology",
        "short":"빠르게 작동하며 pattern recognition을 중심으로 하는 선천적 방어 체계입니다.",
        "detail":"macrophage, neutrophil, dendritic cell, NK cell 등이 주요 구성 요소이며 adaptive immunity의 방향에도 영향을 줍니다.",
        "depends":[]
    },
    "Antigen presentation": {
        "aliases":["antigen-presenting","APC"],
        "level":1,"category":"Immunology",
        "short":"항원에서 유래한 peptide를 MHC에 올려 T 세포가 인식하도록 하는 과정입니다.",
        "detail":"dendritic cell, macrophage, B cell 등이 대표적인 전문 APC입니다.",
        "depends":["MHC"]
    }
}

def detect_concepts(text):
    out = []
    for name, info in CONCEPTS.items():
        n = 0
        for term in [name] + info.get("aliases", []):
            pat = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
            n += len(re.findall(pat, text, flags=re.I))
        if n:
            out.append({"name":name, "count":n, **info})
    out.sort(key=lambda x:(x["level"], -x["count"]))
    return out

@st.cache_data(show_spinner=False)
def extract_pdf(file_bytes):
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        pages.append({"page":i+1, "text":txt})
    return pages, "\n".join(p["text"] for p in pages)

SECTION_RE = re.compile(
    r"(?im)^\s*(abstract|summary|introduction|background|materials and methods|methods|experimental procedures|results|discussion and conclusions|discussion|conclusions?|references)\s*$"
)

def extract_sections(raw_text):
    matches = list(SECTION_RE.finditer(raw_text))
    sections = {}
    mapping = {
        "abstract":"abstract","summary":"abstract",
        "introduction":"introduction","background":"introduction",
        "materials and methods":"methods","methods":"methods","experimental procedures":"methods",
        "results":"results","discussion":"discussion","discussion and conclusions":"discussion",
        "conclusion":"conclusion","conclusions":"conclusion"
    }
    for i,m in enumerate(matches):
        head = m.group(1).lower()
        if head == "references":
            continue
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(raw_text)
        body = clean_text(raw_text[start:end])
        key = mapping.get(head)
        if key and body and (key not in sections or len(body) > len(sections[key])):
            sections[key] = body
    return sections

OBJECTIVE = ["we sought","we aimed","we investigate","we investigated","we examine","we examined","we test","we tested","here, we","in this study"]
CONCLUSION = ["we show","we demonstrate","we found","our results","these findings","we reveal","we identify","we report"]

def extract_glance(sections, full_text):
    source = sections.get("abstract") or full_text[:6000]
    sents = sentence_split(source)
    scored = []
    for i,s in enumerate(sents):
        low=s.lower()
        score=sum(4 for x in OBJECTIVE+CONCLUSION if x in low)
        if i==0: score += 2
        if i>=len(sents)-2: score += 2
        if 60 <= len(s) <= 350: score += 1
        scored.append((score,i,s))
    best=sorted(scored,key=lambda x:(-x[0],x[1]))[:5]
    return [x[2] for x in sorted(best,key=lambda x:x[1])]

def extract_why(sections):
    intro = sentence_split(sections.get("introduction",""))[-8:]
    abstract = sentence_split(sections.get("abstract",""))
    markers=["however","remains unclear","remains unknown","poorly understood","not known","unknown","lack","limited","gap","we sought","we aimed","here, we","in this study"]
    scored=[]
    for i,s in enumerate(intro+abstract):
        low=s.lower()
        score=sum(4 for x in markers if x in low)
        if score: scored.append((score,i,s))
    return [x[2] for x in sorted(scored,key=lambda x:(-x[0],x[1]))[:4]]

FIG_RE = re.compile(r"(?i)\b(?:Fig(?:ure)?\.?)\s*([1-9][0-9]*)\s*[\.:]?\s*")

def extract_figures(full_text):
    text=clean_text(full_text)
    matches=list(FIG_RE.finditer(text))
    by_num={}
    for i,m in enumerate(matches):
        num=m.group(1)
        start=m.start()
        end=matches[i+1].start() if i+1<len(matches) else min(len(text),start+1800)
        chunk=text[start:min(end,start+1800)].strip()
        if len(chunk)<120: continue
        score=0
        if re.search(r"\b[a-h][\),.:]\s",chunk,re.I): score+=1
        if any(x in chunk.lower() for x in ["representative","quantification","data are","scale bar","n ="]): score+=1
        rec={"figure":f"Fig. {num}","raw":chunk,"score":score}
        if num not in by_num or (score,len(chunk))>(by_num[num]["score"],len(by_num[num]["raw"])):
            by_num[num]=rec
    return [by_num[k] for k in sorted(by_num,key=lambda x:int(x))][:15]

METHOD_PURPOSES = {
    "Flow cytometry":"세포 집단의 marker 발현이나 population 비율을 단일세포 수준에서 측정",
    "FACS":"특정 marker 조합을 기준으로 세포를 분석하거나 분리",
    "Western blotting":"단백질 abundance 또는 phosphorylation 상태를 band로 확인",
    "ELISA":"분비된 cytokine·항체·단백질 농도를 정량",
    "qPCR":"특정 RNA/DNA target의 상대적 양을 정량",
    "PCR":"특정 DNA 서열을 증폭하거나 검출",
    "Single-cell RNA sequencing":"개별 세포 transcriptome을 측정해 세포군과 상태를 분해",
    "RNA sequencing":"조건 간 전사체 변화를 비교",
    "Bulk RNA sequencing":"샘플 전체의 평균 transcriptome 변화를 비교",
    "Confocal microscopy":"세포·조직 내 단백질 위치와 형태를 고해상도로 관찰",
    "Immunofluorescence":"항체 기반 형광표지로 특정 단백질의 위치와 발현을 관찰",
    "Immunohistochemistry":"조직 절편에서 특정 단백질의 위치와 분포를 관찰",
    "Mass cytometry":"다수 단백질 marker를 단일세포 수준에서 동시에 측정",
    "CRISPR":"특정 유전자 기능을 perturbation하여 인과관계를 검증",
    "ATAC-seq":"chromatin accessibility를 측정",
    "ChIP-seq":"특정 단백질과 결합한 genomic region을 분석",
    "Co-IP":"단백질 간 physical interaction을 검증",
    "Cell viability assay":"처리 후 세포 생존/대사 활성을 정량",
    "Luciferase assay":"promoter activity 또는 reporter signal을 정량",
    "Mass spectrometry":"단백질·대사체 등을 질량 기반으로 동정/정량",
    "Spatial transcriptomics":"조직 위치 정보를 유지한 채 gene expression을 측정",
}

def method_strategy(counts):
    out=[]
    for name,count in counts.most_common(12):
        p=profile_by_name.get(name,{})
        out.append({
            "name":name,"count":count,
            "purpose":METHOD_PURPOSES.get(name, f"{p.get('category','Experimental')} 범주의 실험/분석 기법"),
            "category":p.get("category",""),
            "parent":p.get("parent_method"),
            "paper_count":p.get("paper_count"),
            "figure_count":p.get("figure_count"),
        })
    return out

def learning_path(concepts, methods):
    items=[]
    for c in concepts:
        if c["level"]<=2:
            items.append({"kind":"Concept","name":c["name"],"reason":f"{c['category']} 기초 개념"})
        if len(items)>=4: break
    for c in concepts:
        if c["level"]>=3:
            items.append({"kind":"Concept","name":c["name"],"reason":"이 논문의 세부 mechanism/analysis 이해에 도움"})
        if len(items)>=7: break
    for m,n in methods.most_common(3):
        items.append({"kind":"Method","name":m,"reason":f"논문에서 {n}회 감지된 핵심 실험기법"})
    seen=set(); out=[]
    for x in items:
        k=(x["kind"],x["name"])
        if k not in seen:
            seen.add(k); out.append(x)
    return out[:10]

st.sidebar.title("LALSTUDY")
st.sidebar.caption(APP_VERSION)
st.sidebar.write("논문을 `핵심 논리 → 선수지식 → 실험 → Figure → 추가학습` 순서로 재구성합니다.")
debug=st.sidebar.checkbox("Beta debug 정보",False)

st.title("📄 Learn a Paper")
st.caption("Upload a paper → understand the logic → learn what you need next.")

uploaded=st.file_uploader("논문 PDF 업로드",type=["pdf"])

if uploaded is None:
    st.info("PDF를 올리면 LALSTUDY가 논문을 학습용 구조로 재구성합니다.")
    st.markdown("""
### v0.1.0-beta
- **Paper at a Glance**
- **Why This Study?**
- **Prerequisite Knowledge**
- **Experimental Strategy**
- **Figure-by-Figure Story**
- **Methods Used**
- **What Should I Learn Next?**
""")
    st.stop()

with st.spinner("PDF 구조를 읽는 중..."):
    pages,raw=extract_pdf(uploaded.getvalue())

full=clean_text(raw)
if len(full)<500:
    st.error("텍스트를 충분히 추출하지 못했습니다. 스캔 PDF OCR은 아직 지원하지 않습니다.")
    st.stop()

sections=extract_sections(raw)
glance=extract_glance(sections,full)
why=extract_why(sections)
concepts=detect_concepts(full)
methods=detect_methods(full)
strategy=method_strategy(methods)
figures=extract_figures(full)
learn=learning_path(concepts,methods)

m1,m2,m3,m4=st.columns(4)
m1.metric("Pages",len(pages))
m2.metric("Concepts",len(concepts))
m3.metric("Methods",len(methods))
m4.metric("Figures detected",len(figures))

t1,t2,t3,t4,t5=st.tabs(["🎯 Overview","🧠 Background","🔬 Experiments","🖼 Figures","📚 Learn Next"])

with t1:
    st.header("🎯 Paper at a Glance")
    if glance:
        for s in glance: st.markdown(f"- {s}")
    else: st.warning("핵심 문장을 안정적으로 추출하지 못했습니다.")

    st.header("❓ Why This Study?")
    if why:
        for s in why: st.markdown(f"- {s}")
    else: st.info("명확한 research gap 문장을 찾지 못했습니다.")

    if sections.get("abstract"):
        with st.expander("원문 Abstract"):
            st.write(sections["abstract"])

with t2:
    st.header("🧠 Prerequisite Knowledge")
    st.caption("논문에 실제 등장한 개념 중, 읽기 전에 알면 좋은 배경지식입니다.")
    if not concepts:
        st.info("현재 glossary와 매칭되는 개념이 없습니다.")
    for c in concepts[:15]:
        with st.expander(f"{c['name']} · {c['category']} · {c['count']} mentions"):
            st.markdown(f"**30초 설명**  \n{c['short']}")
            st.markdown(f"**조금 더 자세히**  \n{c['detail']}")
            if c["depends"]:
                st.markdown("**먼저 알면 좋은 개념**")
                st.write(" → ".join(c["depends"]))
            match=None
            for term in [c["name"]]+c.get("aliases",[]):
                match=re.search(re.escape(term),full,re.I)
                if match: break
            if match:
                a=max(0,match.start()-220); b=min(len(full),match.end()+300)
                st.markdown("**이 논문에서 등장한 맥락**")
                st.write("…"+full[a:b]+"…")

with t3:
    st.header("🔬 Experimental Strategy")
    st.caption("기존 LALSTUDY method ontology와 PDF 본문을 연결한 결과입니다.")
    if not strategy:
        st.warning("현재 ontology와 매칭되는 실험기법이 없습니다.")
    for x in strategy:
        with st.container(border=True):
            a,b=st.columns([2,1])
            with a:
                st.subheader(x["name"])
                st.write(x["purpose"])
                if x["category"]: st.caption(f"Category: {x['category']}")
                if x["parent"]: st.caption(f"Parent method: {x['parent']}")
            with b:
                st.metric("PDF mentions",x["count"])
                if x["paper_count"] is not None: st.metric("LALSTUDY papers",x["paper_count"])
                if x["figure_count"] is not None: st.metric("Figure examples",x["figure_count"])
            st.caption("→ 통합 앱에서는 여기서 Method Explorer / Figure Gallery로 바로 이동")

with t4:
    st.header("🖼 Figure-by-Figure Story")
    st.caption("PDF text layer에서 Figure caption 후보를 찾는 beta 기능입니다.")
    if not figures:
        st.info("Figure caption을 안정적으로 감지하지 못했습니다.")
    for f in figures:
        with st.expander(f["figure"]):
            sents=sentence_split(f["raw"])
            st.markdown("**이 Figure가 말하는 내용 — 자동 추출**")
            st.write(" ".join(sents[:2])[:700] if sents else f["raw"][:700])
            with st.expander("감지된 원문 구간"):
                st.write(f["raw"])

with t5:
    st.header("📚 What Should I Learn Next?")
    st.caption("기초 → 고급 개념 → 실험기법 순서로 다시 읽기 위한 학습 경로입니다.")
    for i,x in enumerate(learn,1):
        st.markdown(f"### {i}. {x['name']}  `{x['kind']}`")
        st.caption(x["reason"])

    export={
        "lalstudy_version":APP_VERSION,
        "source_file":uploaded.name,
        "paper_at_a_glance":glance,
        "why_this_study":why,
        "prerequisite_knowledge":[
            {"name":c["name"],"category":c["category"],"short":c["short"],"background":c["detail"],"depends_on":c["depends"],"mentions":c["count"]}
            for c in concepts
        ],
        "experimental_strategy":strategy,
        "figure_story":[{"figure":f["figure"],"raw":f["raw"]} for f in figures],
        "learning_path":learn
    }

    st.download_button(
        "⬇️ Learning Map JSON 저장",
        json.dumps(export,ensure_ascii=False,indent=2),
        file_name=Path(uploaded.name).stem+"_lalstudy.json",
        mime="application/json",
        use_container_width=True
    )

if debug:
    st.divider()
    st.write("Detected sections:",list(sections.keys()))
    st.write("Text characters:",len(full))
    with st.expander("Extracted text preview"):
        st.text(full[:12000])

st.divider()
st.caption(
    f"LALSTUDY {APP_VERSION} · Rule-based / extractive prototype. "
    "학습 보조용 자동 분석이며 원 논문과 함께 확인해야 합니다."
)
