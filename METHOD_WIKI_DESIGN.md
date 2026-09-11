# LALSTUDY v0.5.0 Method Wiki

## Product structure

Method Wiki home
- Search by method name / alias
- Browse by Purpose
- Browse by Material
- Browse by Principle
- Browse by Output
- Combine facets: OR inside one facet, AND across different facets

Method article
- concise reusable overview
- core principle
- when to use it
- interpretation caveats
- aliases / parent / submethods
- frequently co-used methods
- existing corpus papers and Figures

## Storage split

Supabase `method_encyclopedia`
- ONLY reusable method-level explanation
- browse facets
- quality/source metadata

Existing local corpus
- method_profiles.json
- figure_images.json
- paper / Figure relations

This intentionally avoids duplicating the large paper corpus in SQL.

## Missing DB entry

The page shows a single button:
`✨ 설명 생성하고 DB에 저장`

The OpenAI call happens once for that method. The saved entry is reused by
future users.

## Facets

1. Purpose
2. Material
3. Principle
4. Output

A method may belong to multiple values in every facet. Initial browsing works
from deterministic taxonomy rules even before its encyclopedia entry exists.
The DB can later hold curated facet values.
