package org.keycloak.broker.saml.mappers;

import org.junit.jupiter.api.Test;
import org.keycloak.broker.provider.BrokeredIdentityContext;
import org.keycloak.broker.provider.ConfigConstants;
import org.keycloak.models.IdentityProviderModel;
import org.keycloak.models.IdentityProviderMapperModel;
import org.keycloak.models.RealmModel;
import org.keycloak.models.RoleModel;
import org.keycloak.models.UserModel;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Microbenchmarks for AbstractAttributeToRoleMapper.updateBrokeredUser behavior
 * comparing scenarios affected by commit 47288a9.
 *
 * This is not a strict performance assertion test; it prints timings to stdout
 * so they can be compared across commits.
 */
public class AbstractAttributeToRoleMapperPerfTest {

    private static final String ROLE_NAME = "testRole";

    private static class AppliesTrueMapper extends AbstractAttributeToRoleMapper {
        @Override
        public String[] getCompatibleProviders() { return new String[] { "saml" }; }
        @Override
        public String getDisplayCategory() { return "perf"; }
        @Override
        public String getDisplayType() { return "applies-true"; }
        @Override
        public String getHelpText() { return "perf"; }
        @Override
        public java.util.List<org.keycloak.provider.ProviderConfigProperty> getConfigProperties() { return java.util.Collections.emptyList(); }
        @Override
        public String getId() { return "perf-applies-true"; }
        @Override
        protected boolean applies(IdentityProviderMapperModel mapperModel, BrokeredIdentityContext context) {
            return true;
        }
    }

    private static class AppliesFalseMapper extends AbstractAttributeToRoleMapper {
        @Override
        public String[] getCompatibleProviders() { return new String[] { "saml" }; }
        @Override
        public String getDisplayCategory() { return "perf"; }
        @Override
        public String getDisplayType() { return "applies-false"; }
        @Override
        public String getHelpText() { return "perf"; }
        @Override
        public java.util.List<org.keycloak.provider.ProviderConfigProperty> getConfigProperties() { return java.util.Collections.emptyList(); }
        @Override
        public String getId() { return "perf-applies-false"; }
        @Override
        protected boolean applies(IdentityProviderMapperModel mapperModel, BrokeredIdentityContext context) {
            return false;
        }
    }

    private static IdentityProviderMapperModel mapperModel() {
        IdentityProviderMapperModel m = new IdentityProviderMapperModel();
        m.setName("perf-mapper");
        Map<String, String> cfg = new HashMap<>();
        cfg.put(ConfigConstants.ROLE, ROLE_NAME);
        m.setConfig(cfg);
        return m;
    }

    private static RealmModel realm(RoleModel roleModel) {
        return (RealmModel) Proxy.newProxyInstance(
                RealmModel.class.getClassLoader(), new Class[]{RealmModel.class},
                new InvocationHandler() {
                    @Override
                    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
                        switch (method.getName()) {
                            case "getRole":
                                String rn = (String) args[0];
                                return ROLE_NAME.equals(rn) ? roleModel : null;
                            case "getName":
                                return "perf-realm";
                            default:
                                // Methods not used by this test
                                throw new UnsupportedOperationException("RealmModel method not supported in test: " + method.getName());
                        }
                    }
                });
    }

    private static RoleModel realmRole() {
        return (RoleModel) Proxy.newProxyInstance(
                RoleModel.class.getClassLoader(), new Class[]{RoleModel.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "isClientRole":
                            return false; // realm-level role
                        case "getName":
                            return ROLE_NAME;
                        default:
                            // keep identity equality semantics
                            if (method.getName().equals("equals")) {
                                return proxy == args[0];
                            }
                            if (method.getName().equals("hashCode")) {
                                return System.identityHashCode(proxy);
                            }
                            throw new UnsupportedOperationException("RoleModel method not supported in test: " + method.getName());
                    }
                });
    }

    private static class HeavyOpsCounter {
        volatile long count;
        void heavyWork() {
            // Simulate expensive backing store operation
            long x = count;
            for (int i = 0; i < 20000; i++) {
                x = x * 1664525L + 1013904223L; // LCG step
            }
            count = x;
        }
    }

    private static UserModel userWithRoleAlreadyAssigned(RoleModel targetRole, HeavyOpsCounter counter) {
        return (UserModel) Proxy.newProxyInstance(
                UserModel.class.getClassLoader(), new Class[]{UserModel.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "getRealmRoleMappingsStream":
                            // Stream includes the same instance -> role already mapped
                            return Stream.of(targetRole);
                        case "grantRole":
                            // Simulate expensive no-op write when role already present
                            counter.heavyWork();
                            return null;
                        case "deleteRoleMapping":
                            // Simulate expensive delete call (should be skipped in optimized code)
                            counter.heavyWork();
                            return null;
                        case "getId":
                            return "user-1";
                        case "getUsername":
                            return "user1";
                        default:
                            throw new UnsupportedOperationException("UserModel method not supported in test: " + method.getName());
                    }
                });
    }

    private static UserModel userWithoutRoleAssigned(RoleModel targetRole, HeavyOpsCounter counter) {
        return (UserModel) Proxy.newProxyInstance(
                UserModel.class.getClassLoader(), new Class[]{UserModel.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "getRealmRoleMappingsStream":
                            // Stream does not include target role instance -> role not mapped
                            return Stream.empty();
                        case "grantRole":
                            counter.heavyWork();
                            return null;
                        case "deleteRoleMapping":
                            counter.heavyWork();
                            return null;
                        case "getId":
                            return "user-2";
                        case "getUsername":
                            return "user2";
                        default:
                            throw new UnsupportedOperationException("UserModel method not supported in test: " + method.getName());
                    }
                });
    }

    private static BrokeredIdentityContext newContext() {
        return new BrokeredIdentityContext(new IdentityProviderModel());
    }

    private static long timeMillis(Runnable r) {
        long start = System.nanoTime();
        r.run();
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);
    }

    @Test
    public void perf_updateBrokeredUser_applies_true_role_already_present() {
        RoleModel role = realmRole();
        RealmModel realm = realm(role);
        HeavyOpsCounter counter = new HeavyOpsCounter();
        UserModel user = userWithRoleAlreadyAssigned(role, counter);
        IdentityProviderMapperModel mapper = mapperModel();
        AbstractAttributeToRoleMapper mapperImpl = new AppliesTrueMapper();

        final int iterations = 20000;
        // Warm-up
        for (int i = 0; i < 2000; i++) mapperImpl.updateBrokeredUser(null, realm, user, mapper, newContext());

        long tookMs = timeMillis(() -> {
            for (int i = 0; i < iterations; i++) {
                mapperImpl.updateBrokeredUser(null, realm, user, mapper, newContext());
            }
        });

        System.out.println("PERF: applies=true, role present -> updateBrokeredUser x" + iterations + " took " + tookMs + " ms, heavyOps=" + counter.count);
        assertTrue(tookMs >= 0); // non-flaky placeholder assertion
    }

    @Test
    public void perf_updateBrokeredUser_applies_false_role_absent() {
        RoleModel role = realmRole();
        RealmModel realm = realm(role);
        HeavyOpsCounter counter = new HeavyOpsCounter();
        UserModel user = userWithoutRoleAssigned(role, counter);
        IdentityProviderMapperModel mapper = mapperModel();
        AbstractAttributeToRoleMapper mapperImpl = new AppliesFalseMapper();

        final int iterations = 20000;
        // Warm-up
        for (int i = 0; i < 2000; i++) mapperImpl.updateBrokeredUser(null, realm, user, mapper, newContext());

        long tookMs = timeMillis(() -> {
            for (int i = 0; i < iterations; i++) {
                mapperImpl.updateBrokeredUser(null, realm, user, mapper, newContext());
            }
        });

        System.out.println("PERF: applies=false, role absent -> updateBrokeredUser x" + iterations + " took " + tookMs + " ms, heavyOps=" + counter.count);
        assertTrue(tookMs >= 0);
    }
}
