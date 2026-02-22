I added a JUnit test that stresses the contention in DriverExecutionPrepareEngine's constructor
by concurrently creating many instances from multiple threads. The original version called
ConcurrentHashMap.computeIfAbsent(...) directly in the constructor which can be slower under
concurrent calls due to a known JDK issue; the patched version uses a pre-get then computeIfAbsent
pattern to reduce contention.

Test details:
- Class: org.apache.shardingsphere.infra.executor.sql.prepare.driver.GeneratedTests
- Method: testDriverExecutionPrepareEngineContention
- It spins up 40 threads and each thread constructs 300 DriverExecutionPrepareEngine instances
  (12,000 total). The test prints elapsed milliseconds. Running the test on both versions
  should show that the patched version completes faster.

Note: the environment used for automatic verification may not have a working Java/Maven setup.
If you run locally, execute:

  ./mvnw -pl shardingsphere-infra/shardingsphere-infra-executor -am test -Dtest=org.apache.shardingsphere.infra.executor.sql.prepare.driver.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs
