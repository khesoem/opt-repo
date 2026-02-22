This generated JUnit test measures the performance of detecting write-cypher
keywords. It reflects the private static Pattern WRITE_CYPHER_KEYWORDS from the
ExecuteQueriesDelegate class and then repeatedly matches a cypher string
against it. The test detects whether the pattern is case-insensitive (patched
version) or not (original) and uses the matching strategy accordingly: either
pattern.matcher(cypher) or pattern.matcher(cypher.toUpperCase()). The patched
version uses a CASE_INSENSITIVE pattern and therefore avoids toUpperCase(),
which should show as a lower elapsed time when running the test in the patched
repository.
