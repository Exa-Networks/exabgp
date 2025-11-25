"""shell.py

Shell completion generation and installation utility.

Created on 2025-11-21.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def detect_shell() -> str:
    """Auto-detect current shell from environment."""
    shell = os.environ.get('SHELL', '').lower()

    if 'bash' in shell:
        return 'bash'
    elif 'zsh' in shell:
        return 'zsh'
    elif 'fish' in shell:
        return 'fish'
    else:
        return 'bash'  # Default to bash if unknown


def get_completion_dest(shell: str) -> Path:
    """Get destination path for completion file."""
    home = Path.home()

    paths = {
        'bash': home / '.local/share/bash-completion/completions/exabgp',
        'zsh': home / '.zsh/completions/_exabgp',
        'fish': home / '.config/fish/completions/exabgp.fish',
    }

    return paths.get(shell, paths['bash'])


def get_activation_message(shell: str) -> str:
    """Get activation instructions for the shell."""
    messages = {
        'bash': 'source ~/.local/share/bash-completion/completions/exabgp',
        'zsh': """Add to ~/.zshrc:
    fpath=(~/.zsh/completions $fpath)
    autoload -Uz compinit && compinit
Then run: exec zsh""",
        'fish': 'Restart fish or run: exec fish',
    }

    return messages.get(shell, messages['bash'])


def generate_bash_completion() -> str:
    """Generate Bash completion script."""
    return """# Bash completion for exabgp
# Copyright (c) 2009-2025 Exa Networks. All rights reserved.
# License: 3-clause BSD.

_exabgp() {
    local cur prev words cword
    _init_completion || return

    local subcommands="version cli run healthcheck server env validate decode shell"
    local config_dirs="etc/exabgp /etc/exabgp"

    # If we're at the first argument position
    if [[ $cword -eq 1 ]]; then
        # Offer subcommands and .conf files (backward compatibility)
        local suggestions="$subcommands"

        # Add .conf files from current dir and standard locations
        for dir in . $config_dirs; do
            if [[ -d "$dir" ]]; then
                while IFS= read -r -d $'\\0' file; do
                    suggestions="$suggestions ${file%.conf}"
                done < <(find "$dir" -maxdepth 1 -name "*.conf" -print0 2>/dev/null)
            fi
        done

        COMPREPLY=($(compgen -W "$suggestions" -- "$cur"))
        # Also allow file completion
        _filedir conf
        return 0
    fi

    local subcommand="${words[1]}"

    # Check if first word is a subcommand or a config file (backward compat)
    if [[ ! " $subcommands " =~ " $subcommand " ]]; then
        # Treat as 'server' subcommand (4.x compatibility)
        subcommand="server"
    fi

    case "$subcommand" in
        version)
            # No options for version
            ;;

        cli)
            case "$prev" in
                --pipename)
                    # Complete pipe names (no specific suggestions)
                    ;;
                *)
                    COMPREPLY=($(compgen -W "--pipename --no-color -h --help" -- "$cur"))
                    ;;
            esac
            ;;

        run)
            case "$prev" in
                --pipename)
                    # Complete pipe names
                    ;;
                --batch)
                    _filedir
                    return 0
                    ;;
                *)
                    COMPREPLY=($(compgen -W "--pipename --pipe --socket --batch --no-color -h --help" -- "$cur"))
                    # If past options, don't complete further (user entering command)
                    ;;
            esac
            ;;

        healthcheck)
            case "$prev" in
                --cmd)
                    _command
                    return 0
                    ;;
                --ip|--nexthop|--local-ip)
                    # IP addresses - no completion
                    ;;
                --community|--large-community|--extended-community)
                    # Community values - no completion
                    ;;
                --label|--rd|--route-distinguisher)
                    # Numeric/string values - no completion
                    ;;
                *)
                    local opts="--cmd --name --ip --nexthop --local-ip"
                    opts="$opts --interval --fast-interval --slow-interval --timeout"
                    opts="$opts --rise --disable --withdraw --label"
                    opts="$opts --community --large-community --extended-community"
                    opts="$opts --rd --route-distinguisher --advertisement-delay"
                    opts="$opts --local-preference --med --origin --as-path"
                    opts="$opts --logging --syslog --pid --daemonize --no-daemonize"
                    opts="$opts -h --help"
                    COMPREPLY=($(compgen -W "$opts" -- "$cur"))
                    ;;
            esac
            ;;

        server)
            case "$prev" in
                --signal)
                    # Numeric value - no completion
                    ;;
                --profile)
                    _filedir
                    return 0
                    ;;
                *)
                    if [[ "$cur" == -* ]]; then
                        COMPREPLY=($(compgen -W "-v --verbose -d --debug -s --signal -1 --once -p --pdb -P --passive -m --memory --profile -h --help" -- "$cur"))
                    else
                        # Complete .conf files
                        for dir in . $config_dirs; do
                            if [[ -d "$dir" ]]; then
                                COMPREPLY+=($(compgen -W "$(find "$dir" -maxdepth 1 -name "*.conf" -exec basename {} \\; 2>/dev/null)" -- "$cur"))
                            fi
                        done
                        _filedir conf
                    fi
                    ;;
            esac
            ;;

        env)
            COMPREPLY=($(compgen -W "-d --diff -e --env -h --help" -- "$cur"))
            ;;

        validate)
            case "$prev" in
                *)
                    if [[ "$cur" == -* ]]; then
                        COMPREPLY=($(compgen -W "-n --neighbor -r --route -v --verbose -p --pdb -h --help" -- "$cur"))
                    else
                        # Complete .conf files
                        for dir in . $config_dirs; do
                            if [[ -d "$dir" ]]; then
                                COMPREPLY+=($(compgen -W "$(find "$dir" -maxdepth 1 -name "*.conf" -exec basename {} \\; 2>/dev/null)" -- "$cur"))
                            fi
                        done
                        _filedir conf
                    fi
                    ;;
            esac
            ;;

        decode)
            case "$prev" in
                -c|--configuration)
                    for dir in . $config_dirs; do
                        if [[ -d "$dir" ]]; then
                            COMPREPLY+=($(compgen -W "$(find "$dir" -maxdepth 1 -name "*.conf" -exec basename {} \\; 2>/dev/null)" -- "$cur"))
                        fi
                    done
                    _filedir conf
                    return 0
                    ;;
                -f|--family)
                    local families=(
                        "ipv4 unicast" "ipv4 multicast" "ipv4 mpls-vpn" "ipv4 flow"
                        "ipv6 unicast" "ipv6 mpls-vpn" "ipv6 flow"
                        "l2vpn vpls" "l2vpn evpn"
                        "bgp-ls bgp-ls" "bgp-ls bgp-ls-vpn"
                    )
                    # Quote families with spaces
                    COMPREPLY=($(compgen -W "$(printf '"%s" ' "${families[@]}")" -- "$cur"))
                    return 0
                    ;;
                *)
                    if [[ "$cur" == -* ]]; then
                        COMPREPLY=($(compgen -W "-n --nlri -u --update -o --open -d --debug -p --pdb -c --configuration -f --family -i --path-information -h --help" -- "$cur"))
                    fi
                    # Otherwise, user is entering hex payload - no completion
                    ;;
            esac
            ;;

        shell)
            # After 'shell', suggest subcommands
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "install uninstall completion" -- "$cur"))
            elif [[ $cword -eq 3 ]]; then
                # After 'shell install/uninstall/completion', suggest shells
                COMPREPLY=($(compgen -W "bash zsh fish" -- "$cur"))
            fi
            ;;
    esac
}

complete -F _exabgp exabgp
"""


def generate_zsh_completion() -> str:
    """Generate Zsh completion script."""
    return """#compdef exabgp
# Zsh completion for exabgp
# Copyright (c) 2009-2025 Exa Networks. All rights reserved.
# License: 3-clause BSD.

_exabgp() {
    local context state state_descr line
    typeset -A opt_args

    local config_dirs=(. etc/exabgp /etc/exabgp)
    local -a config_files
    for dir in $config_dirs; do
        if [[ -d "$dir" ]]; then
            config_files+=(${dir}/*.conf(N:t))
        fi
    done

    local -a subcommands
    subcommands=(
        'version:Report ExaBGP version'
        'cli:Interactive CLI with tab completion'
        'run:Execute single command non-interactively'
        'healthcheck:Monitor services and announce/withdraw routes'
        'server:Start ExaBGP daemon'
        'env:Show ExaBGP configuration information'
        'validate:Validate configuration file'
        'decode:Decode hex-encoded BGP packets'
        'shell:Manage shell completion'
    )

    # Check if first argument is a subcommand
    if (( CURRENT == 2 )); then
        # First argument: complete subcommands or .conf files (backward compat)
        _alternative \\
            'subcommands:subcommand:((${subcommands}))' \\
            'configs:configuration file:compadd ${config_files}' \\
            'files:configuration file:_files -g "*.conf"'
        return 0
    fi

    local subcommand="${words[2]}"

    # If not a known subcommand, treat as 'server' (4.x compatibility)
    if [[ ! " version cli run healthcheck server env validate decode shell " =~ " $subcommand " ]]; then
        subcommand="server"
    fi

    case "$subcommand" in
        version)
            # No arguments for version
            ;;

        cli)
            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '--pipename[Name of the pipe]:pipe name' \\
                '--no-color[Disable colored output]'
            ;;

        run)
            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '--pipename[Name of the pipe]:pipe name' \\
                '--pipe[Use named pipe transport]' \\
                '--socket[Use Unix socket transport (default)]' \\
                '--batch[Execute commands from file]:file:_files' \\
                '--no-color[Disable colored output]' \\
                '*:command:'
            ;;

        healthcheck)
            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '--cmd[Command to execute for health check]:command:_command_names' \\
                '--name[Name for this health check]:name' \\
                '--ip[IP address or CIDR to announce]:ip address' \\
                '--nexthop[Next-hop IP address]:ip address' \\
                '--local-ip[Local IP address]:ip address' \\
                '--interval[Check interval in seconds]:seconds' \\
                '--fast-interval[Fast check interval]:seconds' \\
                '--slow-interval[Slow check interval]:seconds' \\
                '--timeout[Command timeout]:seconds' \\
                '--rise[Number of successes before UP]:count' \\
                '--disable[Disable health checks]' \\
                '--withdraw[Withdraw route on failure]' \\
                '--label[MPLS label]:label' \\
                '--community[BGP community]:community' \\
                '--large-community[Large BGP community]:community' \\
                '--extended-community[Extended community]:community' \\
                '--rd[Route distinguisher]:rd' \\
                '--route-distinguisher[Route distinguisher]:rd' \\
                '--advertisement-delay[Delay before announcing]:seconds' \\
                '--local-preference[Local preference value]:value' \\
                '--med[Multi-Exit Discriminator]:value' \\
                '--origin[Origin attribute]:origin:(igp egp incomplete)' \\
                '--as-path[AS path]:as path' \\
                '--logging[Enable logging]' \\
                '--syslog[Log to syslog]:facility' \\
                '--pid[PID file location]:file:_files' \\
                '--daemonize[Run as daemon]' \\
                '--no-daemonize[Do not daemonize]'
            ;;

        server)
            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '(-v --verbose)'{-v,--verbose}'[Toggle all logging]' \\
                '(-d --debug)'{-d,--debug}'[Start Python debugger on issue]' \\
                '(-s --signal)'{-s,--signal}'[Issue SIGUSR1 after N seconds]:seconds' \\
                '(-1 --once)'{-1,--once}'[Only one connection attempt]' \\
                '(-p --pdb)'{-p,--pdb}'[Fire debugger on critical logging]' \\
                '(-P --passive)'{-P,--passive}'[Only accept incoming connections]' \\
                '(-m --memory)'{-m,--memory}'[Display memory usage on exit]' \\
                '--profile[Enable profiling]:file:_files' \\
                '*:configuration file:_alternative "configs:configuration file:compadd ${config_files}" "files:configuration file:_files -g \\"*.conf\\""'
            ;;

        env)
            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '(-d --diff)'{-d,--diff}'[Show only differences from defaults]' \\
                '(-e --env)'{-e,--env}'[Display using environment format]'
            ;;

        validate)
            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '(-n --neighbor)'{-n,--neighbor}'[Check parsing of neighbors]' \\
                '(-r --route)'{-r,--route}'[Check parsing of routes]' \\
                '(-v --verbose)'{-v,--verbose}'[Be verbose in display]' \\
                '(-p --pdb)'{-p,--pdb}'[Fire debugger on critical logging]' \\
                '*:configuration file:_alternative "configs:configuration file:compadd ${config_files}" "files:configuration file:_files -g \\"*.conf\\""'
            ;;

        decode)
            local -a families
            families=(
                'ipv4\\ unicast:IPv4 unicast'
                'ipv4\\ multicast:IPv4 multicast'
                'ipv4\\ mpls-vpn:IPv4 MPLS VPN'
                'ipv4\\ flow:IPv4 FlowSpec'
                'ipv6\\ unicast:IPv6 unicast'
                'ipv6\\ mpls-vpn:IPv6 MPLS VPN'
                'ipv6\\ flow:IPv6 FlowSpec'
                'l2vpn\\ vpls:L2VPN VPLS'
                'l2vpn\\ evpn:L2VPN EVPN'
                'bgp-ls\\ bgp-ls:BGP Link State'
            )

            _arguments \\
                '(- *)'{-h,--help}'[Show help message]' \\
                '(-n --nlri)'{-n,--nlri}'[Data is only the NLRI]' \\
                '(-u --update)'{-u,--update}'[Data is an update message]' \\
                '(-o --open)'{-o,--open}'[Data is an open message]' \\
                '(-d --debug)'{-d,--debug}'[Start Python debugger on errors]' \\
                '(-p --pdb)'{-p,--pdb}'[Fire debugger on fault]' \\
                '(-c --configuration)'{-c,--configuration}'[Configuration file]:file:_alternative "configs:configuration file:compadd ${config_files}" "files:configuration file:_files -g \\"*.conf\\""' \\
                '(-f --family)'{-f,--family}'[Address family]:family:compadd -d families ${families%%:*}' \\
                '(-i --path-information)'{-i,--path-information}'[Decode path-information]' \\
                ':hex payload:'
            ;;

        shell)
            local -a shell_cmds
            shell_cmds=(
                'install:Install shell completion'
                'uninstall:Uninstall shell completion'
                'completion:Generate completion script'
            )

            _arguments \\
                '1:command:((${shell_cmds}))' \\
                '2:shell:(bash zsh fish)'
            ;;
    esac
}

_exabgp "$@"
"""


def generate_fish_completion() -> str:
    """Generate Fish completion script."""
    return """# Fish completion for exabgp
# Copyright (c) 2009-2025 Exa Networks. All rights reserved.
# License: 3-clause BSD.

# Helper function to check if a subcommand has been given
function __fish_exabgp_using_subcommand
    set -l cmd (commandline -opc)
    set -l subcommands version cli run healthcheck server env validate decode shell

    if set -q cmd[2]
        if contains -- $cmd[2] $subcommands
            return 0
        end
    end
    return 1
end

# Helper function to get current subcommand
function __fish_exabgp_subcommand
    set -l cmd (commandline -opc)
    if set -q cmd[2]
        echo $cmd[2]
    end
end

# Helper function to find .conf files
function __fish_exabgp_conf_files
    set -l config_dirs . etc/exabgp /etc/exabgp
    for dir in $config_dirs
        if test -d $dir
            find $dir -maxdepth 1 -name "*.conf" 2>/dev/null | string replace -r '.*/' ''
        end
    end
end

# Subcommands (only suggest if no subcommand given yet)
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'version' -d 'Report ExaBGP version'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'cli' -d 'Interactive CLI with tab completion'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'run' -d 'Execute single command non-interactively'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'healthcheck' -d 'Monitor services and announce/withdraw routes'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'server' -d 'Start ExaBGP daemon'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'env' -d 'Show ExaBGP configuration information'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'validate' -d 'Validate configuration file'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'decode' -d 'Decode hex-encoded BGP packets'
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a 'shell' -d 'Manage shell completion'

# Backward compatibility: suggest .conf files as first argument
complete -c exabgp -n 'not __fish_exabgp_using_subcommand' -a '(__fish_exabgp_conf_files)'

# Common option
complete -c exabgp -s h -l help -d 'Show help message'

# cli subcommand
complete -c exabgp -n '__fish_seen_subcommand_from cli' -l pipename -d 'Name of the pipe' -r
complete -c exabgp -n '__fish_seen_subcommand_from cli' -l no-color -d 'Disable colored output'

# run subcommand
complete -c exabgp -n '__fish_seen_subcommand_from run' -l pipename -d 'Name of the pipe' -r
complete -c exabgp -n '__fish_seen_subcommand_from run' -l pipe -d 'Use named pipe transport'
complete -c exabgp -n '__fish_seen_subcommand_from run' -l socket -d 'Use Unix socket transport (default)'
complete -c exabgp -n '__fish_seen_subcommand_from run' -l batch -d 'Execute commands from file' -r -F
complete -c exabgp -n '__fish_seen_subcommand_from run' -l no-color -d 'Disable colored output'

# healthcheck subcommand
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l cmd -d 'Command to execute for health check' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l name -d 'Name for this health check' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l ip -d 'IP address or CIDR to announce' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l nexthop -d 'Next-hop IP address' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l local-ip -d 'Local IP address' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l interval -d 'Check interval in seconds' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l fast-interval -d 'Fast check interval' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l slow-interval -d 'Slow check interval' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l timeout -d 'Command timeout' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l rise -d 'Number of successes before UP' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l disable -d 'Disable health checks'
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l withdraw -d 'Withdraw route on failure'
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l label -d 'MPLS label' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l community -d 'BGP community' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l large-community -d 'Large BGP community' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l extended-community -d 'Extended community' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l rd -d 'Route distinguisher' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l route-distinguisher -d 'Route distinguisher' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l advertisement-delay -d 'Delay before announcing' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l local-preference -d 'Local preference value' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l med -d 'Multi-Exit Discriminator' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l origin -d 'Origin attribute' -r -a 'igp egp incomplete'
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l as-path -d 'AS path' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l logging -d 'Enable logging'
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l syslog -d 'Log to syslog' -r
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l pid -d 'PID file location' -r -F
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l daemonize -d 'Run as daemon'
complete -c exabgp -n '__fish_seen_subcommand_from healthcheck' -l no-daemonize -d 'Do not daemonize'

# server subcommand
complete -c exabgp -n '__fish_seen_subcommand_from server' -s v -l verbose -d 'Toggle all logging'
complete -c exabgp -n '__fish_seen_subcommand_from server' -s d -l debug -d 'Start Python debugger on issue'
complete -c exabgp -n '__fish_seen_subcommand_from server' -s s -l signal -d 'Issue SIGUSR1 after N seconds' -r
complete -c exabgp -n '__fish_seen_subcommand_from server' -s 1 -l once -d 'Only one connection attempt'
complete -c exabgp -n '__fish_seen_subcommand_from server' -s p -l pdb -d 'Fire debugger on critical logging'
complete -c exabgp -n '__fish_seen_subcommand_from server' -s P -l passive -d 'Only accept incoming connections'
complete -c exabgp -n '__fish_seen_subcommand_from server' -s m -l memory -d 'Display memory usage on exit'
complete -c exabgp -n '__fish_seen_subcommand_from server' -l profile -d 'Enable profiling' -r -F
complete -c exabgp -n '__fish_seen_subcommand_from server' -a '(__fish_exabgp_conf_files)'

# env subcommand
complete -c exabgp -n '__fish_seen_subcommand_from env' -s d -l diff -d 'Show only differences from defaults'
complete -c exabgp -n '__fish_seen_subcommand_from env' -s e -l env -d 'Display using environment format'

# validate subcommand
complete -c exabgp -n '__fish_seen_subcommand_from validate' -s n -l neighbor -d 'Check parsing of neighbors'
complete -c exabgp -n '__fish_seen_subcommand_from validate' -s r -l route -d 'Check parsing of routes'
complete -c exabgp -n '__fish_seen_subcommand_from validate' -s v -l verbose -d 'Be verbose in display'
complete -c exabgp -n '__fish_seen_subcommand_from validate' -s p -l pdb -d 'Fire debugger on critical logging'
complete -c exabgp -n '__fish_seen_subcommand_from validate' -a '(__fish_exabgp_conf_files)'

# decode subcommand
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s n -l nlri -d 'Data is only the NLRI'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s u -l update -d 'Data is an update message'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s o -l open -d 'Data is an open message'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s d -l debug -d 'Start Python debugger on errors'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s p -l pdb -d 'Fire debugger on fault'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s c -l configuration -d 'Configuration file' -r -a '(__fish_exabgp_conf_files)'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s f -l family -d 'Address family' -r -a 'ipv4\\ unicast ipv4\\ multicast ipv4\\ mpls-vpn ipv4\\ flow ipv6\\ unicast ipv6\\ mpls-vpn ipv6\\ flow l2vpn\\ vpls l2vpn\\ evpn bgp-ls\\ bgp-ls'
complete -c exabgp -n '__fish_seen_subcommand_from decode' -s i -l path-information -d 'Decode path-information'

# shell subcommand
complete -c exabgp -n '__fish_seen_subcommand_from shell' -a 'install' -d 'Install shell completion'
complete -c exabgp -n '__fish_seen_subcommand_from shell' -a 'uninstall' -d 'Uninstall shell completion'
complete -c exabgp -n '__fish_seen_subcommand_from shell' -a 'completion' -d 'Generate completion script'

# After 'shell install/uninstall/completion', suggest shells
complete -c exabgp -n '__fish_seen_subcommand_from shell; and __fish_seen_subcommand_from install uninstall completion' -a 'bash zsh fish'
"""


def generate_completion(shell: str) -> str:
    """Generate completion script for the specified shell."""
    generators = {
        'bash': generate_bash_completion,
        'zsh': generate_zsh_completion,
        'fish': generate_fish_completion,
    }

    generator = generators.get(shell)
    if not generator:
        raise ValueError(f'Unknown shell: {shell}')

    return generator()


def completion_command(shell: str) -> int:
    """Output completion script to stdout."""
    if shell not in ('bash', 'zsh', 'fish'):
        sys.stderr.write(f"Error: Unknown shell '{shell}'. Supported: bash, zsh, fish\n")
        return 1

    try:
        script = generate_completion(shell)
        sys.stdout.write(script)
        return 0
    except Exception as e:
        sys.stderr.write(f'Error generating completion: {e}\n')
        return 1


def install_completion(shell: str) -> int:
    """Install shell completion for the specified shell."""
    dest_path = get_completion_dest(shell)

    # Generate the completion script
    try:
        script = generate_completion(shell)
    except Exception as e:
        sys.stderr.write(f'Error generating completion: {e}\n')
        return 1

    # Create destination directory if it doesn't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the file
    try:
        dest_path.write_text(script)
        sys.stdout.write(f'✓ Installed {shell} completion to: {dest_path}\n')
    except Exception as e:
        sys.stderr.write(f'Error installing completion: {e}\n')
        return 1

    # Print activation instructions
    activation = get_activation_message(shell)
    sys.stdout.write(f'\nTo activate completion, {activation}\n')

    # Verify completion works
    sys.stdout.write('\nVerify by running: exabgp <TAB>\n')
    sys.stdout.write('You should see: cli  decode  env  healthcheck  run  server  shell  validate  version\n')

    return 0


def uninstall_completion(shell: str) -> int:
    """Uninstall shell completion for the specified shell."""
    dest_path = get_completion_dest(shell)

    if not dest_path.exists():
        sys.stdout.write(f'✓ {shell.capitalize()} completion is not installed at: {dest_path}\n')
        return 0

    # Remove the file
    try:
        dest_path.unlink()
        sys.stdout.write(f'✓ Removed {shell} completion from: {dest_path}\n')

        # Check if parent directory is now empty and remove it
        if dest_path.parent.exists() and not any(dest_path.parent.iterdir()):
            dest_path.parent.rmdir()
            sys.stdout.write(f'✓ Removed empty directory: {dest_path.parent}\n')

    except Exception as e:
        sys.stderr.write(f'Error removing completion: {e}\n')
        return 1

    sys.stdout.write('\nCompletion removed. Restart your shell for changes to take effect.\n')
    return 0


def cmdline(args):
    """Handle 'exabgp shell' subcommands."""
    if not hasattr(args, 'shell_command') or args.shell_command is None:
        sys.stderr.write('Error: Please specify a subcommand (install, uninstall, or completion)\n')
        sys.stderr.write('Usage: exabgp shell install [bash|zsh|fish]\n')
        sys.stderr.write('       exabgp shell uninstall [bash|zsh|fish]\n')
        sys.stderr.write('       exabgp shell completion <bash|zsh|fish>\n')
        return 1

    shell = args.shell if hasattr(args, 'shell') and args.shell else detect_shell()

    if shell not in ('bash', 'zsh', 'fish'):
        sys.stderr.write(f"Error: Unknown shell '{shell}'. Supported: bash, zsh, fish\n")
        return 1

    if args.shell_command == 'install':
        return install_completion(shell)
    elif args.shell_command == 'uninstall':
        return uninstall_completion(shell)
    elif args.shell_command == 'completion':
        # For 'completion' command, shell argument is required
        if not hasattr(args, 'shell') or not args.shell:
            sys.stderr.write('Error: Shell argument required for completion command\n')
            sys.stderr.write('Usage: exabgp shell completion <bash|zsh|fish>\n')
            return 1
        return completion_command(args.shell)
    else:
        sys.stderr.write(f"Error: Unknown command '{args.shell_command}'\n")
        return 1


def setargs(parser):
    """Configure argparse subcommand for 'shell' commands."""
    subparsers = parser.add_subparsers(dest='shell_command', help='Shell completion commands')

    # 'shell install' subcommand
    install_parser = subparsers.add_parser(
        'install', help='Install shell completion scripts', description='Install shell completion for the current shell'
    )
    install_parser.add_argument(
        'shell',
        nargs='?',
        choices=['bash', 'zsh', 'fish'],
        help='Shell to install completion for (auto-detects if not specified)',
    )

    # 'shell uninstall' subcommand
    uninstall_parser = subparsers.add_parser(
        'uninstall',
        help='Uninstall shell completion scripts',
        description='Uninstall shell completion for the current shell',
    )
    uninstall_parser.add_argument(
        'shell',
        nargs='?',
        choices=['bash', 'zsh', 'fish'],
        help='Shell to uninstall completion for (auto-detects if not specified)',
    )

    # 'shell completion' subcommand - outputs to stdout
    completion_parser = subparsers.add_parser(
        'completion', help='Generate completion script', description='Output completion script to stdout'
    )
    completion_parser.add_argument(
        'shell', choices=['bash', 'zsh', 'fish'], help='Shell to generate completion for (required)'
    )
