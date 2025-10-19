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

# Run tests on repo patched
WORKDIR /app/patched_repo

# Debug: Print environment variables
RUN echo "MODULE_NAMES: $MODULE_NAMES"
RUN echo "Current directory: $(pwd)"

# Download dependencies first
RUN ./mvnw -B dependency:go-offline || echo "Dependency download failed"

# Run tests with better error handling
RUN for i in $(seq 1 $EXEC_TIMES); do \
      ./mvnw -pl $MODULE_NAMES -am test 2>&1 | tee /logs/patched_repo_mvnw_$i.log || echo "Maven test failed, check logs"; \
    done

# Run tests on repo original (before commit)
WORKDIR /app/original_repo

# Debug: Print environment variables
RUN echo "MODULE_NAMES: $MODULE_NAMES"
RUN echo "Current directory: $(pwd)"

# Download dependencies first
RUN ./mvnw -B dependency:go-offline || echo "Dependency download failed"

# Run tests with better error handling
RUN for i in $(seq 1 $EXEC_TIMES); do \
      ./mvnw -pl $MODULE_NAMES -am test 2>&1 | tee /logs/original_repo_mvnw_$i.log || echo "Maven test failed, check logs"; \
    done