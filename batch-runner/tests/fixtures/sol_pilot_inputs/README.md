# Exact registered public input bytes

These three files are unmodified inputs from `openai/gdpval` at revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, retained so the one-task regression
does not mock input integrity, change registered hashes or download data in CI.
The parquet is the original 220-row file; the adapter reads only the registered
five task projections. The two reference files are their complete input closure.

Source: <https://huggingface.co/datasets/openai/gdpval/tree/11e7900cdcac61bc4daf59e65feb238acda98fbf>.
Dataset attribution/terms remain those of that upstream snapshot. These are not
private Task4 results, generated answers, model responses or grading results.

| File | SHA256 |
| --- | --- |
| `data/train-00000-of-00001.parquet` | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` |
| `reference_files/bb09ca2a9999b404d7fced9202b42949/Work Time Study - Source.xlsx` | `bb09ca2a9999b404d7fced9202b42949cd9f142f39554e254bac77b3686dae9e` |
| `reference_files/901e943a97328a661f9e704ae43eeea1/Acquisition Criteria (2).pdf` | `901e943a97328a661f9e704ae43eeea167e7805385a99322f1c24f8e159125c4` |
