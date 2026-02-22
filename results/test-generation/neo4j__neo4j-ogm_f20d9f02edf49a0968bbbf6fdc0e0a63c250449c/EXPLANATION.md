This change adds a JUnit test that measures the execution time of ClassInfo.getEndNodeReader() and ClassInfo.getStartNodeReader().

Rationale:
- The patch to ClassInfo caches the result of finding the @StartNode/@EndNode fields. The test repeatedly calls these methods many times to magnify the difference between the original (no caching) and patched (cached) implementations.

How to run:
- Apply the patch file to both original and patched repositories (git apply).
- Run the test with the maven command provided in the prompt, e.g.:
  ./mvnw -pl core -am test -Dtest=org.neo4j.ogm.metadata.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

The printed timing lines in the maven output for this test will show the total time spent in the loops. The patched version should show lower times due to the cached lookups.
