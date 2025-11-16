ARG JAVA_VERSION=21

FROM eclipse-temurin:${JAVA_VERSION}-jdk

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/opt/java/openjdk

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG PATCHED_REPO_DIR
ARG ORIGINAL_REPO_DIR
ARG MODULE_NAMES
ARG EXEC_TIMES

# Create logs directory
RUN mkdir -p /logs

# Create Maven success checker script
RUN echo '#!/bin/bash\n\
LOG_FILE=$1\n\
\n\
if [ ! -f "$LOG_FILE" ]; then\n\
  echo "Error: Log file $LOG_FILE not found"\n\
  exit 1\n\
fi\n\
\n\
# Check for BUILD FAILURE\n\
if grep -q "BUILD FAILURE" "$LOG_FILE"; then\n\
  echo "Maven build failed: BUILD FAILURE detected in $LOG_FILE"\n\
  exit 1\n\
fi\n\
\n\
# Check for BUILD ERROR\n\
if grep -q "BUILD ERROR" "$LOG_FILE"; then\n\
  echo "Maven build failed: BUILD ERROR detected in $LOG_FILE"\n\
  exit 1\n\
fi\n\
\n\
# Check for BUILD SUCCESS\n\
if ! grep -q "BUILD SUCCESS" "$LOG_FILE"; then\n\
  echo "Maven build failed: BUILD SUCCESS not found in $LOG_FILE"\n\
  exit 1\n\
fi\n\
\n\
echo "Maven build successful: $LOG_FILE"\n\
exit 0\n\
' > /usr/local/bin/check_maven_success.sh && chmod +x /usr/local/bin/check_maven_success.sh

COPY $PATCHED_REPO_DIR /app/patched_repo
COPY $ORIGINAL_REPO_DIR /app/original_repo

WORKDIR /app/patched_repo

# Make mvnw executable (some repos forget this)
RUN chmod +x mvnw || true

# Debug: Check if mvnw exists and is executable
RUN ls -la mvnw || echo "mvnw not found in repo_patched"

WORKDIR /app/original_repo

# Make mvnw executable (some repos forget this)
RUN chmod +x mvnw || true

# Debug: Check if mvnw exists and is executable
RUN ls -la mvnw || echo "mvnw not found in repo_original"

# Debug: Print environment variables
RUN echo "MODULE_NAMES: $MODULE_NAMES"
RUN echo "Current directory: $(pwd)"

# Download dependencies
WORKDIR /app/patched_repo
RUN ./mvnw -B dependency:go-offline || echo "Dependency download failed"

WORKDIR /app/original_repo
RUN ./mvnw -B dependency:go-offline || echo "Dependency download failed"

# Run tests alternating between patched and original repos
RUN for i in $(seq 1 $EXEC_TIMES); do \
      # Run patched version \
      cd /app/patched_repo && \
      LOG_FILE="/logs/patched_repo_mvnw_$i.log"; \
      ./mvnw -pl $MODULE_NAMES -am test -Dsurefire.runOrder=alphabetical 2>&1 | tee "$LOG_FILE"; \
      /usr/local/bin/check_maven_success.sh "$LOG_FILE" || exit 1; \
      \
      # Run original version \
      cd /app/original_repo && \
      LOG_FILE="/logs/original_repo_mvnw_$i.log"; \
      ./mvnw -pl $MODULE_NAMES -am test -Dsurefire.runOrder=alphabetical 2>&1 | tee "$LOG_FILE"; \
      /usr/local/bin/check_maven_success.sh "$LOG_FILE" || exit 1; \
    done