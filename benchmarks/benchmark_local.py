import argparse
import multiprocessing
import os
import sys
import traceback
from typing import Dict

from classes.Envs import Envs
from classes.Patty import Patty
from classes.pattyAllRandom import pattyAllRandom
from classes.pattyBV import pattyBV
from classes.PattyItay import PattyItay
from classes.Planner import Planner
from classes.Result import Result


PLANNERS: Dict[str, Planner] = {
    "PATTY": Patty("PATTY", "arpg", solver="cvc5", encoding="non-linear"),
    "PATTY-BV": pattyBV("PATTY-BV", "arpg", solver="bitwuzla", encoding="non-linear"),
}


def run_worker(worker_index: int, total_workers: int):
    envs = Envs()
    envs.isInsideAWS = False

    log_dir = envs.experiment
    os.makedirs(log_dir, exist_ok=True)
    log_file = open(os.path.join(log_dir, f"{worker_index}.log"), "a", encoding="utf-8")

    with open(envs.file, "r") as f:
        csv = f.read().strip()

    all_instances = [line.split(",") for line in csv.split("\n") if line.strip()]

    chunk = len(all_instances) // total_workers
    start = worker_index * chunk
    end = start + chunk if worker_index < total_workers - 1 else len(all_instances)
    instances = all_instances[start:end]

    print(f"Worker {worker_index}: processing instances {start}–{end - 1} of {len(all_instances)} total")

    for el in instances:
        planner_name, benchmark, domainFile, problemFile = el
        try:
            if planner_name in ('NFD', 'PATTY-BV'):
                planner_name = 'PATTY-BV'
                planner = PLANNERS["PATTY-BV"]
            elif planner_name == "PATTY":
                planner = PLANNERS["PATTY"]
            else:
                planner = PLANNERS[planner_name]
        except Exception:
            continue

        print(f"\n=== Running {planner_name} on {domainFile}/{problemFile} ===")

        try:
            r: Result = planner.run(benchmark, domainFile, problemFile, None, envs.timeout)
            print(r)
            if not r.solved:
                print(r.stdout)
            log_file.write(r.toCSV() + "\n")
            log_file.flush()
        except Exception:
            err = traceback.format_exc()
            print(err, file=sys.stderr)
            log_file.write(err + "\n")
            log_file.flush()

    log_file.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel worker processes")
    args = parser.parse_args()

    print(f"Started with {args.workers} worker(s)...")

    if args.workers == 1:
        run_worker(0, 1)
    else:
        processes = [
            multiprocessing.Process(target=run_worker, args=(i, args.workers))
            for i in range(args.workers)
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join()


if __name__ == '__main__':
    main()
