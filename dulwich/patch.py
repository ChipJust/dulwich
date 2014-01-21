# patch.py -- For dealing with packed-style patches.
# Copyright (C) 2009 Jelmer Vernooij <jelmer@samba.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 2
# of the License or (at your option) a later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.

"""Classes for dealing with git am-style patches.

These patches are basically unified diffs with some extra metadata tacked
on.
"""

from io import StringIO
from difflib import SequenceMatcher
import email
import email.parser
import time

from dulwich.objects import (
    Commit,
    S_ISGITLINK,
    )

FIRST_FEW_BYTES = 8000

def _make_writer(f):
    if hasattr(f, 'encoding'):
        # It's probably a string writer
        def _writer(s):
            if isinstance(s, bytes):
                f.write(s.decode('utf-8'))
            elif isinstance(s, str):
                f.write(s)
            else:
                raise TypeError('only strings and bytes supported')
    else:
        # It's probably a bytes writer
        def _writer(s):
            if isinstance(s, bytes):
                f.write(s)
            elif isinstance(s, str):
                f.write(s.encode('utf-8'))
            else:
                raise TypeError('only strings and bytes supported')
    return _writer


def write_commit_patch(f, commit, contents, progress, version=None):
    """Write a individual file patch.

    :param commit: Commit object
    :param progress: Tuple with current patch number and total.
    :return: tuple with filename and contents
    """
    (num, total) = progress
    write = f.write

    write(b'From ' + commit.id + b' ' + time.ctime(commit.commit_time).encode('ascii') + b'\n')
    write(b'From: ' + commit.author + b'\n')
    write(b'Date: ' + time.strftime("%a, %d %b %Y %H:%M:%S %Z").encode('ascii') + b'\n')
    write(b'Subject: [PATCH ' + str(num).encode('ascii') + b'/' + str(total).encode('ascii') + b'] ' + commit.message + b'\n')
    write(b'\n')
    write(b'---\n')
    try:
        import subprocess
        p = subprocess.Popen(['diffstat'], stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE)
    except (ImportError, OSError) as e:
        pass # diffstat not available?
    else:
        (diffstat, _) = p.communicate(contents)
        write(diffstat)
        write(b'\n')
    write(contents)
    write(b'-- \n')
    if version is None:
        from dulwich import __version__ as dulwich_version
        write(('Dulwich %d.%d.%d\n' % dulwich_version).encode('ascii'))
    else:
        write(version + b'\n')


def get_summary(commit):
    """Determine the summary line for use in a filename.

    :param commit: Commit
    :return: Summary string
    """
    return commit.message.decode('utf-8').splitlines()[0].replace(" ", "-")


def unified_diff(a, b, fromfile='', tofile='', n=3):
    """difflib.unified_diff that doesn't write any dates or trailing spaces.

    Based on the same function in Python2.6.5-rc2's difflib.py
    """
    started = False
    for group in SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            yield '--- %s\n' % fromfile
            yield '+++ %s\n' % tofile
            started = True
        i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        yield "@@ -%d,%d +%d,%d @@\n" % (i1+1, i2-i1, j1+1, j2-j1)
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in a[i1:i2]:
                    yield ' ' + line
                continue
            if tag == 'replace' or tag == 'delete':
                for line in a[i1:i2]:
                    if not line[-1] == '\n':
                        line += '\n\\ No newline at end of file\n'
                    yield '-' + line
            if tag == 'replace' or tag == 'insert':
                for line in b[j1:j2]:
                    if not line[-1] == '\n':
                        line += '\n\\ No newline at end of file\n'
                    yield '+' + line


def is_binary(content):
    """See if the first few bytes contain any null characters.

    :param content: Bytestring to check for binary content
    """
    return b'\0' in content[:FIRST_FEW_BYTES]


def write_object_diff(f, store, old_tuple, new_tuple, diff_binary=False):

    """Write the diff for an object.

    :param f: File-like object to write to
    :param store: Store to retrieve objects from, if necessary
    :param (old_path, old_mode, old_hexsha): Old file
    :param (new_path, new_mode, new_hexsha): New file
    :param diff_binary: Whether to diff files even if they
        are considered binary files by is_binary().

    :note: the tuple elements should be None for nonexistant files
    """

    (old_path, old_mode, old_id) = old_tuple
    (new_path, new_mode, new_id) = new_tuple

    if isinstance(old_path, bytes):
        old_path = old_path.decode('utf-8')
    if isinstance(new_path, bytes):
        new_path = new_path.decode('utf-8')

    write = _make_writer(f)

    def shortid(sha):
        if sha is None:
            return "0" * 7
        else:
            return sha[:7].decode('ascii')

    def content(mode, hexsha):
        if hexsha is None:
            return ''
        elif S_ISGITLINK(mode):
            return "Submodule commit " + hexsha.decode('ascii') + "\n"
        else:
            return store[hexsha].data

    def lines(content):
        if not content:
            return []
        else:
            return [l.decode('utf-8') for l in content.splitlines(True)]

    if old_path is None:
        old_path = "/dev/null"
    else:
        old_path = "a/%s" % old_path
    if new_path is None:
        new_path = "/dev/null"
    else:
        new_path = "b/%s" % new_path
    write("diff --git %s %s\n" % (old_path, new_path))
    if old_mode != new_mode:
        if new_mode is not None:
            if old_mode is not None:
                write("old mode %o\n" % old_mode)
            write("new mode %o\n" % new_mode)
        else:
            write("deleted mode %o\n" % old_mode)
    write("index %s..%s" % (shortid(old_id), shortid(new_id)))
    if new_mode is not None:
        write(" %o" % new_mode)
    write('\n')
    old_content = content(old_mode, old_id)
    new_content = content(new_mode, new_id)
    if not diff_binary and (is_binary(old_content) or is_binary(new_content)):
        write("Binary files %s and %s differ\n" % (old_path, new_path))
    else:
        for line in unified_diff(lines(old_contents), lines(new_contents), old_path, new_path):
            write(line)


def write_blob_diff(f, old_tuple, new_tuple):
    """Write diff file header.

    :param f: File-like object to write to
    :param (old_path, old_mode, old_blob): Previous file (None if nonexisting)
    :param (new_path, new_mode, new_blob): New file (None if nonexisting)

    :note: The use of write_object_diff is recommended over this function.
    """

    (old_path, old_mode, old_blob) = old_tuple
    (new_path, new_mode, new_blob) = new_tuple

    if isinstance(old_path, bytes):
        old_path = old_path.decode('utf-8')
    if isinstance(new_path, bytes):
        new_path = new_path.decode('utf-8')

    write = _make_writer(f)

    def blob_id(blob):
        if blob is None:
            return "0" * 7
        else:
            return blob.id[:7].decode('ascii')
    def lines(blob):
        if blob is not None:
            return [l.decode('utf-8') for l in blob.data.splitlines(True)]
        else:
            return []
    if old_path is None:
        old_path = "/dev/null"
    else:
        old_path = "a/%s" % old_path
    if new_path is None:
        new_path = "/dev/null"
    else:
        new_path = "b/%s" % new_path
    write("diff --git %s %s\n" % (old_path, new_path))
    if old_mode != new_mode:
        if new_mode is not None:
            if old_mode is not None:
                write("old mode %o\n" % old_mode)
            write("new mode %o\n" % new_mode)
        else:
            write("deleted mode %o\n" % old_mode)
    write("index %s..%s" % (blob_id(old_blob), blob_id(new_blob)))
    if new_mode is not None:
        write(" %o" % new_mode)
    write("\n")
    old_contents = lines(old_blob)
    new_contents = lines(new_blob)
    for line in unified_diff(old_contents, new_contents, old_path, new_path):
        write(line)


def write_tree_diff(f, store, old_tree, new_tree, diff_binary=False):
    """Write tree diff.

    :param f: File-like object to write to.
    :param old_tree: Old tree id
    :param new_tree: New tree id
    :param diff_binary: Whether to diff files even if they
        are considered binary files by is_binary().
    """
    changes = store.tree_changes(old_tree, new_tree)
    for (oldpath, newpath), (oldmode, newmode), (oldsha, newsha) in changes:
        write_object_diff(f, store, (oldpath, oldmode, oldsha),
                                    (newpath, newmode, newsha),
                                    diff_binary=diff_binary)


def git_am_patch_split(f):
    """Parse a git-am-style patch and split it up into bits.

    :param f: File-like object to parse
    :return: Tuple with commit object, diff contents and git version
    """

    parser = email.parser.Parser()
    msg = parser.parse(f)

    c = Commit()
    c.author = msg["from"].encode('utf-8')
    c.committer = msg["from"].encode('utf-8')

    try:
        patch_tag_start = msg["subject"].index("[PATCH")
    except ValueError:
        subject = msg["subject"]
    else:
        close = msg["subject"].index("] ", patch_tag_start)
        subject = msg["subject"][close+2:]
    c.message = subject.replace("\n", "").encode('utf-8') + b"\n"
    first = True

    body = StringIO(msg.get_payload())

    for l in body:
        if l == "---\n":
            break
        if first:
            if l.startswith("From: "):
                c.author = l[len("From: "):].rstrip().encode('utf-8')
            else:
                c.message += b"\n" + l.encode('utf-8')
            first = False
        else:
            c.message += l.encode('utf-8')
    diff = ''
    for l in body:
        if l == "-- \n":
            break
        diff += l
    try:
        version = body.__next__().rstrip("\n")
    except StopIteration:
        version = None

    return c, diff, version
