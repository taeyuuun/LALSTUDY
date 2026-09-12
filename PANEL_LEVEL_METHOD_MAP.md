# Panel-Level Method Map

The panel map is intentionally caption-grounded.

Examples:

`(A-C) Flow cytometry analysis of CD4+ T cells ...`

becomes:

`Fig. 2A-C`
- A, B, C — explicit caption evidence
- usage text copied/condensed from the original Figure legend

If the Figure legend says:

`Flow cytometry analysis of treated cells. (A) ... (B) ...`

the method is recognized as Figure-level context and A/B are shown with that
context, rather than pretending the word "flow cytometry" was repeated in each
panel.

If the corpus says a Figure uses the method but the caption does not allow a
reliable A-F assignment, LALSTUDY keeps it at Figure level instead of guessing.

No AI call, SQL migration, or new storage is required.
