The added test GeneratedTests.performanceTest constructs proxies that simulate a slow getUserByUsername (10ms sleep) and a fast getUserById.

The original code called getUserByUsername(uuid) first, then getUserById(uuid) as fallback. The patched code swaps the order to call getUserById first, avoiding the slow username lookup for UUIDs.

The test builds a policy containing 200 UUIDs and measures the time to invoke toRepresentation() which resolves users. Because getUserByUsername is simulated as slow, the original behavior (username-first) will spend ~200 * 10ms = 2000ms per iteration more than the patched behavior (id-first). Running multiple iterations amplifies the measurable difference.

Files added:
- authz/policy/common/src/test/java/org/keycloak/authorization/policy/provider/user/GeneratedTests.java
- improvement_tests.txt (lists the fully-qualified test class name)

To apply the patch on a repository, the tests_addition_diff.patch is provided which adds the test file.

