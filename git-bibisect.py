#!/usr/bin/python3
#
#  git-bibisect is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  git-bibisect is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with git-bibisect. If not, see <http://www.gnu.org/licenses/>.
#
#  Copyright git-bibisect 2013: Patrick Niklaus
#

import subprocess
import configparser
import optparse
import shutil
import os
import sys

def _call_in(cmd, directory, output=False):
    d = os.getcwd()
    os.chdir(directory)
    if output:
        try:
            ret = subprocess.check_output(cmd.split(" ")).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError:
            ret = ""
    else:
        ret = subprocess.call(cmd.split(" "))
    os.chdir(d)
    return ret

class BuildJob:
    def __init__(self, dest, rev, files, cmds):
        self._dest = dest
        self._rev = rev
        self._files = files
        self._cmds = cmds

    def checkout(self):
        cmd = "git checkout -q %s" % self._rev
        # call in cwd
        subprocess.call(cmd.split(" "))

    def configure(self):
        ret = subprocess.call(self._cmds['configure'].split(" "))
        return (ret == 0)

    def build(self):
        ret = subprocess.call(self._cmds['build'].split(" "))
        return (ret == 0)

    def execute(self):
        if 'execute' not in self._cmds:
            return True

        ret = subprocess.call(self._cmds['execute'], shell=True)
        return (ret == 0)

    def commit(self):
        for f in self._files:
            p = os.path.abspath(f)
            directory, name = os.path.split(p)
            dest = os.path.join(self._dest, name)
            shutil.move(p, dest)

            cmd = "git add %s" % name
            ret = _call_in(cmd, self._dest)
            if ret > 0:
                print("Error: Could not add %s" % dest)

        cmd = "git commit -q -m build_%s" % self._rev
        ret = _call_in(cmd, self._dest)
        if ret > 0:
            print("Error: Could not commit %s" % self._rev)

def _get_head():
    head = ""
    try:
        cmd = "git symbolic-ref HEAD"
        tmp = subprocess.check_output(cmd.split(" ")).decode(sys.stdout.encoding).strip()
        head = tmp.replace("refs/heads/", "")
    except subprocess.CalledProcessError:
        cmd = "git show-ref HEAD"
        tmp = subprocess.check_output(cmd.split(" ")).decode(sys.stdout.encoding).strip()
        head = tmp.split(" ")[0]
    return head

def _is_dirty():
    cmd = "git status --porcelain"
    tmp = subprocess.check_output(cmd.split(" ")).decode(sys.stdout.encoding).strip()
    return (tmp != "")

def _parse_revs(revRange):
    cmd = "git rev-list --reverse %s" % revRange
    revs = subprocess.check_output(cmd.split(" ")).split(b"\n")
    revs = [r.decode(sys.stdout.encoding).strip() for r in revs]
    revs = [r for r in revs if len(r)]
    return revs

def _rev_exists(rev, repo):
    cmd = "git log"
    log = _call_in(cmd, repo, output=True)
    return ("build_%s" % rev) in log

def add(revs, files, cmds, dest):
    for r in revs:
        if _rev_exists(r, dest):
            print("Warning: Revision %s already in repository. Skipping." % r)
            continue

        # backup head
        head = _get_head()

        j = BuildJob(dest, r, files, cmds)
        j.checkout()
        if j.configure() and j.build():
            if not j.execute():
                print("Warning: Could not execute!")
            j.commit()

        # restore head
        cmd = "git checkout -q %s" % head
        subprocess.call(cmd.split(" "))

def init(dest):
    if os.path.exists(output):
        print("Error: Output directory exists.")
        return False

    os.makedirs(dest)
    _call_in("git init -q .", dest)
    return True

if __name__ == '__main__':
    if _is_dirty():
        print("Warning: You should not run this on a dirty working tree.")

    config = configparser.ConfigParser()
    config.read([".gitbuild", "../.gitbuild"])

    files = []
    output = "binaries"

    if "bibisect" in config:
        if "files" in config["bibisect"]:
            files = [f.strip() for f in config["bibisect"]["files"].split(",")]
        if "output" in config["bibisect"]:
            output = config["bibisect"]["output"]

    if "build" in config:
        cmds = config["build"]
    else:
        print("Error: No build parameters given.")
        sys.exit(1)

    parser = optparse.OptionParser("Usage: %prog [options] [add | build] file1 file2 ...")
    parser.add_option("-o", "--output", dest="output", help="destination directory of the git repo")
    parser.add_option("-r", "--range", dest="revRange", default="HEAD", help="only build commits in this range")
    parser.add_option("-c", "--configure", dest="configure", help="command to use for configuration (e.g. cmake ..)")
    parser.add_option("-b", "--build", dest="build", help="command to use for building (e.g. make -j2)")
    parser.add_option("-x", "--execute", dest="execute", help="command to run after the build is finished")

    options, args = parser.parse_args()

    if len(args) == 0 or args[0] not in ("build", "add"):
        print("Error: No command given.")
        sys.exit(1)

    command = args[0]
    files = args[1:] or files
    files = [os.path.abspath(f) for f in files]
    output = options.output or output
    output = os.path.abspath(output)
    if options.configure:
        cmds['configure'] = options.configure
    if options.build:
        cmds['build'] = options.build
    if options.execute:
        cmds['execute'] = options.execute

    if len(files) == 0:
        print("Error: No files given.")
        sys.exit(1)

    revs = _parse_revs(options.revRange)

    print("Building %i revisions." % len(revs))

    if command == "build":
        if not init(output):
            sys.exit(1)
    add(revs, files, cmds, output)


