from src.gh.commit_collector import CommitCollector
import logging
from datetime import datetime
from src.data.dataset_adapter import DatasetAdapter

logging.basicConfig(filename='logs/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

def main() -> None:
    logging.info("Starting Commit Collector")

    with CommitCollector() as collector:
        collector.collect_commits()

if __name__ == '__main__':
    main()