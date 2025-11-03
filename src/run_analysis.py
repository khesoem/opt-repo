import logging
from datetime import datetime
import multiprocessing as mp
from multiprocessing import Manager
import src.config as conf
from src.data.dataset_adapter import DatasetAdapter
from src.gh.commit_analysis.test_analyzer import AnalysisType, CommitPerfImprovementAnalyzer
from src.reproducibility.system_resource_checker import check_system_resource_usage
import sys
from src.utils import run_cmd
from enum import Enum

LOG_FILE = conf.run_analysis['log-file']
LOG_FORMAT = conf.run_analysis['log-format']
LOG_DATEFMT = conf.run_analysis['log-datefmt']
WORKING_DIR = conf.run_analysis['working-dir']

logging.basicConfig(filename=LOG_FILE,
                    filemode='a',
                    format=conf.run_analysis['log-format'],
                    datefmt=conf.run_analysis['log-datefmt'],
                    level=logging.INFO)

class RunType(Enum):
    INITIAL = "initial"
    FINAL = "final"

def define_new_builder(builder_index: int, run_type: RunType):
    builder_name = f"builder-{builder_index}"
    cpu_core_per_exec = conf.docker[f'{run_type.value}-cpu-core-per-exec']
    memory_per_exec = conf.docker[f'{run_type.value}-memory-per-exec']
    run_cmd(['docker', 'builder', 'create', '--name', builder_name, '--driver=docker-container', f'--driver-opt=memory={memory_per_exec}g', f'--driver-opt=cpuset-cpus={builder_index*cpu_core_per_exec}-{(builder_index+1)*cpu_core_per_exec-1}'], WORKING_DIR, capture_output=False)
    return builder_name

def run_analysis(repo: str, commit: str, builder_queue: mp.Queue, run_type: RunType):
    builder_name = None
    analyzer = None
    try:
        # Acquire a builder from the queue (blocks until one is available)
        builder_name = builder_queue.get()
        logging.info(f"{repo} - {commit} - Acquired builder: {builder_name}")
        
        logging.info(f"{repo} - {commit} - Running analysis")

        analyzer = CommitPerfImprovementAnalyzer(repo, commit, WORKING_DIR, builder_name, AnalysisType.INITIAL if run_type == RunType.INITIAL else AnalysisType.FINAL)

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

def run(run_type: RunType = RunType.INITIAL):

    pool = None
    if run_type == RunType.INITIAL:
        NUM_PROCESSES = conf.run_analysis['num-processes']
        pool = mp.Pool(processes=NUM_PROCESSES)
    elif run_type != RunType.FINAL:
        raise ValueError(f"Invalid run type: {run_type}")

    # Create a manager and a queue to hold builder names
    manager = Manager()
    builder_queue = manager.Queue()
    
    # Create builders and add them to the queue
    for i in range(NUM_PROCESSES if run_type == RunType.INITIAL else 1):
        builder_name = define_new_builder(i, run_type)
        builder_queue.put(builder_name)
        logging.info(f"Created and added builder to queue: {builder_name}")
    
    dataset = DatasetAdapter()
    df = dataset.get_dataset()
    for _, row in df.iterrows():
        repo = row['repo']
        commit = row['commit_hash']
        if run_type == RunType.INITIAL:
            pool.apply_async(run_analysis, (repo, commit, builder_queue, run_type))
        elif run_type == RunType.FINAL:
            run_analysis(repo, commit, builder_queue, run_type)

    if run_type == RunType.INITIAL:
        pool.close()
        pool.join()

    for i in range(NUM_PROCESSES if run_type == RunType.INITIAL else 1):
        builder_name = builder_queue.get()
        logging.info(f"Released builder: {builder_name}")
        run_cmd(['docker', 'builder', 'prune', '--builder', builder_name, '--force'], WORKING_DIR, capture_output=False)
        run_cmd(['docker', 'builder', 'rm', builder_name], WORKING_DIR, capture_output=False)
        logging.info(f"Deleted builder: {builder_name}")