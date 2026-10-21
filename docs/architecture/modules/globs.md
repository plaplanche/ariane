# Module `ariane.globs`

Path globs (C9, C22, ADR 0056): the one set of rules for every glob of `ariane.toml` (`documentation.map`, `checks[].paths`, `not_run_locally`, `check_all_paths`, `review.sensitive_paths`, `next.paths`) and for the expected files of `ariane next` (ADR 0060).

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `matching_paths(globs, paths)` | function | The paths matching at least one glob; a line break in a path is matched like any other character (ADR 0056). |
| `is_glob(text)` | function | Whether `text` holds `*` or `?`, rather than naming one path. |
| `glob_regex(glob)` | function | The regular expression of one glob: `*` and `?` stay within a path segment, `**` crosses segments, `**/` is any folders (none included). |
| `overlap(first, second)` | function | Whether one path can match both globs (a path without wildcards included): `docs/**` and `docs/architecture/**` do, `*.md` and `docs/*.md` do not. |

## Behaviour and errors

- Paths are relative, with `/` as separator, as git prints them; matching is case-sensitive and whole (`fullmatch`).
- Every other character matches itself: there are no character classes or braces.
- `overlap` builds each glob's automaton (one state per character, a looping state per `*` or `**`, `**/` as nothing or any characters then `/`) and walks the pairs of states from both starts; a step of both is taken when one character can take each (`*` and `?` take any but `/`). It answers whether both ends are reached together, without listing paths, so a file not created yet counts.

## Workflow

`matching_paths` compiles each glob once with `glob_regex` and keeps the paths one of them matches whole.

## Code view (C4 level 4)

```mermaid
classDiagram
class globs {
  <<module>>
  matching_paths(globs, paths) list~str~
  is_glob(text) bool
  glob_regex(glob) Pattern
  overlap(first, second) bool
}
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  checks --> globs
  config --> globs
  next_ticket --> globs
  replay --> globs
  verify --> globs
```
<!-- end generated -->

## Serves

C9, C22; ADR 0056, ADR 0060. See [the component view](../3-components.md).
