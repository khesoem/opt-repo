Generated performance test

The test GeneratedTests creates a DataSource that returns a fresh mock Connection on each call. The mock Connection is set up so that getAutoCommit() returns false and setAutoCommit(true) sleeps for SLOW_MS milliseconds to simulate an expensive database operation when resetting autocommit during close().

The test runs two phases:
- Phase 1 (baseline): Creates and closes ITERATIONS transactions using JdbcTransactionFactory with default properties (skipSetAutoCommitOnClose is false by default).
- Phase 2 (skip enabled): Calls setProperties on the factory to set skipSetAutoCommitOnClose=true, then repeats the create/close loop.

On the original code this property is ignored, so both phases take roughly the same time. On the patched code the factory forwards the property and JdbcTransaction will skip the slow setAutoCommit(true) call in resetAutoCommit when the flag is true, so Phase 2 is faster by approximately ITERATIONS * SLOW_MS milliseconds.

Files added:
- src/test/java/org/apache/ibatis/transaction/jdbc/GeneratedTests.java : the JUnit test.
- improvement_tests.txt : list of test classes to run (one per line).
- tests_addition_diff.patch : a patch file containing the new test file so it can be applied to either repository.
