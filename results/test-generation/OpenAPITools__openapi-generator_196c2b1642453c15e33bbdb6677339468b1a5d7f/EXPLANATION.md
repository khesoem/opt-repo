This performance test creates a large output directory (1000 files) and then executes the maven plugin
with skipIfSpecIsUnchanged=true and cleanupOutput=true. In the original code cleanupOutput is executed
before the check that skips generation, so the large directory is deleted on every run even when the
spec hasn't changed. In the patched version cleanupOutput is evaluated after skipIfSpecIsUnchanged, so
when the plugin detects the spec hasn't changed it skips generation and avoids deleting the directory,
resulting in a faster execution time.

The test does not assert on timing — it simply forces the expensive deletion to occur in the original
version and prints the execution time. You can compare the reported "Time elapsed" in the maven test
output between the original and patched versions to observe the improvement.
