FROM {base-image}

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/project

# Start an interactive shell by default
CMD ["bash"]