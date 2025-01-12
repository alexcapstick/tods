# -*- coding: utf-8 -*-
"""Autoregressive model for univariate time series outlier detection.
"""
import numpy as np
from sklearn.utils import check_array
from sklearn.utils.validation import check_is_fitted
from sklearn.ensemble import GradientBoostingRegressor

from .CollectiveBase import CollectiveBaseDetector

from .utility import get_sub_matrices


class GBRegOD(CollectiveBaseDetector):
    """Autoregressive models use linear regression to calculate a sample's
    deviance from the predicted value, which is then used as its
    outlier scores. This model is for univariate time series.
    See MultiAutoRegOD for multivariate data.
    
    See :cite:`aggarwal2015outlier` Chapter 9 for details.

    Parameters
    ----------
    window_size : int
        The moving window size.

    step_size : int, optional (default=1)
        The displacement for moving window.

    contamination : float in (0., 0.5), optional (default=0.1)
        The amount of contamination of the data set, i.e.
        the proportion of outliers in the data set. When fitting this is used
        to define the threshold on the decision function.

    Attributes
    ----------
    decision_scores_ : numpy array of shape (n_samples,)
        The outlier scores of the training data.
        The higher, the more abnormal. Outliers tend to have higher
        scores. This value is available once the detector is fitted.

    threshold_ : float
        The threshold is based on ``contamination``. It is the
        ``n_samples * contamination`` most abnormal samples in
        ``decision_scores_``. The threshold is calculated for generating
        binary outlier labels.

    labels_ : int, either 0 or 1
        The binary labels of the training data. 0 stands for inliers
        and 1 for outliers/anomalies. It is generated by applying
        ``threshold_`` on ``decision_scores_``.
    """

    def __init__(self, window_size, step_size=1, contamination=0.1):
        super(GBRegOD, self).__init__(contamination=contamination)
        self.window_size = window_size
        self.step_size = step_size

    def fit(self, X: np.array) -> object:
        """Fit detector. y is ignored in unsupervised methods.

        Parameters
        ----------
        X : numpy array of shape (n_samples, n_features)
            The input samples.

        y : Ignored
            Not used, present for API consistency by convention.

        Returns
        -------
        self : object
            Fitted estimator.
        """
        X = check_array(X).astype(np.float)

        # generate X and y
        sub_matrices, self.left_inds_, self.right_inds_ = get_sub_matrices(
            X,
            window_size=self.window_size,
            step=self.step_size,
            return_numpy=True,
            flatten=True)
        # remove the last one
        sub_matrices = sub_matrices[:-1, :]
        self.left_inds_ = self.left_inds_[:-1]
        self.right_inds_ = self.right_inds_[:-1]

        self.valid_len_ = sub_matrices.shape[0]

        y_buf = np.zeros([self.valid_len_, 1])

        for i in range(self.valid_len_):
            y_buf[i] = X[i * self.step_size + self.window_size]
        # print(sub_matrices.shape, y_buf.shape)

        # fit the linear regression model
        self.gbr_ = GradientBoostingRegressor()
        self.gbr_.fit(sub_matrices, y_buf)
        self.decision_scores_ = np.absolute(
            y_buf.ravel() - self.gbr_.predict(sub_matrices).ravel())

        self._process_decision_scores()
        return self

    def predict(self, X): # pragma: no cover
        """Predict if a particular sample is an outlier or not.

        Parameters
        ----------
        X : numpy array of shape (n_samples, n_features)
            The input samples.

        Returns
        -------
        outlier_labels : numpy array of shape (n_samples,)
            For each observation, tells whether or not
            it should be considered as an outlier according to the
            fitted model. 0 stands for inliers and 1 for outliers.
        """

        check_is_fitted(self, ['decision_scores_', 'threshold_', 'labels_'])

        pred_score, X_left_inds, X_right_inds = self.decision_function(X)

        pred_score = np.concatenate((np.zeros((self.window_size,)), pred_score))
        X_left_inds = np.concatenate((np.zeros((self.window_size,)), X_left_inds))
        X_right_inds = np.concatenate((np.zeros((self.window_size,)), X_right_inds))

        return (pred_score > self.threshold_).astype(
            'int').ravel(), X_left_inds.ravel(), X_right_inds.ravel()

    def decision_function(self, X: np.array):
        """Predict raw anomaly scores of X using the fitted detector.

        The anomaly score of an input sample is computed based on the fitted
        detector. For consistency, outliers are assigned with
        higher anomaly scores.

        Parameters
        ----------
        X : numpy array of shape (n_samples, n_features)
            The input samples. Sparse matrices are accepted only
            if they are supported by the base estimator.

        Returns
        -------
        anomaly_scores : numpy array of shape (n_samples,)
            The anomaly score of the input samples.
        """
        check_is_fitted(self, ['gbr_'])

        sub_matrices, X_left_inds, X_right_inds = \
            get_sub_matrices(X,
                             window_size=self.window_size,
                             step=self.step_size,
                             return_numpy=True,
                             flatten=True)

        # remove the last one
        sub_matrices = sub_matrices[:-1, :]
        X_left_inds = X_left_inds[:-1]
        X_right_inds = X_right_inds[:-1]

        valid_len = sub_matrices.shape[0]

        y_buf = np.zeros([valid_len, 1])

        for i in range(valid_len):
            y_buf[i] = X[i * self.step_size + self.window_size]

        pred_score = np.absolute(
            y_buf.ravel() - self.gbr_.predict(sub_matrices).ravel())

        return pred_score, X_left_inds.ravel(), X_right_inds.ravel()


if __name__ == "__main__": # pragma: no cover
    X_train = np.asarray(
        [3., 4., 8., 16, 18, 13., 22., 36., 59., 128, 62, 67, 78,
         100]).reshape(-1, 1)

    X_test = np.asarray(
        [3., 4., 8.6, 13.4, 22.5, 17, 19.2, 36.1, 127, -23, 59.2]).reshape(-1,
                                                                           1)

    clf = GBRegOD(window_size=3, contamination=0.2)
    clf.fit(X_train)
    decision_scores, left_inds_, right_inds = clf.decision_scores_, \
                                              clf.left_inds_, clf.right_inds_
    print(clf.left_inds_, clf.right_inds_)
    pred_scores, X_left_inds, X_right_inds = clf.decision_function(X_test)
    pred_labels, X_left_inds, X_right_inds = clf.predict(X_test)
    pred_probs, X_left_inds, X_right_inds = clf.predict_proba(X_test)

    print(pred_scores)
    print(pred_labels)
    print(pred_probs)
