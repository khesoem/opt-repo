import logging
from datetime import datetime
import multiprocessing as mp

from src.gh.commit_analysis.test_analyzer import CommitPerfImprovementAnalyzer

NUM_PROCESSES = 10

logging.basicConfig(filename='logs/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

def run_analysis(repo, commit, working_dir: str):
    try:
        logging.info(f"{repo} - {commit} - Running analysis")
        analyzer = CommitPerfImprovementAnalyzer(repo, commit, working_dir)
        analysis_result = analyzer.run_analysis()
        logging.info(f"{repo} - {commit} - Analysis Result - {analysis_result.__dict__}")
    except Exception as e:
        logging.error(f"{repo} - {commit} - Analysis Error - {e}")
    finally:
        analyzer.clean_tmp_dirs()
        logging.info(f"{repo} - {commit} - Cleaned tmp dirs")

def run(commits_file: str, working_dir: str):
    pool = mp.Pool(processes=NUM_PROCESSES)

    with open(commits_file, "r") as f:
        lines = f.readlines()
        for row in lines[1:]:
            row = row.strip()
            row = row.split(",")
            repo = row[0] + "/" + row[1]
            commit = row[2]
            pool.apply_async(run_analysis, (repo, commit, working_dir))

    pool.close()
    pool.join()