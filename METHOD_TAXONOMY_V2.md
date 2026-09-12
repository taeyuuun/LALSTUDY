# Method Taxonomy V2

## Why

The previous single `principle` bucket mixed different conceptual levels.

Example:
Flow cytometry was shown as:
- antibody-based
- cytometry
- fluorescence-based

That is misleading because:
- Cytometry is the defining measurement principle.
- Fluorescence is a common detection mode, not required.
- Antibody labeling is a common targeting strategy, not required.

## V2 facets

1. Purpose
2. Material
3. Core principle
4. Detection
5. Labeling
6. Output

## Flow cytometry

Purpose:
- Cell identity / phenotype

Material:
- Cell

Core principle:
- Cytometry

Detection:
- Light scatter
- Fluorescence

Labeling:
- Label-free
- Antibody
- Fluorescent dye
- Fluorescent protein

Output:
- Population / frequency
- Single-cell signal

## Database compatibility

No SQL migration is required.

Existing Method Wiki rows may contain old v1 `facets`.
Those are ignored unless `facets._taxonomy_version == 2`.

Newly generated/upgraded entries save taxonomy v2 facets automatically.
