import logging
from datetime import datetime
import multiprocessing as mp
from multiprocessing import Manager
import src.config as conf
from src.gh.commit_analysis.test_analyzer import CommitPerfImprovementAnalyzer
from src.reproducibility.system_resource_checker import check_system_resource_usage
import sys
from src.utils import run_cmd

NUM_PROCESSES = conf.run_analysis['num-processes']
LOG_FILE = conf.run_analysis['log-file']
LOG_FORMAT = conf.run_analysis['log-format']
LOG_DATEFMT = conf.run_analysis['log-datefmt']

logging.basicConfig(filename=LOG_FILE,
                    filemode='a',
                    format=conf.run_analysis['log-format'],
                    datefmt=conf.run_analysis['log-datefmt'],
                    level=logging.INFO)


def define_builder(builder_index: int, working_dir: str):
    builder_name = f"builder-{builder_index}"
    cpu_core_per_exec = conf.docker['cpu-core-per-exec']
    memory_per_exec = conf.docker['memory-per-exec']
    run_cmd(['docker', 'builder', 'create', '--name', builder_name, '--driver=docker-container', f'--driver-opt=memory={memory_per_exec}g', f'--driver-opt=cpuset-cpus={builder_index*cpu_core_per_exec}-{(builder_index+1)*cpu_core_per_exec-1}'], working_dir, capture_output=False)
    return builder_name

def run_analysis(repo, commit, working_dir: str, builder_queue):
    builder_name = None
    analyzer = None
    try:
        # Acquire a builder from the queue (blocks until one is available)
        builder_name = builder_queue.get()
        logging.info(f"{repo} - {commit} - Acquired builder: {builder_name}")
        
        logging.info(f"{repo} - {commit} - Running analysis")
        analyzer = CommitPerfImprovementAnalyzer(repo, commit, working_dir, builder_name)
        analysis_result = analyzer.run_analysis()
        logging.info(f"{repo} - {commit} - Analysis Result - {analysis_result.__dict__}")
    except Exception as e:
        logging.error(f"{repo} - {commit} - Analysis Error - {e}")
    finally:
        if analyzer is not None:
            analyzer.clean_tmp_dirs()
            logging.info(f"{repo} - {commit} - Cleaned tmp dirs")

        # Release the builder back to the queue
        if builder_name is not None:
            builder_queue.put(builder_name)
            logging.info(f"{repo} - {commit} - Released builder: {builder_name}")

def run_resource_checker():
    try:
        check_system_resource_usage()
    except Exception as e:
        logging.error(f"Resource checker error: {e}")
        sys.exit(1)

def run(commits_file: str, working_dir: str):
    pool = mp.Pool(processes=NUM_PROCESSES)
    
    # resource_checker_process = mp.Process(target=run_resource_checker)
    # resource_checker_process.start()

    # Create a manager and a queue to hold builder names
    manager = Manager()
    builder_queue = manager.Queue()
    
    # Create builders and add them to the queue
    for i in range(NUM_PROCESSES):
        builder_name = define_builder(i, working_dir)
        builder_queue.put(builder_name)
        logging.info(f"Created and added builder to queue: {builder_name}")
    

    with open(commits_file, "r") as f:
        lines = f.readlines()
        for row in lines[1:]:
            row = row.strip()
            row = row.split(",")
            repo = row[0] + "/" + row[1]
            commit = row[2]
            pool.apply_async(run_analysis, (repo, commit, working_dir, builder_queue))

    pool.close()
    pool.join()

    for i in range(NUM_PROCESSES):
        builder_name = builder_queue.get()
        logging.info(f"Released builder: {builder_name}")
        run_cmd(['docker', 'builder', 'prune', '--builder', builder_name, '--force'], working_dir, capture_output=False)
        run_cmd(['docker', 'builder', 'rm', builder_name], working_dir, capture_output=False)
        logging.info(f"Deleted builder: {builder_name}")

    # resource_checker_process.join()