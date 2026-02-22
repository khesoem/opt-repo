This patch adds a JUnit test class org.keycloak.events.jpa.GeneratedTests which inserts 3000 EventEntity and 3000 AdminEventEntity rows into an in-memory H2 database and measures the time to fetch all events and admin events via JpaEventStoreProvider.

The upstream patch for model/jpa marks queries as read-only (by setting the Hibernate hint AvailableHints.HINT_READ_ONLY=true) when creating TypedQuery in JpaEventQuery and JpaAdminEventQuery. These tests exercise those code paths and should show reduced execution time in the patched version where queries are read-only.

Files produced by this run:
- /workspace/tests_addition_diff.patch : unified patch that adds the test class to model/jpa/src/test/java/org/keycloak/events/jpa/GeneratedTests.java
- /workspace/improvement_tests.txt : list with the fully-qualified test class name
- /workspace/EXPLANATION.md : this explanation

To run the tests (from project root):
./mvnw -pl model/jpa -am test -Dtest=org.keycloak.events.jpa.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs -DtrimStackTrace=false -q
