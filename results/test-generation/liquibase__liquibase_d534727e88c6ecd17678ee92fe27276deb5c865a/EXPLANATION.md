I added a JUnit test class liquibase.snapshot.GeneratedTests which simulates a slow
snapshot creation when the SnapshotControl contains many included types. The test
replaces the SnapshotGeneratorFactory singleton with a CustomMockSnapshotGeneratorFactory
that reports a large number of container types and sleeps for a duration proportional
to the number of included types before delegating to the existing mock snapshot
implementation.

This artificially amplifies the performance difference introduced by the fix in
SnapshotGeneratorFactory (passing the corrected SnapshotControl to the internal
createSnapshot call). Running the test on the original (slower) code will show
longer elapsed time compared to the patched (faster) code.

To run the test use the command described in the task. The test class fully
qualified name is listed in improvement_tests.txt.
