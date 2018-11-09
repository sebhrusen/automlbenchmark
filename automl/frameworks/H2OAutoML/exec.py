import logging
import time

import h2o
from h2o.automl import H2OAutoML

from automl.benchmark import TaskConfig
from automl.data import Dataset
from automl.results import save_predictions_to_file

log = logging.getLogger(__name__)


def run(dataset: Dataset, config: TaskConfig):
    log.info("\n**** H2O AutoML ****\n")
    # Mapping of benchmark metrics to H2O metrics
    if config.metric == 'acc':
        h2o_metric = 'mean_per_class_error'
    elif config.metric == 'auc':
        h2o_metric = 'AUC'
    elif config.metric == 'logloss':
        h2o_metric = 'logloss'
    else:
        # TODO: Figure out if we are going to blindly pass metrics through, or if we use a strict mapping
        log.warning("Performance metric {} not supported, using AUTO.".format(config.metric))
        h2o_metric = None

    try:
        log.info("Starting H2O cluster.")
        log.debug("cores {}, memory {}mb".format(config.cores, config.max_mem_size_mb))
        h2o.init(nthreads=config.cores, max_mem_size=str(config.max_mem_size_mb) + "M")

        # Load train as an H2O Frame, but test as a Pandas DataFrame
        log.debug("Loading train data from {}".format(dataset.train.path))
        train = h2o.import_file(dataset.train.path)
        log.debug("Loading test data from {}".format(dataset.test.path))
        test = h2o.import_file(dataset.test.path)

        log.info("Running model on task {}, fold {}".format(config.name, config.fold))
        log.debug("Running H2O AutoML with a maximum time of {}s on {} core(s), optimizing {}."
              .format(config.max_runtime_seconds, config.cores, h2o_metric))
        start_time = time.time()

        aml = H2OAutoML(max_runtime_secs=config.max_runtime_seconds, sort_metric=h2o_metric)
        aml.train(y=dataset.target.index, training_frame=train)
        actual_runtime_min = (time.time() - start_time)/60.0
        log.info("Requested training time (minutes): " + str((config.max_runtime_seconds/60.0)))
        log.info("Actual training time (minutes): " + str(actual_runtime_min))

        log.debug("Predicting the test set.")
        predictions = aml.predict(test).as_data_frame()

        y_pred = predictions.iloc[:, 0]
        y_true = test[:, dataset.target.index].as_data_frame(header=False)

        class_predictions = y_pred.values
        class_probabilities = predictions.iloc[:, 1:].values

        save_predictions_to_file(dataset=dataset,
                                 output_file=config.output_file_template,
                                 class_probabilities=class_probabilities,
                                 class_predictions=class_predictions,
                                 class_truth=y_true.values,
                                 encode_classes=True)

    finally:
        if h2o.connection():
            h2o.connection().close()
