import os
import re

PLANNERS = ["PATTY", "PATTY-BV", "ENHSP"]


def _natsort_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _natsorted(items):
    return sorted(items, key=_natsort_key)


def _domain_file(path):
    for name in os.listdir(path):
        if name.startswith("domain") and name.endswith(".pddl"):
            return name
    return None


def main():
    base = "files_itay"
    instances = []

    for name in _natsorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            continue
        instancesDir = os.path.join(path, "instances")
        domainFile = _domain_file(path)
        if domainFile is None or not os.path.isdir(instancesDir):
            continue
        _emit(instances, name, os.path.join(path, domainFile), instancesDir)

    print(f"Listing {len(instances)} instances")
    with open("benchmarks/instances_all.csv", "w") as f:
        f.write("\n".join([",".join(i) for i in instances]))


def _emit(instances, label, domainFile, instancesDir):
    for problem in _natsorted(os.listdir(instancesDir)):
        if problem[-5:] != ".pddl":
            continue
        problemFile = os.path.join(instancesDir, problem)
        for planner in PLANNERS:
            instances.append([planner, label, domainFile, problemFile])


if __name__ == '__main__':
    main()
