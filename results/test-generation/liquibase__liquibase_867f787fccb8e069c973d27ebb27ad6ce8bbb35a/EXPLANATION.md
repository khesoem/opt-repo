I added two JUnit tests that exercise StringUtil.randomIdentifier heavily.

1) liquibase.util.GeneratedPerformanceTest
   - Single-threaded loop of 300k iterations (plus warmup) calling randomIdentifier(32).
   - Prints elapsed time; includes a trivial assertion to avoid dead code elimination.

2) liquibase.util.GeneratedPerformanceConcurrencyTest
   - Multi-threaded test using N threads (number of processors) with 200k iterations per thread.
   - Measures concurrent performance of randomIdentifier.

These tests target the change in StringUtil.randomIdentifier which replaced RandomStringUtils (which could use SecureRandom internally) with ThreadLocalRandom and a custom alphabet. The patched version should avoid SecureRandom blocking and be faster, especially on fresh VMs with low entropy.

Files added are listed in tests_addition_diff.patch and the test class names are in improvement_tests.txt.
