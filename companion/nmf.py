"Non-negative matrix factorization of full datasets"
from sklearn.decomposition import NMF
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl


def decomposition(Q, I, n_components=3, q_range=None, bkg_removal=None):
    """
    Decompose and label a set of I(Q) data with optional focus bounds

    Parameters
    ----------
    Q : array
        Ordinate Q for I(Q). Assumed to be rank 2, shape (m_patterns, n_data)
    I : array
        The intensity values for each Q, assumed to be the same shape as Q. (m_patterns, n_data)
    n_components: int
        Number of components for NMF
    q_range : tuple, list
        (Min, Max) Q values for consideration in NMF. This enables a focused region for decomposition.

    Returns
    -------
    sub_Q : array
        Subsampled ordinate used for NMF
    sub_I : array
        Subsampled I used for NMF
    alphas : array
        Resultant weights from NMF

    """

    nmf = NMF(n_components=n_components, max_iter=10000)

    if bkg_removal:
        # Integer should call peakutils.baseline. TODO: Choose sensible degree of polynomial.
        # Array should be broadcast subtraction
        raise NotImplementedError

    if np.min(I) < 0:
        I = I - np.min(I, axis=1, keepdims=True)

    if q_range is None:
        idx_min = 0
        idx_max = I.shape[1]
    else:
        idx_min = np.where(Q[0, :] < q_range[0])[0][-1] if len(np.where(Q[0, :] < q_range[0])[0]) else 0
        idx_max = np.where(Q[0, :] > q_range[1])[0][0] if len(np.where(Q[0, :] > q_range[1])[0]) else I.shape[1]

    sub_I = I[:, idx_min:idx_max]
    sub_Q = Q[:, idx_min:idx_max]
    alphas = nmf.fit_transform(sub_I)

    return sub_Q, sub_I, alphas


def waterfall(ax, xs, ys, alphas, color='k', sampling=1, offset=0.2, **kwargs):
    indicies = range(0, xs.shape[0])[::sampling]
    for plt_i, idx in enumerate(indicies):
        y = ys[idx, :] + plt_i * offset
        x = xs[idx, :]
        ax.plot(x, y, color=color, alpha=alphas[idx], **kwargs)
    return ax


def example_plot(sub_Q, sub_I, alphas, axes=None, cmap='tab10', alt_ordinate=None):
    """
    Example plotting of NMF results. Not necessarily for Bluesky deployment

    Parameters
    ----------
    sub_Q: array
        Q to plot in I(Q)
    sub_I: array
        I to plot in I(Q)
    alphas: array
        transparencies of multiple repeated plots of I(Q)
    axes: optional existing axes
    cmap: mpl colormap
    alt_ordinate: array
        Array len sub_I.shape[0], corresponding to an alternative labeled dimension for which to order the stacked plots

    Returns
    -------
    fig, axes

    """

    n_components = alphas.shape[1]
    cmap = mpl.cm.get_cmap(cmap)
    norm = mpl.colors.Normalize(vmin=0, vmax=n_components)

    # Create alternative ordinate for the waterfall/stacking
    if alt_ordinate:
        idxs, labels = list(zip(*sorted(zip(range(sub_I.shape[0]), alt_ordinate), key=lambda x: x[1])))
    else:
        idxs = list(range(sub_I.shape[0]))
        labels = list(range(sub_I.shape[0]))
    xs = sub_Q[idxs, :]
    ys = sub_I[idxs, :]
    alphas = alphas[idxs, :]

    # Order by proxy center of mass of class in plot regime. Makes the plots feel like a progression not random.
    alpha_ord = np.argsort(np.matmul(np.arange(alphas.shape[0]), alphas))

    if axes is None:
        fig, axes = plt.subplots(int(np.ceil(np.sqrt(n_components))), int(np.ceil(np.sqrt(n_components))))
        axes = axes.reshape(-1)
    else:
        axes = np.ravel(axes)
    for i, ax in enumerate(axes):
        if i < n_components:
            i_a = alpha_ord[i]
            color = cmap(norm(i))
            alpha = (alphas[:, i_a] - np.min(alphas[:, i_a])) / (np.max(alphas[:, i_a]) - np.min(alphas[:, i_a]))
            ax = waterfall(ax, xs, ys, alpha, color=color)
        else:
            ax.set_visible = False

    return axes[0].figure, axes
