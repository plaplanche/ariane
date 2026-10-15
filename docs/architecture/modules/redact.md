# Module `ariane.redact`

Masks known secrets and common token formats in any text that leaves Ariane.

## Main types and functions

- `redact`: return the text with secrets replaced.

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  delivery --> redact
  flow --> redact
  git --> redact
  logs --> redact
  ticket --> redact
  verify --> redact
```
<!-- end generated -->

## Serves

C21; ADR 0013. See [the component view](../3-components.md).
