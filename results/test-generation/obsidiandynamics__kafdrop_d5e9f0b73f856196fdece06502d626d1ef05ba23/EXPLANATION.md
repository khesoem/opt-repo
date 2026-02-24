Generated performance test

What I added

- src/test/java/kafdrop/service/GeneratedTests.java: a JUnit test that simulates the original (slow) per-topic code paths and the patched (batched) fast code paths by providing a TestKafkaHighLevelConsumer and TestKafkaHighLevelAdminClient.

How the test works

- The test constructs a KafkaMonitorImpl backed by the test doubles (TestKafkaHighLevelConsumer and TestKafkaHighLevelAdminClient).
- The test doubles implement both the old (per-topic) and new (batched) APIs used by the original and patched kafdrop code.
  - getTopicInfos(String[] topics) and getPartitionSize(String topic) simulate slow per-topic behavior by sleeping proportional to the number of topics or partitions.
  - getAllTopics(), getTopicInfos(Map<String, List<PartitionInfo>> allTopicsMap, String[] topics) and setTopicPartitionSizes(List<TopicVO>) simulate the batched, faster behavior by performing a single, shorter sleep and returning data for all topics at once.
- The test calls monitor.getTopics() and prints the time taken. The Maven test report will also include the elapsed time for the test class; the patched repository should exercise the fast paths and therefore show a shorter elapsed time compared to the original repository.

Notes and instructions

- To run the test (from the repository root):
  ./mvnw -pl . -am test -Dtest=kafdrop.service.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

- The improvement is visible by comparing the "Time elapsed" line for the GeneratedTests class when running the test in the original and patched repositories. The patched version should be faster because KafkaMonitorImpl in the patched repo calls the batched APIs (getAllTopics, getTopicInfos with the allTopics map and setTopicPartitionSizes).

Limitations

- The CI environment used to verify this patch must have Maven (or the Maven wrapper files present) available. In this workspace the maven wrapper couldn't be executed because the wrapper jar/properties were not present at the expected path; however the test files and patch are ready.
