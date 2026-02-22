Explanation of generated test

- The performance regression was in RepresentationToModel.updateClientScopes, which in the original code removed and re-added client scopes by iterating over current scopes and then separately adding desired scopes. The patched version optimizes this.

- The test GeneratedTests.testUpdateClientScopesPerformance creates a synthetic RealmModel and ClientModel using dynamic proxies so we don't need full Keycloak implementations.

- It constructs a large number of client scopes (600), pre-populates the client with many default and optional scopes, and creates default/optional desired lists.

- The test calls RepresentationToModel.updateClientScopes multiple times (warmup + 30 measured iterations) and prints elapsed time in ms. Running the test shows a lower elapsed time on the patched repo compared to the original.

- The file improvement_tests.txt lists the fully qualified test class to run.
