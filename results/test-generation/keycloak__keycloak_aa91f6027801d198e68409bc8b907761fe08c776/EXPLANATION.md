I added a JUnit test DefaultEvaluationPerformanceTest that exercises DefaultEvaluation.getUser lookup path by repeatedly calling isUserInRealmRole.

The test creates dynamic proxy stubs for KeycloakSession, KeycloakContext, RealmModel, UserProvider and ClientModel. The UserProvider proxy simulates expensive lookups by sleeping a few milliseconds on each user lookup method (getUserById/getUserByUsername/getUserByEmail/getServiceAccount). The DefaultEvaluation implementation in the patched code caches lookups in the KeycloakSession attribute; the original code did not cache nulls and could re-run expensive lookups many times. The test measures total elapsed time printing it to the test logs; when run against the patched repository the elapsed time should be lower because of caching introduced by the patch.

Run the test via:
  ./mvnw -pl server-spi-private -am test -Dtest=org.keycloak.performance.DefaultEvaluationPerformanceTest -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

Files added (to be applied to both original and patched):
  server-spi-private/src/test/java/org/keycloak/performance/DefaultEvaluationPerformanceTest.java

The improvement test class is listed in improvement_tests.txt
