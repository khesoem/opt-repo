import os

# llm = {
#     'llm-invocation-cache-dir': 'cache/llm_invocations',
#     'api-url': 'https://openrouter.ai/api/v1',
#     'openrouter-api-key': os.environ['OPENROUTER_API_KEY'],
#     'default-temp': 0,
#     'default-sample-size': 1,
#     'default-improvement-iterations': 0,
#     'default-model': 'deepseek/deepseek-r1-0528-qwen3-8b',
#     'max-o4-tokens': 10000,
# }

# github = {
#     'access-token': os.environ['access_token'],
# }

perf_commit = {
    'max-files': 20,
    'min-likelihood': 50.0,
    'max-likelihood': 90.0,
    'min-exec-time-improvement': 0.1,
}

docker = {
    'dockerfile': 'docker/Dockerfile',
    'image-name-prefix': 'optds',
    'mvnw-log-path': '/logs',
    'original-repo-path': '/app/original_repo',
    'patched-repo-path': '/app/patched_repo',
    'original-mvnw-log-file': 'logs/original_repo_mvnw.log',
    'patched-mvnw-log-file': 'logs/patched_repo_mvnw.log',
}