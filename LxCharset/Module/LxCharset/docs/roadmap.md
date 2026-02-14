# LxCharset Roadmap

1. Core: implement byte-pattern heuristics (UTF-8 validity, BOM detection).
2. Core: add baseline scoring for legacy encodings (cp1250/cp1252/iso-8859-*).
3. Logics: implement multi-stage ranking and confidence aggregation pipeline.
4. Add C++/Python binding and benchmark against current decode path.
5. Integrate into app only after parity tests and crash/regression checks.
