I added a performance-focused JUnit test TextDecorationCreationTest that repeatedly constructs TextDecoration instances via the builder API. The patched version changes TextDecoration to use lightweight font attributes instead of javafx.scene.text.Font; this test stresses builder creation and should run faster on the patched version.

The test uses reflection so it works against both original and patched builder APIs.
