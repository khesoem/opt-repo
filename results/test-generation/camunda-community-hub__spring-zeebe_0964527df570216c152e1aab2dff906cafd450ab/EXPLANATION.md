Generated performance test (GeneratedTests) repeatedly invokes the JobHandlerInvokingSpringBeans.handle(...) method to expose the overhead of parameter mapping.

Why it demonstrates improvement:
- The original implementation computes and maps parameters for each invocation using reflection, building objects and doing JSON mapping repeatedly.
- The patched implementation precomputes ParameterResolver instances (one per parameter) and uses them on each invocation. This reduces per-invocation reflection and branching.
- The test runs the handler many times (ITERATIONS=5000) to make the time difference visible in Maven's test output. Compare the "Time elapsed" line between original and patched runs; the patched version should be faster.

How the test works:
- It builds a MethodInfo for a sample worker method and constructs a JobHandlerInvokingSpringBeans instance reflectively (supports both constructor shapes present in original and patched code).
- It uses dynamic proxies for ActivatedJob and JobClient to avoid pulling in Zeebe runtime.
- The test measures wall-clock time for many invocations and prints the elapsed seconds to stdout. The maven surefire output also contains the Time elapsed for the test.

Files added:
- spring-client-zeebe/src/test/java/io/camunda/zeebe/spring/client/performance/GeneratedTests.java
- improvement_tests.txt (list of fully qualified test class to run)
