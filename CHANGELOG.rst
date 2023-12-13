
Changelog
=========

0.3.2 (unreleased)
------------------
- Fix missing of groups in `obr run --list-operations` view, see https://github.com/hpsim/OBR/pull/159. 

0.3.0 (unreleased)
------------------
- Add common notation see https://github.com/hpsim/OBR/pull/146
- Make numberOfSubdomains argument in yaml consistent see https://github.com/hpsim/OBR/pull/148
- Make view folders relative see https://github.com/hpsim/OBR/pull/164

0.2.0 (2023-09-14)
------------------
- Add --json=file.json option to obr query, which writes the result of the query to a json file.
- Add --validate=file.json option to obr query. If the query results are not identical to the provided json file it will return with a failure exit code.
  For validation either raw json files can be used or json schema, cf. json-schema.org
- Fixes Issue #144 of non working obr run command
- Make -t=1 the default option for obr run -o runParallelSolver

0.0.0 (2022-01-13)
------------------

* First release on PyPI.
