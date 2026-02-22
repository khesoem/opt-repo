The added JUnit test org.keycloak.broker.saml.mappers.GeneratedTests.performanceTestAvoidUnnecessaryGrant
is a synthetic performance test designed to amplify the runtime difference introduced by the patch to
AbstractAttributeToRoleMapper.

What the test does:
- Mocks a RoleModel, UserModel, RealmModel and other necessary types using Mockito.
- Configures the UserModel mock so that user.getRealmRoleMappingsStream() returns a stream containing the
  role. This represents the common case where the user already has the realm role.
- Mocks expensive side-effecting operations user.grantRole(...) and user.deleteRoleMapping(...) to sleep 10ms
  to simulate database operations / locking. The original implementation called these unconditionally when a
  mapper applied/mismatched; the patched implementation checks the existing mappings and avoids calling
  these methods when unnecessary.
- Calls mapper.updateBrokeredUser(...) many times (ITER=80) to amplify the difference so elapsed times are
  measurable in the Maven test output. The test prints the elapsed wall-clock time in milliseconds.

Why this demonstrates an improvement:
- On the original code, updateBrokeredUser would call user.grantRole(role) every time even if the user already
  had the role, which in this test triggers a 10ms sleep per iteration.
- On the patched code, the mapper first checks the existing role streams and will skip calling grantRole when
  the role is already present, avoiding the 10ms per-iteration cost.

Files produced:
- tests_addition_diff.patch: unified diff that adds the new test file under services/src/test/...
- improvement_tests.txt: contains the fully-qualified test class name to run
- EXPLANATION.md: this file explaining the test and how it demonstrates the improvement
