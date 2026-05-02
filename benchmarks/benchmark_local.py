import sys
import traceback
from typing import Dict

# from classes.ENHSP import ENHSP
from classes.Envs import Envs
# from classes.MetricFF import MetricFF
# from classes.NFD import NFD
# from classes.OMT import OMT
from classes.Patty import Patty
from classes.pattyAllRandom import pattyAllRandom
from classes.pattyBV import pattyBV
from classes.PattyItay import PattyItay
from classes.Planner import Planner
from classes.Result import Result
# from classes.SpringRoll import SpringRoll


PLANNERS: Dict[str, Planner] = {
    "PATTY": Patty("PATTY", "arpg", solver="cvc5", encoding="non-linear"),
    "PATTY-BV": pattyBV("PATTY-BV", "arpg", solver="bitwuzla", encoding="non-linear"),
    # "PATTY-R": pattyAllRandom("PATTY-R", "random", solver="z3", encoding="non-linear"),
    # "SPRINGROLL": SpringRoll(),
    # "RANTANPLAN": Patty("RANTANPLAN", "arpg", solver="z3", encoding="non-linear", rollBound=1, hasEffectAxioms=True),
    # "ENHSP-HADD": ENHSP("sat-hadd"),
    # "ENHSP-HRADD": ENHSP("sat-hradd"),
    # "ENHSP-HMRP": ENHSP("sat-hmrphj"),
    # "METRIC-FF": MetricFF(),
    # "NFD": NFD(),
    # "OMT": OMT(),
}


def main():
    print("Started...")

    envs = Envs()
    envs.isInsideAWS = False   # make sure nothing AWS-specific runs

    # Per-worker log file avoids concurrent write conflicts on a cluster
    log_suffix = f"_{envs.index}" if envs.index > 0 else ""
    log_file = open(f"{envs.experiment}{log_suffix}.log", "a", encoding="utf-8")

    # --- read CSV of instances ---
    with open(envs.file, "r") as f:
        csv = f.read().strip()

    all_instances = [
        line.split(",") for line in csv.split("\n") if line.strip()
    ]

    # Slice this worker's chunk: set INSTANCES_PER_MACHINE + WORKER_INDEX on the cluster
    start = envs.index * envs.instances
    instances = all_instances[start: start + envs.instances]
    print(f"Worker {envs.index}: processing instances {start}–{start + len(instances) - 1} "
          f"of {len(all_instances)} total")

    # --- run each instance locally ---
    for el in instances:
        planner_name, benchmark, domainFile, problemFile = el
        try:
            if planner_name == 'NFD':
                planner_name = 'PATTY-BV'
                planner = PLANNERS["PATTY-BV"]
            elif planner_name == 'ENHSP-HADD':
                planner_name = 'PATTY-R'
                planner = PLANNERS["PATTY-R"]
            elif planner_name == "PATTY":
                planner_name = 'PATTY'
                planner = PLANNERS["PATTY"]
            else:
                # continue
                planner = PLANNERS[planner_name]
        except:
            continue
        print(f"\n=== Running {planner_name} on {domainFile}/{problemFile} ===")

        try:
            r: Result = planner.run(
                benchmark,
                domainFile,
                problemFile,
                None,              # no cloud logger
                envs.timeout
            )

            print(r)
            if not r.solved:
                print(r.stdout)

            # local logging only
            log_file.write(r.toCSV() + "\n")
            log_file.flush()

        except Exception:
            err = traceback.format_exc()
            print(err, file=sys.stderr)
            log_file.write(err + "\n")
            log_file.flush()

    log_file.close()


if __name__ == '__main__':
    main()
