# porcelain.py -- Porcelain-like layer on top of Dulwich
# Copyright (C) 2013 Jelmer Vernooij <jelmer@samba.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# or (at your option) a later version of the License.
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

import os
import sys

from dulwich.client import get_transport_and_path
from dulwich.patch import write_tree_diff
from dulwich.repo import (BaseRepo, Repo)
from dulwich.server import update_server_info as server_update_server_info

"""Simple wrapper that provides porcelain-like functions on top of Dulwich.

Currently implemented:
 * archive
 * add
 * clone
 * commit
 * commit-tree
 * diff-tree
 * init
 * rm 
 * update-server-info
 * symbolic-ref

These functions are meant to behave similarly to the git subcommands.
Differences in behaviour are considered bugs.

TODO:

 * add--interactive
 * am
 * annotate
 * apply
 * bisect
 * bisect--helper
 * blame
 * branch
 * bundle
 * cat-file
 * check-attr
 * check-ignore
 * check-mailmap
 * checkout
 * checkout-index
 * check-ref-format
 * cherry
 * cherry-pick
 * clean
 * column
 * config
 * count-objects
 * credential
 * credential-cache
 * credential-cache--daemon  remote-fd
 * credential-store
 * daemon
 * describe
 * diff
 * diff-files
 * diff-index
 * difftool
 * difftool--helper
 * diff-tree
 * fast-export
 * fast-import
 * fetch
 * fetch-pack
 * filter-branch
 * fmt-merge-msg
 * for-each-ref
 * format-patch
 * fsck
 * fsck-objects
 * gc
 * get-tar-commit-id
 * grep
 * hash-object
 * help
 * http-backend
 * http-fetch
 * http-push
 * imap-send
 * index-pack
 * init-db
 * instaweb
 * log
 * lost-found
 * ls-files
 * ls-remote
 * ls-tree
 * mailinfo
 * mailsplit
 * merge
 * merge-base
 * merge-file
 * merge-index
 * merge-octopus
 * merge-one-file
 * merge-ours
 * merge-recursive
 * merge-resolve
 * merge-subtree
 * mergetool
 * merge-tree
 * mktag
 * mktree
 * mv
 * name-rev
 * notes
 * pack-objects
 * pack-redundant
 * pack-refs
 * patch-id
 * peek-remote
 * prune
 * prune-packed
 * pull
 * push
 * quiltimport
 * read-tree
 * rebase
 * receive-pack
 * reflog
 * relink
 * remote
 * remote-ext
 * remote-ftp
 * remote-ftps
 * remote-http
 * remote-https
 * remote-testsvn
 * repack
 * replace
 * repo-config
 * request-pull
 * rerere
 * reset
 * revert
 * rev-list
 * rev-parse
 * send-pack
 * shell
 * sh-i18n--envsubst
 * shortlog
 * show
 * show-branch
 * show-index
 * show-ref
 * stage
 * stash
 * status
 * stripspace
 * submodule
 * tag
 * tar-tree
 * unpack-file
 * unpack-objects
 * update-index
 * update-ref
 * upload-archive
 * upload-pack
 * var
 * verify-pack
 * verify-tag
 * web--browse
 * whatchanged
 * write-tree
"""

__docformat__ = 'restructuredText'


def open_repo(path_or_repo):
    """Open an argument that can be a repository or a path for a repository."""
    if isinstance(path_or_repo, BaseRepo):
        return path_or_repo
    return Repo(path_or_repo)


def archive(location, committish=None, outstream=sys.stdout,
            errstream=sys.stderr):
    """Create an archive.

    :param location: Location of repository for which to generate an archive.
    :param committish: Commit SHA1 or ref to use
    :param outstream: Output stream (defaults to stdout)
    :param errstream: Error stream (defaults to stderr)
    """

    client, path = get_transport_and_path(location)
    if committish is None:
        committish = "HEAD"
    client.archive(path, committish, outstream.write, errstream.write)


def update_server_info(repo="."):
    """Update server info files for a repository.

    :param repo: path to the repository
    """
    r = open_repo(repo)
    server_update_server_info(r)


def symbolic_ref(repo, ref_name, force=False):
    """Set git symbolic ref into HEAD.

    :param repo: path to the repository
    :param ref_name: short name of the new ref
    :param force: force settings without checking if it exists in refs/heads
    """
    repo_obj = open_repo(repo)
    ref_path = 'refs/heads/%s' % ref_name
    if not force and ref_path not in repo_obj.refs.keys():
        raise ValueError('fatal: ref `%s` is not a ref' % ref_name)
    repo_obj.refs.set_symbolic_ref('HEAD', ref_path)


def commit(repo=".", message=None, author=None, committer=None):
    """Create a new commit.

    :param repo: Path to repository
    :param message: Optional commit message
    :param author: Optional author name and email
    :param committer: Optional committer name and email
    :return: SHA1 of the new commit
    """
    # FIXME: Support --all argument
    # FIXME: Support --signoff argument
    r = open_repo(repo)
    return r.do_commit(message=message, author=author,
        committer=committer)


def commit_tree(repo, tree, message=None):
    """Create a new commit object.

    :param repo: Path to repository
    :param tree: An existing tree object
    """
    r = open_repo(repo)
    return r.do_commit(message=message, tree=tree)


def init(path=".", bare=False):
    """Create a new git repository.

    :param path: Path to repository.
    :param bare: Whether to create a bare repository.
    :return: A Repo instance
    """
    if not os.path.exists(path):
        os.mkdir(path)

    if bare:
        return Repo.init_bare(path)
    else:
        return Repo.init(path)


def clone(source, target=None, bare=False, outstream=sys.stdout):
    """Clone a local or remote git repository.

    :param source: Path or URL for source repository
    :param target: Path to target repository (optional)
    :param bare: Whether or not to create a bare repository
    :param outstream: Optional stream to write progress to
    :return: The new repository
    """
    client, host_path = get_transport_and_path(source)

    if target is None:
        target = host_path.split("/")[-1]

    if not os.path.exists(target):
        os.mkdir(target)
    if bare:
        r = Repo.init_bare(target)
    else:
        r = Repo.init(target)
    remote_refs = client.fetch(host_path, r,
        determine_wants=r.object_store.determine_wants_all,
        progress=outstream.write)
    r["HEAD"] = remote_refs["HEAD"]
    return r


def add(repo=".", paths=None):
    """Add files to the staging area.

    :param repo: Repository for the files
    :param paths: Paths to add
    """
    # FIXME: Support patterns, directories, no argument.
    r = open_repo(repo)
    r.stage(paths)


def rm(repo=".", paths=None):
    """Remove files from the staging area.

    :param repo: Repository for the files
    :param paths: Paths to remove
    """
    r = open_repo(repo)
    index = r.open_index()
    for p in paths:
        del index[p]
    index.write()


def print_commit(commit, outstream):
    """Write a human-readable commit log entry.

    :param commit: A `Commit` object
    :param outstream: A stream file to write to
    """
    outstream.write("-" * 50 + "\n")
    outstream.write("commit: %s\n" % commit.id)
    if len(commit.parents) > 1:
        outstream.write("merge: %s\n" % "...".join(commit.parents[1:]))
    outstream.write("author: %s\n" % commit.author)
    outstream.write("committer: %s\n" % commit.committer)
    outstream.write("\n")
    outstream.write(commit.message + "\n")
    outstream.write("\n")


def log(repo=".", outstream=sys.stdout):
    """Write commit logs.

    :param repo: Path to repository
    :param outstream: Stream to write log output to
    """
    r = open_repo(repo)
    walker = r.get_walker()
    for entry in walker:
        print_commit(entry.commit, outstream)


def show(repo=".", committish=None, outstream=sys.stdout):
    """Print the changes in a commit.

    :param repo: Path to repository
    :param committish: Commit to write
    :param outstream: Stream to write to
    """
    if committish is None:
        committish = "HEAD"
    r = open_repo(repo)
    commit = r[committish]
    parent_commit = r[commit.parents[0]]
    print_commit(commit, outstream)
    write_tree_diff(outstream, r.object_store, parent_commit.tree, commit.tree)


def diff_tree(repo, old_tree, new_tree, outstream=sys.stdout):
    """Compares the content and mode of blobs found via two tree objects.

    :param repo: Path to repository
    :param old_tree: Id of old tree
    :param new_tree: Id of new tree
    :param outstream: Stream to write to
    """
    r = open_repo(repo)
    write_tree_diff(outstream, r.object_store, old_tree, new_tree)
