The test GeneratedTests.testConcurrentReadPerformance repeatedly reads from TableMetaData concurrently.
It stresses the Map returned by getColumns/getIndexes; in the original version the maps are wrapped with Collections.synchronizedMap which adds synchronization overhead on each access.
The patched version returns the plain LinkedHashMap which is faster for concurrent reads when external synchronization is not required for these usages.

The test measures elapsed time for many concurrent getColumnMetaData and isPrimaryKey invocations; the patched repo should show lower time.
