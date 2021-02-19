import os
import os.path as op
import sys
from typing import List

from watchdog.events import FileSystemEvent

from foremon.config import *
from foremon.display import *
from foremon.monitor import Monitor
from foremon.task import ForemonTask, ScriptTask
from foremon.util import guess_args, relative_if_cwd

DEFAULT_CONFIG = op.join(os.getcwd(), "pyproject.toml")
AUTO_RELOAD_ALIAS = 'foremon-auto-reload'


class ReloadTask(ForemonTask):
    """
    This task will reload the Foremon app when a config change is detected.
    """

    app: 'Foremon'
    config_file: str

    def __init__(self, app: 'Foremon', config_file: str):
        super().__init__(ForemonConfig(
            alias=AUTO_RELOAD_ALIAS,
            skip=False,
            paths=[op.dirname(config_file)],
            patterns=[op.basename(config_file)]))
        self.app = app
        self.config_file = config_file

    async def _run(self, ev: FileSystemEvent):
        if not ev or not isinstance(ev, FileSystemEvent):
            return
        display_info(
            f'config {relative_if_cwd(ev.src_path)} was {ev.event_type}, reloading ...')
        try:
            self.app.reload()
        except Exception as e:
            display_error('fatal error, stopping', e)
            self.app.monitor.handle_input('exit')


class Foremon:

    config: ForemonConfig
    options: ForemonOptions
    monitor: Monitor

    def __init__(self, options: ForemonOptions):
        self.options = options or ForemonOptions()
        self.monitor = Monitor()
        self.config = ForemonConfig()

    @property
    def tasks(self) -> List[ForemonTask]:
        return list(self.monitor.all_tasks)

    def get_task(self, name: str) -> Optional[ForemonTask]:
        for task in self.tasks:
            if task.name == name:
                return task
        return None

    def get_pipe(self):
        return sys.stdin

    ###########################################################################
    #
    # Configuration loading & modification.
    #
    ###########################################################################

    def load_config(self):
        """
        Load the `self.config`. This will also update the `default` config with
        the current `self.options`.
        """

        self._load_config_file()
        self._extend_default_config()

    def _load_config_file(self, default: str = DEFAULT_CONFIG):
        """
        Load a config file. If no config is loaded the `self.config` property is
        reset to en empty config.
        """

        config_file: str = self.options.config_file or default

        exists = op.exists(config_file)
        if not exists:

            if config_file != default:
                display_error(f'cannot find config file {config_file}')

            self.config = ForemonConfig()
            return

        with open(config_file, 'r') as fd:
            project = PyProjectConfig.parse_toml(fd.read())
            config = project.tool.foremon
            if config is None:
                display_debug(
                    'no [tool.foremon] section specified in', relative_if_cwd(config_file))
                self.config = ForemonConfig()
            else:
                display_success(
                    'loaded [tool.foremon] config from', relative_if_cwd(config_file))
                self.config = config
        return

    def _new_reload_task(self, config_file: str) -> ForemonTask:
        return ReloadTask(self, config_file)

    def _extend_default_config(self):
        c: ForemonConfig = self.config
        o: ForemonOptions = self.options

        if not o.no_guess:
            args = list(map(guess_args, o.scripts))
            c.scripts.extend(args)
        else:
            c.scripts.extend(o.scripts)
        if o.unsafe:
            c.ignore_defaults.clear()
        if o.cwd:
            c.cwd = o.cwd

        if o.ignore:
            c.ignore = o.ignore
        if o.paths:
            c.paths = o.paths
        if o.patterns:
            c.patterns = o.patterns

    ###########################################################################
    #
    # Runtime state & events.
    #
    ###########################################################################

    def run_forever(self) -> int:
        self.load_config()
        self.reset_monitor()

        if not self.monitor.all_tasks:
            display_warning(
                "no scripts or executable specified, nothing to do ...")
            return 2

        if self.options.dry_run:
            display_success('dry run complete')
            return 0

        self._run()

        return 0

    def _run(self):
        """
        Blocks until program exits.
        """
        try:
            loop = self.monitor.loop
            loop.run_until_complete(self.monitor.start_interactive())
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.monitor.terminate_tasks()
            except:
                pass

    def reload(self):
        # pause events
        with self.monitor.paused():
            self.monitor.reset()
            self.load_config()
            self.reset_monitor()

        self.monitor.queue_all_tasks()

    def reset_monitor(self):
        self.monitor.reset()
        self.monitor.set_pipe(self.get_pipe())

        for task in self._make_tasks():
            task.add_before_callback(self._before_task_runs)
            self.monitor.add_task(task)
            display_debug("task", task.name, "ready for monitor")

        # Do not schedule an auto-reload if there were no scripts
        if self.monitor.all_tasks and self.options.auto_reload:
            self.monitor.add_task(
                self._new_reload_task(self.options.config_file))

    def _make_tasks(self):
        """
        Generator yields all tasks that are active.

        The default task is always active unless its `scripts` list is empty.

        Other tasks are always skipped unless it's alias is in the
        `options.aliases` list or the `options.use_all` flag is true.

        If `options.use_all` and `config.skip` are true and the `config.alias`
        is not in the `options.aliases` list then the task is skipped.
        """

        use_all: bool = self.options.use_all
        aliases: List[str] = self.options.aliases

        configs = [self.config]

        while configs:
            task = ScriptTask(configs.pop(0))

            configs.extend(task.config.configs)

            if not task.config.scripts:
                display_debug("task", task.name,
                              "was skipped because scripts is empty")
                continue

            if task.name in aliases:
                # Override skip if `-a` is used explicitly
                task.config.skip = False

                yield task
                continue

            if use_all and not task.config.skip:
                yield task
                continue

            if task.config.skip:
                display_debug('task', task.name, 'is skipped')

    def _before_task_runs(self, task: ForemonTask, ev: Optional[FileSystemEvent] = None):

        if self.options.verbose and isinstance(ev, FileSystemEvent):
            # try to shorten the name for more readable output
            path = relative_if_cwd(ev.src_path)
            kind = ev.event_type
            display_info(f'triggered because {path} was {kind}')
