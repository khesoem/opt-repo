This test (io.prestosql.spi.type.GeneratedTests) measures the time spent repeatedly calling
HashSet.contains(...) on TypeSignature instances. The patch in the project caches the
TypeSignature.hashCode() result, which should significantly reduce the cost of repeated
hashCode() computations when the same instances are looked up many times.

Test details:
- The test builds 500 distinct TypeSignature instances (parametric types) and inserts them
  into a HashSet.
- It then performs 200,000 contains() calls cycling through the 500 instances, timing
  only the loop of contains() calls.
- The patched version (with cached hashCode) should execute this loop faster than the
  original version because hashCode() is computed once per instance and reused.

To run the test (from project root):
./mvnw -pl presto-spi -am test -Dtest=io.prestosql.spi.type.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

The file tests_addition_diff.patch can be applied to the project root with:
    git apply /path/to/tests_addition_diff.patch
