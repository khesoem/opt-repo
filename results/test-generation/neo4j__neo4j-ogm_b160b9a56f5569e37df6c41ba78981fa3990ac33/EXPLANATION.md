The added test RelationshipCachingPerformanceTest stresses FieldInfo.relationship() by repeatedly
calling it for a class with many non-primitive fields (treated as relationship fields).

On the patched code the relationship() result is cached, so repeated calls are much faster.
The test fails if the repeated calls loop takes longer than 1200 ms on CI, which is expected to
be true for the original (slower) version and false for the patched (faster) version.
