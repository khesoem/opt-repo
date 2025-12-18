package org.keycloak.broker.saml.mappers;

import org.junit.Test;
import org.keycloak.broker.provider.BrokeredIdentityContext;
import org.keycloak.models.IdentityProviderMapperModel;
import org.keycloak.broker.provider.ConfigConstants;
import org.keycloak.models.*;
import org.keycloak.models.utils.KeycloakModelUtils;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Stream;

import static org.junit.Assert.assertTrue;

public class AttributeToRoleMapperPerformanceTest {

    private static final int ITERATIONS = 80;

    private static class DummyMapper extends AbstractAttributeToRoleMapper {
        private final boolean applies;
        public DummyMapper(boolean applies) { this.applies = applies; }
        @Override
        protected boolean applies(IdentityProviderMapperModel mapperModel, BrokeredIdentityContext context) {
            return applies;
        }
        @Override public String getDisplayCategory() { return "test"; }
        @Override public String getDisplayType() { return "test"; }
        @Override public String[] getCompatibleProviders() { return new String[0]; }
        @Override public String getId() { return "test"; }
        @Override public java.util.List<org.keycloak.provider.ProviderConfigProperty> getConfigProperties() { return java.util.Collections.emptyList(); }
        @Override public String getHelpText() { return ""; }
    }

    // Use dynamic proxies to create lightweight RoleModel/RealmModel/UserModel implementations so we don't need
    // to implement the full interfaces in the test.
    private RoleModel createRole(final String name) {
        return (RoleModel) java.lang.reflect.Proxy.newProxyInstance(
                RoleModel.class.getClassLoader(),
                new Class[]{RoleModel.class},
                (proxy, method, args) -> {
                    String m = method.getName();
                    if (m.equals("getName")) return name;
                    if (m.equals("getId")) return name;
                    if (m.equals("getDescription")) return null;
                    if (m.equals("isClientRole")) return false;
                    if (m.equals("getContainerId")) return null;
                    if (m.equals("equals")) {
                            if (args == null || args.length != 1 || args[0] == null) return false;
                            Object o = args[0];
                            if (o instanceof RoleModel) return name.equals(((RoleModel)o).getName());
                            return name.equals(o.toString());
                        }
                    if (m.equals("hashCode")) return name.hashCode();
                    if (method.getReturnType().isPrimitive()) return 0;
                    return null;
                }
        );
    }

    private RealmModel createRealm(final RoleModel role) {
        return (RealmModel) java.lang.reflect.Proxy.newProxyInstance(
                RealmModel.class.getClassLoader(),
                new Class[]{RealmModel.class},
                (proxy, method, args) -> {
                    String m = method.getName();
                    if (m.equals("getRole")) {
                        String name = (String) args[0];
                        return name.equals(role.getName()) ? role : null;
                    }
                    if (m.equals("getClientByClientId")) return null;
                    if (method.getReturnType().isPrimitive()) return 0;
                    return null;
                }
        );
    }

    private static class UserHandler implements java.lang.reflect.InvocationHandler {
        private final RoleModel presentRole;
        private final AtomicInteger grantCalls = new AtomicInteger();
        private final AtomicInteger deleteCalls = new AtomicInteger();
        UserHandler(RoleModel presentRole) { this.presentRole = presentRole; }
        public Object invoke(Object proxy, java.lang.reflect.Method method, Object[] args) throws Throwable {
            String m = method.getName();
            if (m.equals("getRealmRoleMappingsStream")) return java.util.stream.Stream.of(presentRole);
            if (m.equals("getClientRoleMappingsStream")) return java.util.stream.Stream.empty();
            if (m.equals("grantRole")) { grantCalls.incrementAndGet(); Thread.sleep(12); return null; }
            if (m.equals("deleteRoleMapping")) { deleteCalls.incrementAndGet(); Thread.sleep(12); return null; }
            if (m.equals("getId")) return "u";
            if (m.equals("getUsername")) return "u";
            if (method.getReturnType().isPrimitive()) return 0;
            return null;
        }
        int getGrantCalls() { return grantCalls.get(); }
        int getDeleteCalls() { return deleteCalls.get(); }
    }

    private UserModel createExpensiveUser(RoleModel presentRole, UserHandler[] outHandler) {
        UserHandler h = new UserHandler(presentRole);
        outHandler[0] = h;
        return (UserModel) java.lang.reflect.Proxy.newProxyInstance(
                UserModel.class.getClassLoader(),
                new Class[]{UserModel.class},
                h
        );
    }
    
    @Test
    public void testUpdateBrokeredUserPerformanceWhenRoleAlreadyPresent() {
        RoleModel role = createRole("myrole");
        RealmModel realm = createRealm(role);

        IdentityProviderMapperModel mapperModel = new IdentityProviderMapperModel();
        mapperModel.setConfig(new HashMap<>());
        mapperModel.getConfig().put(ConfigConstants.ROLE, "myrole");

        BrokeredIdentityContext context = new BrokeredIdentityContext(null);

        UserHandler[] h = new UserHandler[1];
        UserModel user = createExpensiveUser(role, h);
        DummyMapper mapper = new DummyMapper(true);

        long start = System.nanoTime();
        for (int i = 0; i < ITERATIONS; i++) {
            mapper.updateBrokeredUser(null, realm, user, mapperModel, context);
        }
        long elapsedMs = (System.nanoTime() - start) / 1_000_000;

        // On the optimized version grantRole should not be called because role is already present
        // so grantCalls should be 0 && elapsed should be small. Use a loose upper bound to avoid flakiness
        assertTrue("Expected no grantRole calls, but got " + h[0].getGrantCalls(), h[0].getGrantCalls() == 0);
        assertTrue("Elapsed too large: " + elapsedMs + "ms", elapsedMs < ITERATIONS * 5L + 200);
    }
}
