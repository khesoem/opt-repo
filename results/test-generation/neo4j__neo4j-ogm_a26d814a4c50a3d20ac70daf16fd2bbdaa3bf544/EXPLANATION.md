Explanation of generated performance test

We added a single JUnit test org.neo4j.ogm.metadata.GeneratedPerformanceTest

Purpose:
- The patch removed the unnecessary 'synchronized' modifier from ClassInfo.postLoadMethodOrNull().
- The test stresses concurrent calls to this method from many threads to amplify synchronization overhead.

Test details:
- Creates a ClassInfo for a simple TestEntity that declares one @PostLoad method.
- Warms up by calling postLoadMethodOrNull() once to ensure initialization.
- Launches THREADS (32) threads, each calling postLoadMethodOrNull() ITERATIONS (10000) times.
- Measures wall-clock time for all concurrent calls and prints the elapsed time.

How to run:
- Apply the patch in tests_addition_diff.patch to both original and patched repos.
- Run the test with Maven (core module):
  ./mvnw -pl core -am test -Dtest=org.neo4j.ogm.metadata.GeneratedPerformanceTest -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

Expected outcome:
- The patched version (where the public method is not synchronized) should show a lower elapsed time than the original version (where it is synchronized).

Notes:
- The test is intentionally heavy to amplify the effect; you can reduce THREADS or ITERATIONS if needed to fit time constraints.
