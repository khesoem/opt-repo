The test AsyncToSyncInvokerPerformanceTest simulates the behavior described in the issue: it creates an Invoker that returns a Result whose get() method sleeps briefly (simulating the expensive spin-wait observed in certain JDKs), while get(timeout, TimeUnit) is fast. The original AsyncToSyncInvoker called get() without a timeout; the patched version calls get(timeout, MILLISECONDS). Running the test in the original and patched repositories shows the patched version completes faster. The test prints a per-class elapsed time so the Maven surefire output includes timing.

Files added:
- dubbo-rpc/dubbo-rpc-api/src/test/java/org/apache/dubbo/rpc/protocol/AsyncToSyncInvokerPerformanceTest.java (added to both repositories for comparison)
- /workspace/tests_addition_diff.patch (git-style patch that adds the test file)
- /workspace/improvement_tests.txt (contains the fully qualified test class name)

How to run:
./mvnw -pl dubbo-rpc/dubbo-rpc-api -am test -Dtest=org.apache.dubbo.rpc.protocol.AsyncToSyncInvokerPerformanceTest -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs
