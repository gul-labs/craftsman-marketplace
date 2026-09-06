# Layout templates (producer-keyed overrides)

`doc_types.py` carries the label regexes printed on the **IRS** form. Most
issuers follow them. Some do not: a payroll bureau prints "Gross Taxable Wages"
where the IRS prints "Wages, tips, other compensation", and the anchor parse
finds nothing.

A template is the narrow escape hatch for that case. It never changes what a
box *means* — only where on the page its value is found.

## How selection works

`form_parser.py` loads every `*.json` in this directory, and picks the **first**
whose `match` block hits the PDF's own metadata (`/Producer`, `/Creator`, read
with `pdfinfo`). An empty `match` never matches, which is why `generic.json` is
inert. The chosen template's name is recorded in `_extraction.template`, so a
parse always says which layout assumptions it ran under.

## Schema

```json
{
  "match":   {"producer": "<regex>", "creator": "<regex>"},
  "doc_type": "W-2",
  "box_patterns": {"box_1": ["<regex>", "<regex>"]},
  "value_side": "right"
}
```

| Key | Meaning |
|---|---|
| `match.producer` / `match.creator` | Case-insensitive regexes against the PDF metadata. All keys present must hit. |
| `doc_type` | Optional. When set, the template only applies to that registry type. |
| `box_patterns` | `{box_id: [regex, …]}` — **replaces** the registry patterns for that box. Box ids come from `doc_types.py`. |
| `value_side` | `right` (default): the value follows the label on the same line. `below`: the value sits under the label's own column. |

## Adding one

1. Run `pdfinfo <vendor>.pdf` and copy the `Producer` / `Creator` strings.
2. Run `pdftotext -layout <vendor>.pdf -` and find the labels the vendor actually prints.
3. Write `<vendor>.json` with `match` and only the boxes that need overriding.
4. Re-parse and confirm the previously missing boxes now read.

Do not add a template speculatively. An unverified `match` regex that hits the
wrong PDF silently changes how a real tax document is read — worse than no
template at all. `example-vendor.json.example` is a shape reference, not a
working override, which is why it carries an extension the loader ignores.
