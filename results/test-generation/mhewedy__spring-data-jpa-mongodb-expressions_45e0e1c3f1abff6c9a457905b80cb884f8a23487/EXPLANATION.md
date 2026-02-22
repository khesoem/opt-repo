The generated test (com.github.mhewedy.expressions.GeneratedTests) measures the time
spent invoking the ExpressionsSpecification.toPredicate method repeatedly.

It mocks the CriteriaQuery.distinct(true) call to be artificially expensive (Thread.sleep(5)).
The original code always calls query.distinct(true) unconditionally which makes it slower.
The patched code only calls query.distinct(true) when a plural attribute (collection) is encountered.

The test runs the toPredicate method ITERATIONS times and prints the elapsed milliseconds.
When applied to the original and patched repositories the printed time for the patched
version should be lower.
