#!/usr/bin/python3
from dataclasses import dataclass

import os
import os.path as path
from pathlib import Path

import subprocess
import shutil
from jinja2 import Environment, FileSystemLoader, Template, StrictUndefined
import json
import sys
import itertools

build_dir = "build"


def mkdirs(p):
    Path(path.dirname(p)).mkdir(parents=True, exist_ok=True)


def get_output_path(filepath, root):
    relpath = path.relpath(filepath, root)
    newpath = path.join(build_dir, relpath)
    os.makedirs(path.dirname(newpath), exist_ok=True)
    return newpath


@dataclass
class Flag:
    long: str = ""
    short: str = ""
    default: str = ""
    help: str = ""
    flag_only: bool = False



    def var(self) -> float:
        return self.long.replace("-", "_")

global_build_files = set()

import sys

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
def readfile(file_path):
    with open(file_path, 'r') as file:
        return file.read()
def mkcli(content, **kwargs):
    name = kwargs["name"]
    flags = kwargs.get("flags", [])
    userhelp = kwargs.get("help", "")
    opts = []
    # Inspired by https://argbash.io/send_template#generated
    for o in flags:
        if o.short != "":
            test=f'''test $# -lt 2 && {{ die "Missing value for argument {o.short}." || return 1; }}'''
            set=f'{o.var()}="$2"; shift'
            if o.flag_only:
                test=""
                set=f'{o.var()}="on"'
            ot=f'''-{o.short})
    [[ ${o.var()} == "" ]] || {{ die "Flag already set '{o.var()}'." || return 1; }}
    {test}
    {set}
;;
-{o.short}=*)
    [[ ${o.var()} == "" ]] || {{ die "Flag already set '{o.var()}'." || return 1; }}
    {o.var()}="${{_key##-{o.short}=}}"
;;'''
            opts.append(ot)
        if o.long != "":
            test=f'''test $# -lt 2 && {{ die "Missing value for argument {o.long}." || return 1; }}'''
            set=f'{o.var()}="$2"; shift'
            if o.flag_only:
                test=""
                set=f'{o.var()}="on"'
            ot=f'''--{o.long})
    [[ ${o.var()} == "" ]] || {{ die "Flag already set '{o.var()}'." || return 1; }}
    {test}
    {set}
;;
--{o.long}=*)
    [[ ${o.var()} == "" ]] || {{ die "Flag already set '{o.var()}'." || return 1; }}
    {o.var()}="${{_key##--{o.long}=}}"
;;
'''
            opts.append(ot)
    jopts = '\n'.join(opts)

    help = f'''print_help() {{
    printf "{name}{userhelp}

Options:\\n"
'''
    for o in flags:
        opts = ' '.join(x for x in ["-"+o.short, "--"+o.long] if x.replace("-", ""))
        help += f"\nprintf '\\t%s\\n' '{opts}: {o.help} [{o.default}]'"
    help += "\n}"

    locals=""
    for o in flags:
        locals+=f'local {o.var()}\n'
    set_defaults=""
    for o in flags:
        if o.default != "":
            set_defaults+=f'[[ ${{{o.var()}:-}} == "" ]] && {{ {o.var()}={o.default}; }}\n'
    core = f'''
{help}
die()
{{
	test "${{_PRINT_HELP:-no}}" = yes && print_help >&2
	echo "$1" >&2
	return 1
}}
_positionals=()
parse_commandline() {{
	_positionals_count=0
	while test $# -gt 0
	do
		_key="$1"
		case "$_key" in
            {jopts}
			-h|--help|-h*)
				print_help
                return 2
				;;
            -*)
                die "Unknown flag ${{_key}}"
                ;;
			*)
				_last_positional="$1"
				_positionals+=("$_last_positional")
				_positionals_count=$((_positionals_count + 1))
				;;
		esac
		shift
	done
	{set_defaults}
	return 0
}}
'''
    s = f'''#!/usr/bin/env bash
function {name}() {{
{locals}
{core}
parse_commandline "$@"
ret=$?
if [[ $ret == 2 ]]; then
    return 0
fi
if [[ $ret != 0 ]]; then
    return $ret
fi
set -- "${{_positionals[@]}}"
{content}
}}
{name} "$@"
'''

    # Inspired by https://blog.kloetzl.info/how-to-write-a-zsh-completion/
    completion=f'''#compdef {name}

_{name}() {{
    local I="-h --help --version"
    local ret=1
    local -a args

    args+=(
'''
    for o in flags:
        ss, ls = "+", "="
        if o.flag_only:
            ss, ls = "", ""
        if o.short and o.long:
            completion+=f'''"($I -{o.short} --{o.long})"{{-{o.short}{ss},--{o.long}{ls}}}'[{o.help}]'
'''
        elif o.long:
            completion+=f'''"($I --{o.long})"--{o.long}{ls}'[{o.help}]'
'''
        else:
            completion+=f'''"($I -{o.short})"{{-{o.short}{ss}}}'[{o.help}]'
'''

    completion+=f'''
        '(- *)'{{-h,--help}}'[Display help and exit]'
        '1:name'
    )

    _arguments -w -s -S $args[@] && ret=0

    return ret
}}

_{name}
'''
    cp = path.join(build_dir, ".zsh", "completion", "_"+name)
    global_build_files.add(cp)
    mkdirs(cp)
    with open(cp, "w") as f:
        f.write(completion)
    bp = path.join(build_dir, "bin", name)
    global_build_files.add(bp)
    mkdirs(bp)
    with open(bp, "w") as f:
        f.write(s)
    # make_executable(bp)
    # The original file gets nothing
    return s


def render(fname, variables):
    env = Environment(loader=FileSystemLoader(os.getcwd()), undefined=StrictUndefined)
    env.filters["mkcli"] = mkcli
    try:
        tmpl = env.get_template(fname)
        tmpl.globals["mkcli"] = mkcli
        tmpl.globals["readfile"] = readfile
        tmpl.globals["Flag"] = Flag
        return tmpl.render(variables)
    except Exception as exec:
        raise ValueError(f"failed to render {fname}") from exec


def copyattrs(vars, source, target):
    shutil.copymode(source, target)


def build(infile, outfile):
    rendered = render(infile, {})
    with open(outfile, "w") as f:
        f.write(rendered)
        copyattrs(vars, infile, outfile)


if __name__ == "__main__":
    build("base.sh", "getambient.sh")
