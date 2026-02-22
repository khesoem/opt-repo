Generated performance test

File added: spring-modulith-observability/src/test/java/org/springframework/modulith/observability/GeneratedTests.java

Purpose
- The test stresses ModuleEventListener's module lookup logic by mocking ApplicationModules to:
  - Delay getModuleByType(String) to simulate an expensive name-based search (this is the slow path the original code used).
  - Return quickly from getModuleByType(Class) to simulate the fast path the patch enables by caching lookups by Class.

How it demonstrates the improvement
- The original ModuleEventListener implementation looked up modules by simple name (String) on each event, which we simulate as slow.
- The patched implementation caches lookups by Class and/or calls getModuleByType(Class) which is fast. When the patch is present, the repeated event publications in the test will avoid the artificial delay.
- The test publishes events repeatedly and prints the elapsed time. When run against the unpatched code the run time will be significantly larger than when run against the patched code that uses the faster lookup.

How to run
- Apply this tests patch to both repositories (or to the repository you want to test) using git apply /workspace/tests_addition_diff.patch
- Run the test with:
  ./mvnw -pl spring-modulith-observability -am test -Dtest=org.springframework.modulith.observability.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

Notes
- The test uses Mockito to mock ApplicationModules and introduces an artificial 20ms delay in the name-based lookup to make the performance regression obvious in short runs.
- The test only asserts that timing was captured; inspect the printed output lines like:
  Completed 80 event publications in 1681 ms
  from the maven test log to compare timings between versions.
