The generated JUnit test GeneratedTests.testReadLongAsciiString constructs a large ASCII-only JSON string and parses it repeatedly using JSON.parse(byte[]).
This stresses the JSONReaderUTF8 path that scans long ASCII runs using 64-bit vectorized checks.
The patch in the project replaced a UTF-16 mask (0xFF00FF00FF00FF00) with the correct UTF-8 byte high-bit mask (0x8080808080808080), which enables faster detection of ASCII-only bytes and improves performance.

The test measures elapsed time for multiple runs and prints it; when run on the patched code the time should be lower than on the original code.
