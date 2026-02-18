# Highly coupled tests

- CVE-2020-4053  Official PoC tests against `cleanJoin` helper function
- CVE-2021-36157 Official PoC references implementation detail `errInvalidTenantID`
- CVE-2023-30172 Official PoC tests against `validate_path_is_safe` helper function
- CVE-2023-34457 Official PoC included test for an additional API refactoring
- CVE-2024-21542 Official PoC tests against `SafeExtractor` implementation detail
- CVE-2024-24579 Official PoC references `tarVisitor` implementation detail

# Error handling mismatch (not sure if these should be overridden, may need to reconsider)

- CVE-2017-16083 Official PoC prevents any ../ segments
- CVE-2017-16198 Official PoC prevents any ../ segments
- CVE-2018-16482 Official patch "mangles the path"
- CVE-2020-10691 Error message mismatch
- CVE-2020-7687  Official PoC prevents any ../ segments
- CVE-2024-54132 Error message mismatch. Note it's still brittle as it performs a "contains" check for "path traversal"
- CVE-2024-45388 Error message mismatch
- CVE-2021-3281  Error message mismatch
- CVE-2018-3734  Official PoC prevents any ../ segments
