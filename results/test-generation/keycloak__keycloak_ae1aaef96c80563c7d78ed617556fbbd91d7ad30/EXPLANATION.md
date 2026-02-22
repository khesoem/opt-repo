This test stresses the RequiredActionProviderModel.RequiredActionComparator by repeatedly sorting lists of RequiredActionProviderModel instances.

The original implementation re-creates a delegate comparator on each compare invocation which adds overhead. The patched version re-uses a single comparator instance.

The test performs several warmup sorts, then times a number of sorts (200) on a list of 2000 elements. The printed time should be smaller on the patched version compared to the original.

To run the test after applying the patch to a repo, use:

./mvnw -pl server-spi -am test -Dtest=org.keycloak.models.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs -DtrimStackTrace=false -q
