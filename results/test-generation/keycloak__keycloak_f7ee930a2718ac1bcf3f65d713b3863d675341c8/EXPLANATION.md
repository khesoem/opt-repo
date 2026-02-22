These tests exercise the change that removed the remote get in RemoteInfinispanNotificationManager by simulating both behaviors:

- For the original implementation (slower), the manager calls getAsync on the remote cache, which we simulate with a CompletableFuture that completes after REMOTE_DELAY_MS (250ms).
- For the patched implementation (faster), the manager receives event data containing both key and value (raw bytes) and uses the marshaller to extract the WrapperClusterEvent without performing a remote call. We simulate this by invoking the onEntryUpdated method with crafted raw bytes and providing a fake Marshaller implementation via the RemoteCacheManager proxy.

The test registers a ClusterListener for the event key and measures elapsed time from invoking the event handler until the listener is called. When run against the original repo the test should show a longer Time elapsed reported by Maven than when run against the patched repo.

Files added:
- model/infinispan/src/test/java/org/keycloak/cluster/infinispan/GeneratedTests.java
- improvement_tests.txt (lists the fully qualified test class name)

Run with:
./mvnw -pl model/infinispan -am test -Dtest=org.keycloak.cluster.infinispan.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs
