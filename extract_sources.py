"""
Given a kernel tree and a config, builds the kernel with that config and
extracts the list of source files compiled in the vmlinux image and modules.
The output is written to sources.txt in the directory provided as --output-dir.

The kernel must be compiled with debug information for this to work,
by setting CONFIG_DEBUG_INFO=y and CONFIG_DEBUG_INFO_DWARF4=y.

The current directory must be a clean Linux kernel tree.
Also, make sure that the llvm-dwarfdump binary is installed and in the PATH.
"""

import argparse
import glob
import logging
import multiprocessing
import os
import shutil
import subprocess


CUR_DIR = os.path.abspath(os.curdir)
OUTPUT_FILENAME = 'sources.txt'


def setup_config(config_path: str):
    """
    Copies the kernel config to the current directory and runs
    `make olddefconfig`.
    """

    logging.info('Running `make clean` and `make mrproper`')
    subprocess.run(['make', 'clean'], check=True)
    subprocess.run(['make', 'mrproper'], check=True)

    src = os.path.abspath(config_path)
    logging.info(f'Copying config file from {src}')
    dst = os.path.join(CUR_DIR, '.config')
    try:
        shutil.copyfile(src, dst)
    except shutil.SameFileError:
        pass  # It's fine.

    logging.info('Running `make olddefconfig`')
    subprocess.run(['make', 'olddefconfig'], check=True)

def compile_kernel():
    """Compiles the kernel."""

    logging.info('Compiling kernel')
    subprocess.run(['make', '-j', str(multiprocessing.cpu_count())], check=True)
    logging.info('Kernel compiled successfully')

def extract_sources_from_binary(binary_path: str) -> list[str]:
    def normalize_source_path(path: str) -> str:
        path = path.strip()
        if not path.startswith(CUR_DIR):
            logging.warning(f'Found anomalous source file path {path}')
            return ''
        return os.path.normpath(path.removeprefix(CUR_DIR+'/'))

    logging.info(f'Extracting sources from {binary_path}')
    output = subprocess.check_output(['llvm-dwarfdump', '--show-sources', binary_path]).decode('utf-8')
    return [f for f in map(normalize_source_path, output.strip().splitlines()) if f not in ('', '<built-in>')]

def extract_sources() -> list[str]:
    """
    Uses llvm-dwarfdump to extract the list of source files.
    """

    binaries = ['vmlinux'] + glob.glob('**/*.ko', recursive=True)
    return list(set(source for binary in binaries for source in extract_sources_from_binary(binary)))

def write_sources(sources: list[str], output_dir: str):
    """Writes the given source files to the output file."""

    sources.sort()
    output_dir = os.path.abspath(output_dir)
    output_file = os.path.join(output_dir, OUTPUT_FILENAME)

    logging.info(f'Writing sources to {output_file}')

    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, 'w') as f:
        print(*sources, sep='\n', file=f)

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config-path', help='Relative or absolute path of the kernel config', required=True)
    parser.add_argument('-o', '--output-dir', help='Directory to write the output to', default=CUR_DIR)
    parser.add_argument(
        '--no-compile',
        help='Don\'t compile the kernel (implies vmlinux and .ko objects already exist)',
        action='store_true',
        default=False,
    )
    args = parser.parse_args()

    if not args.no_compile:
        try:
            setup_config(args.config_path)
        except Exception as e:
            logging.exception(e.add_note('Failed to set up kernel config'))
            exit(0)

        try:
            compile_kernel()
        except Exception as e:
            logging.exception(e.add_note('Failed to compile kernel'))
            exit(0)

    try:
        sources = extract_sources()
    except Exception as e:
        logging.exception(e.add_note('Failed to extract sources from compiled binaries'))
        exit(0)

    try:
        write_sources(sources, args.output_dir)
    except Exception as e:
        logging.exception(e.add_note('Failed to write output'))
        exit(0)


if __name__ == '__main__':
    main()
