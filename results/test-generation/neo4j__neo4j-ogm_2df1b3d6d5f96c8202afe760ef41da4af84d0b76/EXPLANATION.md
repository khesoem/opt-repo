The added JUnit test org.neo4j.ogm.metadata.GeneratedTests.performanceMissingSimpleName
is a micro-benchmark that stresses DomainInfo.getClassSimpleName for the case
where a simple class name is not present in the internal class map. The original
implementation scanned the entire key set using a regex on each lookup; the
patched implementation caches the (negative or positive) lookup result which
makes repeated lookups much faster.

The test populates DomainInfo.classNameToClassInfo with many fake entries and
performs a large number of repeated lookups for a non-existing simple name.
When running the test on both the original and patched repositories, compare
the Maven test Time elapsed line for this test class — the patched version
should show a significantly lower elapsed time.

This file explains the purpose of the test and how it demonstrates the
performance improvement.
