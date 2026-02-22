I added a JUnit-style TestNG performance test that exercises MessageCryptoBc.encrypt()
using a 32KB payload repeated many times. The patch being measured changes the AES/GCM
Cipher provider selection (preferring SunJCE when available), which yields a large
throughput improvement on HotSpot JVMs due to AES hardware intrinsics.

How to run:
  ./mvnw -pl pulsar-client-messagecrypto-bc -am test -Dtest=org.apache.pulsar.client.impl.crypto.GeneratedTests \
    -Dsurefire.runOrder=alphabetical -DfailIfNoTests=false -DskipITs

The test prints the elapsed time for a fixed number of encrypt operations. Run it
on both the original and patched codebases and compare the printed times; the
patched version should be significantly faster.
