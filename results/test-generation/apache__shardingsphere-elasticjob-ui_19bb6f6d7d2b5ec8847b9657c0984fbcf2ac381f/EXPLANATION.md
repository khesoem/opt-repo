These tests measure the runtime cost of AuthenticationFilter.respondWithUnauthorized when invoked repeatedly.

What the tests do
- Two JUnit tests were added (one for cloud backend, one for lite backend) at:
  - shardingsphere-elasticjob-cloud-ui/.../GeneratedTests.java
  - shardingsphere-elasticjob-lite-ui/.../GeneratedTests.java
- Each test repeatedly triggers the filter in a scenario where the access token is missing so respondWithUnauthorized() is executed.
- The test performs a warm-up loop (500 iterations) and then a timed loop (20,000 iterations) and prints the elapsed seconds.
- A simple assertion checks the response contains the text "Unauthorized" to ensure the filter executed.

Why this shows improvement
- The original code created a new Gson() inside respondWithUnauthorized for each invocation; the patched code uses a single existing gson instance.
- Creating many Gson instances is relatively expensive. By invoking the method many times the test amplifies the difference so the patched version should complete the timed loop faster.

How to run
- Apply the patch to your repository root with:
  git apply /path/to/tests_addition_diff.patch
- Run the tests with Maven (example for the cloud test):
  ./mvnw -pl shardingsphere-elasticjob-cloud-ui/shardingsphere-elasticjob-cloud-ui-backend,shardingsphere-elasticjob-lite-ui/shardingsphere-elasticjob-lite-ui-backend -am test -Dtest=org.apache.shardingsphere.elasticjob.cloud.ui.security.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs
- Compare the reported "Time elapsed" for the test class between the original and patched branches.

Notes
- The environment used to run the build must have a compatible JDK for the project. In this workspace a Maven build previously showed a javac-related error; if you see similar errors, run the build with a Java version matching the project's requirements.
