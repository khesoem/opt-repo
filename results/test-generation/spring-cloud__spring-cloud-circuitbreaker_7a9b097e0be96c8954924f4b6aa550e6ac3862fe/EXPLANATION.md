Generated performance test

I created a JUnit test class org.springframework.cloud.circuitbreaker.resilience4j.GeneratedTests
that repeatedly invokes the CircuitBreaker created by Resilience4JCircuitBreakerFactory configured
with a Resilience4jBulkheadProvider. The test performs 50 warm-up calls and 1000 measured calls,
printing the total elapsed time for the measured loop. The change in Resilience4jBulkheadProvider
(replacing a scheduler-based TimeLimiter decoration with a non-scheduler Callable-based decoration)
reduces executor creation and thread overhead; running this test on the patched code should show
lower total time than on the original.

How to run

Apply the patch to both repositories (the test file is added under the resilience4j module). Then run:

./mvnw -pl spring-cloud-circuitbreaker-resilience4j -am test -Dtest=org.springframework.cloud.circuitbreaker.resilience4j.GeneratedTests -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

