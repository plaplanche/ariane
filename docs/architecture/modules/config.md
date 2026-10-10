# Module `ariane.config`

Loads and validates `ariane.toml`. Every error names the faulty key.

## Main types and functions

- `Config`, `TrackerConfig`, `AgentConfig`, `CheckConfig`, `DoneItem`: the validated settings; `Config.definition_of_done` holds the
  definition of done (C26), `DEFAULT_DEFINITION_OF_DONE` when the table is absent.
- `load`: read the file at the repository root.
- `parse`: validate a parsed TOML mapping.
- `ConfigError`: raised for any invalid key.

## Collaborations

Arrows go from the caller to the callee.

```mermaid
flowchart LR
  checks --> config
  cli --> config
  context --> config
  flow --> config
```

## Reference

See the generated [JSON Schema of `ariane.toml`](../../reference/ariane.toml.schema.json), generated from the code (`scripts/generate_docs.py`).

## Serves

C22, C26; ADR 0003, ADR 0023. See [the component view](../3-components.md).
