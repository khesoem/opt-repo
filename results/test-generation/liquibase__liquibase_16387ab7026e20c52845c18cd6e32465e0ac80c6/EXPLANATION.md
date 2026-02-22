GeneratedPerformanceTests

This test file (liquibase.statement.GeneratedPerformanceTests) was added to exercise the performance-sensitive code path in ExecutablePreparedStatementBase.applyColumnParameter when handling valueBlobFile for Postgres databases.

What the test does:
- Registers a SnapshotGenerator that causes SnapshotGeneratorFactory to return a Column with type "bytea" for any column requested. This triggers the Postgres-specific branch in applyColumnParameter where the code checks snapshot.getType().getTypeName().equalsIgnoreCase("bytea").
- Repeats applyColumnParameter numerous times (200 iterations) with mocked ColumnConfig and a small InputStream to simulate many changesets inserting binary data.
- Uses lenient Mockito stubbings to avoid strict unnecessary stubbing errors in the test runner.

Why this demonstrates the improvement:
- The upstream issue described a performance regression when many valueBlobFile columns are processed on Postgres due to snapshot generation overhead. The patched version reduces snapshot work by using SnapshotControl when creating the Column snapshot. By repeatedly exercising the code path that looks up the column snapshot, the test amplifies the performance difference between the original and patched code. When running the test in the original and patched repositories, you should observe the test's Time elapsed log line to be smaller in the patched_repo run.

How to run the test:

From repository root run:
  ./mvnw -pl liquibase-standard -am test -Dtest=liquibase.statement.GeneratedPerformanceTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

Files produced by this change:
- /workspace/tests_addition_diff.patch : unified diff between the test in original and patched copy (apply to repo to add/modify the test)
- /workspace/improvement_tests.txt : list containing the fully-qualified test class name
- /workspace/EXPLANATION.md : this explanation file
