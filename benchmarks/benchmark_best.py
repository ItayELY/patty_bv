import argparse
import multiprocessing
import os
import sys
import traceback
from typing import Dict, List, Optional

from classes.Envs import Envs
from classes.Patty import Patty
from classes.pattyBV import pattyBV
from classes.Planner import Planner
from classes.Result import Result


PLANNERS: Dict[str, Planner] = {
    "PATTY": Patty("PATTY", "random", solver="cvc5", encoding="non-linear"),
    "PATTY-BV": pattyBV("PATTY-BV", "arpg", solver="bitwuzla", encoding="non-linear"),
}

RUNS = 5


def best_result(results: List[Result]) -> Optional[Result]:
    solved = [r for r in results if r.solved]
    if not solved:
        return results[-1]
    return min(solved, key=lambda r: r.time)


def run_worker(worker_index: int, total_workers: int, runs: int):
    envs = Envs()
    envs.isInsideAWS = False

    log_dir = envs.experiment
    os.makedirs(log_dir, exist_ok=True)
    log_file = open(os.path.join(log_dir, f"{worker_index}.log"), "a", encoding="utf-8")

    with open(envs.file, "r") as f:
        csv = f.read().strip()

    all_instances = [line.split(",") for line in csv.split("\n") if line.strip()]
    instances = all_instances[worker_index::total_workers]

    print(f"Worker {worker_index}: processing {len(instances)} of {len(all_instances)} total instances, {runs} runs each")

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

        print(f"\n=== Running {planner_name} on {domainFile}/{problemFile} ({runs} runs) ===")

        run_results: List[Result] = []
        try:
            for i in range(runs):
                r: Result = planner.run(benchmark, domainFile, problemFile, None, envs.timeout)
                run_results.append(r)
                print(f"  Run {i+1}/{runs}: solved={r.solved}, time={r.time}ms, bound={r.bound}")

            best = best_result(run_results)
            print(f"  Best: {best}")
            log_file.write(best.toCSV() + "\n")
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
    parser.add_argument("--runs", type=int, default=RUNS,
                        help="Number of times to run each instance (default: 5)")
    args = parser.parse_args()

    print(f"Started with {args.workers} worker(s), {args.runs} runs per instance...")

    if args.workers == 1:
        run_worker(0, 1, args.runs)
    else:
        processes = [
            multiprocessing.Process(target=run_worker, args=(i, args.workers, args.runs))
            for i in range(args.workers)
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join()


if __name__ == '__main__':
    main()
