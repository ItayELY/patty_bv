import subprocess

from subprocess import Popen

from classes.CloudLogger import CloudLogger
from classes.Result import Result


class Planner:
    name: str

    def __init__(self):
        pass

    def run(self, benchmark: str, domainFile: str, problemFile: str, logger: CloudLogger, timeout: int) -> Result:
        stdout, code, cmd = self.exec(domainFile, problemFile, timeout)
        r = Result(benchmark, problemFile)
        r.solver = self.name
        r.code = code
        r.cmd = cmd
        r.stdout = stdout
        self.parseOutput(r, stdout)

        # main.py/main_bv.py only print "Overall: Xms" once their search loop exits
        # on its own (plan found, or every bound up to bMax exhausted). If that line
        # never shows up, the process was cut off mid-search - whether by the
        # `timeout` wrapper (exit 124), an OOM-kill/segfault (some other
        # signal-derived exit code), or an uncaught exception. All of these mean "we
        # don't know if this instance is solvable at a higher bound", i.e. a timeout
        # from the benchmark's point of view - not a genuine "exhausted the search
        # space and found nothing" (the only case where solved == False should be
        # trusted at face value). Relying on code == 124 alone previously misfiled
        # these as ordinary failures with a bogus time of 0.
        if r.solved:
            return r

        if "Overall:" not in stdout:
            if code != 124:
                print(f"[{self.name}] {problemFile}: cut off before completion with "
                      f"unexpected exit code {code} (expected 124 for a clean timeout)")
                print(r.stdout)
            r.timeout = True
            r.solved = False
            r.time = timeout * 1000
            return r

        print(r.stdout)
        return r

    def exec(self, domain: str, problem: str, timeout: int) -> (str, int):
        cmd: [str] = self.getCommand(domain, problem)
        output = ""
        command = ["timeout", str(timeout)] + ["time", "-p"] + cmd
        # command = ["timeout", str(timeout)] + cmd

        print(" ".join(command))
        with Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as p:
            for line in iter(p.stdout.readline, b''):
                output += line.decode('utf-8').rstrip() + "\n"
        return output, p.returncode, " ".join(cmd)
    
    def exec_windows(self, domain: str, problem: str, timeout: int):
        cmd = self.getCommand(domain, problem)
        output = ""

        print(" ".join(cmd))

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,     #  <-- THIS is the timeout!
                text=True
            )
            output = res.stdout
            return output, res.returncode, " ".join(cmd)

        except subprocess.TimeoutExpired as e:
            return e.stdout or "", -1, " ".join(cmd)


    def getCommand(self, domain: str, problem: str) -> [str]:
        raise NotImplemented()

    @staticmethod
    def parseOutput(r: Result, stdout: str):
        raise NotImplemented()
