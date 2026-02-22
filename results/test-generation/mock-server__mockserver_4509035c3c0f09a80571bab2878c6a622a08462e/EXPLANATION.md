The added test org.mockserver.benchmark.HttpStateGcPerformanceTest repeatedly calls HttpState.handle for the /mockserver/clear endpoint and HttpState.reset, operations which in the original code invoked System.gc(). The patch removed those explicit System.gc() calls.

The test uses a synchronous Scheduler to avoid background threads affecting timing and prints the elapsed time for the repeated clear and reset calls. When run on the original repository (with System.gc calls present) the test should take longer to complete than on the patched repository (without System.gc calls).

Files added:
- mockserver-core/src/test/java/org/mockserver/benchmark/HttpStateGcPerformanceTest.java
- improvement_tests.txt (lists the fully qualified test class name)

To run the test for the mockserver-core module use:

./mvnw -pl mockserver-core -am test -Dtest=org.mockserver.benchmark.HttpStateGcPerformanceTest -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs -DtrimStackTrace=false

Compare the Time elapsed reported by Maven between the original and patched versions; the patched version should be faster.
