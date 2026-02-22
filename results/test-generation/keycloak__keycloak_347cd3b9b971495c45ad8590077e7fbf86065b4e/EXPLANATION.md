The generated test org.keycloak.userprofile.GeneratedTests.performance_noErrorValidation repeatedly calls DefaultUserProfile.validate() where Attributes.validate(...) will execute without producing ValidationErrors. The patch replaces always-constructed ValidationException with a lazy ValidationExceptionBuilder that only creates a real ValidationException when there are errors. The test measures total time of many validate() calls; on the patched code the absence of exception creation reduces allocation and stacktrace overhead and the printed total time should be lower.

Run the tests with:
./mvnw -pl :keycloak-server-spi-private -am test -Dtest=org.keycloak.userprofile.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs
