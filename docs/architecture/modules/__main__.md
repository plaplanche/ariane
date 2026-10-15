# Module `ariane.__main__`

Lets `python -m ariane` run the command line. It holds no logic of its own.

## Main types and functions

- `main` (imported from `cli`) is the exit code of the process.

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  __main__ --> cli
```
<!-- end generated -->

## Serves

C23; ADR 0002. See [the component view](../3-components.md).
