import sys

import traceback

import os

# import boto3
import time
import boto3
from botocore.config import Config
from typing import Dict

from classes.pattySecondRandom import pattySecondRandom
from classes.pattyAllRandom import pattyAllRandom 
from classes.CloudLogger import CloudLogger
from classes.ENHSP import ENHSP
from classes.Envs import Envs
from classes.MetricFF import MetricFF
from classes.NFD import NFD
from classes.OMT import OMT
from classes.Patty import Patty
from classes.Planner import Planner
from classes.Result import Result
from classes.SpringRoll import SpringRoll

my_config = Config(
    region_name='eu-central-1',
)

PLANNERS: Dict[str, Planner] = {
    "PATTY": Patty("PATTY", "arpg", solver="z3", encoding="non-linear"),
    "PATTY-R-FROM-SECOND": pattySecondRandom("PATTY-R-FROM-SECOND", "arpg", solver="z3", encoding="non-linear"),
    "PATTY-R": pattyAllRandom("PATTY-R", "random", solver="z3", encoding="non-linear"),
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

    s3 = boto3.client('s3', config=my_config)

    envs = Envs()
    if envs.isInsideAWS:
        time.sleep(envs.index / 4)

    logger = CloudLogger(envs.experiment)

    f = open(envs.file, "r")
    csv = f.read()
    f.close()
    instances = [[v for v in line.split(",")] for line in csv.split("\n")]

    if envs.isInsideAWS:
        a = min(envs.startFrom + (envs.index * envs.instances), len(instances))
        b = min(envs.startFrom + ((envs.index + 1) * envs.instances), len(instances))
        instances = instances[a:b]

    
    for el in instances:
        planner_name, benchmark, domainFile, problemFile = el
        try:
            if planner_name == 'NFD':
                planner_name = 'PATTY-R-FROM-SECOND'
                planner = PLANNERS["PATTY-R-FROM-SECOND"]
            elif planner_name == 'ENHSP-HADD':
                planner_name = 'PATTY-R'
                planner = PLANNERS["PATTY-R"]
            elif planner_name == "PATTY":
                planner_name = 'PATTY'
                planner = PLANNERS["PATTY"]
            else:
                continue
                # planner = PLANNERS[planner_name]
        except:
            continue
        print(f"\n=== Running {planner_name} on {domainFile}/{problemFile} ===")

        try:
            if envs.isInsideAWS:
                print(f"Starting {planner} {benchmark} {domainFile} {problemFile}")
            r: Result = planner.run(benchmark, domainFile, problemFile, logger, envs.timeout)
            print(r)
            if not r.solved:
                print(r.stdout)
            logger.log(r.toCSV())
            s3.put_object(
                Key=f"{envs.experiment}/{r.solver}-{r.domain}-{r.problem}-{time.time_ns()}.txt",
                Bucket="patty-benchmarks",
                Body=bytes(r.stdout, 'utf-8')
            )

        except Exception as error:
            if isinstance(error, KeyboardInterrupt):
                print("Interrupted by user...")
                break
            logger.error(traceback.format_exc())
            print(traceback.format_exc(), file=sys.stderr)


if __name__ == '__main__':
    main()
