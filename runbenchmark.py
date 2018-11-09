# prevent asap other modules from defining the root logger using basicConfig
import logging
logging.basicConfig(handlers=[logging.NullHandler()])

import argparse
import os

import automl
from automl.utils import json_load
from automl import log


parser = argparse.ArgumentParser()
parser.add_argument('framework', type=str,
                    help='The framework to evaluate as defined in resources/frameworks.json')
parser.add_argument('benchmark', type=str, nargs='?', default='test',
                    help='The benchmark type to run as defined in resources/benchmarks/{benchmark}.json or the path to a benchmark description file. Defaults to `test`')
parser.add_argument('-m', '--mode', choices=['local', 'docker', 'aws'], default='local',
                    help='The mode that specifies what backend is used (currently local [default], docker, or aws)')
parser.add_argument('-t', '--task', metavar='task_id', default=None,
                    help='The specific task name to run in the benchmark')
parser.add_argument('-f', '--fold', metavar='fold_num', type=int, nargs='*',
                    help='The specific fold(s) to run in the benchmark')
parser.add_argument('-i', '--indir', metavar='input_dir', default=None,
                    help='Folder where datasets are loaded by default.')
parser.add_argument('-o', '--outdir', metavar='output_dir', default=None,
                    help='Folder where all the outputs should be written.')
parser.add_argument('-r', '--region', metavar='aws_region', default=None,
                    help='The region on which to run the benchmark when using AWS.')
parser.add_argument('-s', '--setup', choices=['auto', 'skip', 'force', 'only'], default='auto',
                    help='Framework/platform setup mode: supported values = auto [default], skip, force, only')
parser.add_argument('--reuse-instance', type=bool, metavar='true|false', nargs='?', const=True, default=False,
                    help='Set to true if reusing the same container instance(s) for all tasks (docker and aws mode only)')
args = parser.parse_args()

script_name = os.path.splitext(os.path.basename(__file__))[0]
log_dir = args.outdir if args.outdir else '.'
automl.logger.setup(log_file=os.path.join(log_dir, script_name+'.log'),
                    root_file=os.path.join(log_dir, script_name+'_full.log'),
                    root_level='DEBUG', console_level='INFO')

log.info("Running `%s` on `%s` benchmarks in `%s` mode", args.framework, args.benchmark, args.mode)
log.debug("script args: %s", args)

with open("resources/config.json") as file:
    config = json_load(file, as_object=True)
    config.script = os.path.basename(__file__)
    if args.indir:
        config.input_dir = args.indir
    if args.outdir:
        config.output_dir = args.outdir
resources = automl.Resources(config)

if args.mode == "local":
    bench = automl.Benchmark(args.framework, args.benchmark, resources)
elif args.mode == "docker":
    bench = automl.DockerBenchmark(args.framework, args.benchmark, resources, reuse_instance=args.reuse_instance)
elif args.mode == "aws":
    bench = automl.AWSBenchmark(args.framework, args.benchmark, resources, region=args.region, reuse_instance=args.reuse_instance)
else:
    raise ValueError("mode must be one of 'aws', 'docker' or 'local'.")

if args.setup == 'only':
    log.warn("Setting up {} environment only, no benchmark will be run".format(args.mode))

bench.setup(automl.Benchmark.SetupMode[args.setup])
if args.setup != 'only':
    if args.task is None:
        res = bench.run()
    else:
        res = bench.run_one(args.task, args.fold)
