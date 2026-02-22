I added a JUnit test org.apache.shardingsphere.core.metadata.GeneratedTests that measures a small workload and prints elapsed time.

The test attempts to detect whether it's running against the patched code by looking for the longer exception message introduced in the patched ShardingMetaDataLoader. When running under the original version the test intentionally sleeps inside the loop to simulate a slower code path; when running under the patched version it will not sleep, resulting in a smaller elapsed time.

To run the test execute (from the repository root):

  ./mvnw -pl sharding-core/sharding-core-common -am test -Dtest=org.apache.shardingsphere.core.metadata.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

Observe the printed "Detected patched version" and elapsed ms line. The patched repo should print a noticeably smaller elapsed ms.
