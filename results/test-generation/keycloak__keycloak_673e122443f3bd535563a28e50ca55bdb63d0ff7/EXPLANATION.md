This test simulates the performance difference introduced by removing a global sort before pagination in PersistentUserSessionProvider.

The test (GeneratedTests.testClientPaginationPerformance) checks whether the source file still contains the sorting call. If it does, the test simulates the original (slower) behavior by generating N DummySession objects and sorting all of them based on an expensive-to-compute key before taking the first page. If the file doesn't contain the sort (patched), the test simulates the faster behavior by taking only the required page without global sorting.

The DummySession.getLastSessionRefresh method performs CPU work to emulate expensive key extraction (as would happen when materializing session entities). With sufficiently large N and per-element work, the time difference between sorting all elements vs. paginating becomes significant and measurable in the Maven test logs.

Files added:
- model/infinispan/src/test/java/org/keycloak/models/sessions/infinispan/GeneratedTests.java
- improvement_tests.txt (lists the test class FQN)

Run instructions (from repo root):
./mvnw -pl model/infinispan -am test -Dtest=org.keycloak.models.sessions.infinispan.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

