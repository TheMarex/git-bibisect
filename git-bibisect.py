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
import shutil
import os
import sys

def call_in(cmd, directory):
    d = os.getcwd()
    os.chdir(directory)
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

    def run(self):
        if 'run' not in self._cmds:
            return True

        ret = subprocess.call(self._cmds['run'].split(" "))
        return (ret == 0)

    def commit(self):
        for f in self._files:
            p = os.path.abspath(f)
            directory, name = os.path.split(p)
            dest = os.path.join(self._dest, name)
            shutil.move(p, dest)

            cmd = "git add %s" % name
            ret = call_in(cmd, self._dest)
            if ret > 0:
                print("Error: Could not add %s" % dest)

        cmd = "git commit -q -m build_%s" % self._rev
        ret = call_in(cmd, self._dest)
        if ret > 0:
            print("Error: Could not commit %s" % self._rev)

def get_head():
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

def is_dirty():
    cmd = "git status --porcelain"
    tmp = subprocess.check_output(cmd.split(" ")).decode(sys.stdout.encoding).strip()
    print(tmp)
    return (tmp != "")

def build(revs, files, cmds, dest):
    # backup head
    head = get_head()

    os.makedirs(dest)
    call_in("git init -q .", dest)

    for r in revs:
        j = BuildJob(dest, r, files, cmds)
        j.checkout()
        if j.configure() and j.build():
            if not j.run():
                print("Error: Could not run!")
            j.commit()

    # restore head
    cmd = "git checkout -q %s" % head
    subprocess.call(cmd.split(" "))


if __name__ == '__main__':
    if is_dirty():
        print("Warning: You should not run this on a dirty working tree.")

    # git bibisect --range HEAD^^..HEAD file1 file2 ... dest-dir
    n = len(sys.argv) - 1
    args = sys.argv[1:]
    s = 0

    if n == 0:
        print("Error: No destination given.")
        sys.exit(1)

    cmd = "git rev-list HEAD"
    if n >= 2 and args[0] == "--range":
        cmd = "git rev-list --reverse %s" % args[1]
        # first 2 entries parsed
        s += 2
    revs = subprocess.check_output(cmd.split(" ")).split(b"\n")
    revs = [r.decode(sys.stdout.encoding) for r in revs if r != '']

    if s >= n:
        print("Error: No destination given.")
        sys.exit(1)

    files = args[s:n-1]
    s += len(files)

    if s >= n:
        print("Error: No destination given.")
        sys.exit(1)

    dest = args[n-1]

    cmds = {'build': "make -j2", 'configure': "cmake .. -DCMAKE_BUILD_TYPE=Release"}
    build(revs, files, cmds, dest)

