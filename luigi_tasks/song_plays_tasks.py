import luigi
import os
from urllib2 import urlopen, HTTPError
from luigi.contrib.spark import SparkSubmitTask

class HttpTarget(luigi.Target):

    def __init__(self, url):
        self.url = url

    def exists(self):
        try:
            urlopen(self.url)
            return True
        except HTTPError:
            return False


class ExternalFileChecker(luigi.ExternalTask):

    url = luigi.Parameter()

    def output(self):
        return HttpTarget(self.url)


def make_local_dirs_if_not_exists(path):
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))


class DownloadSpins(luigi.Task):

    date = luigi.DateParameter()
    url = "https://s3.amazonaws.com/storage-handler-docs/spins.snappy.parquet"

    def output(self):
        path = 'data/spins/%Y/%m/%d/spins.snappy.parquet'
        path = self.date.strftime(path)
        return luigi.LocalTarget(path)

    def requires(self):
        return ExternalFileChecker(url=self.url)

    def run(self):
        path = self.output().path
        make_local_dirs_if_not_exists(path)
        with open(path, 'w') as out_file:
            for data in urlopen(self.url).read():
                out_file.write(data)



class DownloadListeners(luigi.Task):

    date = luigi.DateParameter()
    url = "https://s3.amazonaws.com/storage-handler-docs/listeners.snappy.parquet"

    def output(self):
        path = 'data/listeners/listeners.snappy.parquet'
        data_path = self.date.strftime(path)
        path = 'data/markers/%Y/%m/%d/listeners_downloaded.SUCCESS'
        marker_path = self.date.strftime(path)
        return {'data': luigi.LocalTarget(data_path), 
                'marker': luigi.LocalTarget(marker_path)}


    def requires(self):
        return ExternalFileChecker(url=self.url)

    def run(self):
        data_path = self.output()['data'].path
        marker_path = self.output()['marker'].path
        make_local_dirs_if_not_exists(data_path)
        make_local_dirs_if_not_exists(marker_path)
        with open(data_path, 'w') as out_file:
            for data in urlopen(self.url).read():
                out_file.write(data)
        with open(marker_path, 'w') as out_file:
            pass


class DatasetGen(SparkSubmitTask):

    date = luigi.DateParameter()

    # Spark properties
    driver_memory = '1g'
    executor_cores = 1
    driver_cores = 1
    executor_memory = '1g'
    num_executors = 1
    deploy_mode = 'client'
    spark_submit = 'spark-submit'
    master = 'local'

    app = 'song_plays.jar'
    entry_class = 'com.song.plays.DatasetGen'


    def requires(self):
        return {
            "listeners" : DownloadListeners(date=self.date),
            "spins": DownloadSpins(date=self.date)
        }

    def output(self):
        path = "data/output/%Y/%m/%d/enriched_spins.snappy.parquet"
        path = self.date.strftime(path)
        return luigi.LocalTarget(path)

    def app_options(self):
        reqs_dict = self.requires()
        listeners_path = reqs_dict['listeners'].output()['data'].path
        spins_path = reqs_dict['spins'].output().path
        args = [
            "--day", self.date.strftime("%Y-%m-%d"),
            "--listeners_path", listeners_path,
            "--spins_path", spins_path,
            "--out_path", self.output().path,
        ]
        return args