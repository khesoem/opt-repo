Performance test for SecretGenerator optimizations

What I changed
- Added a JUnit test (PerformanceSecretGeneratorTest) which performs a large number of calls to SecretGenerator.generateSecureID() and SecretGenerator.randomBytesHex(16) to amplify the runtime difference between the original and patched implementations.

Why this test demonstrates improvement
- The patch replaces multiple StringBuilder/insert and repeated Random usage with a single SecureRandom and more efficient UUID and bytes handling. Calling generateSecureID() and randomBytesHex(...) many times makes the removed allocations and copy work obvious in wall-clock time.
- The test makes a modest warm-up (5,000 calls) to reduce JIT noise, then runs two heavy loops of 50,000 iterations each. This should produce measurable differences in the test timing printed by Maven's surefire plugin.

How to run
- Apply the patch to both repositories (if needed):
  git apply /path/to/tests_addition_diff.patch

- Run the test (example):
  ./mvnw -pl common -am test -Dtest=org.keycloak.common.util.PerformanceSecretGeneratorTest -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

- Compare the Time elapsed reported in Maven logs for the test class between the original and patched versions. The patched version should show a lower Time elapsed.

Notes and limitations
- I could not run the Maven build/tests in this environment because JDK is not installed (maven enforcer complains about Java 17 and the container does not have java/javac). Therefore I could not verify actual timings here. The test is designed to be deterministic and should compile and run in a proper Java 17 environment.

Files produced
- /workspace/tests_addition_diff.patch  (git patch that adds the test)
- /workspace/improvement_tests.txt   (one-line list with the fully-qualified test class name)
- /workspace/EXPLANATION.md          (this explanation)

