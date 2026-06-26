from __future__ import annotations

from django.template.response import TemplateResponse

UWB_STEM_URL = "https://www.uwb.edu/stem"
UWB_STEM_FACT_SHEET_URL = "https://www.uwb.edu/wp-content/uploads/2026/02/School_of_STEM_Fact_Sheet.pdf"
UWB_STEM_LOGO_STATIC_PATH = "assets/uwb/web-left-school-signature-uw-bothell.png"
UWB_STEM_WHITE_LOGO_STATIC_PATH = "assets/uwb/web-white-left-school-signature-uw-bothell.png"
GITHUB_BLOB_BASE_URL = "https://github.com/BrentLagesse/CytoCV/blob/main"
CC_LICENSE_NAME = "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License"
CC_LICENSE_IDENTIFIER = "CC BY-NC-SA 4.0"
CC_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
CC_LICENSE_LEGAL_CODE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en"

HOME_AFFILIATION_LINES = (
    "University of Washington Bothell",
    "School of STEM",
    "School of Science, Technology, Engineering & Mathematics",
    "Department of Computing & Software Systems",
)

LICENSE_SUMMARY_POINTS = (
    "You may copy and redistribute the material in any medium or format.",
    "You may remix, transform, and build upon the material.",
    "You must give appropriate credit, provide a link to the license, and indicate whether changes were made.",
    "You may not use the material for commercial purposes.",
    "If you adapt the material, you must distribute your contributions under the same license.",
    "You may not apply legal terms or technological measures that restrict uses the license permits.",
)

LICENSE_SCOPE_NOTE = (
    "CytoCV's current published project statement is that it is licensed under "
    "CC BY-NC-SA 4.0. If maintainers later intend different terms for source code, "
    "documentation, or other assets, that distinction should be clarified separately."
)

LICENSE_DISCLAIMER = (
    "This page is a brief summary only. Confirm reuse, attribution, noncommercial, "
    "and share-alike requirements against the official Creative Commons license and "
    "legal code."
)

HOME_PROOF_CARDS = (
    {
        "eyebrow": "Team",
        "title": "CytoCV Team",
        "body": (
            "Built by the UW Bothell School of STEM SEE Lab engineering team in "
            "collaboration with the University of Utah Miller Lab biology team."
        ),
        "href": "/collaborators/",
        "link_label": "View CytoCV Team",
    },
    {
        "eyebrow": "About",
        "title": "About CytoCV",
        "body": (
            "CytoCV is a web-based research workflow for DeltaVision microscopy of "
            "yeast cells. It keeps validation, segmentation, measurement, and "
            "review connected in one place so imaging results are easier to analyze, "
            "compare, and interpret."
        ),
        "href": "/about/",
        "link_label": "See About page",
    },
)

HOME_SECTION_CARDS = (
    {
        "eyebrow": "WORKFLOW",
        "title": "From Upload to Export",
        "body": (
            "See how CytoCV guides users through upload, validation, preprocessing, "
            "segmentation, measurement, review, and export."
        ),
        "href": "/about/#workflow",
        "link_label": "View Workflow",
    },
    {
        "eyebrow": "MEASUREMENTS",
        "title": "Cell-Level Research Outputs",
        "body": (
            "Review the software-generated cell-level measurements CytoCV reports "
            "for each segmented yeast cell."
        ),
        "href": "/about/#measurements",
        "link_label": "View Measurements",
    },
    {
        "eyebrow": "IMAGE INPUT",
        "title": "Built for DeltaVision Yeast Images",
        "body": (
            "CytoCV is designed around DeltaVision yeast imaging workflows that use "
            "the logical roles `DIC`, `Blue`, `Red`, and `Green`, often mapped from "
            "biology-facing names such as DAPI, mCherry, and GFP."
        ),
        "href": "/about/#image-inputs",
        "link_label": "View Image Inputs",
    },
    {
        "eyebrow": "RESULTS",
        "title": "Review Segmentation and Export Data",
        "body": (
            "Users can inspect segmented cells, review overlays, compare calculated "
            "measurements, and export results for downstream analysis."
        ),
        "href": "/about/#results",
        "link_label": "View Results",
    },
    {
        "eyebrow": "DOCUMENTATION",
        "title": "Using CytoCV",
        "body": (
            "Find upload requirements, workflow guidance, output explanations, and "
            "troubleshooting notes."
        ),
        "href": "https://github.com/BrentLagesse/CytoCV/tree/main/docs",
        "link_label": "View Documentation",
        "external": True,
    },
)

ABOUT_PAGE_SECTION_ITEMS = (
    {"id": "overview", "label": "Overview"},
    {"id": "research-need", "label": "Research Need"},
    {"id": "workflow", "label": "Workflow"},
    {"id": "measurements", "label": "Measurements"},
    {"id": "image-inputs", "label": "Image Inputs"},
    {"id": "results", "label": "Results"},
    {"id": "biological-value", "label": "Biological Value"},
)

COLLABORATOR_GROUPS = (
    {
        "id": "engineering-team",
        "eyebrow": "Engineering Team",
        "title": "UW Bothell School of STEM, SEE Lab Engineering Team",
        "entries": (
            {
                "name": "Nicolas Gioanni",
                "role": "Research Assistant",
                "institution_label": "UW",
                "email": "ngioanni@uw.edu",
                "summary": (
                    "Led the development of CytoCV's architecture, implementation, "
                    "deployment, requirements translation, and ongoing maintenance, "
                    "with work across image-processing design, segmentation and "
                    "preprocessing workflows, metadata extraction and validation, data "
                    "handling, authentication and third-party integrations, cloud "
                    "deployment, merge stabilization, and ML model optimization."
                ),
                "bio": (
                    "Graduate student in the University of Washington Bothell School of "
                    "STEM, Department of Computing & Software Systems, working with the "
                    "SEE Lab."
                ),
                "links": (
                    {
                        "href": "https://www.linkedin.com/in/nicolas-gioanni",
                        "label": "LinkedIn",
                    },
                    {
                        "href": "https://github.com/nicolasgioanni",
                        "label": "GitHub",
                    },
                    {
                        "href": "https://nicolasmgioanni.dev",
                        "label": "Personal",
                    },
                ),
            },
            {
                "name": "Anoop Prasad",
                "role": "Research Assistant",
                "institution_label": "UW",
                "email": "anoopp@uw.edu",
                "summary": (
                    "Contributed to requirements translation and contour-processing work "
                    "for the project, with a primary focus on red-contour development, "
                    "biorientation thresholding, and related contour-analysis workflows."
                ),
                "bio": (
                    "Graduate student in the University of Washington Bothell School of "
                    "STEM, Department of Computing & Software Systems, working with the "
                    "SEE Lab."
                ),
                "links": (
                    {
                        "href": "https://www.linkedin.com/in/anoop-prasad-uwb",
                        "label": "LinkedIn",
                    },
                    {
                        "href": "https://github.com/AnoopP7",
                        "label": "GitHub",
                    },
                ),
            },
            {
                "name": "Brent Lagesse",
                "role": "Associate Professor",
                "institution_label": "UW",
                "email": "lagesse@uw.edu",
                "summary": (
                    "Supervising professor for the UW Bothell and SEE Lab side of "
                    "the project."
                ),
                "bio": (
                    "Associate Professor in the University of Washington Bothell School "
                    "of STEM, Department of Computing & Software Systems, and faculty "
                    "lead within the SEE Lab."
                ),
                "links": (
                    {
                        "href": "https://www.linkedin.com/in/brent-lagesse-1a117960/",
                        "label": "LinkedIn",
                    },
                    {
                        "href": "https://github.com/BrentLagesse",
                        "label": "GitHub",
                    },
                    {
                        "href": "https://faculty.washington.edu/lagesse/",
                        "label": "Faculty",
                    },
                ),
            },
        ),
    },
    {
        "id": "biology-team",
        "eyebrow": "Biology collaborators",
        "title": (
            "University of Utah Spencer Fox Eccles School of Medicine, Miller Lab "
            "Biology Team"
        ),
        "entries": (
            {
                "name": "Emily Parnell",
                "role": "Research Associate",
                "institution_label": "Utah",
                "email": "emily.parnell@biochem.utah.edu",
                "summary": (
                    "Provided the biology-facing requirements, expected experimental "
                    "context, validation testing input, and feedback on what the system "
                    "should surface and support biologically, including preparing cells, "
                    "capturing microscopy images, confirming interpretations, and helping "
                    "define the biological expectations for the workflow."
                ),
                "bio": (
                    "Research associate in the University of Utah Department of "
                    "Biochemistry, Spencer Fox Eccles School of Medicine, working with "
                    "the Miller Lab."
                ),
                "links": (
                    {
                        "href": "https://miller.biochem.utah.edu/members",
                        "label": "Lab",
                    },
                ),
            },
            {
                "name": "Matthew P. Miller",
                "role": "Assistant Professor",
                "institution_label": "Utah",
                "email": "matt.miller@biochem.utah.edu",
                "summary": (
                    "Supervising professor for the University of Utah and Miller Lab "
                    "side of the project."
                ),
                "bio": (
                    "Assistant Professor in the University of Utah Department of "
                    "Biochemistry, Spencer Fox Eccles School of Medicine, and faculty "
                    "lead of the Miller Lab."
                ),
                "links": (
                    {
                        "href": "https://medicine.utah.edu/faculty/matthew-p-miller",
                        "label": "Faculty",
                    },
                    {
                        "href": "https://miller.biochem.utah.edu/members",
                        "label": "Lab",
                    },
                ),
            },
        ),
    },
)


def _github_blob(path: str) -> str:
    return f"{GITHUB_BLOB_BASE_URL}/{path}"


def _doc_link(
    *,
    label: str,
    path: str,
    description: str,
    link_type: str,
) -> dict[str, object]:
    return {
        "label": label,
        "href": _github_blob(path),
        "description": description,
        "meta": link_type,
        "external": True,
    }


ABOUT_TECHNICAL_PAGE = {
    "template_title": "CytoCV Technical Overview",
    "meta_description": (
        "Technical overview for CytoCV covering architecture, workflows, pipelines, "
        "dependencies, outputs, and documentation links."
    ),
    "page_eyebrow": "About Technical",
    "page_title": "Technical Overview",
    "show_doc_overview": False,
    "page_intro": (
        "CytoCV is organized as a web application that moves from supported source-image upload "
        "through export, with supporting documentation for workflow stages, major "
        "dependencies, outputs, and repository references."
    ),
    "page_actions": (),
    "detail_sections": (
        {
            "id": "purpose-scope",
            "jump_label": "Purpose and Scope",
            "eyebrow": "System Shape",
            "title": "Purpose, scope, and application boundaries",
            "paragraphs": (
                "CytoCV is a Django-based web application that keeps authenticated research workflows, image-processing stages, segmentation, measurement, and result review together in one browser-based workflow rather than scattering those steps across separate tools.",
                "At a high level, the codebase separates account and workflow concerns from scientific processing concerns, while preserving a run-centered view of uploaded files, derived artifacts, and exported measurements.",
            ),
            "highlights": (
                "The main emphasis is application structure and workflow behavior rather than deployment setup.",
                "The platform is shaped around DeltaVision yeast analysis instead of general-purpose microscopy hosting.",
            ),
        },
        {
            "id": "architecture",
            "jump_label": "Architecture",
            "eyebrow": "Architecture",
            "title": "High-level architecture and workflow ownership",
            "paragraphs": (
                "The implementation combines HTML template views, request handlers, background workflow coordination, database-backed state, and file-backed run artifacts. Presentation, request handling, persistence, and scientific processing remain distinct layers even though they work together in one application.",
                "Long-running work such as upload preparation and analysis is coordinated outside the initial browser request so validation, preprocessing, segmentation, and quantification can progress through explicit workflow stages.",
            ),
            "highlights": (
                "Authenticated flows govern who owns uploads, runs, and retained outputs.",
                "Background workflow ownership keeps analysis state explicit instead of hiding it inside one long request.",
            ),
        },
        {
            "id": "workflow-pipeline",
            "jump_label": "Workflow Pipeline",
            "eyebrow": "Pipeline",
            "title": "End-to-end workflow from upload to export",
            "paragraphs": (
                "A typical run begins with supported `.dv`, `.tif`, or `.tiff` upload, channel validation, preview generation, and scale extraction. After that, the workflow advances through preprocess review, segmentation, per-cell measurement, display review, and export.",
                "Each stage keeps the run configuration, channel interpretation, and produced outputs connected so researchers can review what happened at each point in the pipeline instead of only seeing a final spreadsheet.",
            ),
            "highlights": (
                "Upload-time validation surfaces incompatible inputs before segmentation begins.",
                "Preview generation and preprocess review provide an explicit checkpoint before deeper analysis runs.",
                "Review and export are treated as part of the same workflow, not an afterthought.",
            ),
        },
        {
            "id": "analysis-pipeline",
            "jump_label": "Analysis Pipeline",
            "eyebrow": "Analysis Pipeline",
            "title": "Segmentation, measurement, and result assembly",
            "paragraphs": (
                "The default modern analysis path centers on DIC as the structural input for Mask R-CNN-based segmentation. Fluorescence channels then contribute to plugin-scoped measurements such as puncta distance, contour summaries, nuclear or cell-pair intensity, and CEN dot classification.",
                "This separation matters: cell finding is driven by structural context, while fluorescence channels remain the primary source of biological signal quantification. Legacy Blue-based workflows are still supported, but they are not the main default path.",
            ),
            "highlights": (
                "DIC provides the structural baseline for segmentation.",
                "Red and Green channels drive the default modern measurement set.",
                "Legacy Blue analysis remains available for backward-compatible workflows.",
            ),
        },
        {
            "id": "state-and-artifacts",
            "jump_label": "Data and Artifacts",
            "eyebrow": "State And Artifacts",
            "title": "Data model, artifact flow, and output surfaces",
            "paragraphs": (
                "CytoCV persists both database-backed workflow state and run-scoped media artifacts. Uploaded files, preparation jobs, analysis jobs, segmented runs, previews, and per-cell statistics are treated as related pieces of one analysis record rather than isolated files.",
                "The review surfaces then expose outlined images, segmented cell assets, overlays, and table exports so users can move from visual inspection to quantitative output without losing the connection to the run that produced those results.",
            ),
            "highlights": (
                "Run metadata and exported cell-level statistics remain tied to the same workflow state.",
                "Run artifacts and outputs stay connected so users can trace results back to the analysis that produced them.",
            ),
        },
        {
            "id": "dependencies",
            "jump_label": "Dependencies",
            "eyebrow": "Dependencies",
            "title": "Runtime stack, dependencies, and practical limits",
            "paragraphs": (
                "The major runtime stack combines Django for the web layer, django-allauth for authentication flows, django-tables2 for tabular presentation, NumPy/OpenCV/scikit-image/Pillow for image processing, and TensorFlow/Keras/Mask R-CNN components for inference and segmentation support.",
                "These dependencies are easiest to understand by role: web framework, scientific image processing, inference, persistence, and export. The goal here is to show what each category contributes to the workflow.",
            ),
            "highlights": (
                "Dependencies should be grouped by role: web, scientific processing, inference, persistence, and export.",
                "Environment and infrastructure details are documented separately from this overview.",
            ),
        },
    ),
    "doc_groups": (
        {
            "id": "developer-docs",
            "jump_label": "Developer Docs",
            "eyebrow": "Developer Docs",
            "title": "Architecture, codebase, and artifact references",
            "description": (
                "These repository documents outline the system shape, codebase organization, and artifact lifecycle at a high level."
            ),
            "links": (
                _doc_link(
                    label="Architecture Overview",
                    path="docs/developer/architecture-overview.md",
                    description="Current system shape, major layers, request handlers, worker responsibilities, and persistence boundaries.",
                    link_type="GitHub Markdown",
                ),
                _doc_link(
                    label="Codebase Map",
                    path="docs/developer/codebase-map.md",
                    description="High-level map of the major packages, templates, and workflow entry points in the repository.",
                    link_type="GitHub Markdown",
                ),
                _doc_link(
                    label="Data Flow And Artifacts",
                    path="docs/developer/data-flow-and-artifacts.md",
                    description="Run-centered explanation of how uploaded data, generated assets, and persisted workflow state move through the application.",
                    link_type="GitHub Markdown",
                ),
                _doc_link(
                    label="Data Model",
                    path="docs/reference/data-model.md",
                    description="Summary of the primary persisted entities used by the application.",
                    link_type="GitHub Markdown",
                ),
                _doc_link(
                    label="File Format And Artifact Spec",
                    path="docs/reference/file-format-and-artifact-spec.md",
                    description="Reference guide for the major file classes and generated artifact types used by CytoCV.",
                    link_type="GitHub Markdown",
                ),
            ),
        },
        {
            "id": "workflow-docs",
            "jump_label": "Workflow Docs",
            "eyebrow": "Workflow Docs",
            "title": "User-facing workflow and output guides",
            "description": (
                "These docs explain how the workflow moves from upload through export and how to interpret the major outputs."
            ),
            "links": (
                _doc_link(
                    label="Workflow Guide",
                    path="docs/user/workflow-guide.md",
                    description="End-to-end user workflow from upload through review and export.",
                    link_type="GitHub Markdown",
                ),
                _doc_link(
                    label="Output Guide",
                    path="docs/user/output-guide.md",
                    description="Explanation of preview assets, segmentation products, persisted rows, and export categories.",
                    link_type="GitHub Markdown",
                ),
            ),
        },
        {
            "id": "research-pdfs",
            "jump_label": "Research PDFs",
            "eyebrow": "Research PDFs",
            "title": "Formal methods and figure references",
            "description": (
                "These formal references provide deeper material for methods, reproducibility, and figures."
            ),
            "links": (
                _doc_link(
                    label="Methods And System Description",
                    path="docs/research/pdfs/methods-and-system-description.pdf",
                    description="Formal PDF covering system objectives, input model, validation logic, measurement model, and workflow stages.",
                    link_type="GitHub PDF",
                ),
                _doc_link(
                    label="Figure Catalog",
                    path="docs/research/pdfs/figure-catalog.pdf",
                    description="Catalog of architecture, workflow, validation, and output figures available in the repository.",
                    link_type="GitHub PDF",
                ),
                _doc_link(
                    label="Reproducibility And Validation",
                    path="docs/research/pdfs/reproducibility-and-validation.pdf",
                    description="PDF covering reproducibility assumptions, validation semantics, and workflow defaults context.",
                    link_type="GitHub PDF",
                ),
            ),
        },
    ),
}

ABOUT_BIOLOGY_PAGE = {
    "template_title": "CytoCV Biological Context",
    "meta_description": (
        "Biology overview for CytoCV covering yeast microscopy context, "
        "chromosome segregation assays, channel roles, biological interpretation, "
        "and supporting documentation links."
    ),
    "page_eyebrow": "About Biology",
    "page_title": "Biological Context",
    "show_doc_overview": False,
    "page_intro": (
        "CytoCV is built around yeast microscopy assays that use segmented "
        "cell structure, red and green fluorescent markers, and per-cell measurements "
        "to support chromosome segregation, localization, and intensity comparisons."
    ),
    "page_actions": (),
    "detail_sections": (
        {
            "id": "experimental-context",
            "jump_label": "Core Use Case",
            "eyebrow": "Experimental Context",
            "title": "Chromosome segregation in yeast",
            "paragraphs": (
                "CytoCV contains analysis workflows developed primarily for microscopy assays that study chromosome segregation in yeast. These experiments often depend on comparing cellular structure, spindle-pole position, chromosome-associated fluorescent dots, and protein localization across many individual cells.",
                "That biological focus shapes the software: DIC defines the cell and mother/daughter geometry, while red and green fluorescence channels provide the main markers for distance, localization, contour, and intensity measurements.",
            ),
            "highlights": (
                "The software is tuned for a domain-specific microscopy workflow, not generic image browsing.",
                "Per-cell interpretation matters because segregation and localization phenotypes can appear only in specific cell-cycle stages or subsets of cells.",
            ),
        },
        {
            "id": "red-green-intensity",
            "jump_label": "Red/Green Intensity",
            "eyebrow": "Intensity Assays",
            "title": "Reference and experimental fluorophore comparisons",
            "paragraphs": (
                "Red/green intensity assays are designed to compare the abundance of a fluorescently tagged protein across strains, mutants, or other experimental conditions. In the experimental design, one tagged protein can serve as a reference control expected to stay relatively stable, while the other marks the experimental protein or signal being tested.",
                "CytoCV draws contours around red and green puncta, measures red and green signal inside those contour masks, and reports total, maximum, and average raw intensity summaries. The current public outputs also include Measurement/Contour Ratio columns derived from the total intensity values, with Red/Green or Green/Red labeling determined by the selected measurement mode.",
            ),
            "highlights": (
                "The user-facing Red and Green roles stay generic so the experiment can decide which marker is the reference control and which is the test signal.",
                "Raw total, maximum, and average intensity values remain primary outputs; ratio columns are derived interpretation aids and should be reviewed with the source images.",
            ),
        },
        {
            "id": "puncta-distance",
            "jump_label": "Puncta Distance",
            "eyebrow": "Distance Assays",
            "title": "Measuring a biological axis between paired puncta",
            "paragraphs": (
                "The puncta-distance workflow measures the spacing between two structures marked by the same fluorophore, such as a pair of red or green puncta that define an axis inside the cell. The reported distance can be reviewed in pixels or converted to microns through the saved scale context.",
                "After the source puncta are selected, CytoCV measures signal from the opposite fluorophore along the line between them. This supports assays where the distance between structures, such as spindle poles, and the intensity of another protein along that axis are both biologically meaningful.",
            ),
            "highlights": (
                "Red puncta mode measures Green signal along the Red-dot line; Green puncta mode measures Red signal along the Green-dot line.",
                "The line width can be configured in pixels or microns, with micron values converted through the run's scale context.",
            ),
        },
        {
            "id": "cen-dot-location",
            "jump_label": "CEN Dot Location",
            "eyebrow": "Chromosome Segregation",
            "title": "Classifying CEN dots after anaphase",
            "paragraphs": (
                "The CEN dot location assay is intended for cells that have progressed through anaphase, when nuclei have separated and chromosomes have segregated into mother and daughter regions. A red marker defines spindle-pole puncta, and a green marker identifies a CEN-marked chromosome.",
                "CytoCV first checks whether a segmented cell pair has two usable red puncta separated by at least the configured minimum distance. It then determines whether green CEN dots fall within the configured proximity radius around the red spindle-pole markers and reports whether the signal is associated with the mother side, daughter side, both sides, or neither side.",
            ),
            "highlights": (
                "The document's 3.5-4 micron spacing is best treated as an experiment-dependent example for selecting anaphase-like cells, not a universal software default.",
                "Mother and daughter assignment depends on DIC-derived cell geometry and size context, so the overlay should be reviewed before biological conclusions are drawn.",
            ),
        },
        {
            "id": "biorientation",
            "jump_label": "Biorientation",
            "eyebrow": "Attachment State",
            "title": "Evaluating chromosome biorientation in metaphase",
            "paragraphs": (
                "The biorientation assay also uses a green CEN-marked chromosome and a red spindle-pole marker, but it targets metaphase-like cells. Correct biorientation places sister chromatids under tension from opposite spindle poles, which can appear as two distinct green puncta along the spindle-pole axis. Chromosomes that are not yet bioriented or are incorrectly attached may appear as a single green punctum.",
                "CytoCV checks whether two red puncta fall inside the configured distance range, draws the red-puncta axis, and counts green puncta as colinear or off-axis according to the configured colinearity threshold. Those counts let researchers calculate the proportion of cells with one versus two colinear green puncta and compare normally positioned chromosomes with off-axis chromosomes.",
            ),
            "highlights": (
                "The document's 1-2.5 micron red-puncta range is an experiment-dependent example for metaphase selection and may need adjustment for mutants or abnormal spindle length.",
                "The colinearity threshold is empirical and should be tuned for the experiment rather than treated as a physical distance by itself.",
            ),
        },
        {
            "id": "nuclear-cytoplasmic-intensity",
            "jump_label": "Nuclear Intensity",
            "eyebrow": "Localization Assays",
            "title": "Nuclear versus cytoplasmic protein localization",
            "paragraphs": (
                "Nuclear and cytoplasmic intensity assays ask how much of a fluorescently tagged protein is present in the nucleus compared with the rest of the cell. This is useful for localization questions such as characterizing nuclear import or export behavior.",
                "The workflow uses one fluorophore as the nucleus-defining reference and measures the opposite fluorophore, representing the protein of interest, inside the nuclear contour and across the full cell-pair mask. Cytoplasmic signal is derived from the difference between cellular and nuclear signal. The biological assay is often interpreted through nuclear-to-cytoplasmic comparison; the current CytoCV outputs expose the nuclear, cell-pair, and cytoplasmic intensity values used for that downstream comparison.",
            ),
            "highlights": (
                "In the modern workflow, users choose whether Red or Green supplies the nucleus contour source.",
                "Legacy Blue-based nucleus workflows remain available when an older DAPI-like channel setup is intentionally used.",
            ),
        },
        {
            "id": "use-and-caveats",
            "jump_label": "Use and Caveats",
            "eyebrow": "Use And Caveats",
            "title": "Practical value and biological caution points",
            "paragraphs": (
                "CytoCV can reduce manual workload and increase consistency across larger image sets, but biological interpretation still depends on experimental design, channel configuration, marker behavior, and review of the resulting cells and overlays.",
                "The exported values are software-generated measurements tied to source images. They support comparison and downstream analysis, but they should not be treated as final biological conclusions without image review, controls, and statistical judgment.",
            ),
            "highlights": (
                "Per-cell outputs preserve heterogeneity that can be hidden by one run-level average.",
                "Thresholds and marker choices should be documented with the experiment so exported results remain interpretable later.",
            ),
        },
    ),
    "doc_groups": (
        {
            "id": "biology-research-docs",
            "jump_label": "Research Docs",
            "eyebrow": "Research Docs",
            "title": "Methods, figures, and biological framing",
            "description": (
                "These research documents provide methods, figures, and workflow context related to the biological use case."
            ),
            "links": (
                _doc_link(
                    label="Methods And System Description",
                    path="docs/research/pdfs/methods-and-system-description.pdf",
                    description="Formal PDF covering input model, validation logic, measurement model, and overall workflow framing.",
                    link_type="GitHub PDF",
                ),
                _doc_link(
                    label="Figure Catalog",
                    path="docs/research/pdfs/figure-catalog.pdf",
                    description="Figure reference set covering architecture, workflow, validation, and output diagrams relevant to the biological story.",
                    link_type="GitHub PDF",
                ),
            ),
        },
        {
            "id": "biology-workflow-docs",
            "jump_label": "Workflow Docs",
            "eyebrow": "Workflow Docs",
            "title": "Workflow and output references for experimental interpretation",
            "description": (
                "These user-facing docs help connect the biology-oriented explanation back to what researchers actually review during upload, analysis, and output interpretation."
            ),
            "links": (
                _doc_link(
                    label="Workflow Guide",
                    path="docs/user/workflow-guide.md",
                    description="Public guide for the upload, validation, preprocess, analysis, review, and export flow.",
                    link_type="GitHub Markdown",
                ),
                _doc_link(
                    label="Output Guide",
                    path="docs/user/output-guide.md",
                    description="Public guide to the major output classes, segmented assets, and exported result categories.",
                    link_type="GitHub Markdown",
                ),
            ),
        },
    ),
}

RESEARCH_SECTIONS = (
    {
        "id": "methods",
        "eyebrow": "Methods",
        "title": "Methods and system description",
        "summary": (
            "CytoCV is documented as a web-based analysis system for DeltaVision microscopy "
            "of yeast cells. The active implementation combines authenticated web "
            "workflows, source-image metadata parsing, Mask R-CNN-based segmentation, "
            "plugin-scoped per-cell quantification, and retention-aware result management."
        ),
        "highlights": (
            "Supported source-image ingestion stays connected to channel interpretation, scale context, and measurement output.",
            "The computational path moves from upload and preview generation into DIC-driven segmentation and per-cell quantification.",
            "The platform is described as a domain-specific research workflow rather than a generic microscopy framework.",
        ),
        "primary_label": "Open methods PDF",
        "primary_href": f"{GITHUB_BLOB_BASE_URL}/docs/research/pdfs/methods-and-system-description.pdf",
        "secondary_label": "Open figure catalog",
        "secondary_href": f"{GITHUB_BLOB_BASE_URL}/docs/research/pdfs/figure-catalog.pdf",
    },
    {
        "id": "validation",
        "eyebrow": "Validation",
        "title": "Validation-aware workflow rules",
        "summary": (
            "The documented validation model treats DIC as the only universal baseline "
            "channel and builds the rest of the requirement set from plugin selection and "
            "optional enforcement policy. Exact four-layer enforcement remains optional "
            "rather than universal."
        ),
        "highlights": (
            "Default modern selected plugins require DIC, Red, and Green.",
            "Blue channel requirements are introduced only by legacy plugins or optional all-wavelength enforcement.",
            "Upload-time validation and preview generation happen before segmentation and measurement.",
        ),
        "primary_label": "Open reproducibility PDF",
        "primary_href": f"{GITHUB_BLOB_BASE_URL}/docs/research/pdfs/reproducibility-and-validation.pdf",
        "secondary_label": "Open methods PDF",
        "secondary_href": f"{GITHUB_BLOB_BASE_URL}/docs/research/pdfs/methods-and-system-description.pdf",
    },
    {
        "id": "reproducibility",
        "eyebrow": "Reproducibility",
        "title": "Reproducibility-minded run context",
        "summary": (
            "The reproducibility notes treat environment, model weights, input data, and "
            "run configuration as part of the result definition. The codebase records scale "
            "context, plugin selection, and exported measurement output to keep completed "
            "runs interpretable."
        ),
        "highlights": (
            "Python 3.11.5 is a documented fixed target for the current scientific stack.",
            "Per-run scale context and plugin metadata are treated as first-class workflow state.",
            "Formal result packages should preserve commit hash, dependency set, model weight identifier, and exported tables.",
        ),
        "primary_label": "Open reproducibility PDF",
        "primary_href": f"{GITHUB_BLOB_BASE_URL}/docs/research/pdfs/reproducibility-and-validation.pdf",
        "secondary_label": "Open figure catalog",
        "secondary_href": f"{GITHUB_BLOB_BASE_URL}/docs/research/pdfs/figure-catalog.pdf",
    },
    {
        "id": "institutional-affiliation",
        "eyebrow": "Institutional affiliation",
        "title": "UW Bothell School of STEM context",
        "summary": (
            "The public homepage now frames CytoCV with the official University of Washington "
            "Bothell School of STEM signature mark while retaining the University of Utah "
            "research collaboration language already present in the product. The official "
            "UW Bothell STEM materials describe a school centered on research, hands-on "
            "training, and interdisciplinary STEM work."
        ),
        "highlights": (
            "The homepage uses the official School of STEM web signature asset from UW Bothell’s school-logo pack.",
            "The public research page links to official UW Bothell STEM reference material in addition to local research PDFs.",
            "This pass emphasizes institutional affiliation plus research-proof content, not rankings or marketing-heavy claims.",
        ),
        "primary_label": "Visit UWB STEM",
        "primary_href": UWB_STEM_URL,
        "primary_external": True,
        "secondary_label": "Open School of STEM fact sheet",
        "secondary_href": UWB_STEM_FACT_SHEET_URL,
        "secondary_external": True,
    },
)


def _build_page_section_nav(
    items: tuple[dict[str, str], ...] | list[dict[str, str]],
) -> dict[str, object] | None:
    if not items:
        return None
    return {
        "label": "Table of contents",
        "items": tuple(
            {
                "label": item["label"],
                "href": f"#{item['id']}",
            }
            for item in items
        ),
    }


def _build_detail_page_section_nav(page_data: dict[str, object]) -> dict[str, object] | None:
    items: list[dict[str, str]] = []
    for section in page_data.get("detail_sections", ()):
        items.append(
            {
                "id": section["id"],
                "label": section.get("jump_label", section["title"]),
            }
        )
    for group in page_data.get("doc_groups", ()):
        items.append(
            {
                "id": group["id"],
                "label": group.get("jump_label", group["title"]),
            }
        )
    return _build_page_section_nav(items)


def _shared_public_context() -> dict[str, object]:
    return {
        "proof_cards": HOME_PROOF_CARDS,
        "section_cards": HOME_SECTION_CARDS,
        "collaborator_groups": COLLABORATOR_GROUPS,
        "home_affiliation_lines": HOME_AFFILIATION_LINES,
        "about_nav_current_key": None,
        "page_section_nav": None,
        "github_blob_base_url": GITHUB_BLOB_BASE_URL,
        "cc_license_name": CC_LICENSE_NAME,
        "cc_license_identifier": CC_LICENSE_IDENTIFIER,
        "cc_license_url": CC_LICENSE_URL,
        "cc_license_legal_code_url": CC_LICENSE_LEGAL_CODE_URL,
        "license_summary_points": LICENSE_SUMMARY_POINTS,
        "license_scope_note": LICENSE_SCOPE_NOTE,
        "license_disclaimer": LICENSE_DISCLAIMER,
        "uwb_logo_static_path": UWB_STEM_LOGO_STATIC_PATH,
        "uwb_white_logo_static_path": UWB_STEM_WHITE_LOGO_STATIC_PATH,
        "uwb_logo_alt": "University of Washington Bothell School of STEM signature logo",
        "uwb_stem_url": UWB_STEM_URL,
        "uwb_stem_fact_sheet_url": UWB_STEM_FACT_SHEET_URL,
    }


def home(request):
    return TemplateResponse(request, "home.html", _shared_public_context())


def about(request):
    context = _shared_public_context()
    context.update(
        {
            "about_nav_current_key": "about",
            "page_section_nav": _build_page_section_nav(ABOUT_PAGE_SECTION_ITEMS),
        }
    )
    return TemplateResponse(request, "about.html", context)


def about_technical(request):
    context = _shared_public_context()
    context.update(ABOUT_TECHNICAL_PAGE)
    context.update(
        {
            "about_nav_current_key": "technical",
            "page_section_nav": _build_detail_page_section_nav(ABOUT_TECHNICAL_PAGE),
        }
    )
    return TemplateResponse(request, "about_detail.html", context)


def about_biology(request):
    context = _shared_public_context()
    context.update(ABOUT_BIOLOGY_PAGE)
    context.update(
        {
            "about_nav_current_key": "biological",
            "page_section_nav": _build_detail_page_section_nav(ABOUT_BIOLOGY_PAGE),
        }
    )
    return TemplateResponse(request, "about_detail.html", context)


def collaborators(request):
    return TemplateResponse(request, "collaborators.html", _shared_public_context())


def license_page(request):
    return TemplateResponse(request, "license.html", _shared_public_context())
