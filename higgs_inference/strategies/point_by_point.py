################################################################################
# Imports
################################################################################

from __future__ import absolute_import, division, print_function

import logging
import numpy as np

from scipy.interpolate import LinearNDInterpolator
from sklearn.preprocessing import StandardScaler

from keras.wrappers.scikit_learn import KerasRegressor
from keras.callbacks import EarlyStopping

from carl.ratios import ClassifierScoreRatio
from carl.learning import CalibratedClassifierScoreCV

from higgs_inference.models.models_point_by_point import make_classifier, make_regressor


################################################################################
# What do
################################################################################

def point_by_point_inference(algorithm='carl',
                             options=''):
    """
    Trains and evaluates one of the point-by-point higgs_inference methods.

    :param algorithm: Type of the algorithm used. Currently supported: 'carl' and 'regression'.
    :param options: Further options in a list of strings or string.
    """

    logging.info('Starting point-by-point inference')

    assert algorithm in ['carl', 'regression']

    denom1_mode = ('denom1' in options)
    debug_mode = ('debug' in options)
    learn_logr_mode = ('learns' not in options)
    short_mode = ('short' in options)
    long_mode = ('long' in options)
    deep_mode = ('deep' in options)
    shallow_mode = ('shallow' in options)

    filename_addition = ''

    if not learn_logr_mode:
        filename_addition += '_learns'

    n_hidden_layers = 2
    if shallow_mode:
        n_hidden_layers = 1
        filename_addition += '_shallow'
    elif deep_mode:
        n_hidden_layers = 3
        filename_addition += '_deep'

    n_epochs = 20
    early_stopping = True
    if debug_mode:
        n_epochs = 1
        early_stopping = False
        filename_addition += '_debug'
    elif long_mode:
        n_epochs = 50
        filename_addition += '_long'
    elif short_mode:
        n_epochs = 1
        early_stopping = False
        filename_addition += '_short'

    theta1 = 708
    input_filename_addition = ''
    if denom1_mode:
        input_filename_addition = '_denom1'
        filename_addition += '_denom1'
        theta1 = 422

    data_dir = '../data'
    # unweighted_events_dir = '../data/unweighted_events'
    unweighted_events_dir = '/scratch/jb6504/higgs_inference/data/unweighted_events'
    results_dir = '../results/point_by_point'
    neyman_dir = results_dir + '/neyman'

    logging.info('Main settings:')
    logging.info('  Algorithm:                %s', algorithm)
    logging.info('Options:')
    logging.info('  Number of epochs:         %s', n_epochs)
    logging.info('  Number of hidden layers:  %s', n_hidden_layers)

    ################################################################################
    # Data
    ################################################################################

    thetas = np.load(data_dir + '/thetas/thetas_parameterized.npy')
    n_thetas = len(thetas)
    theta_benchmark_trained = 422
    theta_benchmark_nottrained = 9
    training_thetas = [0, 13, 14, 15, 16, 9, 422, 956, 666, 802, 675, 839, 699, 820, 203, 291, 634, 371, 973, 742, 901,
                       181, 82, 937, 510, 919, 745, 588, 804, 963, 396, 62, 401, 925, 874, 770, 108, 179, 669, 758, 113,
                       587, 600, 975, 496, 66, 467, 412, 701, 986, 598, 810, 97, 18, 723, 159, 320, 301, 352, 159, 89,
                       421, 574, 923, 849, 299, 119, 167, 939, 402, 52, 787, 978, 41, 873, 533, 827, 304, 294, 760, 890,
                       539, 1000, 291, 740, 276, 679, 167, 125, 429, 149, 430, 720, 123, 908, 256, 777, 809, 269, 851]

    X_calibration = np.load(unweighted_events_dir + '/X_calibration' + input_filename_addition + '.npy')
    weights_calibration = np.load(
        unweighted_events_dir + '/weights_calibration' + input_filename_addition + '.npy')

    X_test = np.load(unweighted_events_dir + '/X_test' + input_filename_addition + '.npy')
    r_test = np.load(unweighted_events_dir + '/r_test' + input_filename_addition + '.npy')
    X_neyman_observed = np.load(unweighted_events_dir + '/X_neyman_observed.npy')

    n_expected_events = 36
    n_events_test = X_test.shape[0]
    assert n_thetas == r_test.shape[0]

    ################################################################################
    # Regression approaches
    ################################################################################

    if algorithm == 'regression':

        expected_llr = []

        # Loop over the training thetas
        for i, t in enumerate(training_thetas):

            logging.info('Starting theta %s/%s: number %s (%s)', i + 1, len(training_thetas), t, thetas[t])

            # Load data
            X_train = np.load(
                unweighted_events_dir + '/X_train_point_by_point_' + str(t) + input_filename_addition + '.npy')
            r_train = np.load(
                unweighted_events_dir + '/r_train_point_by_point_' + str(t) + input_filename_addition + '.npy')

            assert np.all(np.isfinite(np.log(r_train)))

            # Scale data
            scaler = StandardScaler()
            scaler.fit(np.array(X_train, dtype=np.float64))
            X_train_transformed = scaler.transform(X_train)
            X_test_transformed = scaler.transform(X_test)
            X_neyman_observed_transformed = scaler.transform(
                X_neyman_observed.reshape((-1, X_neyman_observed.shape[2])))

            assert np.all(np.isfinite(X_train_transformed))
            assert np.all(np.isfinite(X_test_transformed))

            regr = KerasRegressor(lambda: make_regressor(n_hidden_layers=n_hidden_layers),
                                  epochs=n_epochs, validation_split=0.1,
                                  verbose=2)

            # Training
            regr.fit(X_train_transformed, np.log(r_train),
                     callbacks=([EarlyStopping(verbose=1, patience=3)] if early_stopping else None))

            # Evaluation
            prediction = regr.predict(X_test_transformed)
            this_r = np.exp(prediction[:])

            if not np.all(np.isfinite(prediction)):
                logging.warning('Regression output contains NaNs')

            expected_llr.append(- 2. * n_expected_events / n_events_test * np.sum(np.log(this_r)))

            # For some benchmark thetas, save r for each phase-space point
            if t == theta_benchmark_nottrained:
                np.save(results_dir + '/r_nottrained_' + algorithm + filename_addition + '.npy', this_r)
            elif t == theta_benchmark_trained:
                np.save(results_dir + '/r_trained_' + algorithm + filename_addition + '.npy', this_r)

            # Neyman construction: evaluate observed sample (raw)
            log_r_neyman_observed = regr.predict(X_neyman_observed_transformed)
            llr_neyman_observed = -2. * np.sum(log_r_neyman_observed.reshape((-1, n_expected_events)), axis=1)
            np.save(neyman_dir + '/neyman_llr_observed_' + algorithm + '_' + str(t) + '.npy',
                    llr_neyman_observed)

            # Neyman construction: load distribution sample
            X_neyman_distribution = np.load(unweighted_events_dir + '/X_neyman_distribution_' + str(t) + '.npy')
            X_neyman_distribution_transformed = scaler.transform(
                X_neyman_distribution.reshape((-1, X_neyman_distribution.shape[2])))

            # Neyman construction: evaluate distribution sample (raw)
            log_r_neyman_distribution = regr.predict(X_neyman_distribution_transformed)
            llr_neyman_distribution = -2. * np.sum(log_r_neyman_distribution.reshape((-1, n_expected_events)), axis=1)
            np.save(neyman_dir + '/neyman_llr_distribution_' + algorithm + '_' + str(t) + '.npy',
                    llr_neyman_distribution)

        expected_llr = np.asarray(expected_llr)

        logging.info('Interpolation')

        interpolator = LinearNDInterpolator(thetas[training_thetas], expected_llr)
        expected_llr_all = interpolator(thetas)
        # gp = GaussianProcessRegressor(normalize_y=True,
        #                              kernel=C(1.0) * Matern(1.0, nu=0.5), n_restarts_optimizer=10)
        # gp.fit(thetas[training_thetas], expected_llr)
        # expected_llr_all = gp.predict(thetas)
        np.save(results_dir + '/llr_' + algorithm + filename_addition + '.npy', expected_llr_all)

    ################################################################################
    # Carl approaches
    ################################################################################

    else:

        expected_llr = []
        expected_llr_calibrated = []

        # Loop over the 15 thetas
        for i, t in enumerate(training_thetas):

            logging.info('Starting theta %s/%s: number %s (%s)', i + 1, len(training_thetas), t, thetas[t])

            # Load data
            X_train = np.load(
                unweighted_events_dir + '/X_train_point_by_point_' + str(t) + input_filename_addition + '.npy')
            y_train = np.load(
                unweighted_events_dir + '/y_train_point_by_point_' + str(t) + input_filename_addition + '.npy')

            # Scale data
            scaler = StandardScaler()
            scaler.fit(np.array(X_train, dtype=np.float64))
            X_train_transformed = scaler.transform(X_train)
            X_test_transformed = scaler.transform(X_test)
            X_calibration_transformed = scaler.transform(X_calibration)
            X_neyman_observed_transformed = scaler.transform(
                X_neyman_observed.reshape((-1, X_neyman_observed.shape[2])))

            clf = KerasRegressor(lambda: make_classifier(n_hidden_layers=n_hidden_layers, learn_log_r=learn_logr_mode),
                                 epochs=n_epochs, validation_split=0.1,
                                 verbose=2)

            # Training
            clf.fit(X_train_transformed, y_train,
                    callbacks=([EarlyStopping(verbose=1, patience=3)] if early_stopping else None))

            # carl wrapper
            ratio = ClassifierScoreRatio(clf, prefit=True)

            # Evaluation
            this_r, _ = ratio.predict(X_test_transformed)

            expected_llr.append(- 2. * n_expected_events / n_events_test * np.sum(np.log(this_r)))

            if t == theta_benchmark_nottrained:
                np.save(results_dir + '/r_nottrained_' + algorithm + filename_addition + '.npy', this_r)
            elif t == theta_benchmark_trained:
                np.save(results_dir + '/r_trained_' + algorithm + filename_addition + '.npy', this_r)

            # Calibration
            n_calibration_each = X_calibration_transformed.shape[0]
            X_calibration_both = np.zeros((2 * n_calibration_each, X_calibration_transformed.shape[1]))
            X_calibration_both[:n_calibration_each] = X_calibration_transformed
            X_calibration_both[n_calibration_each:] = X_calibration_transformed
            y_calibration = np.zeros(2 * n_calibration_each)
            y_calibration[n_calibration_each:] = 1.
            w_calibration = np.zeros(2 * n_calibration_each)
            w_calibration[:n_calibration_each] = weights_calibration[t]
            w_calibration[n_calibration_each:] = weights_calibration[theta1]

            ratio_calibrated = ClassifierScoreRatio(
                # CalibratedClassifierScoreCV(clf, cv='prefit', bins=100, independent_binning=False)
                CalibratedClassifierScoreCV(clf, cv='prefit', method='isotonic')
            )
            ratio_calibrated.fit(X_calibration_both, y_calibration, sample_weight=w_calibration)

            # Evaluation of calibrated classifier
            this_r, _ = ratio_calibrated.predict(X_test_transformed)
            expected_llr_calibrated.append(- 2. * n_expected_events / n_events_test * np.sum(np.log(this_r)))

            if t == theta_benchmark_nottrained:
                np.save(results_dir + '/r_nottrained_' + algorithm + '_calibrated' + filename_addition + '.npy', this_r)

                # Save calibration histograms
                np.save(results_dir + '/calvalues_nottrained_' + algorithm + filename_addition + '.npy',
                        ratio_calibrated.classifier_.calibration_sample[:n_calibration_each])
                # np.save(results_dir + '/cal0histo_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.histogram_)
                # np.save(results_dir + '/cal0edges_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.edges_[0])
                # np.save(results_dir + '/cal1histo_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.histogram_)
                # np.save(results_dir + '/cal1edges_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.edges_[0])

            elif t == theta_benchmark_trained:
                np.save(results_dir + '/r_trained_' + algorithm + '_calibrated' + filename_addition + '.npy', this_r)

                # Save calibration histograms
                np.save(results_dir + '/calvalues_trained_' + algorithm + filename_addition + '.npy',
                        ratio_calibrated.classifier_.calibration_sample[:n_calibration_each])
                # np.save(results_dir + '/cal0histo_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.histogram_)
                # np.save(results_dir + '/cal0edges_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.edges_[0])
                # np.save(results_dir + '/cal1histo_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.histogram_)
                # np.save(results_dir + '/cal1edges_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.edges_[0])

            # Neyman construction: evaluate observed sample (raw)
            r_neyman_observed, _ = ratio.predict(X_neyman_observed_transformed)
            llr_neyman_observed = -2. * np.sum(np.log(r_neyman_observed).reshape((-1, n_expected_events)), axis=1)
            np.save(neyman_dir + '/neyman_llr_observed_' + algorithm + '_' + str(t) + '.npy',
                    llr_neyman_observed)

            # Neyman construction: evaluate observed sample (calibrated)
            r_neyman_observed, _ = ratio_calibrated.predict(X_neyman_observed_transformed)
            llr_neyman_observed = -2. * np.sum(np.log(r_neyman_observed).reshape((-1, n_expected_events)), axis=1)
            np.save(neyman_dir + '/neyman_llr_observed_' + algorithm + '_calibrated_' + str(t) + '.npy',
                    llr_neyman_observed)

            # Neyman construction: load distribution sample
            X_neyman_distribution = np.load(unweighted_events_dir + '/X_neyman_distribution_' + str(t) + '.npy')
            X_neyman_distribution_transformed = scaler.transform(
                X_neyman_distribution.reshape((-1, X_neyman_distribution.shape[2])))

            # Neyman construction: evaluate distribution sample (raw)
            r_neyman_distribution, _ = ratio.predict(X_neyman_distribution_transformed)
            llr_neyman_distribution = -2. * np.sum(np.log(r_neyman_distribution).reshape((-1, n_expected_events)),
                                                   axis=1)
            np.save(neyman_dir + '/neyman_llr_distribution_' + algorithm + '_' + str(t) + '.npy',
                    llr_neyman_distribution)

            # Neyman construction: evaluate distribution sample (calibrated)
            r_neyman_distribution, _ = ratio_calibrated.predict(X_neyman_distribution_transformed)
            llr_neyman_distribution = -2. * np.sum(np.log(r_neyman_distribution).reshape((-1, n_expected_events)),
                                                   axis=1)
            np.save(neyman_dir + '/neyman_llr_distribution_' + algorithm + '_calibrated_' + str(t) + '.npy',
                    llr_neyman_distribution)

        expected_llr = np.asarray(expected_llr)
        expected_llr_calibrated = np.asarray(expected_llr_calibrated)

        logging.info('Starting interpolation')

        interpolator = LinearNDInterpolator(thetas[training_thetas], expected_llr)
        expected_llr_all = interpolator(thetas)
        # gp = GaussianProcessRegressor(normalize_y=True,
        #                              kernel=C(1.0) * Matern(1.0, nu=0.5), n_restarts_optimizer=10)
        # gp.fit(thetas[training_thetas], expected_llr)
        # expected_llr_all = gp.predict(thetas)
        np.save(results_dir + '/llr_' + algorithm + filename_addition + '.npy', expected_llr_all)

        interpolator = LinearNDInterpolator(thetas[training_thetas], expected_llr_calibrated)
        expected_llr_calibrated_all = interpolator(thetas)
        # gp = GaussianProcessRegressor(normalize_y=True,
        #                              kernel=C(1.0) * Matern(1.0, nu=0.5), n_restarts_optimizer=10)
        # gp.fit(thetas[training_thetas], expected_llr_calibrated)
        # expected_llr_calibrated_all = gp.predict(thetas)
        np.save(results_dir + '/expected_llr_' + algorithm + '_calibrated' + filename_addition + '.npy',
                expected_llr_calibrated_all)
