#!/usr/bin/env python
# Mode: -*- python -*-
#
# Copyright (c) 2015-2017, 2019-2022 by Rocky Bernstein
# Copyright (c) 2000-2002 by hartmut Goebel <h.goebel@crazy-compilers.com>
#
import click
import os
import sys

from xdis.version_info import version_tuple_to_str

case_sensitive = {"case_sensitive": False}
program = "decompyle3"

from decompyle3.main import main, status_msg
from decompyle3.version import __version__


def usage():
    print(__doc__)
    sys.exit(1)


@click.command()
@click.option("--asm/--no-asm", "-a", "show_asm", default=False)
@click.option("--grammar/--no-grammar", "-g", "show_grammar", default=False)
@click.option("--tree/--no-tree", "-t", default=False)
@click.option("--tree++/--no-tree++", "-T", "tree_plus", default=False)
@click.option(
    "--verify", type=click.Choice(["run", "syntax"]), default=None,
)
@click.option(
    "--recurse/--no-recurse", "-r", "recurse_dirs", default=False,
)
@click.option(
    "--output",
    "-o",
    "outfile",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=True, writable=True, resolve_path=True
    ),
    required=False,
)
@click.version_option(version=__version__)
@click.argument("files", nargs=-1, type=click.Path(readable=True), required=True)
def main_bin(
    show_asm, show_grammar, tree, tree_plus, verify, recurse_dirs, outfile, files
):
    """
    Python byecode decompiler for 3.10 bytecode
    """
    version_tuple = sys.version_info[0:2]

    out_base = None
    source_paths = []
    # timestamp = False
    # timestampfmt = "# %Y.%m.%d %H:%M:%S %Z"

    pyc_paths = files

    # expand directory if specified
    if recurse_dirs:
        expanded_files = []
        for f in pyc_paths:
            if os.path.isdir(f):
                for root, _, dir_files in os.walk(f):
                    for df in dir_files:
                        if df.endswith(".pyc") or df.endswith(".pyo"):
                            expanded_files.append(os.path.join(root, df))
        pyc_paths = expanded_files

    # argl, commonprefix works on strings, not on path parts,
    # thus we must handle the case with files in 'some/classes'
    # and 'some/cmds'
    src_base = os.path.commonprefix(pyc_paths)
    if src_base[-1:] != os.sep:
        src_base = os.path.dirname(src_base)
    if src_base:
        sb_len = len(os.path.join(src_base, ""))
        pyc_paths = [f[sb_len:] for f in pyc_paths]

    if not pyc_paths and not source_paths:
        print("No input files given to decompile", file=sys.stderr)
        usage()

    if outfile == "-":
        outfile = None  # use stdout
    elif outfile and os.path.isdir(outfile):
        out_base = outfile
        outfile = None
    elif outfile and len(pyc_paths) > 1:
        out_base = outfile
        outfile = None

    # if timestamp:
    #     print(time.strftime(timestampfmt))

    numproc = 1
    if numproc <= 1:
        try:
            show_ast = {"before": tree or tree_plus, "after": tree_plus}
            result = main(
                src_base,
                out_base,
                pyc_paths,
                source_paths,
                outfile,
                showasm=show_asm,
                showgrammar=show_grammar,
                showast=show_ast,
                do_verify=verify,
            )

            if len(pyc_paths) > 1:
                mess = status_msg(verify, *result)
                print("# " + mess)
                pass
        except ImportError as e:
            print(str(e))
            sys.exit(2)
        except (KeyboardInterrupt):
            pass
    else:
        from multiprocessing import Process, Queue

        try:
            from Queue import Empty
        except ImportError:
            from queue import Empty

        fqueue = Queue(len(pyc_paths) + numproc)
        for f in pyc_paths:
            fqueue.put(f)
        for i in range(numproc):
            fqueue.put(None)

        rqueue = Queue(numproc)

        def process_func():
            try:
                (tot_files, okay_files, failed_files, verify_failed_files) = (
                    0,
                    0,
                    0,
                    0,
                )
                while 1:
                    f = fqueue.get()
                    if f is None:
                        break
                    (t, o, f, v) = main(src_base, out_base, [f], None, outfile)
                    tot_files += t
                    okay_files += o
                    failed_files += f
                    verify_failed_files += v
            except (Empty, KeyboardInterrupt):
                pass
            rqueue.put((tot_files, okay_files, failed_files, verify_failed_files))
            rqueue.close()

        try:
            procs = [Process(target=process_func) for i in range(numproc)]
            for p in procs:
                p.start()
            for p in procs:
                p.join()
            try:
                (tot_files, okay_files, failed_files, verify_failed_files) = (
                    0,
                    0,
                    0,
                    0,
                )
                while True:
                    (t, o, f, v) = rqueue.get(False)
                    tot_files += t
                    okay_files += o
                    failed_files += f
                    verify_failed_files += v
            except Empty:
                pass
            print(
                "# decompiled %i files: %i okay, %i failed, %i verify failed"
                % (tot_files, okay_files, failed_files, verify_failed_files)
            )
        except (KeyboardInterrupt, OSError):
            pass

    # if timestamp:
    #     print(time.strftime(timestampfmt))

    return


if __name__ == "__main__":
    main_bin()
