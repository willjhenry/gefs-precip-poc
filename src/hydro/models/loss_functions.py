import logging

import tensorflow as tf
from tensorflow_probability import distributions as tfd

logger = logging.getLogger(__name__)


def crps_loss(y_true, gamma_params, N_mc=100):
    """CRPS approx via MC: Output shape/scale from net, sample Gamma, compute emp CRPS."""

    logger.debug(f"Shape of y_true: {y_true.shape}")
    logger.debug(f"Shape of gamma_params: {gamma_params.shape}")

    # Remeber that y_true has two columns because it is required to match
    # the dimension of the model output. However, only the first column are
    # the true observations.
    obs = y_true[:, 1]  # Real precip obs
    # split the batch into two, for shape and scale
    # pyrefly: ignore[unexpected-keyword, bad-argument-count]
    shape, scale = tf.split(gamma_params, 2, axis=1)
    shape = tf.maximum(shape, 1e-3)  # Clip for stability
    scale = tf.maximum(scale, 1e-3)

    # Sample N_mc from Gamma per batch item
    # NOTE: scale is actually being used as rate, but that is fine as long
    # as we are consistent
    gamma_dist = tfd.Gamma(shape, scale)

    # This paper explain how the smaplers are differentiable:
    # https://arxiv.org/abs/1805.08498
    samples = gamma_dist.sample(N_mc)
    # This returns a shape of (N_mc, batch, 1)
    # but we want to make it (batch, N_mc, 1)
    # pyrefly: ignore[bad-argument-count]
    samples = tf.transpose(samples, [1, 0, 2])

    logger.debug(f"Shape of samples: {samples.shape}")

    # Vectorized emp CRPS
    logger.debug(f"Shape of obs before expand_dims: {obs.shape}")
    # pyrefly: ignore[bad-argument-count]
    obs = tf.expand_dims(tf.expand_dims(obs, -1), -1)  # (batch, 1, 1)
    logger.debug(f"Shape of obs: {obs.shape}")

    # pyrefly: ignore[unexpected-keyword]
    term1 = tf.reduce_mean(tf.abs(samples - obs), axis=1)  # (batch,)

    diff_term_1 = samples
    # pyrefly: ignore[bad-argument-count]
    diff_term_2 = tf.transpose(samples, [0, 2, 1])
    logger.debug(f"Shape of diff_term_1: {diff_term_1.shape}")
    logger.debug(f"Shape of diff_term_2: {diff_term_2.shape}")
    diffs = tf.abs(diff_term_1 - diff_term_2)  # (batch, N_mc, N_mc)
    logger.debug(f"Shape of diffs: {diffs.shape}")
    # pyrefly: ignore[unexpected-keyword]
    sum_diffs = tf.reduce_sum(diffs, axis=[1, 2])  # (batch,)
    term2 = 0.5 * sum_diffs / (N_mc**2)

    crps = term1 - term2
    return tf.reduce_mean(crps)  # Mean over batch
