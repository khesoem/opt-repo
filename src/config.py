import os
from datetime import datetime
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

def get_mvnw_log_file_name(version: str, exec_time: int) -> str:
    return f'logs/{version}_repo_mvnw_{exec_time}.log'

docker = {
    'dockerfile': 'docker/Dockerfile',
    'image-name-prefix': 'optds',
    'mvnw-log-path': '/logs',
    'original-repo-path': '/app/original_repo',
    'patched-repo-path': '/app/patched_repo',
    'host-mvnw-log-path': get_mvnw_log_file_name,
    'exec-times': 4,
    'cpu-core-per-exec': 4,
    'memory-per-exec': 2,
}

run_analysis = {
    'num-processes': 2,
    'log-file': 'logs/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
    'log-format': '%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    'log-datefmt': '%H:%M:%S',
}