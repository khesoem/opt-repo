The test GeneratedTests.performance_multipleRemoves_afterPut simulates a slow RemoteCache by
using a dynamic proxy that delays putAsync/replaceAsync/removeAsync calls. It performs
put followed by two removes for many keys. In the original implementation the second remove
may still trigger a remote remove call in some cases, causing extra remote latency. The
patched implementation uses a TOMBSTONE sentinel to avoid extra remote calls when multiple
removes follow a put. The test prints elapsed time for commit so you can compare original vs patched.
