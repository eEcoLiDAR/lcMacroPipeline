import sys

from dask.distributed import Client, LocalCluster, SSHCluster

from lc_macro_pipeline.pipeline import Pipeline


class MacroPipeline(object):
    """
    Class to setup macro pipeline workflows. Each MacroPipeline object entails
    multiple tasks that correspond to Pipeline instances. All the tasks are run
    in parallel using dask.

    We implement dask for embarrassingly parallel tasks, see
    https://examples.dask.org/applications/embarrassingly-parallel.html

    Example:
        >>> class Foo(Pipeline):
        ...     def __init__(self):
        ...         self.pipeline = ['task_info']
        ...     def task_info(self):
        ...         print(os.getpid())
        >>> macro = MacroPipeline()
        >>> one, two = Foo(), Foo()
        >>> macro.tasks = [one, two]
        >>> macro.run() # the default thread parallelism is used
        61244
        61245
    """
    def __init__(self):
        self._tasks = list()

    @property
    def tasks(self):
        """ List of tasks that need to be run. """
        return self._tasks

    @tasks.setter
    def tasks(self, tasks):
        try:
            _ = iter(tasks)
        except TypeError as err:
            raise err('The collection of tasks should be an iterable object.')
        for task in tasks:
            assert isinstance(task, Pipeline), \
                'Task {} is not a derived Pipeline object'.format(task)
        self._tasks = [task for task in tasks]

    def add_task(self, task):
        """
        Add pipeline instance to the collection of tasks to be executed.

        :param task: Pipeline instance.
        """
        assert isinstance(task, Pipeline)
        self.tasks.append(task)
        return self

    @staticmethod
    def _run_task(f):
        exctype, value = (None, None)
        try:
            _ = f()
        except:
            # sys.exc_info() provides info about current exception,
            # thus it must remain in the except block!
            exctype, value = sys.exc_info()[:2]
        return (exctype, value)

    # def run(self):
    #     """ Run the macro pipeline. """
    #     delayed_tasks = [delayed(self._run_task)(task.run)
    #                      for task in self.tasks]
    #     # return dask.compute(*delayed_tasks)
    #     bag = dask.bag.from_delayed(delayed_tasks)
    #     return bag.compute()


    def setup_client(self, mode='local', **kwargs):
        if mode == 'local':
            self.client = Client()
        elif mode == 'ssh':
            ssh_cluster = SSHCluster(**kwargs)
            self.client = Client(ssh_cluster)
        elif mode == 'slurm':
            print('Slurm cluster is not implemented in this version!')
            raise NotImplementedError
        else:
            print('Unknown mode of setup client {}!'.format(mode))
            raise RuntimeError

    def run(self):
        """ Run the macro pipeline. """
        futures = [self.client.submit(self._run_task, task.run)
                   for task in self.tasks]
        results = self.client.gather(futures)
        self.client.shutdown()
        return results

