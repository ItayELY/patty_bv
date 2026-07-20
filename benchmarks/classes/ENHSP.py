import re

from classes.Planner import Planner
from classes.Result import Result

NAME = "ENHSP"


class ENHSP(Planner):
    name = NAME

    def __init__(self, p: str):
        self.p = p
        self.name = f"{NAME}-{p}"
        super().__init__()

    @staticmethod
    def parseOutput(r: Result, stdout: str):
        r.solved = len(re.findall(r"Problem Solved", stdout)) > 0
        r.time = ENHSP.parseTime(stdout)
        r.plan = re.findall(r"^.*?: (\(.*?\))$", stdout, re.MULTILINE)
        r.planLength = len(r.plan)

        return r

    @staticmethod
    def parseTime(stdout: str) -> float:
        # ENHSP reports its own internal planning time rather than PATTY's
        # "Overall: Xms" convention. When it proves a problem unsolvable during
        # grounding/preprocessing, it exits before ever printing that line, so
        # fall back to the wall-clock "real" time from the `time -p` wrapper
        # (see Planner.exec) rather than reporting a bogus 0.
        rePlanningTime = re.findall(r"^Planning Time \(msec\): (\d+)", stdout, re.MULTILINE)
        if rePlanningTime:
            return float(rePlanningTime[0])

        reReal = re.findall(r"^real\s+([\d.]+)", stdout, re.MULTILINE)
        if reReal:
            return float(reReal[0]) * 1000

        return 0.0

    @staticmethod
    def completionMarkers() -> [str]:
        return ["Problem Solved", "Problem unsolvable", "Problem Detected as Unsolvable"]

    def getCommand(self, domain: str, problem: str):
        return ["enhsp", "-o", domain, "-f", problem, "-planner", self.p]
