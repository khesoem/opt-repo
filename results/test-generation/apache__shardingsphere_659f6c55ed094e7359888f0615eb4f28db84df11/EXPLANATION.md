I added a JUnit performance test ShadowInsertColumnPerformanceTest that constructs a large LinkedList of ColumnSegment instances and repeatedly calls ShadowInsertColumnTokenGenerator.generateSQLTokens().

Rationale:
- The original issue described excessive random access of LinkedList; the test uses LinkedList to trigger the poor behavior.
- By running many iterations and many elements (1000 columns x 50 iterations), the total time amplifies the difference between the original and patched versions.

Files added:
- shardingsphere-features/shardingsphere-shadow/shardingsphere-shadow-core/src/test/java/.../ShadowInsertColumnPerformanceTest.java
- improvement_tests.txt lists the fully qualified test class name.

How to run:
Run the test class with the provided mvnw command in original/patched repo roots. The test prints a total time (ms) which you can compare between versions.

