Generated performance test

What the test does

- Adds a single JUnit test class com.alibaba.otter.canal.common.GeneratedTests.
- The test constructs an in-memory Message containing 400 row entries (protobuf Entry objects).
- It then uses reflection to detect whether the patched MQMessageUtils API (buildMessageData + new messageConverter signature) is present.
  - If patched API exists, the test invokes buildMessageData(message, executor) to let MQMessageUtils parse/prepare EntryRowData in parallel using the executor,
    and then calls messageConverter(datas, id) to build FlatMessage objects from the prepared datas.
  - If the patched API is not present (original code), the test falls back to calling messageConverter(message) which performs the original, serial conversion.
- The test measures only the conversion path (after a short warm-up) using System.nanoTime and prints elapsed seconds.

Why this shows an improvement

- The provided patch parallelizes CPU-heavy protobuf parsing/RowChange processing via buildMessageData and uses thread pools in producers. The original implementation parsed everything serially.
- The GeneratedTests performance measurement focuses on exactly that work (parsing RowChange and converting to FlatMessage), so the patched code should show lower elapsed time when run on the patched repository vs the original one.

How to apply the test and run it

1) From the root of original_repo and patched_repo you can apply the patch file produced here:

   git apply /path/to/tests_addition_diff.patch

   (You can run the same command in both repositories. The patch only adds server/src/test/java/..., so it should apply cleanly to both.)

2) Run the test provided in the task description (adjust path to mvnw or use mvn if you have Maven installed):

   ./mvnw -pl deployer,server -am test -Dtest=com.alibaba.otter.canal.common.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs -DtrimStackTrace=false

   Or if mvnw is missing and you have maven installed system-wide:

   mvn -pl deployer,server -am test -Dtest=com.alibaba.otter.canal.common.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs -DtrimStackTrace=false

3) Compare the printed elapsed time (and the surefire summary line in the maven log) between the original and patched repositories. The patched repository should report a smaller "Time elapsed" for the test class and a smaller printed "PERF Test message conversion elapsed" value.

Notes about the execution environment used here

- I attempted to run the tests in this environment, but the repositories don't include a working maven wrapper (the mvnw files are present but the wrapper JAR / main class was not runnable here), and maven is not installed in the environment (mvn: command not found). Therefore I could not execute the tests here. The test files and patch were created and placed in /workspace so you can run them locally or in CI where Maven is available.

Contact me if you want me to (a) convert this to a JMH benchmark, (b) add more test cases or larger message sizes, or (c) run the tests in an environment that has Maven/wrapper available.
