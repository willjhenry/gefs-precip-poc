import numpy as np


# Vectorized empirical CRPS
def vectorized_crps(members_array, obs_array):
    """
    members_array: (N_samples, N_members) float array
    obs_array: (N_samples,) float array
    Returns: (N_samples,) CRPS values
    """
    N_members = members_array.shape[1]

    # Term 1: E[|X - y|] = mean(abs(members - obs), axis=1)
    # Add axis to obs_array to broadcast along members_array
    obs_broadcast = obs_array[:, np.newaxis]  # (N_samples, 1)
    term1 = np.mean(np.abs(members_array - obs_broadcast), axis=1)

    # Term 2: (1/2) E[|X - X'|] = (1/(2 * N^2)) * sum_{i,j} |X_i - X_j|
    # Vectorize pairwise: broadcast to (N_samples, N, N)
    diffs = np.abs(
        members_array[:, :, np.newaxis] - members_array[:, np.newaxis, :]
    )  # First array is [n_samples, n_members, 1], second array is [n_samples, 1, n_members]
    # Image two 3d matrices, one facing you, and the other perpendicular to you
    # This is what we have created. Then, when we subtract the perpendicular
    # matrix from the one facing you, in subtracts along every member pair.
    # We end up with a 3d matrix of shape [n_samples, n_members, n_members]

    sum_diffs = np.sum(diffs, axis=(1, 2))  # Sum over members pairs per sample
    term2 = (1 / (2 * N_members**2)) * sum_diffs

    return term1 - term2
