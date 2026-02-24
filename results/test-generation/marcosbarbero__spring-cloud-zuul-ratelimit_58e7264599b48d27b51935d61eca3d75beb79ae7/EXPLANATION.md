Generated performance test

I added a JUnit test class com.marcosbarbero.cloud.autoconfigure.zuul.ratelimit.GeneratedTests which runs many repeated calls to
RateLimitPreFilter.shouldFilter() and RateLimitPreFilter.run() in a tight loop and prints the elapsed time for each loop.

This stresses the code paths changed by the patch: caching route and policy objects in RequestContext to avoid repeated computation.
The test is intentionally synthetic and focuses on CPU/time for the hot path; it's not a functional assertion test.

Files produced by this task:
- /workspace/tests_addition_diff.patch : a diff between the original and patched repositories (contains many changes but includes the new test file addition)
- /workspace/improvement_tests.txt : list with the fully qualified name of the test class to run
- /workspace/EXPLANATION.md : this explanation file
